from serial.tools.list_ports import comports
from serial_driver import SerialHardware
from base_logger import logger


class FanCommander(SerialHardware):
    fan_rpm = {}
    temperature_sensors = {}

    def __init__(self, port_info):
        super(FanCommander, self).__init__(port_info, timeout=2)

    def _sendCommand(self, cmd, data=None, ret_entire_response=False):
        if isinstance(data, list):
            data_str = ''.join('{:02X}'.format(x) for x in data)
        elif isinstance(data, int):
            data_str = f"{data:02X}"
        elif data is None:
            data_str = ""
        else:
            data_str = ""

        payload = f">{cmd:02X}{data_str}"

        logger.debug(f"CMD:{cmd} Data: {data}")
        logger.debug(f"Sending `{payload}`")
        response = self.serial_transaction(payload)
        return self._parseResponse(response, ret_entire_response)

    def _parseResponse(self, response, ret_entire_response):
        for i, line in enumerate(response):
            logger.debug(line)
            if line.startswith('<'):
                if ret_entire_response:
                    logger.debug(f"Response {i}: '{response[i:]}'")
                    return response[i:]
                else:
                    logger.debug(f"Response {i}: '{line}'")
                    return line
        return False

    def _parse_fan_rpm(self, response):
        res = response.split("|")
        if len(res) >= 1:
            fans_str = res[1].rstrip(';').split(";")

            for fan in fans_str:
                index, rpm = fan.split(":")
                self.fan_rpm[int(index)] = int(rpm, 16)
                # logger.debug(f"Fan #{int(index)} RPM:{int(rpm, 16)}")
            logger.debug(self.fan_rpm)
        return self.fan_rpm

    ## Signed hex conversion with bit manipulation
    def _hex_to_signed(self, hex_value, bits=16):
        value = int(hex_value, 16)
        if value & (1 << (bits - 1)):
            value -= 1 << bits
        return value

    def _parse_temperatures(self, response, single=True):
        res = response.split("|")
        if len(res) >= 1:
            temperature_str = res[1].rstrip(';').split(";")

            for temperature in temperature_str:
                index, value = temperature.split(":")
                value = self._hex_to_signed(value)
                value = round(float(value/10),1)
                self.temperature_sensors[int(index)] = value
            logger.debug(self.temperature_sensors)
        if single:
            return value
        return self.temperature_sensors

    def get_all_fan_rpm(self, fan_index=0):
        if fan_index == 0:
            cmd = 0x00
            data = None
        else:
            cmd = 0x01
            data = [fan_index]
        res = self._sendCommand(cmd, data)
        return self._parse_fan_rpm(res)

    def set_fan_pwm(self, fan, pwm):
        if int(pwm) > 255:
            raise ValueError(f'Invalid PWM value (`{pwm}`>255)')

        pwm = int(pwm * 255 / 100)

        cmd = 0x02
        data = [fan, pwm]
        return self._sendCommand(cmd, data)

    def set_all_fan_pwm(self, pwm):
        if int(pwm) > 255:
            raise ValueError(f'Invalid PWM value (`{pwm}`>255)')

        pwm = int(pwm * 255 / 100)

        cmd = 0x03
        data = pwm
        return self._sendCommand(cmd, data)

    def set_fan_rpm(self, fan, rpm):
        cmd = 0x04
        data = [fan, (rpm>>8)&0xFF, rpm&0xFF]
        return self._sendCommand(cmd, data)

    def get_hw_info(self):
        cmd = 0x05
        data = None
        hw_info = self._sendCommand(cmd, data, True)

        return ' '.join(hw_info).replace("\n", "").strip()

    def get_fw_info(self):
        cmd = 0x06
        data = None
        fw_info = self._sendCommand(cmd, data, True)
        return ' '.join(fw_info).replace("\n", "").strip()

    def get_temperature(self, channel=0):
        cmd = 0x0B
        data = [channel]
        res = self._sendCommand(cmd, data)
        return self._parse_temperatures(res, single=True)

    def get_temperature_all(self):
        cmd = 0x0C
        data = None
        res = self._sendCommand(cmd, data)
        return self._parse_temperatures(res, single=False)

    @classmethod
    def find_fan_controller(cls):
        availablePorts = comports()
        logger.debug("Searching for COM port with VID:0x2E8A and PID:0x000A")
        for port in availablePorts:
            logger.debug(f"{port.device}")
            logger.debug(f"\tProduct: {port.product}")
            logger.debug(f"\tDesc: {port.description}")
            logger.debug(f"\tSN: {port.serial_number}")
            logger.debug(f"\tVID:{port.vid} PID:{port.pid}")
            logger.debug(f"\tLocation: {port.location}")
            logger.debug(f"\tInterface: {port.interface}")
            if port.vid == 0x2E8A and port.pid == 0x000A:
                logger.debug("Using '{}' as Fan Controller COM port".format(port.description))
                return port
        return None



def main():
    print("You should probably not use this module directly...")

if __name__ == '__main__':
    main()
