# Extending the hardware tests

Recipes for common changes to `hardware_tests/`. For how everything fits together, read
[Hardware tests](hardware-tests.md) first.

**Quick index:**

* [Add a test to an existing suite](#add-a-test-to-an-existing-suite)
* [Guidelines for hardware tests](#guidelines-for-hardware-tests)
* [Add a physical controller](#add-a-physical-controller)
* [Mark a known failure on one device](#mark-a-known-failure-on-one-device)
* [Change thresholds, timing and the safe state](#change-thresholds-timing-and-the-safe-state)
* [Add a new suite](#add-a-new-suite)
* [Add a new feature](#add-a-new-feature)
* [Add a board model](#add-a-board-model)
* [Add a parametrized fixture](#add-a-parametrized-fixture)
* [Add a command-line option](#add-a-command-line-option)
* [Change what the identity check compares](#change-what-the-identity-check-compares)

After any change, run it against the simulators first. No hardware is needed:

```bash
./run_tests.sh --device sim-controller --scope all --suite all
./run_tests.sh --device sim-xl --scope all --suite all
./run_tests.sh --device sim-micro --scope all --suite all
```

---

## Add a test to an existing suite

Put it in the suite's file (`test_hw_<suite>.py`). The file's `pytestmark` already assigns the suite.

```python
# test_hw_fan_control.py   (pytestmark = pytest.mark.fan_control)

@pytest.mark.requires("pwm")                     # feature(s) the test needs
def test_zero_pwm_stops_fan(api, connected_fan, wait, expect):
    reply = api.raw(f"/api/v0/fan/{connected_fan}/pwm?value=0")
    if expect.unsupported:                       # 1. unsupported branch first
        expect.unsupported_error(reply)
        return
    assert reply["status"] == "ok", reply        # 2. the command was accepted
    wait(lambda: api.fan_rpm(connected_fan) < 200,  # 3. the hardware reacted
         f"fan {connected_fan} still spinning at 0% PWM")
```

Checklist:

1. **Pick fixtures** for the data you need: `api`, `device`, `wait`, `expect`, and a channel
   fixture (`fan`, `connected_fan`, `disconnected_fan`, `invalid_fan_index`, `sensor`,
   `connected_sensor`, `invalid_sensor_index`).
2. **Declare features** with `@pytest.mark.requires(...)` if the test depends on one. Tests that
   exercise always-available behaviour, like validation, don't need it.
3. **Handle `expect.unsupported`** first in any test that has `requires`. Otherwise `--scope all` on a
   device without the feature makes the test fail on the "not supported" reply.
4. **Run** it on all three simulators with `--scope all`.

A test that checks something in the web page:

```python
# test_hw_html.py   (pytestmark = pytest.mark.html; `page` = parsed "/" for the module)

def test_rpm_unit_shown_for_each_fan(page, device):
    for i in range(device.board.fan_count):
        tile = page.select_one(f"#fan-{i}-rpm")
        assert tile is not None
        assert "RPM" in tile.parent.get_text()
```

Select elements by `id` (or add a `data-testid` attribute to the template) rather than by styling
classes, which change with the design.

## Guidelines for hardware tests

* **Poll, don't sleep.** Use `wait(condition, message)`; it uses the device's `timing` and fails
  with your message and the last value seen.
* **Record, change, verify.** Measure the "before" state yourself (`stable_rpm()` in
  `test_hw_fan_control.py` waits for steady readings) and compare relative changes. Don't compare
  against absolute numbers from another fan.
* **Allow for noise.** Real tachometers jitter. Use thresholds from `device.rpm`
  (`min_increase_pct`, `target_tolerance_pct`, `min_running_rpm`), not exact equality.
* **Don't assume a starting state.** Set what you need at the start of the test.
* **Put things back.** Restore aliases and remove profiles you created (see the `try/finally` in
  `test_hw_aliases.py` and the `cleanup_profiles` fixture). Fan speeds are reset to `safe_pwm` at the end of the run.
* **One channel per test case.** Use channel fixtures instead of loops, so `[fan3]` shows up (and can be marked a known failure) on its own.
* **Only use HTTP.** Hardware tests must not import application modules; they test the running server.

## Add a physical controller

1. Plug it in and run `run_tests.bat --list-devices`. Note its port and `usb_serial`
   (shown as `NOT IN INVENTORY`).
2. Add an entry under `devices:` in `devices.yaml`:

   ```yaml
   lab-ctrl-02:
     enabled: true
     board: openfan-controller          # a key under boards:
     usb_serial: "E6614C311B2F4B28"     # preferred: survives COM-port renumbering
     # port: COM12                      # alternative
     server_port: 3104                  # unique among devices on that machine
     fans_connected: [0, 1, 4]          # channels with a real fan on the test rig
     suites: [smoke, html, fan_control, profiles, aliases]
   ```

3. Try it: `run_tests.bat --device lab-ctrl-02`, then `--scope all`.
4. Commit. The GitHub hardware workflow picks up every `enabled: true` physical device automatically
   (`inventory.py matrix`); no workflow edit is needed.

To take a controller out of rotation temporarily, set `enabled: false`. It stays runnable by hand.

## Mark a known failure on one device

When a test fails on one unit because of that unit (a damaged tach wire, a missing sensor) and not
because of the software:

```yaml
lab-ctrl-01:
  known_failures:
    "test_hw_fan_control.py::test_rpm_follows_pwm[fan1]": "fan 1 tach wire damaged (issue #61)"
    "test_hw_fan_control.py::test_rpm_target_is_reached[fan1]": "fan 1 tach wire damaged (issue #61)"
    "test_hw_service.py::test_software_version_is_reported": "no git checkout on this runner"
```

* The key is matched against the **end** of the test id (`item.nodeid.endswith(key)`). For a
  parametrized test, include the parameter (`[fan1]`), and list each channel that should be
  covered. `run_tests.bat --list --device <name>` prints the exact ids.
* The test becomes a strict `xfail` on that device only. If it starts passing (`XPASS(strict)`),
  the entry is stale and the run fails until you remove it.
* For software bugs that affect every device, fix the bug or document it in the software tests
  instead (see [Software tests](software-tests.md#known-bugs-the-xfail-convention)).

## Change thresholds, timing and the safe state

In `devices.yaml`, under `defaults:` for all devices, or under a device to override just that one
(nested keys are merged, so you can override a single value):

| Setting | Used by | Meaning |
|---|---|---|
| `safe_pwm` | `safe_fan_state` fixture | PWM % set on every fan before and after a run (currently `0`, i.e. fans off; use e.g. `100` if the rig needs cooling after a run) |
| `timing.settle_s` | `wait` fixture | maximum time a condition may take (fan spin-up/down) |
| `timing.poll_s` | `wait` fixture | poll interval |
| `timing.test_timeout_s` | pytest-timeout | hard limit per test |
| `rpm.min_running_rpm` | `test_rpm_follows_pwm` | minimum RPM of a connected fan at 100 % |
| `rpm.min_increase_pct` | `test_rpm_follows_pwm` | how much 30 % → 100 % PWM must raise RPM |
| `rpm.target_tolerance_pct` | `test_rpm_target_is_reached` | allowed deviation from an RPM target |

```yaml
lab-xl-01:
  timing: {settle_s: 20}        # big slow fans: only settle_s changes, poll_s etc. stay default
  rpm: {min_running_rpm: 150}
```

To add a new tunable, add it to `defaults:`, read it in the test through `device.rpm.get("name", default)` /
`device.timing.get(...)`, and, for a new top-level group, add the key to the tuple in `Device.__init__` (`inventory.py`) that picks up
`safe_pwm`, `timing` and `rpm`.

Test-specific constants that aren't per device (e.g. `PLAUSIBLE_RANGE_C` in `test_hw_sensors.py`)
live at the top of the test file.

## Add a new suite

Example: a `persistence` suite that checks settings survive a server restart.

1. **Register it** in `inventory.py`:

   ```python
   SUITES = ("smoke", "html", "fan_control", "profiles", "aliases", "sensors", "persistence")
   ```

   This makes it a valid marker, a valid `--suite` value and a valid `suites:` entry.
2. **Create `test_hw_persistence.py`**:

   ```python
   import pytest

   pytestmark = pytest.mark.persistence          # every test in the file belongs to the suite

   def test_alias_survives_restart(api, ...):
       ...
   ```

   Every hardware test must carry a suite marker; collection stops with an error otherwise.
3. **Enable it** by adding `persistence` to the `suites:` of the devices (including the `sim-*` ones) that should run it.
4. **Document it** in the suite table of [Hardware tests](hardware-tests.md#suites-features-and-scope) and in the `--suite` help text of
   `run_tests.bat` / `run_tests.sh` / `hardware_tests.yaml` (the list there is informational).

## Add a new feature

Example: firmware adds fan **curves**, reported by the server as `capabilities.has_curves`, and
unsupported boards answer "`does not support fan curves`".

1. **`inventory.py`**:

   ```python
   FEATURES = ("pwm", "rpm_control", "profiles", "temperature", "aliases", "curves")

   UNSUPPORTED_MESSAGES = {
       ...,
       "curves": "does not support fan curves",
   }

   def features_from_capabilities(caps):
       ...
       if caps.get("has_curves"):
           features.add("curves")
   ```

2. **`devices.yaml`**: add `curves` to the `features:` of the board models that support it. The identity
   check fails until the inventory and the server agree, which is intended.
3. **Tests**: mark them `@pytest.mark.requires("curves")` and handle `expect.unsupported`.
4. **`summarize.py`**: add `"curves"` to `FEATURE_ORDER` so it gets a row in the feature matrix.
5. **Simulator**: if simulated boards should support it, extend `SimulatedFirmware` (and
   `FakeFirmware` in `tests/fakes.py`) with the new command, and set the HW info so `board.py` reports it.

## Add a board model

1. **Server side:** `board.py` must recognise it from the HW info string, and the software tests need a
   case in `test_board.py` (see [Software tests](software-tests.md#example-a-new-board-model)).
2. **Inventory:** add it under `boards:` with exactly what the server reports:

   ```yaml
   openfan-mini:
     name: OpenFAN Mini
     hw_rev: "5"
     fan_count: 4
     sensor_count: 2
     features: [pwm, temperature, aliases]
   ```

3. **Simulator (recommended):** add `HW_INFO_MINI` to `tests/fakes.py`, register it in
   `HW_INFO_BY_BOARD` in `simulator.py` (`"OpenFAN Mini": (HW_INFO_MINI, 4)`), and add a
   `sim-mini` device with `simulated: true`, a free `server_port` and its suites.
4. **CI:** add `sim-mini` to the `hardware-simulated` matrix in `.github/workflows/python_tests.yaml`.

Tests that use `device.board.fan_count`, `device.has(...)` and the channel fixtures adapt
automatically. Only tests that hard-code board-specific values need attention.

## Add a parametrized fixture

Channel fixtures are generated in `pytest_generate_tests` (`conftest.py`). To add one, e.g.
`pwm_step` over a list defined per device:

1. Add the data to the inventory (`pwm_steps: [25, 50, 75, 100]`) and read it in `Device.__init__`
   (`self.pwm_steps = list(data.get("pwm_steps", [25, 50, 75, 100]))`).
2. Add an entry to the `fixtures` dict in `pytest_generate_tests`:

   ```python
   "pwm_step": _params(device.pwm_steps, "pwm", "no PWM steps configured"),
   ```

3. Use it: `def test_rpm_increases_with_pwm(api, connected_fan, pwm_step, ...)`.

`_params` makes readable ids (`[pwm50]`) and turns an empty list into one visible skipped test.

## Add a command-line option

1. **Register it** in `pytest_addoption` (`conftest.py`):

   ```python
   group.addoption("--max-rpm", type=int, default=None, help="skip RPM targets above this")
   ```

2. **Use it** in `pytest_sessionstart` (store it on the `HardwareState`) or in a fixture via
   `request.config.getoption("max_rpm")`.
3. **Teach the scripts** that it takes a value, so they pass it through and switch to hardware mode:
   * `run_tests.sh`: add it to both hardware option `case` patterns (`--device|--scope|...` and `--device=*|...`);
   * `run_tests.bat`: add it to the `for %%o in (--device --scope ...)` list;
   * both: add a line to the help text at the top.
4. If CI should set it, add it to the pytest arguments in `hardware_tests.yaml` (both the bash and the pwsh step).

## Change what the identity check compares

`Board.differences(caps)` in `inventory.py` compares `name`, `hw_rev`, `fan_count`,
`sensor_count` and the feature set with `/api/v0/info → capabilities`. To compare more (e.g. a
firmware version), add the field to `boards:` in the inventory, read it in `Board.__init__` and
`Board.from_capabilities`, and add it to the attribute list in `differences()`.

Keep the check strict. It's what makes a result trustworthy: a test run that passes on the wrong
controller is worse than one that doesn't run.
