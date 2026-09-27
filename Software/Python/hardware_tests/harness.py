"""Building blocks for the hardware tests: server process, API client, polling, expectations."""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import requests
from bs4 import BeautifulSoup
from ruamel.yaml import YAML

from inventory import UNSUPPORTED_MESSAGES

HW_DIR = os.path.dirname(os.path.abspath(__file__))
SOFTWARE_DIR = os.path.dirname(HW_DIR)
WEBSERVER = os.path.join(SOFTWARE_DIR, "webserver.py")
SIMULATOR = os.path.join(HW_DIR, "simulator.py")


class HarnessError(Exception):
    pass


# ---------------------------------------------------------------- polling

def wait_until(condition, timeout, interval=0.5, message="condition not met"):
    """Call `condition()` until it returns something truthy; return that value.

    Raises AssertionError with the last value seen if `timeout` seconds pass first.
    """
    deadline = time.monotonic() + timeout
    last = None
    while True:
        last = condition()
        if last:
            return last
        if time.monotonic() >= deadline:
            raise AssertionError(f"{message} (after {timeout}s, last value: {last!r})")
        time.sleep(interval)


# ---------------------------------------------------------------- API client

class ApiClient:
    """Thin wrapper around `requests` for the OpenFAN REST API."""

    def __init__(self, base_url, timeout=10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.log = []           # (method, path, status_code, json_or_text) of every call, for debugging

    def http(self, path, method="GET", data=None):
        """Raw `requests.Response` (no status checks)."""
        response = self.session.request(method, self.base_url + path, data=data, timeout=self.timeout)
        body = response.text
        try:
            body = response.json()
        except ValueError:
            pass
        self.log.append((method, path, response.status_code, body))
        return response

    def raw(self, path, method="GET", data=None):
        """Parsed JSON envelope ({status, message, data}); asserts HTTP 200 + JSON."""
        response = self.http(path, method=method, data=data)
        assert response.status_code == 200, f"{method} {path} -> HTTP {response.status_code}: {response.text[:300]}"
        try:
            reply = response.json()
        except ValueError as error:
            raise AssertionError(f"{method} {path} did not return JSON: {response.text[:300]}") from error
        assert set(reply) >= {"status", "message", "data"}, f"{method} {path}: unexpected envelope {reply}"
        return reply

    def get(self, path):
        """`data` of a successful call; asserts `status == ok`."""
        reply = self.raw(path)
        assert reply["status"] == "ok", f"GET {path} failed: {reply}"
        return reply["data"]

    def post(self, path, fields):
        reply = self.raw(path, method="POST", data=fields)
        assert reply["status"] == "ok", f"POST {path} failed: {reply}"
        return reply["data"]

    def html(self, path="/"):
        response = self.http(path)
        assert response.status_code == 200, f"GET {path} -> HTTP {response.status_code}"
        return BeautifulSoup(response.text, "html.parser")

    # -- convenience --
    def fan_rpm(self, fan):
        return int(self.get("/api/v0/fan/status")[str(fan)])

    def all_fan_rpm(self):
        return {int(k): int(v) for k, v in self.get("/api/v0/fan/status").items()}

    def is_up(self):
        try:
            return self.http("/api/v0/info").status_code == 200
        except requests.RequestException:
            return False


def assert_error(reply, contains=""):
    assert reply["status"] == "error", f"expected an error reply, got: {reply}"
    assert contains in reply["message"], f"expected error containing {contains!r}, got: {reply['message']!r}"
    return reply


# ---------------------------------------------------------------- expectations

class Expect:
    """Per-test helper. `unsupported` is set when the test needs a feature the device does not
    have and the run uses `--scope all`: the test must then verify the documented error instead."""

    def __init__(self, feature, device_name):
        self.feature = feature
        self.device_name = device_name

    @property
    def unsupported(self):
        return self.feature is not None

    def unsupported_error(self, reply):
        """Assert `reply` is the documented "not supported" error for this feature."""
        assert self.unsupported, "unsupported_error() called but the device supports this feature"
        if reply.get("status") == "ok":
            raise AssertionError(f"inventory says `{self.device_name}` does not support `{self.feature}`, "
                                 f"but the API accepted the call: {reply}. Update devices.yaml or fix the API.")
        return assert_error(reply, UNSUPPORTED_MESSAGES.get(self.feature, ""))


# ---------------------------------------------------------------- server process

def port_is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if os.name != "nt":
            # Same as Tornado: ignore connections of a previous run still in TIME_WAIT
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def load_yaml(path):
    with open(path, "r", encoding="utf8") as file:
        return YAML(typ="safe", pure=True).load(file) or {}


def write_yaml(path, data):
    with open(path, "w", encoding="utf8") as file:
        YAML().dump(data, file)


class ServerProcess:
    """Runs the OpenFAN web server (or the simulator) as a subprocess.

    The server always gets a *copy* of the config file in a temp directory, because tests
    change aliases and profiles and the server writes those back to its config file.
    """

    def __init__(self, name, server_port, log_path, base_config=None, serial_port=None,
                 simulator_args=None, startup_timeout=45):
        self.name = name
        self.server_port = server_port
        self.log_path = log_path
        self.base_config = base_config
        self.serial_port = serial_port
        self.simulator_args = simulator_args
        self.startup_timeout = startup_timeout
        self.process = None
        self._log_file = None
        self.workdir = tempfile.mkdtemp(prefix=f"openfan-{name}-")
        self.config_path = os.path.join(self.workdir, "config.yaml")

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.server_port}"

    def _write_config(self):
        config = load_yaml(self.base_config) if self.base_config else {}
        config.setdefault("server", {})
        config["server"]["port"] = self.server_port
        config["server"].setdefault("hostname", "localhost")
        config["server"].setdefault("communication_timeout", 1)
        config.setdefault("hardware", {})
        config["hardware"]["port"] = self.serial_port or ""
        config["hardware"].setdefault("communication_timeout", 1)
        write_yaml(self.config_path, config)

    def start(self):
        if not port_is_free(self.server_port):
            raise HarnessError(f"TCP port {self.server_port} is already in use. Is another OpenFAN server "
                               f"running? Stop it, change `server_port`, or test it with --base-url.")
        self._write_config()
        env = dict(os.environ, OPENFANCONFIG=self.config_path, PYTHONUNBUFFERED="1")
        env.pop("OPENFANCOMPORT", None)
        if self.simulator_args is not None:
            cmd = [sys.executable, SIMULATOR, "--config", self.config_path, *self.simulator_args]
        else:
            cmd = [sys.executable, WEBSERVER, "--logging", "debug"]
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        self._log_file = open(self.log_path, "w", encoding="utf8")     # pylint: disable=consider-using-with
        self._log_file.write(f"$ {' '.join(cmd)}\n# OPENFANCONFIG={self.config_path}\n")
        self._log_file.flush()
        # cwd=SOFTWARE_DIR: webserver.py finds its HTML templates relative to the working directory
        self.process = subprocess.Popen(cmd, cwd=SOFTWARE_DIR, env=env,      # pylint: disable=consider-using-with
                                        stdout=self._log_file, stderr=subprocess.STDOUT)
        client = ApiClient(self.base_url, timeout=5)
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise HarnessError(f"OpenFAN server for `{self.name}` exited during start-up "
                                   f"(code {self.process.returncode}).\n{self.log_tail()}")
            if client.is_up():
                return self
            time.sleep(0.5)
        self.stop()
        raise HarnessError(f"OpenFAN server for `{self.name}` did not answer on {self.base_url} within "
                           f"{self.startup_timeout}s.\n{self.log_tail()}")

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(5)
        if self._log_file:
            self._log_file.close()
            self._log_file = None
        shutil.rmtree(self.workdir, ignore_errors=True)

    def log_tail(self, lines=40):
        try:
            with open(self.log_path, "r", encoding="utf8", errors="replace") as file:
                content = file.readlines()[-lines:]
            return f"--- last {len(content)} lines of {self.log_path} ---\n" + "".join(content)
        except OSError:
            return f"(no server log at {self.log_path})"
