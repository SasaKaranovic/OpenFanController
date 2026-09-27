"""Temperature sensors."""
import pytest

from harness import assert_error

pytestmark = [pytest.mark.sensors, pytest.mark.requires("temperature")]

PLAUSIBLE_RANGE_C = (-20.0, 100.0)


def test_read_all_sensors(api, device, expect):
    reply = api.raw("/api/v0/sensor/temperature/all/get")
    if expect.unsupported:
        expect.unsupported_error(reply)
        return
    assert reply["status"] == "ok", reply
    assert sorted(int(k) for k in reply["data"]) == list(range(device.board.sensor_count))


def test_read_each_sensor(api, sensor, expect):
    reply = api.raw(f"/api/v0/sensor/temperature/{sensor}/get")
    if expect.unsupported:
        expect.unsupported_error(reply)
        return
    assert reply["status"] == "ok", reply
    assert isinstance(reply["data"], (int, float))


def test_connected_sensor_reading_is_plausible(api, connected_sensor):
    single = api.get(f"/api/v0/sensor/temperature/{connected_sensor}/get")
    low, high = PLAUSIBLE_RANGE_C
    assert low <= single <= high, f"sensor {connected_sensor}: {single} C is outside {PLAUSIBLE_RANGE_C}"
    from_all = api.get("/api/v0/sensor/temperature/all/get")[str(connected_sensor)]
    assert abs(from_all - single) <= 2.0, f"single read {single} vs all-read {from_all}"


def test_invalid_sensor_index_is_rejected(api, invalid_sensor_index):
    assert_error(api.raw(f"/api/v0/sensor/temperature/{invalid_sensor_index}/get"), "Invalid temperature index")
