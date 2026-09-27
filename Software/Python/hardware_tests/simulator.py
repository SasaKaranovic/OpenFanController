"""Simulated OpenFAN device: the real web server code, with a simulated controller behind it.

Runs `webserver.make_app()` with a `FakeFanCommander` whose firmware models simple fan
physics (connected fans spin proportionally to PWM or follow an RPM target, empty channels
read 0 RPM). Lets you run the hardware test suite without any hardware:

    run_tests.bat hardware --device sim-xl

Started automatically by the hardware tests for devices marked `simulated: true`.
"""
import argparse
import asyncio
import os
import random
import sys

HW_DIR = os.path.dirname(os.path.abspath(__file__))
SOFTWARE_DIR = os.path.dirname(HW_DIR)
for _path in (SOFTWARE_DIR, os.path.join(SOFTWARE_DIR, "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# pylint: disable=wrong-import-position
from tornado.ioloop import IOLoop                                            # noqa: E402

import webserver                                                            # noqa: E402
from board import OpenFAN_Board                                             # noqa: E402
from config import ConfigReader                                             # noqa: E402
from fakes import (FakeFanCommander, FakeFirmware, HW_INFO_CONTROLLER,     # noqa: E402
                   HW_INFO_MICRO, HW_INFO_XL)

HW_INFO_BY_BOARD = {
    "OpenFAN Controller": (HW_INFO_CONTROLLER, 10),
    "OpenFAN XL": (HW_INFO_XL, 10),
    "OpenFAN Micro": (HW_INFO_MICRO, 1),
}


class SimulatedFirmware(FakeFirmware):
    """FakeFirmware plus a crude fan model."""

    def __init__(self, hw_info, fan_count, fans_connected, sensors_connected, max_rpm=2000):
        temperatures = {i: (215 + 15 * i if i in sensors_connected else 0) for i in range(4)}
        super().__init__(hw_info=hw_info, fan_count=fan_count, temperatures=temperatures)
        self.fans_connected = set(fans_connected)
        self.max_rpm = max_rpm
        self.mode = {i: "pwm" for i in range(fan_count)}
        self.pwm = {i: 255 for i in range(fan_count)}          # boots at 100%
        self._update_rpm()

    def _update_rpm(self):
        for i in range(self.fan_count):
            if i not in self.fans_connected:
                self.rpm[i] = 0
            elif self.mode[i] == "rpm":
                self.rpm[i] = int(self.target_rpm[i] * random.uniform(0.98, 1.02)) if self.target_rpm[i] else 0
            else:
                self.rpm[i] = int(self.pwm[i] / 255 * self.max_rpm * random.uniform(0.98, 1.02))

    def respond(self, payload):
        cmd = int(payload.strip()[1:3], 16)
        if cmd == 0x00:
            self._update_rpm()              # fresh reading with a bit of noise
        response = super().respond(payload)
        if cmd in (0x02, 0x03):
            fans = range(self.fan_count) if cmd == 0x03 else [int(payload.strip()[3:5], 16)]
            for i in fans:
                self.mode[i] = "pwm"
        elif cmd == 0x04:
            self.mode[int(payload.strip()[3:5], 16)] = "rpm"
        self._update_rpm()
        return response


def _channels(text):
    return [int(x) for x in text.split(",") if x.strip() != ""] if text else []


def main(argv=None):
    parser = argparse.ArgumentParser(description="Simulated OpenFAN device + web server")
    parser.add_argument("--config", required=True, help="config.yaml to use (server port is read from it)")
    parser.add_argument("--board", required=True, choices=sorted(HW_INFO_BY_BOARD))
    parser.add_argument("--fans-connected", default="", help="comma separated fan channels with a fan")
    parser.add_argument("--sensors-connected", default="", help="comma separated sensor channels")
    args = parser.parse_args(argv)

    hw_info, fan_count = HW_INFO_BY_BOARD[args.board]
    firmware = SimulatedFirmware(hw_info, fan_count, _channels(args.fans_connected), _channels(args.sensors_connected))
    commander = FakeFanCommander(firmware)
    config = ConfigReader(os.path.abspath(args.config))
    board = OpenFAN_Board(commander.get_hw_info(), commander.get_fw_info())
    app = webserver.make_app(commander, config, board, debug=False, autoreload=False,
                             template_path=webserver.WEBPAGE_ROOT)
    port = int(config.get_server_config().get("port", 3000))

    asyncio.set_event_loop(asyncio.new_event_loop())
    app.listen(port, address="127.0.0.1")
    print(f"Simulated {args.board} listening on http://127.0.0.1:{port}", flush=True)
    IOLoop.current().start()


if __name__ == "__main__":
    main()
