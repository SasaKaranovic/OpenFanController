"""Hardware-aware pytest plugin for the OpenFAN hardware tests.

How a run is put together
-------------------------
1. Pick the target (see README.md):
     --device NAME            a device from devices.yaml (physical or simulated); the server is started for you
     --base-url URL           test a server that is already running (profile read from /api/v0/info,
                              or from the inventory if --device is also given)
     --server-config FILE     start webserver.py with (a copy of) this config file
2. Before any test runs, the board declared in the inventory is compared with the capabilities
   the server reports. A mismatch aborts the run (wrong controller / cable / firmware).
3. Tests are filtered and adapted to the device:
     * suites (pytest markers, one per test file): only the device's `suites` run, unless --suite
     * @pytest.mark.requires("feature"):
         --scope supported (default)  test is SKIPPED when the device lacks the feature
         --scope all                  test RUNS and must verify the documented "unsupported" error
                                      (the `expect` fixture tells the test which case it is in)
     * `known_failures` in the inventory become strict xfails
     * fixtures `fan`, `connected_fan`, `sensor`, ... are parametrized from the device profile
4. Results are written to hardware_tests/results/<device>.json (+ server log) for summarize.py.
"""
import datetime
import json
import os
import sys

import pytest

HW_DIR = os.path.dirname(os.path.abspath(__file__))
if HW_DIR not in sys.path:
    sys.path.insert(0, HW_DIR)

# pylint: disable=wrong-import-position
from harness import ApiClient, Expect, HarnessError, ServerProcess, wait_until     # noqa: E402
from inventory import (FEATURES, SUITES, AdHocDevice, Inventory, InventoryError,   # noqa: E402
                       describe_inventory, DEFAULT_INVENTORY)

MAX_CHANNEL_INDEX = 9           # API routes accept a single digit channel index
STATE_KEY = pytest.StashKey()
_UNSUPPORTED_KEY = pytest.StashKey()
_STATE = None                   # the HardwareState of the current session (for hooks without `config`)


def _channel_list(text):
    return [int(x) for x in text.split(",") if x.strip() != ""] if text else []


# ============================================================ options

def pytest_addoption(parser):
    group = parser.getgroup("openfan-hardware", "OpenFAN hardware tests")
    group.addoption("--device", help="device name from the inventory (see --list-devices)")
    group.addoption("--base-url", help="test an already running OpenFAN server, e.g. http://localhost:3000")
    group.addoption("--server-config", help="start webserver.py with a copy of this config.yaml")
    group.addoption("--server-port", type=int, help="override the TCP port the started server listens on")
    group.addoption("--scope", choices=("supported", "all"), default="supported",
                    help="supported: skip tests for features the device lacks (default); "
                         "all: run them and verify the API reports them as unsupported")
    group.addoption("--suite", default=None,
                    help=f"comma separated suites to run ({', '.join(SUITES)}) or `all`; "
                         "default: the device's `suites` from the inventory")
    group.addoption("--inventory", default=DEFAULT_INVENTORY, help="inventory file (default: devices.yaml)")
    group.addoption("--fans-connected", default="",
                    help="without --device: comma separated fan channels that have a fan attached")
    group.addoption("--sensors-connected", default="",
                    help="without --device: comma separated sensor channels that have a sensor attached")
    group.addoption("--results-dir", default=os.path.join(HW_DIR, "results"),
                    help="where to write <device>.json results and the server log")
    group.addoption("--list-devices", action="store_true", help="show the inventory and detected ports, then exit")


def pytest_configure(config):
    for suite in SUITES:
        config.addinivalue_line("markers", f"{suite}: OpenFAN hardware test suite `{suite}`")
    config.addinivalue_line("markers", "requires(feature): test needs a hardware/firmware feature "
                                       f"({', '.join(FEATURES)})")


def pytest_cmdline_main(config):
    if config.getoption("list_devices"):
        try:
            print(describe_inventory(Inventory(config.getoption("inventory"))))
        except InventoryError as error:
            print(f"ERROR: {error}")
            return 2
        return 0
    return None


# ============================================================ session state

class HardwareState:
    """Everything the hardware tests know about the device under test."""

    def __init__(self):
        self.active = False
        self.inactive_reason = ""
        self.device = None
        self.server = None
        self.base_url = None
        self.info = None
        self.scope = "supported"
        self.suites = list(SUITES)
        self.results = []
        self.started_at = None


def _is_hw_item(item):
    return str(item.path).startswith(HW_DIR)


def pytest_sessionstart(session):
    config = session.config
    global _STATE       # pylint: disable=global-statement
    state = HardwareState()
    config.stash[STATE_KEY] = state
    _STATE = state
    state.scope = config.getoption("scope")
    device_name = config.getoption("device")
    base_url = config.getoption("base_url")
    server_config = config.getoption("server_config")
    if not (device_name or base_url or server_config):
        state.inactive_reason = ("no hardware target selected: use --device NAME, --base-url URL or "
                                 "--server-config FILE (see --list-devices)")
        return

    results_dir = config.getoption("results_dir")
    try:
        inventory = Inventory(config.getoption("inventory"))
        device = inventory.get(device_name) if device_name else None

        if base_url:
            state.base_url = base_url
        elif device and config.option.collectonly:
            # Only listing tests: the inventory profile is enough, don't touch the hardware
            state.device = device
            state.suites = _selected_suites(config, device)
            state.active = True
            return
        else:
            name = device.name if device else "adhoc"
            port = config.getoption("server_port") or (device.server_port if device else None)
            if port is None:
                raise HarnessError("--server-port is required when starting a server without --device")
            sim_args = None
            serial_port = None
            if device and device.simulated:
                sim_args = ["--board", device.board.name,
                            "--fans-connected", ",".join(map(str, device.fans_connected)),
                            "--sensors-connected", ",".join(map(str, device.sensors_connected))]
            elif device:
                serial_port = device.resolve_port()
            base_config = server_config or (device.config if device else None)
            state.server = ServerProcess(name, int(port), os.path.join(results_dir, f"{name}-server.log"),
                                         base_config=base_config, serial_port=serial_port,
                                         simulator_args=sim_args)
            print(f"\n[openfan] starting server for {device.describe() if device else name} "
                  f"on {state.server.base_url} ...")
            state.server.start()
            state.base_url = state.server.base_url

        api = ApiClient(state.base_url)
        state.info = api.get("/api/v0/info")
        caps = state.info.get("capabilities") or {}
        if not caps:
            raise HarnessError("/api/v0/info has no `capabilities`; the server is too old for these tests")

        if device:
            differences = device.board.differences(caps)
            if differences:
                raise HarnessError(f"device `{device.name}` does not match the inventory "
                                   f"(wrong controller, cable or firmware?):\n  - " + "\n  - ".join(differences))
        else:
            device = AdHocDevice(caps, inventory.defaults,
                                 _channel_list(config.getoption("fans_connected")),
                                 _channel_list(config.getoption("sensors_connected")))
    except (InventoryError, HarnessError) as error:
        if state.server:
            state.server.stop()
        pytest.exit(f"[openfan] {error}", returncode=3)

    state.device = device
    state.suites = _selected_suites(config, device)
    state.active = True
    state.started_at = datetime.datetime.now().isoformat(timespec="seconds")


def _selected_suites(config, device):
    suite_option = config.getoption("suite")
    if not suite_option:
        return list(device.suites)
    if suite_option == "all":
        return list(SUITES)
    suites = [s.strip() for s in suite_option.split(",") if s.strip()]
    unknown = set(suites) - set(SUITES)
    if unknown:
        pytest.exit(f"[openfan] unknown suite(s) {sorted(unknown)}; valid: {', '.join(SUITES)}", returncode=3)
    return suites


def pytest_report_header(config):
    state = config.stash.get(STATE_KEY, None)
    if not state or not state.active:
        return None
    device = state.device
    return [f"openfan device: {device.describe()} at {state.base_url or '(not started: listing only)'}",
            f"openfan board: fans={device.board.fan_count} sensors={device.board.sensor_count} "
            f"features={','.join(sorted(device.features))}",
            f"openfan wiring: fans_connected={device.fans_connected} sensors_connected={device.sensors_connected}",
            f"openfan scope={state.scope} suites={','.join(state.suites)}"]


def pytest_unconfigure(config):
    state = config.stash.get(STATE_KEY, None)
    if state and state.server:
        state.server.stop()


# ============================================================ parametrization from the device profile

def _params(values, prefix, empty_reason):
    if not values:
        return [pytest.param(None, id=f"no-{prefix}", marks=pytest.mark.skip(reason=empty_reason))]
    return [pytest.param(v, id=f"{prefix}{v}") for v in values]


def pytest_generate_tests(metafunc):
    if not str(metafunc.definition.path).startswith(HW_DIR):
        return
    state = metafunc.config.stash.get(STATE_KEY, None)
    if not state or not state.active:
        return
    device = state.device
    board = device.board
    all_fans = list(range(board.fan_count))
    sensors = list(range(board.sensor_count)) or [0]     # [0] = probe index when the board has no sensors
    fixtures = {
        "fan": _params(all_fans, "fan", "board has no fan channels"),
        "connected_fan": _params(device.fans_connected, "fan", f"no fans connected on {device.name}"),
        "disconnected_fan": _params([f for f in all_fans if f not in device.fans_connected], "fan",
                                    f"every fan channel on {device.name} has a fan"),
        "invalid_fan_index": _params(list(range(board.fan_count, MAX_CHANNEL_INDEX + 1)), "fan",
                                     f"{board.name} uses every channel index 0..{MAX_CHANNEL_INDEX}"),
        "sensor": _params(sensors, "sensor", "no sensors"),
        "connected_sensor": _params(device.sensors_connected, "sensor",
                                    f"no sensors connected on {device.name}"),
        "invalid_sensor_index": _params(
            list(range(board.sensor_count, MAX_CHANNEL_INDEX + 1)) if device.has("temperature") else [],
            "sensor", f"{board.name} has no temperature sensors (covered by the unsupported checks)"),
    }
    for name, params in fixtures.items():
        if name in metafunc.fixturenames:
            metafunc.parametrize(name, params)


# ============================================================ selection / adaptation

def pytest_collection_modifyitems(session, config, items):
    state = config.stash.get(STATE_KEY, None)
    hw_items = [item for item in items if _is_hw_item(item)]
    if not hw_items:
        return
    if not state or not state.active:
        skip = pytest.mark.skip(reason=state.inactive_reason if state else "hardware tests inactive")
        for item in hw_items:
            item.add_marker(skip)
        return

    device = state.device
    has_timeout_plugin = config.pluginmanager.hasplugin("timeout")
    selected, deselected = [], []
    for item in items:
        if not _is_hw_item(item):
            selected.append(item)
            continue
        suites = [s for s in SUITES if item.get_closest_marker(s)]
        if not suites:
            raise pytest.UsageError(f"{item.nodeid}: hardware test has no suite marker ({', '.join(SUITES)})")
        if not set(suites) & set(state.suites):
            deselected.append(item)
            continue
        selected.append(item)

        required = [m.args[0] for m in item.iter_markers("requires")]
        unknown = set(required) - set(FEATURES)
        if unknown:
            raise pytest.UsageError(f"{item.nodeid}: unknown feature(s) {sorted(unknown)} in requires()")
        missing = [f for f in required if not device.has(f)]
        item.stash[_UNSUPPORTED_KEY] = None
        if missing:
            if state.scope == "supported":
                item.add_marker(pytest.mark.skip(
                    reason=f"`{missing[0]}` not supported by {device.name} ({device.board.name})"))
            else:
                item.stash[_UNSUPPORTED_KEY] = missing[0]

        for key, reason in device.known_failures.items():
            if item.nodeid.endswith(key):
                item.add_marker(pytest.mark.xfail(strict=True, reason=f"known failure on {device.name}: {reason}"))

        if has_timeout_plugin and not item.get_closest_marker("timeout"):
            item.add_marker(pytest.mark.timeout(device.timing.get("test_timeout_s", 180)))

        item.user_properties.extend([("device", device.name), ("suites", ",".join(suites)),
                                     ("features", ",".join(required)),
                                     ("expect_unsupported", item.stash[_UNSUPPORTED_KEY] or "")])
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected



# ============================================================ fixtures

@pytest.fixture(scope="session")
def hw(pytestconfig):
    """The HardwareState: `hw.device`, `hw.info`, `hw.base_url`, `hw.scope`."""
    state = pytestconfig.stash[STATE_KEY]
    if not state.active:
        pytest.skip(state.inactive_reason)
    return state


@pytest.fixture(scope="session")
def device(hw):
    return hw.device


@pytest.fixture(scope="session")
def api(hw):
    return ApiClient(hw.base_url)


@pytest.fixture(scope="session")
def timing(device):
    return {"settle_s": device.timing.get("settle_s", 15), "poll_s": device.timing.get("poll_s", 0.5)}


@pytest.fixture
def expect(request, device):
    return Expect(request.node.stash.get(_UNSUPPORTED_KEY, None), device.name)


@pytest.fixture
def wait(timing):
    """`wait(condition, message)` polls with the device's timing settings."""
    def _wait(condition, message="condition not met", timeout=None):
        return wait_until(condition, timeout or timing["settle_s"], timing["poll_s"], message)
    return _wait


@pytest.fixture(scope="session", autouse=True)
def safe_fan_state(hw):
    """Put every fan at the device's `safe_pwm` before and after the run (these are real fans)."""
    state = hw
    if not state.active or not state.device.has("pwm"):
        yield
        return
    client = ApiClient(state.base_url)
    client.get(f"/api/v0/fan/all/set?value={state.device.safe_pwm}")
    yield
    try:
        client.get(f"/api/v0/fan/all/set?value={state.device.safe_pwm}")
    except Exception as error:      # pylint: disable=broad-except
        print(f"\n[openfan] WARNING: could not restore safe fan state: {error}")


# ============================================================ results

def pytest_runtest_logreport(report):
    props = dict(report.user_properties)
    if _STATE is None or not _STATE.active or "device" not in props:
        return      # not a hardware test
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        if hasattr(report, "wasxfail"):
            outcome = "xpassed" if report.passed else "xfailed"
        else:
            outcome = report.outcome
        if outcome == "passed" and props.get("expect_unsupported"):
            outcome = "unsupported-verified"
        message = ""
        if report.failed:
            message = str(report.longrepr)[-2000:]
        elif report.skipped and isinstance(report.longrepr, tuple):
            message = report.longrepr[2]
        elif hasattr(report, "wasxfail"):
            message = report.wasxfail
        _STATE.results.append({
            "nodeid": report.nodeid, "outcome": outcome, "duration_s": round(report.duration, 3),
            "suites": props.get("suites", ""), "features": props.get("features", ""),
            "expect_unsupported": props.get("expect_unsupported", ""), "message": message,
        })


def pytest_sessionfinish(session, exitstatus):
    state = session.config.stash.get(STATE_KEY, None)
    if not state or not state.active or session.config.option.collectonly:
        return
    device = state.device
    results_dir = session.config.getoption("results_dir")
    os.makedirs(results_dir, exist_ok=True)
    counts = {}
    for result in state.results:
        counts[result["outcome"]] = counts.get(result["outcome"], 0) + 1
    payload = {
        "device": device.name, "board": device.board.name, "simulated": device.simulated,
        "base_url": state.base_url, "scope": state.scope, "suites": state.suites,
        "features": sorted(device.features), "fan_count": device.board.fan_count,
        "sensor_count": device.board.sensor_count, "fans_connected": device.fans_connected,
        "sensors_connected": device.sensors_connected, "info": state.info,
        "started_at": state.started_at, "exitstatus": int(exitstatus), "counts": counts,
        "results": state.results,
    }
    path = os.path.join(results_dir, f"{device.name}.json")
    with open(path, "w", encoding="utf8") as file:
        json.dump(payload, file, indent=2, default=str)
    print(f"\n[openfan] results written to {path}")
