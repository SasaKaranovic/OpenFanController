# OpenFAN hardware tests

End-to-end tests that start the OpenFAN web server against a **real controller** (or a
simulated one) and exercise it over HTTP: the API, the web page, and the fans themselves
(set a value → record the reading → change it → verify the reading changed).

Tests know which hardware they run on. Every device is described in `devices.yaml`, and each
test adapts to it:

* **Suites**: each device only runs its own list of suites (`smoke`, `html`, `fan_control`,
  `profiles`, `aliases`, `sensors`), unless you pick others with `--suite`.
* **Features**: tests marked `@pytest.mark.requires("rpm_control")` (or `profiles`,
  `temperature`, ...) are
  * **skipped** on devices without that feature (`--scope supported`, the default), or
  * **run** with `--scope all`, and then they must get the documented "not supported" error
    back from the API. If the API accepts the call instead, the test fails.
* **Channels**: `fan`, `connected_fan`, `disconnected_fan`, `sensor`, `connected_sensor`,
  `invalid_fan_index`, ... are generated from the board's fan/sensor count and from which
  channels actually have a fan or sensor attached.
* **Known failures** listed for a device become strict `xfail`s.
* **Identity check**: before any test runs, the board declared in the inventory is compared
  with what the server reports in `/api/v0/info`. A mismatch (wrong controller, cable or
  firmware) aborts the run.

## Running them manually

From `Software/Python` (Windows: `run_tests.bat`, Linux/macOS: `./run_tests.sh`; same options):

| Command | What it does |
|---|---|
| `run_tests.bat --setup` | One time: create `.venv` and install everything (software + hardware tests) |
| `run_tests.bat --list-devices` | Show the inventory and the OpenFAN serial ports that are plugged in |
| `run_tests.bat --device sim-xl` | Run the suites for the simulated XL (**no hardware needed**) |
| `run_tests.bat --device lab-ctrl-01` | Start the server for that controller and run its suites |
| `run_tests.bat --device lab-ctrl-01 --scope all` | Also verify unsupported features return the documented error |
| `run_tests.bat --device lab-ctrl-01 --suite "smoke,html"` | Only some suites (quote comma lists in `cmd.exe`) |
| `run_tests.bat --device lab-ctrl-01 -k rpm -x -v` | Any pytest option works too |
| `run_tests.bat --list --device lab-xl-01` | List the tests that would run on that device |
| `run_tests.bat --base-url http://localhost:3000` | Test a server that is **already running** (profile read from `/api/v0/info`) |
| `run_tests.bat --base-url http://localhost:3000 --fans-connected "0,1"` | ...and also run RPM tests on fans 0 and 1 |
| `run_tests.bat --server-config my_config.yaml --server-port 3000` | Start `webserver.py` with (a copy of) your config file |
| `run_tests.bat tests hardware --device sim-micro` | Software tests and hardware tests together |

Plain `run_tests.bat` (no hardware options) still runs only the software tests.

Without the scripts: `python -m pytest hardware_tests --device sim-xl`.

The server always gets a **copy** of the config in a temp folder, because tests change aliases
and profiles and the server writes those to its config file. Your `config.yaml` is never touched.
Every fan is set to the device's `safe_pwm` (default 100%) before and after a run.

## Adding a physical controller

1. Plug it in and run `run_tests.bat --list-devices` to see its port and USB serial number.
2. Add it to `devices.yaml` under `devices:`, with its `board`, `usb_serial` (or `port`), a free
   `server_port`, `fans_connected` / `sensors_connected`, and its `suites`. Then set `enabled: true`.
3. Try it: `run_tests.bat --device <name>`.

A new board model goes under `boards:`, with its name, hw_rev, fan/sensor count and features,
exactly as the server reports them.

## Results

Each run writes `results/<device>.json` and `results/<device>-server.log`. To merge all devices
into one Markdown table (the same one the GitHub workflow shows on the run page):

    python hardware_tests/summarize.py

## Files

| File | Purpose |
|---|---|
| `devices.yaml` | Inventory: board models, devices, wiring, suites, known failures, timing |
| `conftest.py` | The pytest plugin: options, identity check, suite/feature filtering, channel parametrization, results |
| `harness.py` | Server process, API client, `wait_until`, `Expect` (unsupported-feature checks) |
| `inventory.py` | Inventory loader; `python hardware_tests/inventory.py list` / `matrix` |
| `simulator.py` | Simulated controller behind the real web server code (for `simulated: true` devices) |
| `summarize.py` | Merge `results/*.json` into a Markdown report |
| `test_hw_*.py` | The tests: one file per suite |

## Writing a test

```python
import pytest

pytestmark = pytest.mark.fan_control          # the suite this file belongs to


@pytest.mark.requires("rpm_control")           # feature the test needs
def test_rpm_target_is_reached(api, connected_fan, wait, expect):
    reply = api.raw(f"/api/v0/fan/{connected_fan}/rpm?value=1200")
    if expect.unsupported:                     # --scope all on a device without rpm_control
        expect.unsupported_error(reply)        # must be the documented error
        return
    assert reply["status"] == "ok"
    wait(lambda: abs(api.fan_rpm(connected_fan) - 1200) < 120, "RPM target not reached")
```

Fixtures: `api` (`get`, `post`, `raw`, `http`, `html`, `fan_rpm`), `device` (inventory profile),
`hw` (session state and `/api/v0/info`), `wait` (polls using the device's timing), `expect`, and
the channel fixtures listed above.

## GitHub

* `.github/workflows/hardware_tests.yaml` runs on the self-hosted runner(s) labelled
  `openfan-lab`, with one job per enabled device, on pushes to `master`, nightly (`--scope all`),
  and on demand (pick device, scope and suites). It never runs on pull requests: this is a public
  repository, and code from a fork's PR would run on the lab machine.
* `.github/workflows/python_tests.yaml` runs the same suite against the three simulated devices
  on every PR, on GitHub-hosted runners.
