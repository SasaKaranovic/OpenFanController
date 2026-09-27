"""Smoke tests: the server is up, talks to the right board, and validates channel indices."""
import re

import pytest

from harness import assert_error

pytestmark = pytest.mark.smoke


def test_info_matches_inventory(api, device):
    info = api.get("/api/v0/info")
    caps = info["capabilities"]
    assert caps["name"] == device.board.name
    assert str(caps["hw_rev"]) == device.board.hw_rev
    assert caps["fan_count"] == device.board.fan_count
    assert caps["sensor_count"] == device.board.sensor_count
    assert info["hardware"], "hardware info string is empty"
    assert "FW_REV" in info["firmware"]


def test_software_version_is_reported(api):
    software = api.get("/api/v0/info")["software"]
    assert re.fullmatch(r"Version: v\S+ Build: \S+", software), software


def test_fan_status_has_one_entry_per_fan(api, device):
    status = api.get("/api/v0/fan/status")
    assert sorted(int(k) for k in status) == list(range(device.board.fan_count))
    assert all(isinstance(v, int) and v >= 0 for v in status.values()), status


def test_unknown_route_returns_404(api):
    assert api.http("/api/v0/this/does/not/exist").status_code == 404


def test_invalid_fan_index_is_rejected(api, invalid_fan_index):
    assert_error(api.raw(f"/api/v0/fan/{invalid_fan_index}/pwm?value=50"), "Invalid fan index")


def test_non_numeric_value_is_rejected(api):
    assert_error(api.raw("/api/v0/fan/0/pwm?value=fast"))
