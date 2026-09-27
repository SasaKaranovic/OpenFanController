# OpenFAN Python software tests

Unit and API tests for the code in `Software/Python`. They run on any machine: **no OpenFAN
hardware is needed**. The serial link is replaced by a fake firmware, and config files are
written to a temporary folder, so your real `config.yaml` is never touched.

## Running the tests

From `Software/Python`:

| Windows | Linux / macOS | What it does |
|---|---|---|
| `run_tests.bat --setup` | `./run_tests.sh --setup` | One time: create `.venv` and install everything the tests need |
| `run_tests.bat` | `./run_tests.sh` | Run all tests |
| `run_tests.bat api config` | `./run_tests.sh api config` | Run only some suites |
| `run_tests.bat api -k alias` | `./run_tests.sh api -k alias` | Only tests whose name contains `alias` |
| `run_tests.bat tests\test_board.py::test_unknown_board_is_marked_unsupported` | `./run_tests.sh tests/test_board.py::test_unknown_board_is_marked_unsupported` | A single test |
| `run_tests.bat --list` | `./run_tests.sh --list` | List the tests without running them |
| `run_tests.bat --cov` | `./run_tests.sh --cov` | Add a coverage report |
| `run_tests.bat known-bugs` | `./run_tests.sh known-bugs` | Only the tests that document known bugs |

Suites: `api`, `board`, `config`, `fancommander`, `serial` (and `known-bugs`).
Any other argument is passed straight to pytest (`-x`, `-v`, `-k ...`, and so on).
The scripts use `%PYTHON%`/`$PYTHON` if it is set, otherwise `.venv`, otherwise the system Python.

Without the scripts: `python -m pip install -r requirements-dev.txt`, then `python -m pytest`.

## What is tested

| File | Covers |
|---|---|
| `test_fancommander.py` | Command encoding (`>02037F` ...), response parsing, signed temperatures, USB discovery |
| `test_serial_driver.py` | `SerialHardware` on a fake `serial.Serial`, plus a full `FanCommander` → serial → firmware round trip |
| `test_board.py` | Board type and capabilities for OpenFAN Controller / XL / Micro |
| `test_config.py` | Loading `config.yaml`, filling in defaults, fan profiles, aliases, saving |
| `test_api.py` | Every REST route over real HTTP, validation and clamping, per-board capability gating |

Test helpers live in `fakes.py` (`FakeFirmware`, `FakeFanCommander`, `FakeSerialPort`) and
`conftest.py` (shared fixtures).

## Known bugs (`xfail`)

Tests that document a bug that still exists are marked
`@pytest.mark.xfail(strict=True, reason="Known bug: ...")`. They show up as `x`/`XFAIL` and
don't fail the run. When a bug gets fixed, its test starts passing. Because of `strict=True` it
is then reported as a **failure** (`XPASS(strict)`), as a reminder to delete the `xfail` marker
so the test guards against the bug coming back.

## CI

`.github/workflows/python_tests.yaml` runs `run_tests.sh --cov` on Python 3.9, 3.10 and 3.12
for every pull request that changes `Software/Python`, and on pushes to `master`.
