"""Shared pytest fixtures for the OpenFAN Python software tests.

None of the tests need real hardware: the serial link is replaced by the fakes in
`tests/fakes.py`, and config files are written to pytest's temporary directory so the
real `config.yaml` is never touched.
"""
import os
import sys
import pytest
import FanCommander as fan_commander_module

# Make the application modules (which use flat imports such as `from base_logger import logger`)
# importable no matter where pytest is started from. `pytest.ini` does the same via `pythonpath`.
SOFTWARE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
for _path in (SOFTWARE_DIR, TESTS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# pylint: disable=wrong-import-position
from config import ConfigReader                 # noqa: E402
from fakes import FakeFirmware, FakeFanCommander, FakeSerialPort   # noqa: E402

@pytest.fixture(autouse=True)
def isolate_shared_state():
    """Reset class-level mutable state that would otherwise leak between tests."""
    fan_commander_module.FanCommander.fan_rpm = {}
    fan_commander_module.FanCommander.temperature_sensors = {}
    FakeSerialPort.firmware = None
    FakeSerialPort.instances = []
    yield

@pytest.fixture(autouse=True)
def reset_fake_serial_port():
  """FakeSerialPort is configured through class attributes; reset them for every test."""
  FakeSerialPort.firmware = None
  FakeSerialPort.instances = []
  yield

@pytest.fixture
def firmware():
    return FakeFirmware()


@pytest.fixture
def commander(firmware):
    return FakeFanCommander(firmware)


@pytest.fixture
def config_path(tmp_path):
    """Path to a not-yet-existing config file inside the test's temp directory."""
    return str(tmp_path / "config.yaml")


@pytest.fixture
def config(config_path):
    return ConfigReader(config_path)
