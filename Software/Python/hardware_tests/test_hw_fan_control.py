"""Fan control on real fans: set -> record -> set again -> verify the reading changed."""
import pytest

pytestmark = pytest.mark.fan_control


def stable_rpm(api, fan, wait, samples=3):
    """Wait until `samples` consecutive readings agree (within 10% / 50 RPM); return their average."""
    readings = []

    def _stable():
        readings.append(api.fan_rpm(fan))
        recent = readings[-samples:]
        if len(recent) == samples and max(recent) - min(recent) <= max(50, max(recent) * 0.1):
            return [sum(recent) // samples]       # list: truthy even when the average is 0
        return None

    return wait(_stable, f"fan {fan}: RPM did not settle")[0]


def rpm_above(api, fan, threshold):
    """Condition for `wait`: the current RPM if it is above `threshold`, else None."""
    def _check():
        rpm = api.fan_rpm(fan)
        return rpm if rpm > threshold else None
    return _check


@pytest.mark.requires("pwm")
def test_set_pwm_is_accepted_on_every_channel(api, fan, expect):
    reply = api.raw(f"/api/v0/fan/{fan}/pwm?value=60")
    if expect.unsupported:
        expect.unsupported_error(reply)
        return
    assert reply["status"] == "ok", reply
    assert f"#{fan}" in reply["message"]


@pytest.mark.requires("pwm")
def test_rpm_follows_pwm(api, connected_fan, device, wait, expect):
    reply = api.raw(f"/api/v0/fan/{connected_fan}/pwm?value=30")
    if expect.unsupported:
        expect.unsupported_error(reply)
        return
    low = stable_rpm(api, connected_fan, wait)                         # record

    api.get(f"/api/v0/fan/{connected_fan}/pwm?value=100")              # change
    threshold = max(low * (1 + device.rpm.get("min_increase_pct", 20) / 100),
                    device.rpm.get("min_running_rpm", 300))
    wait(rpm_above(api, connected_fan, threshold),                     # verify it changed
         f"fan {connected_fan}: RPM at 100% PWM did not rise above {threshold:.0f} (was {low} at 30%)")


@pytest.mark.requires("pwm")
def test_set_all_pwm_changes_every_connected_fan(api, device, wait, expect):
    reply = api.raw("/api/v0/fan/all/set?value=30")
    if expect.unsupported:
        expect.unsupported_error(reply)
        return
    if not device.fans_connected:
        pytest.skip(f"no fans connected on {device.name}")
    low = {fan: stable_rpm(api, fan, wait) for fan in device.fans_connected}

    api.get("/api/v0/fan/all/set?value=100")
    for fan in device.fans_connected:
        wait(rpm_above(api, fan, low[fan] * 1.1), f"fan {fan} did not speed up after set-all 100% (was {low[fan]})")


@pytest.mark.requires("pwm")
def test_empty_channel_reads_zero_rpm(api, disconnected_fan, wait, expect):
    reply = api.raw(f"/api/v0/fan/{disconnected_fan}/pwm?value=100")
    if expect.unsupported:
        expect.unsupported_error(reply)
        return
    wait(lambda: api.fan_rpm(disconnected_fan) == 0,
         f"fan {disconnected_fan} is listed as empty in the inventory but reports RPM (fan attached?)")


@pytest.mark.requires("rpm_control")
def test_rpm_command_is_accepted_on_every_channel(api, fan, expect):
    reply = api.raw(f"/api/v0/fan/{fan}/rpm?value=1000")
    if expect.unsupported:
        expect.unsupported_error(reply)
        return
    assert reply["status"] == "ok", reply


@pytest.mark.requires("rpm_control")
def test_rpm_target_is_reached(api, connected_fan, device, wait, expect):
    target = 1200
    reply = api.raw(f"/api/v0/fan/{connected_fan}/rpm?value={target}")
    if expect.unsupported:
        expect.unsupported_error(reply)
        return
    assert reply["status"] == "ok", reply
    tolerance = target * device.rpm.get("target_tolerance_pct", 10) / 100
    wait(lambda: abs(api.fan_rpm(connected_fan) - target) <= tolerance,
         f"fan {connected_fan} did not reach {target} +/- {tolerance:.0f} RPM")
