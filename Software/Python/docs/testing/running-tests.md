# Running the tests

All commands are run from `Software/Python`. `run_tests.bat` (Windows `cmd`) and `run_tests.sh`
(bash on Linux, macOS, Git Bash, WSL) accept the same options and both end up calling
`python -m pytest`.

## One-time setup

```bat
run_tests.bat --setup
```

This creates `.venv` if it does not exist and installs `requirements-dev.txt`, which pulls in the
runtime `requirements.txt` plus pytest, pytest-cov, requests, beautifulsoup4 and pytest-timeout.
Later runs use `.venv` automatically.

**Which Python is used:** `%PYTHON%` / `$PYTHON` if set, otherwise `.venv`, otherwise `python`/`py`
(Windows) or `python3`/`python` (Linux/macOS). If pytest is missing, the script tells you to run `--setup`.

## Software tests

| Command | Runs |
|---|---|
| `run_tests.bat` | all software tests (`tests/`) |
| `run_tests.bat api config` | only the `api` and `config` suites (any combination) |
| `run_tests.bat known-bugs` | only tests marked `xfail` (documented known bugs) |
| `run_tests.bat api -k alias` | API tests whose name contains `alias` |
| `run_tests.bat tests\test_board.py::test_unknown_board_is_marked_unsupported` | one test |
| `run_tests.bat --cov` | all, plus a coverage report |
| `run_tests.bat --list` | list tests without running them |

Software suites map to files: `api` → `test_api.py`, `board` → `test_board.py`,
`config` → `test_config.py`, `fancommander` → `test_fancommander.py`, `serial` → `test_serial_driver.py`.

## Hardware tests

Any hardware option (or the `hardware` keyword) makes the script run `hardware_tests/`.

| Command | Runs |
|---|---|
| `run_tests.bat --list-devices` | prints the inventory and detected OpenFAN serial ports |
| `run_tests.bat --device sim-controller` | the device's suites against a **simulated** controller |
| `run_tests.bat --device lab-ctrl-01` | the device's suites against a real controller (server started for you) |
| `run_tests.bat --device lab-ctrl-01 --scope all` | also verify unsupported features return the documented error |
| `run_tests.bat --device lab-ctrl-01 --suite "smoke,html"` | only some suites (`all` = every suite) |
| `run_tests.bat --list --device lab-xl-01` | list what would run on that device (no hardware touched) |
| `run_tests.bat --base-url http://localhost:3000` | test a server that is **already running** |
| `run_tests.bat --base-url http://localhost:3000 --device lab-ctrl-01` | ...and check it against that inventory entry |
| `run_tests.bat --base-url http://localhost:3000 --fans-connected "0,1"` | ...and run RPM tests on fans 0 and 1 |
| `run_tests.bat --server-config my.yaml --server-port 3000` | start `webserver.py` with a copy of `my.yaml` |
| `run_tests.bat tests hardware --device sim-micro` | both layers in one run |

### Hardware options

| Option | Default | Meaning |
|---|---|---|
| `--device NAME` | — | Device from the inventory. Real devices get a server started on their `server_port`; `simulated: true` devices get `simulator.py` |
| `--base-url URL` | — | Don't start a server; test the one at URL. Without `--device`, the profile comes from `/api/v0/info` |
| `--server-config FILE` | — | Start `webserver.py` with a copy of this config (combine with `--device` or `--server-port`) |
| `--server-port N` | device's `server_port` | TCP port for the server that gets started |
| `--scope supported\|all` | `supported` | `supported`: skip tests for features the device lacks. `all`: run them and require the "unsupported" error |
| `--suite a,b` | device's `suites` | `smoke`, `html`, `fan_control`, `profiles`, `aliases`, `sensors`, or `all` |
| `--fans-connected 0,1` | none | Without `--device`: channels with a real fan (for RPM measurements) |
| `--sensors-connected 0` | none | Without `--device`: channels with a real temperature sensor |
| `--inventory FILE` | `hardware_tests/devices.yaml` | Use another inventory |
| `--results-dir DIR` | `hardware_tests/results` | Where `<device>.json` and `<device>-server.log` go |
| `--list-devices` | — | Print inventory + detected ports and exit |

Without `--device`, `--base-url` or `--server-config`, hardware tests are **skipped** with a message
telling you to pick a target. That's why `pytest tests hardware_tests` is safe to run anywhere.

### `cmd.exe` quirks

`cmd.exe` splits arguments on commas, semicolons and `=`. Put comma lists in quotes:
`--suite "smoke,html"`, `--fans-connected "0,1"`. `--scope=all` works because the script treats
the split-off value correctly. Bash has no such problem.

### Any pytest option

Anything the script doesn't recognise goes to pytest unchanged: `-x` (stop at first failure),
`-v`, `-k expr`, `-m marker`, `--lf` (last failed), `--junitxml file.xml`, `-p no:cacheprovider`, ...
Options that take a value (`-k`, `-m`, `--junitxml`, `--maxfail`, ...) keep their value, so
`-k api` filters by name instead of selecting the `api` suite.

## Running pytest directly

The scripts are thin wrappers, so this works too:

```bash
python -m pytest                                   # software tests
python -m pytest tests/test_api.py -k alias
python -m pytest hardware_tests --device sim-xl --scope all
python hardware_tests/inventory.py list            # same as --list-devices
python hardware_tests/summarize.py                 # Markdown report from results/
```

## Reading the output

| Mark | Meaning |
|---|---|
| `.` / `PASSED` | passed |
| `F` / `FAILED` | failed: see the assertion message; hardware tests add the server log path |
| `s` / `SKIPPED` | skipped: the reason says why (feature not supported, no fan connected, no target, ...) |
| `x` / `XFAIL` | expected failure: a documented known bug or a device's `known_failures` entry |
| `XPASS(strict)` | a known bug or known failure started passing: remove its `xfail` marker / inventory entry |
| `deselected` | hardware test outside the selected suites |

Hardware runs print a header with the device, board, features and wiring, and write:

* `hardware_tests/results/<device>.json`: every test outcome, plus the device profile and `/api/v0/info`
* `hardware_tests/results/<device>-server.log`: the server's output for that run

`python hardware_tests/summarize.py` merges all JSON files into one Markdown table (per device and per feature).

## Exit codes

| Code | Meaning |
|---|---|
| 0 | all selected tests passed (skips and xfails are fine) |
| 1 | some tests failed |
| 2 | the run was interrupted, or `run_tests` was given an option without its value |
| 3 | hardware run aborted before testing: unknown device, port not found, server didn't start, or the **identity check failed** (wrong controller) |
| 4 | usage error: unknown option or value (e.g. `--scope maybe`), hardware test without a suite marker, unknown feature in `requires()` |
| 5 | no tests collected (e.g. a `-k` expression that matches nothing) |

## Continuous integration

| Workflow | Trigger | Runner | What it does |
|---|---|---|---|
| `python_tests.yaml` → `test` | PRs and pushes to `master` touching `Software/Python/**` | GitHub-hosted | `run_tests.sh --cov` on Python 3.9, 3.10, 3.12 |
| `python_tests.yaml` → `hardware-simulated` | same | GitHub-hosted | hardware suite against `sim-controller`, `sim-xl`, `sim-micro` with `--scope all --suite all`; summary on the run page |
| `hardware_tests.yaml` | push to `master`, nightly (`--scope all`), manual | self-hosted `openfan-lab` | one job per **enabled, non-simulated** device in the inventory; results table on the run page |

**Manual hardware run:** Actions → *Hardware tests* → *Run workflow*. Pick the branch, a device
(`all` or a name), a scope, and suites (`default` = each device's own list).

`hardware_tests.yaml` has **no `pull_request` trigger on purpose**. The repository is public, and a
fork's PR code would run on the lab machine. To test a PR on hardware, run the workflow manually on the PR's branch.

### Setting up the lab runner

1. Add a self-hosted runner (repo *Settings → Actions → Runners*) on the machine the controllers
   are plugged into, and give it the label `openfan-lab`. Windows and Linux both work.
2. Make sure `python` (Windows) or `python3` (Linux) is on the runner's `PATH`. The job runs
   `run_tests --setup` itself.
3. On Linux, the runner user must be able to open the serial ports (usually the `dialout` group).
4. Fill in the devices in `devices.yaml` and set `enabled: true` (see
   [Extending the hardware tests](extending-hardware-tests.md#add-a-physical-controller)).
5. Each device's `server_port` must be free on the runner. Jobs for the same device never run at
   the same time (`concurrency: openfan-hw-<device>`); different devices run in parallel.
