"""Merge hardware test results (results/<device>.json) into one Markdown report.

    python hardware_tests/summarize.py [results_dir ...]  >  summary.md

In GitHub Actions, append the output to $GITHUB_STEP_SUMMARY to show it on the run page.
"""
import glob
import json
import os
import sys

HW_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_ORDER = ["pwm", "rpm_control", "profiles", "temperature", "aliases"]
FAILED = ("failed", "error", "xpassed")


def load_results(paths):
    runs = []
    for path in paths:
        files = sorted(glob.glob(os.path.join(path, "**", "*.json"), recursive=True)) if os.path.isdir(path) else [path]
        for file in files:
            try:
                with open(file, "r", encoding="utf8") as handle:
                    data = json.load(handle)
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and "device" in data and "results" in data:
                runs.append(data)
    return sorted(runs, key=lambda r: r["device"])


def feature_cell(run, feature):
    results = [r for r in run["results"] if feature in r["features"].split(",")]
    if not results:
        return "–"
    counts = {}
    for result in results:
        counts[result["outcome"]] = counts.get(result["outcome"], 0) + 1
    failed = sum(counts.get(o, 0) for o in FAILED)
    if failed:
        return f"❌ {failed} failed"
    if counts.get("unsupported-verified"):
        return "✅ correctly unsupported"
    if counts.get("passed"):
        extra = f" ({counts['xfailed']} known)" if counts.get("xfailed") else ""
        return f"✅ {counts['passed']} passed{extra}"
    if counts.get("xfailed"):
        return f"⚠️ {counts['xfailed']} known failures"
    return "⏭ skipped (not supported)" if feature not in run["features"] else "⏭ skipped"


def render(runs):
    if not runs:
        return "## OpenFAN hardware tests\n\nNo results found.\n"
    lines = ["## OpenFAN hardware tests", ""]
    lines.append("| Device | Board | Scope | Passed | Unsupported ✔ | Skipped | Known failures | Failed |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for run in runs:
        c = run["counts"]
        failed = sum(c.get(o, 0) for o in FAILED)
        name = run["device"] + (" (sim)" if run.get("simulated") else "")
        lines.append(f"| {'❌ ' if failed else ''}{name} | {run['board']} | {run['scope']} | {c.get('passed', 0)} | "
                     f"{c.get('unsupported-verified', 0)} | {c.get('skipped', 0)} | {c.get('xfailed', 0)} | {failed} |")

    lines += ["", "### Features", "", "| Feature | " + " | ".join(r["device"] for r in runs) + " |",
              "|---|" + "---|" * len(runs)]
    for feature in FEATURE_ORDER:
        lines.append(f"| {feature} | " + " | ".join(feature_cell(r, feature) for r in runs) + " |")
    lines += ["", "_✅ correctly unsupported: the device lacks the feature and the API returned the documented "
                  "error. –: no test for this feature was selected for the device._"]

    failures = [(run["device"], r) for run in runs for r in run["results"] if r["outcome"] in FAILED]
    if failures:
        lines += ["", "### Failures", ""]
        for device, result in failures:
            message_lines = [l.strip() for l in result["message"].splitlines() if l.strip()]
            detail = next((l for l in message_lines if l.startswith("E ")), message_lines[0] if message_lines else "")
            lines.append(f"- **{device}** `{result['nodeid']}`: {detail[:200]}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")     # emoji on Windows consoles
    paths = (argv if argv is not None else sys.argv[1:]) or [os.path.join(HW_DIR, "results")]
    sys.stdout.write(render(load_results(paths)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
