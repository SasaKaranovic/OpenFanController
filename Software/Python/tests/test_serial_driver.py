"""Tests for `SerialHardware` (serial_driver.py) using a fake `serial.Serial`.

The last tests run `FanCommander` on top of the real serial driver code, talking to
`FakeFirmware`, to cover the full host -> device -> host path without hardware.
"""
import pytest
import serial

import serial_driver
from serial_driver import SerialHardware
from FanCommander import FanCommander
from fakes import FakeFirmware, FakeSerialPort, make_port_info


@pytest.fixture
def fake_serial(monkeypatch):
    """Replace `serial.Serial` with `FakeSerialPort` and answer with `FakeFirmware`."""
    monkeypatch.setattr(serial_driver._serial, "Serial", FakeSerialPort)
    FakeSerialPort.firmware = FakeFirmware()
    return FakeSerialPort


@pytest.fixture
def hardware(fake_serial):
    return SerialHardware(make_port_info(), timeout=0.05)


# --- Construction ---

def test_accepts_port_info(hardware):
    assert hardware.port.port == "/dev/ttyFAKE0"
    assert hardware.port.kwargs["baudrate"] == 115200
    assert hardware.description() == "OpenFAN Controller"


def test_finds_port_by_name(fake_serial, monkeypatch):
    port = make_port_info("/dev/ttyACM3")
    monkeypatch.setattr(serial_driver, "comports", lambda: [make_port_info("/dev/ttyACM0"), port])
    hw = SerialHardware("/dev/ttyACM3")
    assert hw.get_port_info() is port


def test_unknown_port_name_raises_type_error(fake_serial, monkeypatch):
    monkeypatch.setattr(serial_driver, "comports", lambda: [])
    with pytest.raises(TypeError):
        SerialHardware("/dev/does-not-exist")


# --- Open / close ---

def test_context_manager_opens_and_closes(hardware):
    hardware.port.close()
    with hardware as hw:
        assert hw.is_open()
    assert not hardware.is_open()


def test_transaction_on_closed_port_raises(hardware):
    hardware.close()
    with pytest.raises(serial.SerialException):
        hardware.serial_transaction(">00")


def test_transaction_rejects_non_string_payload(hardware):
    with pytest.raises(TypeError):
        hardware.serial_transaction(123)


# --- Sending ---

def test_send_appends_line_ending(hardware):
    hardware.serial_transaction(">05")
    assert hardware.port.written == [b">05\r\n"]


def test_send_discards_stale_input(hardware):
    hardware.port.inject("<00|stale\r\n")
    lines = hardware.serial_transaction(">06")
    assert lines[0].startswith("<06|")
    assert not any("stale" in line for line in lines)


# --- Receiving ---

def test_read_until_response_skips_log_noise(fake_serial):
    fake_serial.firmware = FakeFirmware(log_noise=True)
    hw = SerialHardware(make_port_info(), timeout=0.05)
    lines = hw.serial_transaction(">06")
    assert [line for line in lines if line] == ["<06|FW_REV:01", "PROTOCOL_VERSION:01"]


def test_read_until_response_times_out_without_reply(fake_serial):
    fake_serial.firmware = None     # device never answers
    hw = SerialHardware(make_port_info(), timeout=0.05)
    assert hw.read_until_response(timeout=0.05) == []


def test_wait_for_re_string_default_matches_any_line(hardware):
    hardware.port.inject("hello\r\n")
    assert hardware.wait_for_re_string(timeout=0.05) is True


@pytest.mark.xfail(strict=True, reason="Known bug: _read_until_re_match() has its `if not status_re` check "
                                        "inverted, so any real regex raises UnboundLocalError")
def test_wait_for_re_string_with_regex(hardware):
    hardware.port.inject("noise\r\nREADY\r\n")
    assert hardware.wait_for_re_string(r"^READY$", timeout=0.05) is True


# --- Full stack: FanCommander -> SerialHardware -> fake serial port -> FakeFirmware ---

def test_fan_commander_end_to_end(fake_serial):
    commander = FanCommander(make_port_info())
    assert commander.port.written == []

    assert commander.get_all_fan_rpm() == fake_serial.firmware.rpm
    commander.set_fan_pwm(1, 100)
    assert fake_serial.firmware.pwm[1] == 255
    commander.set_fan_rpm(2, 1500)
    assert fake_serial.firmware.target_rpm[2] == 1500
    assert "MCU:PICO2040" in commander.get_hw_info()
    assert commander.port.written[-1] == b">05\r\n"
