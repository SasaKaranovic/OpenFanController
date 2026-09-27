#!/usr/bin/env bash
# Run the OpenFAN Python software tests (no hardware needed).
#
# Usage: ./run_tests.sh [options] [suite ...] [pytest args ...]
#
#   Suites (any combination; default is all):
#     api            REST API (webserver.py)
#     board          board detection (board.py)
#     config         config.yaml handling (config.py)
#     fancommander   serial protocol encoding/parsing (FanCommander.py)
#     serial         serial driver (serial_driver.py)
#     known-bugs     only the tests documenting known bugs (xfail)
#
#   Options:
#     --setup        create .venv (if missing) and install requirements + test tools
#     --cov          show a coverage report (needs pytest-cov)
#     --list         list the tests instead of running them
#     -h, --help     show this help
#
#   Anything else is passed straight to pytest, e.g.
#     ./run_tests.sh api -k alias          only API tests with "alias" in their name
#     ./run_tests.sh tests/test_config.py::test_set_fan_alias_persists
#     ./run_tests.sh -x -v                 verbose, stop at the first failure
#
# Uses $PYTHON if set, otherwise .venv (if present), otherwise python3 / python.

set -euo pipefail
cd "$(dirname "$0")"

usage() { sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; }

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
        all)            ;;
        *)              PYTEST_ARGS+=("$1") ;;
    esac
    shift
done

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
