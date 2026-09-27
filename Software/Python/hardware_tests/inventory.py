"""Hardware inventory (devices.yaml): board models, physical/simulated devices, port lookup.

Also usable from the command line:
    python hardware_tests/inventory.py list                 # devices + detected OpenFAN serial ports
    python hardware_tests/inventory.py matrix [--device X]  # JSON list for a GitHub Actions matrix
"""
import argparse
import copy
import json
import os
import sys

from ruamel.yaml import YAML

HW_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INVENTORY = os.path.join(HW_DIR, "devices.yaml")

FEATURES = ("pwm", "rpm_control", "profiles", "temperature", "aliases")
SUITES = ("smoke", "html", "fan_control", "profiles", "aliases", "sensors")

# Error message the API returns when a board does not support a feature
UNSUPPORTED_MESSAGES = {
    "rpm_control": "does not yet support RPM control",
    "profiles": "does not support fan profiles",
    "temperature": "does not support temperature sensors",
}

OPENFAN_USB_VID = 0x2E8A


class InventoryError(Exception):
    pass


def features_from_capabilities(caps):
    """Features a running server reports, derived from /api/v0/info `capabilities`."""
    features = {"aliases"}
    if caps.get("fw_support_pwm"):
        features.add("pwm")
    if caps.get("fw_support_rpm"):
        features.add("rpm_control")
    if caps.get("has_profiles"):
        features.add("profiles")
    if caps.get("has_sensors"):
        features.add("temperature")
    return features


def _merge(base, override):
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


class Board:
    def __init__(self, key, data):
        self.key = key
        self.name = data["name"]
        self.hw_rev = str(data["hw_rev"])
        self.fan_count = int(data["fan_count"])
        self.sensor_count = int(data.get("sensor_count", 0))
        self.features = set(data.get("features", []))
        unknown = self.features - set(FEATURES)
        if unknown:
            raise InventoryError(f"board `{key}`: unknown feature(s) {sorted(unknown)}; valid: {FEATURES}")

    @classmethod
    def from_capabilities(cls, caps):
        return cls("reported", {
            "name": caps.get("name"), "hw_rev": caps.get("hw_rev"),
            "fan_count": caps.get("fan_count", 0), "sensor_count": caps.get("sensor_count", 0),
            "features": sorted(features_from_capabilities(caps)),
        })

    def differences(self, caps):
        """List of human readable mismatches between this declaration and reported capabilities."""
        reported = Board.from_capabilities(caps)
        diffs = []
        for attr in ("name", "hw_rev", "fan_count", "sensor_count"):
            if getattr(self, attr) != getattr(reported, attr):
                diffs.append(f"{attr}: declared {getattr(self, attr)!r}, reported {getattr(reported, attr)!r}")
        if self.features != reported.features:
            diffs.append(f"features: declared {sorted(self.features)}, reported {sorted(reported.features)}")
        return diffs


class Device:
    def __init__(self, name, data, board, defaults):
        self.name = name
        self.board = board
        self.enabled = bool(data.get("enabled", True))
        self.simulated = bool(data.get("simulated", False))
        self.port = data.get("port")
        self.usb_serial = data.get("usb_serial")
        self.server_port = data.get("server_port")
        self.config = data.get("config")                 # optional base config.yaml for the server
        self.fans_connected = sorted(int(i) for i in data.get("fans_connected", []))
        self.sensors_connected = sorted(int(i) for i in data.get("sensors_connected", []))
        self.suites = list(data.get("suites") or SUITES)
        self.known_failures = dict(data.get("known_failures") or {})
        settings = _merge(defaults, {k: data[k] for k in ("safe_pwm", "timing", "rpm") if k in data})
        self.safe_pwm = int(settings.get("safe_pwm", 100))
        self.timing = settings.get("timing", {})
        self.rpm = settings.get("rpm", {})
        self._validate()

    def _validate(self):
        bad_suites = set(self.suites) - set(SUITES)
        if bad_suites:
            raise InventoryError(f"device `{self.name}`: unknown suite(s) {sorted(bad_suites)}; valid: {SUITES}")
        for kind, channels, limit in (("fans_connected", self.fans_connected, self.board.fan_count),
                                      ("sensors_connected", self.sensors_connected, self.board.sensor_count)):
            out_of_range = [c for c in channels if c < 0 or c >= limit]
            if out_of_range:
                raise InventoryError(f"device `{self.name}`: {kind} {out_of_range} out of range for "
                                     f"{self.board.name} (0..{limit - 1})")

    @property
    def features(self):
        return self.board.features

    def has(self, feature):
        return feature in self.board.features

    def resolve_port(self):
        """Serial port for a physical device: `port` as given, or looked up by `usb_serial`."""
        if self.port:
            return self.port
        if not self.usb_serial or self.usb_serial == "CHANGE_ME":
            raise InventoryError(f"device `{self.name}`: set `port` or `usb_serial` in the inventory")
        for port in list_serial_ports():
            if (port.serial_number or "").upper() == str(self.usb_serial).upper():
                return port.device
        raise InventoryError(f"device `{self.name}`: no serial port with USB serial `{self.usb_serial}` found. "
                             f"Is it plugged in? (see --list-devices)")

    def describe(self):
        kind = "simulated" if self.simulated else (self.port or f"usb_serial={self.usb_serial}")
        return f"{self.name} ({self.board.name}, {kind})"


class AdHocDevice(Device):
    """A device not in the inventory: profile taken from what the server reports."""

    def __init__(self, caps, defaults, fans_connected=(), sensors_connected=()):
        board = Board.from_capabilities(caps)
        super().__init__("adhoc", {"fans_connected": list(fans_connected),
                                   "sensors_connected": list(sensors_connected)}, board, defaults)


class Inventory:
    def __init__(self, path=DEFAULT_INVENTORY):
        self.path = path
        if not os.path.exists(path):
            raise InventoryError(f"inventory file not found: {path}")
        with open(path, "r", encoding="utf8") as file:
            data = YAML(typ="safe", pure=True).load(file) or {}
        self.defaults = data.get("defaults", {}) or {}
        self.boards = {key: Board(key, value) for key, value in (data.get("boards") or {}).items()}
        self.devices = {}
        for name, value in (data.get("devices") or {}).items():
            board_key = value.get("board")
            if board_key not in self.boards:
                raise InventoryError(f"device `{name}`: unknown board `{board_key}` (known: {sorted(self.boards)})")
            self.devices[name] = Device(name, value, self.boards[board_key], self.defaults)

    def get(self, name):
        if name not in self.devices:
            raise InventoryError(f"unknown device `{name}`; known devices: {', '.join(sorted(self.devices))}")
        return self.devices[name]


def list_serial_ports():
    try:
        from serial.tools.list_ports import comports     # pylint: disable=import-outside-toplevel
    except ImportError:
        return []
    return list(comports())


def describe_inventory(inventory):
    lines = [f"Inventory: {inventory.path}", ""]
    lines.append(f"{'DEVICE':<16} {'BOARD':<20} {'STATE':<10} {'PORT / SERIAL':<28} SUITES")
    for device in inventory.devices.values():
        state = "simulated" if device.simulated else ("enabled" if device.enabled else "disabled")
        where = "-" if device.simulated else (device.port or f"sn:{device.usb_serial}")
        lines.append(f"{device.name:<16} {device.board.name:<20} {state:<10} {where:<28} {','.join(device.suites)}")
    lines += ["", "Detected OpenFAN serial ports:"]
    ports = [p for p in list_serial_ports() if p.vid == OPENFAN_USB_VID]
    if not ports:
        lines.append("  (none)")
    known = {str(d.usb_serial).upper(): d.name for d in inventory.devices.values() if d.usb_serial}
    for port in ports:
        owner = known.get((port.serial_number or "").upper(), "NOT IN INVENTORY")
        lines.append(f"  {port.device:<24} usb_serial={port.serial_number}  -> {owner}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--inventory", default=DEFAULT_INVENTORY)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="show devices and detected serial ports")
    matrix = sub.add_parser("matrix", help="print JSON list of device names for a CI matrix")
    matrix.add_argument("--device", default="all", help="`all` or a device name")
    matrix.add_argument("--simulated", action="store_true", help="list simulated devices instead of physical ones")
    args = parser.parse_args(argv)

    inventory = Inventory(args.inventory)
    if args.command == "list":
        print(describe_inventory(inventory))
    elif args.command == "matrix":
        if args.device not in ("all", ""):
            device = inventory.get(args.device)
            names = [device.name] if device.simulated == args.simulated else []
        else:
            names = [d.name for d in inventory.devices.values()
                     if d.simulated == args.simulated and (d.enabled or d.simulated)]
        print(json.dumps(names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
