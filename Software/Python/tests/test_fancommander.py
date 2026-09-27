"""Tests for `FanCommander`: command encoding and response parsing of the serial protocol."""
import pytest

import FanCommander as fan_commander_module
from FanCommander import FanCommander
from fakes import FakeFanCommander, FakeFirmware, make_port_info

# Known bugs are marked `xfail(strict=True)`: the suite stays green today, and once a bug is
# fixed the test starts passing, which strict mode reports as a failure - remove the marker then.


# --- Command encoding (what goes over the wire) ---

@pytest.mark.parametrize("method, args, expected", [
    ("get_all_fan_rpm", (), ">00"),
    ("get_all_fan_rpm", (3,), ">0103"),
    ("set_fan_pwm", (3, 50), ">02037F"),       # 50% -> 127
    ("set_fan_pwm", (0, 100), ">0200FF"),      # 100% -> 255
    ("set_fan_pwm", (9, 0), ">020900"),
    ("set_all_fan_pwm", (100,), ">03FF"),
    ("set_all_fan_pwm", (0,), ">0300"),
    ("set_fan_rpm", (0, 1200), ">040004B0"),
    ("set_fan_rpm", (9, 16000), ">04093E80"),
    ("get_hw_info", (), ">05"),
    ("get_fw_info", (), ">06"),
    ("get_temperature", (2,), ">0B02"),
    ("get_temperature_all", (), ">0C"),
])
def test_command_encoding(commander, method, args, expected):
    getattr(commander, method)(*args)
    assert commander.sent == [expected]


def test_set_fan_pwm_forwards_scaled_value_to_firmware(commander, firmware):
    commander.set_fan_pwm(4, 50)
    assert firmware.pwm[4] == 127


def test_set_fan_pwm_rejects_values_above_255(commander):
    with pytest.raises(ValueError):
        commander.set_fan_pwm(0, 256)


@pytest.mark.parametrize("pwm", [101, 200])
def test_set_fan_pwm_rejects_percentages_above_100(commander, pwm):
    with pytest.raises(ValueError):
        commander.set_fan_pwm(0, pwm)


def test_set_all_fan_pwm_rejects_percentages_above_100(commander):
    with pytest.raises(ValueError):
        commander.set_all_fan_pwm(150)


# --- Response parsing ---

def test_get_all_fan_rpm_parses_every_fan(commander, firmware):
    assert commander.get_all_fan_rpm() == firmware.rpm


def test_get_single_fan_rpm(commander, firmware):
    firmware.rpm[3] = 0x04B0
    result = commander.get_all_fan_rpm(3)
    assert result[3] == 1200


def test_parse_fan_rpm_handles_trailing_separator(commander):
    assert commander._parse_fan_rpm("<00|00:0000;01:FFFF;") == {0: 0, 1: 65535}


@pytest.mark.parametrize("hex_value, expected", [
    ("0000", 0),
    ("00FA", 250),
    ("7FFF", 32767),
    ("8000", -32768),
    ("FFFF", -1),
    ("FF9C", -100),
])
def test_hex_to_signed(commander, hex_value, expected):
    assert commander._hex_to_signed(hex_value) == expected


def test_get_temperature_all(commander):
    assert commander.get_temperature_all() == {0: 25.0, 1: -10.0, 2: 0.0, 3: 123.4}


def test_get_temperature_single_channel(commander, firmware):
    firmware.temperatures[2] = -55     # -5.5 degC
    assert commander.get_temperature(2) == -5.5


def test_parse_response_skips_lines_before_response(commander):
    lines = ["[debug] boot", "garbage", "<00|00:0001;", "tail"]
    assert commander._parseResponse(lines, ret_entire_response=False) == "<00|00:0001;"
    assert commander._parseResponse(lines, ret_entire_response=True) == ["<00|00:0001;", "tail"]


def test_parse_response_without_response_line_returns_false(commander):
    assert commander._parseResponse(["no", "response"], ret_entire_response=False) is False


def test_get_hw_info_contains_board_identification(commander):
    info = commander.get_hw_info()
    assert info.startswith("<05|")
    assert "MCU:PICO2040" in info
    assert "\n" not in info


def test_get_fw_info(commander):
    info = commander.get_fw_info()
    assert "FW_REV:01" in info
    assert "PROTOCOL_VERSION:01" in info


@pytest.mark.xfail(strict=True, reason="Known bug: _parse_fan_rpm() raises IndexError when the reply has no '|'")
def test_malformed_rpm_reply_does_not_crash(commander):
    assert commander._parse_fan_rpm("<00") == {}


@pytest.mark.xfail(strict=True, reason="Known bug: when the device does not answer, _sendCommand() returns False "
                                        "and get_all_fan_rpm() crashes with AttributeError")
def test_no_reply_does_not_crash(commander, monkeypatch):
    monkeypatch.setattr(commander, "serial_transaction", lambda payload, ignore_response=False: [])
    assert commander.get_all_fan_rpm() == {}


@pytest.mark.xfail(strict=True, reason="Known bug: fan_rpm / temperature_sensors are class attributes shared by "
                                        "every FanCommander instance")
def test_instances_do_not_share_rpm_state():
    first = FakeFanCommander(FakeFirmware())
    second = FakeFanCommander(FakeFirmware(fan_count=2))
    first.get_all_fan_rpm()
    assert not second.fan_rpm


# --- USB discovery ---

def test_find_fan_controller_matches_vid_pid(monkeypatch):
    other = make_port_info("/dev/ttyUSB0", vid=0x0403, pid=0x6001, description="FTDI")
    openfan = make_port_info("/dev/ttyACM0")
    monkeypatch.setattr(fan_commander_module, "comports", lambda: [other, openfan])
    assert FanCommander.find_fan_controller() is openfan


def test_find_fan_controller_returns_none_when_missing(monkeypatch):
    other = make_port_info("/dev/ttyUSB0", vid=0x0403, pid=0x6001, description="FTDI")
    monkeypatch.setattr(fan_commander_module, "comports", lambda: [other])
    assert FanCommander.find_fan_controller() is None
