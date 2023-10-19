import os
from ruamel import yaml
from base_logger import logger

class ConfigReader:
    config_path = None
    defualt_server = { 'hostname': 'localhost', 'port': 3000, 'communication_timeout': 1 }
    defualt_hardware = { 'hostname': 'localhost', 'port': 3000, 'communication_timeout': 1 }
    default_fan_profiles = {
                            '50% PWM' : { 'type': 'pwm', 'values': [50,50,50,50,50,50,50,50,50,50] },
                            '100% PWM' : { 'type': 'pwm', 'values': [100,100,100,100,100,100,100,100,100,100] },
                            '1000 RPM': { 'type': 'rpm', 'values': [1000,1000,1000,1000,1000,1000,1000,1000,1000,1000] },
                            }
    config = {
                'server': defualt_server,
                'hardware': defualt_hardware,
                'fan_profiles': default_fan_profiles
            }

    def __init__(self, config_file='config.yaml'):
        self.config_path =  os.path.join(os.path.dirname(__file__), config_file)
        self._load_config()     # Load configuration from .yaml file

    # Save current configuration to .yaml file
    def _save_config(self):
        with open(self.config_path, 'w') as cfg_file:
            yaml.dump(self.config, cfg_file, Dumper=yaml.RoundTripDumper)

    # Read .yaml config file
    def _load_config(self):
        if not os.path.exists(self.config_path):
            logger.error(f"Can not load config. Config file '{self.config_path}' does not exist!")
            self._init_default_config()
            return False

        with open(self.config_path, 'r') as file:
            cfg = yaml.safe_load(file)

        if cfg is None:
            self._init_default_config()
            return False


        config_data_missing = False
        # Add default values to the config if missing
        logger.debug("Server config:")
        server_cfg = cfg.get('server', False)
        if server_cfg is False:
            self.config['server'] = self.defualt_server
            logger.debug("Server config missing from config file. Adding default values...")
            logger.debug(self.defualt_server)
            config_data_missing = True
        else:
            self.config['server'] = server_cfg
            logger.debug(server_cfg)

        logger.debug("Hardware config:")
        server_hw = cfg.get('hardware', False)
        if server_hw is False:
            self.config['hardware'] = self.defualt_hardware
            config_data_missing = True
            logger.debug("Hardware config missing from config file. Adding default values...")
            logger.debug(self.defualt_hardware)
        else:
            self.config['hardware'] = server_hw
            logger.debug(server_hw)

        logger.debug("Fan profile config:")
        server_fp = cfg.get('fan_profiles', False)
        if server_fp is False:
            self.config['fan_profiles'] = self.default_fan_profiles
            config_data_missing = True
            logger.debug("Fan profiles missing from config file. Adding default values...")
            logger.debug(self.default_fan_profiles)
        else:
            self.config['fan_profiles'] = server_fp
            logger.debug(server_fp)

        if config_data_missing:
            self._save_config()

        return True

    def _init_default_config(self):
        logger.info("Using default config values")
        self._save_config()

    # Print out .yaml config
    def debug_config(self):
        logger.debug("--- Server Config ---")
        logger.debug(f"\t Host: {self.config['server']['hostname']}")
        logger.debug(f"\t Port: {self.config['server']['port']}")
        logger.debug(f"\t Serial Timeout: {self.config['server']['communication_timeout']}")
        logger.debug(f"\t Fan Profiles: {self.config['fan_profiles']}")
        logger.debug("--------------------")

    def get_server_config(self):
        return self.config['server']

    def get_hardware_config(self):
        return self.config['hardware']

    def get_all_fan_profiles(self):
        profiles = []
        for key, item in self.config['fan_profiles'].items():
            item['name'] = key
            profiles.append(item)
        return profiles

    def get_fan_profile(self, name):
        return self.config['fan_profiles'].get(name, False)

    def update_fan_profile(self, profile_name, profile_type, profile_params):
        allowed_profile_types = ['PWM', 'RPM']

        profile_type = profile_type.upper()

        if not any(profile_type in x  for x in allowed_profile_types):
            logger.error(f"Fan profile type must be {allowed_profile_types}! (`{profile_type}` specified)")
            return False

        if len(profile_params) != 10:
            logger.error("Fan profile must be an array of exactly 10 fan values!")
            return False

        self.config['fan_profiles'][profile_name] = { 'type': profile_type, 'values': profile_params}
        self._save_config()
        return True

    def remove_fan_profile(self, profile_name):
        if self.config['fan_profiles'].pop(profile_name, False):
            logger.info(f"Removed `{profile_name}` from fan profiles.")
            return True
        logger.info(f"Profile `{profile_name}` does not exist.")
        return False
