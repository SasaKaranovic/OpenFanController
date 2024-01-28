from serial_driver import SerialHardware
from serial.tools.list_ports import comports
from base_logger import logger


class FanCommander(SerialHardware):
    fan_rpm = {}

    def __init__(self, port_info):
        super(FanCommander, self).__init__(port_info, timeout=2)

    def _sendCommand(self, cmd, data=None):
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
        return self._parseResponse(response)

    def _parseResponse(self, response):
        for line in response:
            logger.debug(line)
            if line.startswith('<'):
                logger.debug(f"Response: '{line}'")
                return line
        return False

    def _parse_fan_rpm(self, response):
        res = response.split("|")
        if len(res) >= 1:
            fans_str = res[1].rstrip(';').split(";")

            for fan in fans_str:
                cnt, rpm = fan.split(":")
                self.fan_rpm[int(cnt)] = int(rpm, 16)
                # logger.debug(f"Fan #{int(cnt)} RPM:{int(rpm, 16)}")
            logger.debug(self.fan_rpm)
        return self.fan_rpm

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
        return self._sendCommand(cmd, data)

    def get_fw_info(self):
        cmd = 0x06
        data = None
        return self._sendCommand(cmd, data)


    @classmethod
    def find_fan_controller(cls):
        dialPort = None
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
