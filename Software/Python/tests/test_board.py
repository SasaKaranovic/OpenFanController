"""Tests for `OpenFAN_Board`: detecting board type and capabilities from the HW info string."""
import pytest

from board import OpenFAN_Board
from fakes import FakeFanCommander, FakeFirmware, HW_INFO_CONTROLLER, HW_INFO_MICRO, HW_INFO_XL


def hw_string(lines):
    """HW info string exactly as `FanCommander.get_hw_info()` returns it."""
    return FakeFanCommander(FakeFirmware(hw_info=lines)).get_hw_info()


@pytest.mark.parametrize("hw_lines, expected", [
    (HW_INFO_CONTROLLER, {
        'name': 'OpenFAN Controller', 'hw_rev': '3', 'fan_count': 10, 'sensor_count': 0,
        'has_sensors': False, 'has_profiles': True, 'fw_support_rpm': True, 'fw_support_pwm': True,
    }),
    (HW_INFO_XL, {
        'name': 'OpenFAN XL', 'hw_rev': '4', 'fan_count': 10, 'sensor_count': 4,
        'has_sensors': True, 'has_profiles': False, 'fw_support_rpm': False, 'fw_support_pwm': True,
    }),
    (HW_INFO_MICRO, {
        'name': 'OpenFAN Micro', 'hw_rev': '4', 'fan_count': 1, 'sensor_count': 0,
        'has_sensors': False, 'has_profiles': False, 'fw_support_rpm': False, 'fw_support_pwm': True,
    }),
], ids=["controller", "xl", "micro"])
def test_board_capabilities(hw_lines, expected):
    board = OpenFAN_Board(hw_string(hw_lines), "FW_REV:01")
    capabilities = board.get_board_capabilities()
    for key, value in expected.items():
        assert capabilities[key] == value, key

    # Accessors must agree with the capabilities dictionary
    assert board.get_name() == expected['name']
    assert board.get_hw_rev() == expected['hw_rev']
    assert board.get_fan_count() == expected['fan_count']
    assert board.get_sensor_count() == expected['sensor_count']
    assert board.board_has_sensors() == expected['has_sensors']
    assert board.board_has_profiles() == expected['has_profiles']
    assert board.fw_support_rpm() == expected['fw_support_rpm']
    assert board.fw_support_pwm() == expected['fw_support_pwm']


def test_unknown_board_is_marked_unsupported():
    board = OpenFAN_Board("<05| HW_REV:99 MCU:SOMETHING_ELSE", "FW_REV:01")
    assert board.get_name() == 'unsupported'
    assert board.get_fan_count() == 0
    assert not board.board_has_sensors()
    assert not board.board_has_profiles()


def test_raw_strings_are_kept():
    board = OpenFAN_Board("MCU:PICO2040", "FW_REV:01")
    capabilities = board.get_board_capabilities()
    assert capabilities['hw_str'] == "MCU:PICO2040"
    assert capabilities['fw_str'] == "FW_REV:01"
