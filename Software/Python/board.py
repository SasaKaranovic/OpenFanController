from base_logger import logger

class OpenFAN_Board:
    def __init__(self, hwrev, fwrev):
        self.str_hwrev = hwrev
        self.str_fwrev = fwrev
        self.board = {}
        self._calc_hw_capabilities()

    def reset_board(self):
        self.board['hw_str'] = self.str_hwrev
        self.board['fw_str'] = self.str_fwrev
        self.board['name'] = 'unsupported'
        self.board['hw_rev'] = 0
        self.board['fw_rev'] = 0
        self.board['fan_count'] = 0
        self.board['sensor_count'] = 0
        self.board['has_sensors'] = False
        self.board['has_profiles'] = False
        self.board['fw_support_pwm'] = True
        self.board['fw_support_rpm'] = False

    def get_board_capabilities(self):
        return self.board

    def _calc_hw_capabilities(self):
        self.reset_board()

        if 'MCU:PICO2040' in self.str_hwrev:
            self.board['hw_rev'] = '3'
            self.board['name'] = 'OpenFAN Controller'
            self.board['fan_count'] = 10
            self.board['fw_support_rpm'] = True
            self.board['has_profiles'] = True

        elif 'MCU:OpenFAN_Micro_ESP32C3' in self.str_hwrev:
            self.board['hw_rev'] = '4'
            self.board['name'] = 'OpenFAN Micro'
            self.board['fan_count'] = 1
            self.board['sensor_count'] = 0
            self.board['has_sensors'] = False

        elif 'MCU:PICO235' in self.str_hwrev:
            self.board['hw_rev'] = '4'
            self.board['name'] = 'OpenFAN XL'
            self.board['fan_count'] = 10
            self.board['sensor_count'] = 4
            self.board['has_sensors'] = True
        else:
            logger.error(f"Uknown board rev: `{self.str_hwrev}`")

    def get_hw_rev(self):
        return self.board['hw_rev']

    def get_fw_rev(self):
        return self.board['fw_rev']

    def get_fan_count(self):
        return self.board['fan_count']

    def get_sensor_count(self):
        return self.board['sensor_count']

    def get_name(self):
        return self.board['name']

    def board_has_sensors(self):
        return self.board['has_sensors']

    def board_has_profiles(self):
        return self.board['has_profiles']

    def fw_support_rpm(self):
        return self.board['fw_support_rpm']

    def fw_support_pwm(self):
        return self.board['fw_support_pwm']

