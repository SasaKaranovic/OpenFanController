#!/usr/bin/env bash
# Run the OpenFAN Python tests: software (unit/API) tests and hardware tests.
#
# Usage: ./run_tests.sh [options] [suite ...] [pytest args ...]
#
#   Software test suites (no hardware needed; default is all of them):
#     api            REST API (webserver.py)
#     board          board detection (board.py)
#     config         config.yaml handling (config.py)
#     fancommander   serial protocol encoding/parsing (FanCommander.py)
#     serial         serial driver (serial_driver.py)
#     known-bugs     only the tests documenting known bugs (xfail)
#
#   Hardware tests (hardware_tests/, driven by hardware_tests/devices.yaml):
#     hardware                 run the hardware tests (added automatically with any option below)
#     --list-devices           show the inventory and detected OpenFAN serial ports
#     --device NAME            device from the inventory (sim-controller, sim-xl, sim-micro need no hardware)
#     --scope supported|all    supported: skip unsupported features (default)
#                              all: run them and verify the API reports them as unsupported
#     --suite a,b              hardware suites: smoke,html,fan_control,profiles,aliases,sensors or all
#     --base-url URL           test an already running server instead of starting one
#     --server-config FILE     start webserver.py with a copy of this config file
#     --server-port N          port for the started server
#     --fans-connected 0,1     (without --device) channels with a real fan attached
#     --sensors-connected 0    (without --device) channels with a real sensor attached
#     --inventory FILE         use another inventory file
#
#   Options:
#     --setup        create .venv (if missing) and install requirements + test tools
#     --cov          show a coverage report (software tests; needs pytest-cov)
#     --list         list the tests instead of running them
#     -h, --help     show this help
#
#   Anything else is passed straight to pytest, e.g.
#     ./run_tests.sh api -k alias                      API tests with "alias" in their name
#     ./run_tests.sh tests/test_config.py::test_set_fan_alias_persists
#     ./run_tests.sh hardware --device sim-xl --scope all
#     ./run_tests.sh --device lab-ctrl-01 --suite smoke,html -x
#
# Uses $PYTHON if set, otherwise .venv (if present), otherwise python3 / python.

set -euo pipefail
cd "$(dirname "$0")"

usage() { sed -n '2,42p' "$0" | sed 's/^# \{0,1\}//'; }

find_python() {
    if [ -n "${PYTHON:-}" ]; then echo "$PYTHON"
    elif [ -x .venv/bin/python ]; then echo .venv/bin/python
    elif [ -x .venv/Scripts/python.exe ]; then echo .venv/Scripts/python.exe
    elif command -v python3 >/dev/null 2>&1; then echo python3
    elif command -v python >/dev/null 2>&1; then echo python
    else echo "ERROR: Python not found. Install Python 3 or set PYTHON=/path/to/python" >&2; exit 1
    fi
}

SETUP=0
HARDWARE=0
PYTEST_ARGS=()
SUITES=()

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help)      usage; exit 0 ;;
        --setup)        SETUP=1 ;;
        --cov)          PYTEST_ARGS+=(--cov=. --cov-report=term-missing) ;;
        --list)         PYTEST_ARGS+=(--collect-only -q) ;;
        api)            SUITES+=(tests/test_api.py) ;;
        board)          SUITES+=(tests/test_board.py) ;;
        config)         SUITES+=(tests/test_config.py) ;;
        fancommander)   SUITES+=(tests/test_fancommander.py) ;;
        serial)         SUITES+=(tests/test_serial_driver.py) ;;
        known-bugs)     PYTEST_ARGS+=(-m xfail) ;;
        hardware)       SUITES+=(hardware_tests); HARDWARE=1 ;;
        all)            ;;
        --list-devices) PYTEST_ARGS+=("$1"); HARDWARE=1 ;;
        # hardware options that take a value
        --device|--scope|--suite|--base-url|--server-config|--server-port|--fans-connected|--sensors-connected|--inventory|--results-dir)
            [ $# -ge 2 ] || { echo "ERROR: $1 needs a value" >&2; exit 2; }
            PYTEST_ARGS+=("$1" "$2"); HARDWARE=1; shift ;;
        --device=*|--scope=*|--suite=*|--base-url=*|--server-config=*|--server-port=*|--fans-connected=*|--sensors-connected=*|--inventory=*|--results-dir=*)
            PYTEST_ARGS+=("$1"); HARDWARE=1 ;;
        # pytest options that take a value: pass the value through untouched (so `-k api` stays a keyword)
        -k|-m|-p|-o|-c|--junitxml|--maxfail|--deselect|--timeout|--rootdir|--basetemp)
            [ $# -ge 2 ] || { echo "ERROR: $1 needs a value" >&2; exit 2; }
            PYTEST_ARGS+=("$1" "$2"); shift ;;
        *)              PYTEST_ARGS+=("$1") ;;
    esac
    shift
done

# Hardware options without an explicit test path -> run the hardware tests
if [ "$HARDWARE" -eq 1 ]; then
    has_path=0
    for arg in ${SUITES[@]+"${SUITES[@]}"} ${PYTEST_ARGS[@]+"${PYTEST_ARGS[@]}"}; do
        case "$arg" in hardware_tests*|tests/*|tests) has_path=1 ;; esac
    done
    [ "$has_path" -eq 1 ] || SUITES+=(hardware_tests)
fi

if [ "$SETUP" -eq 1 ]; then
    if [ ! -d .venv ]; then
        echo "Creating virtual environment in .venv ..."
        "${PYTHON:-python3}" -m venv .venv
    fi
    PY="$(find_python)"
    "$PY" -m pip install --upgrade pip
    "$PY" -m pip install -r requirements-dev.txt
fi

PY="$(find_python)"

if ! "$PY" -c "import pytest" >/dev/null 2>&1; then
    echo "ERROR: pytest is not installed for '$PY'." >&2
    echo "Run './run_tests.sh --setup' (creates .venv) or '$PY -m pip install -r requirements-dev.txt'." >&2
    exit 1
fi

echo "Using: $("$PY" --version 2>&1) ($PY)"
exec "$PY" -m pytest ${SUITES[@]+"${SUITES[@]}"} ${PYTEST_ARGS[@]+"${PYTEST_ARGS[@]}"}
