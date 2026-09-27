"""REST API tests for `webserver.py`.

The Tornado application is created with `webserver.make_app()` around a `FakeFanCommander`
and served on a random local port, so every route is exercised over real HTTP without a
serial port. (A plain pytest fixture is used instead of `tornado.testing.AsyncHTTPTestCase`
so the tests work with any Tornado/pytest version combination.)
"""
import asyncio
import json
import threading
import urllib.error
import urllib.request
from urllib.parse import quote, urlencode

import pytest
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.testing import bind_unused_port

import webserver
from board import OpenFAN_Board
from config import ConfigReader
from fakes import FakeFanCommander, FakeFirmware, HW_INFO_CONTROLLER, HW_INFO_XL


class ApiClient:
    """Runs the OpenFAN API in a background thread and talks to it over HTTP."""

    def __init__(self, hw_info, config_path):
        self.config = ConfigReader(config_path)
        self.firmware = FakeFirmware(hw_info=hw_info)
        self.commander = FakeFanCommander(self.firmware)
        self.board = OpenFAN_Board(self.commander.get_hw_info(), self.commander.get_fw_info())
        self.commander.sent.clear()
        self.app = webserver.make_app(self.commander, self.config, self.board,
                                      debug=False, autoreload=False,
                                      template_path=webserver.WEBPAGE_ROOT)
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        assert self._ready.wait(5), "API server did not start"

    def _serve(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        self.io_loop = IOLoop.current()
        sock, self.port = bind_unused_port()
        self.server = HTTPServer(self.app)
        self.server.add_sockets([sock])
        self._ready.set()
        self.io_loop.start()
        self.server.stop()
        self.io_loop.close(all_fds=True)

    def stop(self):
        self.io_loop.add_callback(self.io_loop.stop)
        self._thread.join(5)

    # -- HTTP helpers --
    def fetch(self, path, method="GET", fields=None):
        """Return (status_code, headers, body_bytes); never raises on HTTP errors."""
        data = urlencode(fields).encode() if fields is not None else None
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.headers, error.read()

    def get_json(self, path, expected_code=200):
        code, _, body = self.fetch(path)
        assert code == expected_code, body
        return json.loads(body)

    def post_json(self, path, fields, expected_code=200):
        code, _, body = self.fetch(path, method="POST", fields=fields)
        assert code == expected_code, body
        return json.loads(body)


def assert_ok(reply):
    assert reply['status'] == 'ok', reply
    return reply


def assert_error(reply, text=''):
    assert reply['status'] == 'error', reply
    assert text in reply['message'], reply
    return reply


@pytest.fixture
def make_api(tmp_path, monkeypatch):
    monkeypatch.setattr(webserver, "get_git_short_hash", lambda: "abc1234")
    monkeypatch.setattr(webserver, "get_git_long_hash", lambda: "abc1234" + "0" * 33)
    monkeypatch.setattr(webserver, "get_git_commit_date", lambda: "20260101")
    clients = []

    def _make(hw_info=HW_INFO_CONTROLLER):
        client = ApiClient(hw_info, str(tmp_path / f"config_{len(clients)}.yaml"))
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.stop()


@pytest.fixture
def api(make_api):
    """API for the OpenFAN Controller (fan profiles and RPM control, no temperature sensors)."""
    return make_api(HW_INFO_CONTROLLER)


@pytest.fixture
def xl_api(make_api):
    """API for the OpenFAN XL (temperature sensors, no fan profiles, no RPM control)."""
    return make_api(HW_INFO_XL)


# --- General ---

def test_response_envelope_and_cors_headers(api):
    code, headers, body = api.fetch("/api/v0/fan/status")
    assert code == 200
    assert headers["Access-Control-Allow-Origin"] == "*"
    assert set(json.loads(body)) == {'status', 'message', 'data'}


def test_unknown_api_route_returns_404(api):
    assert api.fetch("/api/v0/does/not/exist")[0] == 404


def test_fan_index_outside_route_range_returns_404(api):
    assert api.fetch("/api/v0/fan/10/pwm?value=50")[0] == 404


def test_info(api):
    data = assert_ok(api.get_json("/api/v0/info"))['data']
    assert "MCU:PICO2040" in data['hardware']
    assert "FW_REV:01" in data['firmware']
    assert data['software'] == "Version: v20260101 Build: abc1234"


def test_index_page_renders(api):
    code, _, body = api.fetch("/")
    assert code == 200
    assert b"<html" in body.lower()


# --- Fan control ---

def test_fan_status(api):
    data = assert_ok(api.get_json("/api/v0/fan/status"))['data']
    assert data == {str(k): v for k, v in api.firmware.rpm.items()}


@pytest.mark.parametrize("route", ["pwm", "set"], ids=["pwm", "deprecated-set"])
def test_set_pwm(api, route):
    assert_ok(api.get_json(f"/api/v0/fan/3/{route}?value=50"))
    assert api.commander.sent == [">02037F"]
    assert api.firmware.pwm[3] == 127


def test_set_pwm_accepts_float(api):
    assert_ok(api.get_json("/api/v0/fan/0/pwm?value=50.7"))
    assert api.commander.sent == [">02007F"]


@pytest.mark.parametrize("value, expected", [("150", ">0201FF"), ("-5", ">020100"), ("100", ">0201FF")])
def test_set_pwm_clamps_to_0_100(api, value, expected):
    assert_ok(api.get_json(f"/api/v0/fan/1/pwm?value={value}"))
    assert api.commander.sent == [expected]


def test_set_all_pwm(api):
    assert_ok(api.get_json("/api/v0/fan/all/set?value=100"))
    assert api.commander.sent == [">03FF"]
    assert set(api.firmware.pwm.values()) == {255}


def test_set_all_pwm_clamps(api):
    api.get_json("/api/v0/fan/all/set?value=500")
    assert api.commander.sent == [">03FF"]


def test_set_rpm(api):
    assert_ok(api.get_json("/api/v0/fan/0/rpm?value=1200"))
    assert api.commander.sent == [">040004B0"]
    assert api.firmware.target_rpm[0] == 1200


@pytest.mark.parametrize("value, expected", [("20000", ">04003E80"), ("300", ">04000000"), ("480", ">040001E0")])
def test_set_rpm_clamps(api, value, expected):
    api.get_json(f"/api/v0/fan/0/rpm?value={value}")
    assert api.commander.sent == [expected]


@pytest.mark.parametrize("route", ["pwm", "rpm"])
def test_set_non_numeric_value_returns_json_error(api, route):
    assert_error(api.get_json(f"/api/v0/fan/0/{route}?value=abc"))


def test_controller_has_no_temperature_sensors(api):
    assert_error(api.get_json("/api/v0/sensor/temperature/all/get"), "does not support temperature")


# --- Fan profiles ---

def test_profiles_list(api):
    reply = assert_ok(api.get_json("/api/v0/profiles/list"))
    assert {p['name'] for p in reply['data']} == {'50% PWM', '100% PWM', '1000 RPM'}


def test_profiles_add(api):
    assert_ok(api.post_json("/api/v0/profiles/add",
                            {'name': 'Night', 'type': 'pwm', 'values': ';'.join(['25'] * 10)}))
    assert api.config.get_fan_profile('Night') == {'type': 'PWM', 'values': [25] * 10}


@pytest.mark.parametrize("fields, message", [
    ({'name': 'Bad', 'type': 'pwm', 'values': '10;20'}, "exactly 10 values"),
    ({'name': 'Bad', 'type': 'pwm', 'values': ';'.join(['x'] * 10)}, "integer"),
    ({'name': 'Bad', 'type': 'volts', 'values': ';'.join(['5'] * 10)}, '"pwm" or "rpm"'),
], ids=["wrong-count", "not-integer", "unknown-type"])
def test_profiles_add_validation(api, fields, message):
    assert_error(api.post_json("/api/v0/profiles/add", fields), message)
    assert api.config.get_fan_profile('Bad') is False


def test_profiles_add_without_type_returns_json_error(api):
    assert_error(api.post_json("/api/v0/profiles/add", {'name': 'Bad', 'values': ';'.join(['5'] * 10)}))


def test_profiles_set_pwm_profile_sends_every_fan(api):
    assert_ok(api.get_json(f"/api/v0/profiles/set?name={quote('50% PWM')}"))
    assert api.commander.sent == [f">02{i:02X}7F" for i in range(10)]


def test_profiles_set_rpm_profile_sends_every_fan(api):
    assert_ok(api.get_json(f"/api/v0/profiles/set?name={quote('1000 RPM')}"))
    assert api.commander.sent == [f">04{i:02X}03E8" for i in range(10)]


def test_profiles_set_unknown_profile(api):
    assert_error(api.get_json("/api/v0/profiles/set?name=Nope"), "does not exist")
    assert api.commander.sent == []


def test_profiles_remove(api):
    assert_ok(api.get_json(f"/api/v0/profiles/remove?name={quote('1000 RPM')}"))
    assert api.config.get_fan_profile('1000 RPM') is False


def test_profiles_remove_without_name(api):
    assert_error(api.get_json("/api/v0/profiles/remove"), "Name can not be empty")


# --- Fan aliases ---

def test_alias_get_all(api):
    data = assert_ok(api.get_json("/api/v0/alias/all/get"))['data']
    assert data['0'] == 'Fan #1'
    assert len(data) == 10


def test_alias_get_one(api):
    data = assert_ok(api.get_json("/api/v0/alias/4/get"))['data']
    assert data == {'fan_id': 4, 'alias': 'Fan #5'}


def test_alias_set(api):
    assert_ok(api.get_json(f"/api/v0/alias/4/set?value={quote('Rear Exhaust #2')}"))
    assert api.config.get_fan_alias(4) == 'Rear Exhaust #2'


@pytest.mark.parametrize("bad_alias", ["<script>", "a/b", "semi;colon"])
def test_alias_set_rejects_invalid_characters(api, bad_alias):
    reply = api.get_json(f"/api/v0/alias/4/set?{urlencode({'value': bad_alias})}")
    assert_error(reply, "can only contain")
    assert api.config.get_fan_alias(4) == 'Fan #5'


# --- OpenFAN XL (board capability gating) ---

def test_xl_temperature_all(xl_api):
    data = assert_ok(xl_api.get_json("/api/v0/sensor/temperature/all/get"))['data']
    assert data == {'0': 25.0, '1': -10.0, '2': 0.0, '3': 123.4}


def test_xl_temperature_single(xl_api):
    reply = assert_ok(xl_api.get_json("/api/v0/sensor/temperature/0/get"))
    assert reply['data'] == 25.0
    assert xl_api.commander.sent == [">0B00"]


def test_xl_temperature_invalid_index(xl_api):
    assert_error(xl_api.get_json("/api/v0/sensor/temperature/7/get"), "Invalid temperature index")


def test_xl_temperature_single_uses_requested_index(xl_api):
    xl_api.get_json("/api/v0/sensor/temperature/2/get")
    assert xl_api.commander.sent == [">0B02"]


def test_xl_profiles_not_supported(xl_api):
    assert_error(xl_api.get_json("/api/v0/profiles/list"), "does not support fan profiles")


def test_xl_rpm_control_not_supported(xl_api):
    assert_error(xl_api.get_json("/api/v0/fan/0/rpm?value=1000"), "does not yet support RPM control")
    assert xl_api.commander.sent == []


def test_xl_pwm_still_supported(xl_api):
    assert_ok(xl_api.get_json("/api/v0/fan/0/pwm?value=100"))


# --- Service start-up (FAN_API_Service picks the serial port and builds the app) ---

class _RecordingCommander(FakeFanCommander):
    """Stands in for the FanCommander class inside webserver.py and records the port it got."""
    opened_ports = []

    def __init__(self, port_info):
        super().__init__(FakeFirmware())
        _RecordingCommander.opened_ports.append(port_info)

    @classmethod
    def find_fan_controller(cls):
        return None


@pytest.fixture
def service_env(tmp_path, monkeypatch):
    _RecordingCommander.opened_ports = []
    monkeypatch.setattr(webserver, "FanCommander", _RecordingCommander)
    monkeypatch.delenv("OPENFANCOMPORT", raising=False)
    config_path = tmp_path / "config.yaml"
    monkeypatch.setenv("OPENFANCONFIG", str(config_path))
    return config_path


def _write_hardware_port(config_path, port):
    config_path.write_text(f"hardware:\n  port: {port}\n  communication_timeout: 1\n", encoding="utf8")


def test_service_uses_port_from_config(service_env):
    _write_hardware_port(service_env, "/dev/ttyCONFIG")
    service = webserver.FAN_API_Service()
    assert _RecordingCommander.opened_ports == ["/dev/ttyCONFIG"]
    assert service.board.get_name() == "OpenFAN Controller"
    assert len(service.handlers) == len(webserver.build_handlers(None, None, None))


def test_service_uses_port_from_environment(service_env, monkeypatch):
    _write_hardware_port(service_env, "")
    monkeypatch.setenv("OPENFANCOMPORT", "/dev/ttyENV")
    webserver.FAN_API_Service()
    assert _RecordingCommander.opened_ports == ["/dev/ttyENV"]


def test_service_without_port_or_device_fails(service_env):
    _write_hardware_port(service_env, "")
    with pytest.raises(Exception, match="Could not find Fan controller"):
        webserver.FAN_API_Service()
