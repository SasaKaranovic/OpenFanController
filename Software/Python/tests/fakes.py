"""Test doubles that let the OpenFAN software run without real hardware.

* `FakeFirmware`   - emulates the serial protocol implemented by the firmware in
                     `Firmware/src/Application/host_communication.c`.
* `FakeFanCommander` - a `FanCommander` whose serial link is replaced by `FakeFirmware`
                     (fast, records every payload that was sent).
* `FakeSerialPort` - drop-in replacement for `serial.Serial`, used to exercise the real
                     `SerialHardware` read/write code path end to end.
"""
from serial.tools.list_ports_common import ListPortInfo

from FanCommander import FanCommander

# Hardware info strings, as sent by each board in response to CMD_HW_INFO (0x05)
HW_INFO_CONTROLLER = [
    "HW_REV:03",
    "MCU:PICO2040",
    "USB:NATIVE",
    "FAN_CHANNELS_TOTAL:10",
    "FAN_CHANNELS_ARCH:5+5",
    "FAN_CHANNELS_DRIVER:EMC2305",
]
HW_INFO_XL = [
    "HW_REV:04",
    "MCU:PICO235",
    "USB:NATIVE",
    "FAN_CHANNELS_TOTAL:10",
]
HW_INFO_MICRO = [
    "HW_REV:04",
    "MCU:OpenFAN_Micro_ESP32C3",
    "FAN_CHANNELS_TOTAL:1",
]
FW_INFO = [
    "FW_REV:01",
    "PROTOCOL_VERSION:01",
]


class FakeFirmware:
    """Emulates the OpenFAN firmware host protocol.

    Requests look like `>CCDDDD...` (CC = command, DD = data bytes, all hex).
    Responses look like `<CC|payload` followed by CRLF.
    """

    def __init__(self, hw_info=None, fw_info=None, fan_count=10, temperatures=None, log_noise=False):
        self.hw_info = list(HW_INFO_CONTROLLER if hw_info is None else hw_info)
        self.fw_info = list(FW_INFO if fw_info is None else fw_info)
        self.fan_count = fan_count
        self.rpm = {i: 1000 + i * 100 for i in range(fan_count)}   # measured RPM per fan
        self.pwm = {i: 0 for i in range(fan_count)}                  # last PWM (0-255) per fan
        self.target_rpm = {i: 0 for i in range(fan_count)}
        # Temperatures in 0.1 degC units (signed 16-bit)
        self.temperatures = dict(temperatures) if temperatures is not None else {0: 250, 1: -100, 2: 0, 3: 1234}
        self.log_noise = log_noise
        self.requests = []

    @staticmethod
    def _u16(value):
        return f"{value & 0xFFFF:04X}"

    def respond(self, payload):
        """Return the raw text the firmware would send back for `payload`."""
        payload = payload.strip()
        self.requests.append(payload)
        assert payload.startswith('>'), f"Request must start with '>': {payload!r}"
        cmd = int(payload[1:3], 16)
        data = [int(payload[i:i + 2], 16) for i in range(3, len(payload), 2)]

        body = ""
        if cmd == 0x00:     # all fan RPM
            body = "".join(f"{i:02X}:{self._u16(self.rpm[i])};" for i in range(self.fan_count))
        elif cmd == 0x01:   # single fan RPM
            body = f"{data[0]:02X}:{self._u16(self.rpm.get(data[0], 0))}"
        elif cmd == 0x02:   # set fan PWM
            self.pwm[data[0]] = data[1]
            body = f"{data[0]:02X}:{data[1]:02X}"
        elif cmd == 0x03:   # set all PWM
            for i in self.pwm:
                self.pwm[i] = data[0]
            body = f"{data[0]:02X}"
        elif cmd == 0x04:   # set fan RPM
            self.target_rpm[data[0]] = (data[1] << 8) | data[2]
            body = f"{data[0]:02X}:{data[1]:02X}{data[2]:02X}"
        elif cmd == 0x05:   # HW info
            body = "\r\n" + "".join(f"{line}\r\n" for line in self.hw_info)
        elif cmd == 0x06:   # FW info
            body = "".join(f"{line}\r\n" for line in self.fw_info)
        elif cmd == 0x0B:   # single temperature
            body = f"{data[0]:02X}:{self._u16(self.temperatures.get(data[0], 0))}"
        elif cmd == 0x0C:   # all temperatures
            body = "".join(f"{i:02X}:{self._u16(v)};" for i, v in sorted(self.temperatures.items()))

        noise = "[0000001234][D][HOST] debug log line\r\n" if self.log_noise else ""
        return f"{noise}<{cmd:02X}|{body}\r\n"

    def respond_lines(self, payload):
        """Response split into stripped, non-empty lines (what `read_until_response` returns)."""
        lines = [line.strip() for line in self.respond(payload).splitlines()]
        return [line for line in lines if line]


class FakeFanCommander(FanCommander):
    """`FanCommander` talking to `FakeFirmware` instead of a serial port."""

    def __init__(self, firmware=None):     # pylint: disable=super-init-not-called
        # Deliberately skip SerialHardware.__init__ (it would open a serial port)
        self.firmware = firmware or FakeFirmware()
        self.sent = []
        # Normally created by FanCommander.__init__, which is skipped here
        self.fan_rpm = {}
        self.temperature_sensors = {}

    def serial_transaction(self, payload, ignore_response=False):
        self.sent.append(payload)
        lines = self.firmware.respond_lines(payload)
        # Mimic SerialHardware.read_until_response(): drop everything before the '<' line
        for i, line in enumerate(lines):
            if line.startswith('<'):
                return lines[i:]
        return lines


def make_port_info(device="/dev/ttyFAKE0", vid=0x2E8A, pid=0x000A, description="OpenFAN Controller"):
    port = ListPortInfo(device, skip_link_detection=True)
    port.vid = vid
    port.pid = pid
    port.description = description
    port.product = description
    port.serial_number = "E6614C311B2F4B28"
    return port


class FakeSerialPort:
    """Minimal stand-in for `serial.Serial` backed by `FakeFirmware`.

    Set `FakeSerialPort.firmware` (class attribute) before the port is constructed;
    `None` means the device never answers.
    """
    firmware = None
    instances = []

    def __init__(self, port=None, **kwargs):
        self.port = port
        self.kwargs = kwargs
        self._open = True        # pyserial opens the port in the constructor when `port` is given
        self.rx = b""
        self.written = []
        self.input_resets = 0
        FakeSerialPort.instances.append(self)

    # -- pyserial API used by SerialHardware --
    def open(self):
        self._open = True

    def close(self):
        self._open = False

    def isOpen(self):       # pylint: disable=invalid-name
        return self._open

    is_open = property(isOpen)

    @property
    def in_waiting(self):
        return len(self.rx)

    def reset_input_buffer(self):
        self.input_resets += 1
        self.rx = b""

    def reset_output_buffer(self):
        pass

    def write(self, data):
        self.written.append(data)
        if FakeSerialPort.firmware is not None:
            self.rx += FakeSerialPort.firmware.respond(data.decode()).encode()
        return len(data)

    def inject(self, text):
        """Queue bytes as if the device had sent them unprompted."""
        self.rx += text.encode()

    def readline(self):
        if not self.rx:
            return b""
        idx = self.rx.find(b"\n")
        if idx < 0:
            line, self.rx = self.rx, b""
        else:
            line, self.rx = self.rx[:idx + 1], self.rx[idx + 1:]
        return line

    def read_all(self):
        data, self.rx = self.rx, b""
        return data
