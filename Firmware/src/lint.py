#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Run cppcheck and clang-tidy on the OpenFAN firmware sources.

Usage (from anywhere):
    python lint.py                    # run both tools
    python lint.py --tool cppcheck    # only cppcheck
    python lint.py --tool clang-tidy  # only clang-tidy
    python lint.py --help             # all options

How it works
  1. Configures the project with CMake into a separate folder (build-lint/)
     with CMAKE_EXPORT_COMPILE_COMMANDS=ON, so both tools see exactly the
     same include paths and defines as the real firmware build.
     The existing build/ folder is only *read* (to reuse PICO_SDK_PATH,
     the toolchain, generator and picotool location) and never modified.
  2. Filters the compile database down to the firmware's own sources
     (Application/ and Lib/) so Pico SDK / TinyUSB code is not linted.
  3. Runs cppcheck and clang-tidy and writes reports to build-lint/reports/.

Exit code: 0 = no findings, 1 = findings reported, 2 = setup error.

Requirements: Python 3.8+, CMake, arm-none-eabi-gcc, Pico SDK, and
cppcheck and/or clang-tidy (e.g. `pip install clang-tidy`).
"""

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIRS = ("Application", "Lib")

# Sensible default clang-tidy checks for embedded C. Ignored when a
# .clang-tidy file exists next to this script (unless --checks is given).
DEFAULT_TIDY_CHECKS = ",".join([
    "-*",
    "bugprone-*",
    "cert-*",
    "clang-analyzer-*",
    "clang-diagnostic-*",           # compiler warnings, e.g. -Wformat
    "misc-*",
    "performance-*",
    "portability-*",
    "readability-*",
    # Too noisy for firmware / register-level code:
    "-bugprone-easily-swappable-parameters",
    "-readability-magic-numbers",
    "-readability-identifier-length",
    "-readability-uppercase-literal-suffix",
    "-misc-include-cleaner",
    "-clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling",
])

CPPCHECK_TEMPLATE = "{file}:{line}:{column}: {severity}: {message} [{id}]"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def log(msg):
    print(msg, flush=True)


def die(msg):
    print("error: " + msg, file=sys.stderr, flush=True)
    sys.exit(2)


def norm(path):
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def read_cmake_cache(build_dir):
    """Return {VAR: value} from an existing CMakeCache.txt (read-only)."""
    cache = {}
    path = os.path.join(build_dir, "CMakeCache.txt")
    if not os.path.isfile(path):
        return cache
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = re.match(r"^([A-Za-z0-9_.\-]+):[A-Z]+=(.*)$", line.rstrip("\r\n"))
            if m:
                cache[m.group(1)] = m.group(2)
    return cache


def existing(path):
    return path if path and os.path.exists(path) else None


def find_exe(name, explicit=None, extra_candidates=()):
    if explicit:
        found = shutil.which(explicit) or existing(explicit)
        if not found:
            die("'%s' not found: %s" % (name, explicit))
        return found
    found = shutil.which(name)
    if found:
        return found
    # Look in the active / local virtualenv (e.g. `pip install clang-tidy`)
    scripts = "Scripts" if os.name == "nt" else "bin"
    exe = name + (".exe" if os.name == "nt" else "")
    for venv in (os.environ.get("VIRTUAL_ENV"), os.path.join(ROOT, ".venv")):
        if venv and os.path.isfile(os.path.join(venv, scripts, exe)):
            return os.path.join(venv, scripts, exe)
    for cand in extra_candidates:
        if os.path.isfile(cand):
            return cand
    return None


# --------------------------------------------------------------------------
# step 1: configure + compile database
# --------------------------------------------------------------------------
def configure(args, cache):
    lint_cache = read_cmake_cache(os.path.abspath(args.build_dir))
    sdk = (args.sdk or os.environ.get("PICO_SDK_PATH")
           or existing(lint_cache.get("PICO_SDK_PATH")) or existing(cache.get("PICO_SDK_PATH")))
    if not sdk or not os.path.isfile(os.path.join(sdk, "pico_sdk_init.cmake")):
        die("Pico SDK not found. Pass --sdk PATH or set PICO_SDK_PATH.")

    gcc = find_exe("arm-none-eabi-gcc", args.gcc,
                   [lint_cache.get("CMAKE_C_COMPILER", ""), cache.get("CMAKE_C_COMPILER", "")])
    if not gcc:
        die("arm-none-eabi-gcc not found. Put it on PATH or pass --gcc PATH.")

    cmake = find_exe("cmake", args.cmake, [cache.get("CMAKE_COMMAND", "")])
    if not cmake:
        die("cmake not found. Put it on PATH or pass --cmake PATH.")

    build_dir = os.path.abspath(args.build_dir)
    ccdb = os.path.join(build_dir, "compile_commands.json")

    stale = (not os.path.isfile(ccdb)
             or os.path.getmtime(ccdb) < os.path.getmtime(os.path.join(ROOT, "CMakeLists.txt")))
    if stale or args.reconfigure:
        env = dict(os.environ)
        env["PICO_SDK_PATH"] = sdk
        env["PICO_TOOLCHAIN_PATH"] = os.path.dirname(gcc)

        cmd = [cmake, "-S", ROOT, "-B", build_dir,
               "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
               # MinGW Makefiles would otherwise hide include paths in
               # @response files, which cppcheck cannot read.
               "-DCMAKE_C_USE_RESPONSE_FILE_FOR_INCLUDES=OFF",
               "-DCMAKE_CXX_USE_RESPONSE_FILE_FOR_INCLUDES=OFF",
               "-DPICO_SDK_PATH=" + sdk,
               "-DCMAKE_BUILD_TYPE=" + args.build_type]

        # Reuse generator / make program / picotool from the existing build
        # when they are valid on this machine (and none was cached yet).
        if not os.path.isfile(os.path.join(build_dir, "CMakeCache.txt")):
            gen, make = cache.get("CMAKE_GENERATOR"), existing(cache.get("CMAKE_MAKE_PROGRAM"))
            if args.generator:
                cmd += ["-G", args.generator]
            elif gen and make:
                cmd += ["-G", gen, "-DCMAKE_MAKE_PROGRAM=" + make]
            elif shutil.which("ninja"):
                cmd += ["-G", "Ninja"]
        picotool = existing(cache.get("picotool_DIR"))
        if picotool:
            cmd.append("-Dpicotool_DIR=" + picotool)

        log("==> Configuring compile database in %s" % build_dir)
        res = subprocess.run(cmd, env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True)
        if res.returncode != 0 or not os.path.isfile(ccdb):
            print(res.stdout)
            die("CMake configure failed (see output above).")
    else:
        log("==> Reusing compile database in %s (use --reconfigure to refresh)" % build_dir)

    return build_dir, ccdb, gcc


def filter_compile_db(ccdb, build_dir):
    """Keep only the firmware's own sources; write to <build>/lint/."""
    with open(ccdb, encoding="utf-8") as f:
        entries = json.load(f)

    roots = tuple(norm(os.path.join(ROOT, d)) + os.sep for d in SOURCE_DIRS)
    keep, seen = [], set()
    for e in entries:
        path = e["file"]
        if not os.path.isabs(path):
            path = os.path.join(e.get("directory", ""), path)
        key = norm(path)
        if key.startswith(roots) and key not in seen:
            seen.add(key)
            keep.append(e)
    if not keep:
        die("No firmware sources found in %s" % ccdb)

    lint_dir = os.path.join(build_dir, "lint")
    os.makedirs(lint_dir, exist_ok=True)
    with open(os.path.join(lint_dir, "compile_commands.json"), "w", encoding="utf-8") as f:
        json.dump(keep, f, indent=2)
    files = [e["file"] if os.path.isabs(e["file"]) else os.path.join(e["directory"], e["file"])
             for e in keep]
    return lint_dir, sorted(files)


def gcc_system_includes(gcc):
    """Ask arm-none-eabi-gcc for its built-in include dirs (newlib etc.)."""
    res = subprocess.run([gcc, "-xc", "-E", "-v", "-"], stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         universal_newlines=True)
    dirs, grab = [], False
    for line in res.stderr.splitlines():
        if line.startswith("#include <...> search starts here"):
            grab = True
        elif line.startswith("End of search list"):
            break
        elif grab:
            dirs.append(os.path.normpath(line.strip()))
    return dirs


def gcc_stdint_type_macros(gcc):
    """
    Return GCC's predefined stdint type macros, e.g.
    {'__UINT32_TYPE__': 'long unsigned int'}. newlib builds uint32_t etc.
    from these; clang's defaults differ for arm-none-eabi (it uses
    'unsigned int'), which would cause bogus printf-format warnings.
    """
    res = subprocess.run([gcc, "-xc", "-dM", "-E", "-"], stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         universal_newlines=True)
    macros = {}
    for line in res.stdout.splitlines():
        m = re.match(r"^#define (__U?INT(?:_LEAST|_FAST)?(?:8|16|32|64|MAX|PTR)_TYPE__) (.+)$", line)
        if m:
            macros[m.group(1)] = m.group(2).strip()
    return macros


# --------------------------------------------------------------------------
# step 2: tools
# --------------------------------------------------------------------------
def run_cppcheck(args, lint_dir, report_dir, sdk_path):
    exe = find_exe("cppcheck", args.cppcheck,
                   [r"C:\Program Files\Cppcheck\cppcheck.exe",
                    r"C:\Program Files (x86)\Cppcheck\cppcheck.exe"])
    if not exe:
        log("!! cppcheck not found - skipping (install it or pass --cppcheck PATH)")
        return None

    cache_dir = os.path.join(lint_dir, "cppcheck-cache")
    os.makedirs(cache_dir, exist_ok=True)
    report = os.path.join(report_dir, "cppcheck.txt")

    cmd = [exe,
           "--project=" + os.path.join(lint_dir, "compile_commands.json"),
           "--cppcheck-build-dir=" + cache_dir,
           "--enable=warning,style,performance,portability",
           "--std=c11",
           "--platform=" + args.cppcheck_platform,
           "--inline-suppr",
           "--quiet",
           "-j", str(args.jobs),
           "--template=" + CPPCHECK_TEMPLATE,
           "--suppress=missingIncludeSystem",
           "--suppress=missingInclude",
           "--suppress=unmatchedSuppression",
           "--suppress=checkersReport",
           # cppcheck assumes uint32_t == unsigned int, but on arm-none-eabi
           # it is unsigned long, so correct "%lu"/"%lX" would be flagged.
           # clang-tidy (-Wformat) checks printf formats with the real types.
           "--suppress=invalidPrintfArgType_uint",
           "--suppress=invalidPrintfArgType_sint",
           "--output-file=" + report]
    # Ignore findings in Pico SDK / TinyUSB headers. cppcheck uses forward
    # slashes; cover both drive-letter cases seen in CMake caches on Windows.
    if sdk_path:
        sdk = sdk_path.replace("\\", "/").rstrip("/")
        for variant in {sdk, sdk[:1].lower() + sdk[1:], sdk[:1].upper() + sdk[1:]}:
            cmd.append("--suppress=*:%s/*" % variant)
    log("==> Running cppcheck (%s)" % exe)
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         universal_newlines=True)
    if res.returncode != 0:
        print(res.stdout)
        log("!! cppcheck failed with exit code %d" % res.returncode)
        return -1

    with open(report, encoding="utf-8", errors="replace") as f:
        text = f.read().strip()
    count = len(re.findall(r"^\S.*?:\d+:\d+: \w+: ", text, flags=re.M))
    if text:
        print(text)
    log("--> cppcheck: %d finding(s), report: %s\n" % (count, report))
    return count


def run_clang_tidy(args, lint_dir, files, gcc, report_dir):
    exe = find_exe("clang-tidy", args.clang_tidy)
    if not exe:
        log("!! clang-tidy not found - skipping (pip install clang-tidy, or pass --clang-tidy PATH)")
        return None

    extra = ["--extra-arg-before=--target=arm-none-eabi",
             "--extra-arg=-Wno-unknown-warning-option",
             "--extra-arg=-Wno-unused-command-line-argument",
             "--extra-arg=-Wformat"]
    extra.append("--extra-arg=-Wno-ignored-attributes")   # e.g. format(gnu_printf)
    for d in gcc_system_includes(gcc):
        extra.append("--extra-arg=-isystem" + d)
    for name, value in sorted(gcc_stdint_type_macros(gcc).items()):
        extra += ["--extra-arg=-U" + name, "--extra-arg=-D%s=%s" % (name, value)]

    base = [exe, "-p", lint_dir, "--quiet",
            # only report on the firmware's own headers, not SDK ones
            r"--header-filter=.*[\\/](Application|Lib[\\/][^\\/]+)[\\/][^\\/]+$"] + extra
    has_config = os.path.isfile(os.path.join(ROOT, ".clang-tidy"))
    if args.checks:
        base.append("--checks=" + args.checks)
    elif not has_config:
        base.append("--checks=" + DEFAULT_TIDY_CHECKS)
    if args.fix:
        base.append("--fix")

    log("==> Running clang-tidy (%s) on %d files" % (exe, len(files)))

    def one(path):
        r = subprocess.run(base + [path], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           universal_newlines=True)
        return path, r.returncode, r.stdout, r.stderr

    jobs = 1 if args.fix else args.jobs   # --fix must not run in parallel
    outputs, seen, count, failed = [], set(), 0, False
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        for path, rc, out, err in pool.map(one, files):
            # Group lines into diagnostics and drop duplicates coming from
            # headers that are included by several .c files.
            block = []
            for line in out.splitlines() + [None]:
                if line is None or re.match(r"^\S.*:\d+:\d+: (warning|error):", line):
                    if block:
                        text = "\n".join(block)
                        if text not in seen:
                            seen.add(text)
                            outputs.append(text)
                            count += 1
                    block = [line] if line is not None else []
                elif block:
                    block.append(line)
            if rc != 0 and not out.strip():
                failed = True
                outputs.append("clang-tidy failed on %s:\n%s" % (path, err.strip()))

    report = os.path.join(report_dir, "clang-tidy.txt")
    with open(report, "w", encoding="utf-8") as f:
        f.write("\n".join(outputs) + ("\n" if outputs else ""))
    if outputs:
        print("\n".join(outputs))
    log("--> clang-tidy: %d finding(s), report: %s\n" % (count, report))
    return -1 if failed else count


# --------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="Run cppcheck and clang-tidy on the OpenFAN firmware.")
    p.add_argument("--tool", choices=("all", "cppcheck", "clang-tidy"), default="all")
    p.add_argument("--sdk", help="Pico SDK path (default: $PICO_SDK_PATH or build/CMakeCache.txt)")
    p.add_argument("--gcc", help="path to arm-none-eabi-gcc")
    p.add_argument("--cmake", help="path to cmake")
    p.add_argument("--cppcheck", help="path to cppcheck")
    p.add_argument("--clang-tidy", dest="clang_tidy", help="path to clang-tidy")
    p.add_argument("--cppcheck-platform", default="arm32-wchar_t4",
                   help="cppcheck --platform (default: arm32-wchar_t4; use unix32 on old cppcheck)")
    p.add_argument("--checks", help="clang-tidy --checks string (overrides defaults/.clang-tidy)")
    p.add_argument("--fix", action="store_true", help="let clang-tidy apply fixes (MODIFIES SOURCES)")
    p.add_argument("--generator", help="CMake generator, e.g. 'Ninja' or 'MinGW Makefiles'")
    p.add_argument("--build-type", default="Debug", help="CMake build type (default: Debug)")
    p.add_argument("--build-dir", default=os.path.join(ROOT, "build-lint"),
                   help="scratch build dir (default: build-lint/ next to this script)")
    p.add_argument("--reconfigure", action="store_true", help="force re-running CMake")
    p.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 4)
    args = p.parse_args()

    if norm(args.build_dir) == norm(os.path.join(ROOT, "build")):
        die("--build-dir must not be the regular build/ folder.")

    cache = read_cmake_cache(os.path.join(ROOT, "build"))
    build_dir, ccdb, gcc = configure(args, cache)
    lint_dir, files = filter_compile_db(ccdb, build_dir)
    sdk_path = read_cmake_cache(build_dir).get("PICO_SDK_PATH", args.sdk or "")

    report_dir = os.path.join(build_dir, "reports")
    os.makedirs(report_dir, exist_ok=True)

    results = {}
    if args.tool in ("all", "cppcheck"):
        results["cppcheck"] = run_cppcheck(args, lint_dir, report_dir, sdk_path)
    if args.tool in ("all", "clang-tidy"):
        results["clang-tidy"] = run_clang_tidy(args, lint_dir, files, gcc, report_dir)

    log("==> Summary")
    for name, n in results.items():
        status = "skipped (not installed)" if n is None else "FAILED to run" if n < 0 else "%d finding(s)" % n
        log("    %-10s %s" % (name, status))

    ran = [n for n in results.values() if n is not None]
    if not ran or any(n < 0 for n in ran):
        return 2
    return 1 if any(n > 0 for n in ran) else 0


if __name__ == "__main__":
    sys.exit(main())
