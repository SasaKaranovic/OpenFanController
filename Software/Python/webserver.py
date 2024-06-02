import sys
import os
import signal
import argparse
import time
import re
from mimetypes import guess_type
from tornado.web import Application
from tornado.web import RequestHandler
from tornado.web import StaticFileHandler
from tornado.web import Finish
from tornado.web import HTTPError
from tornado.ioloop import IOLoop
from FanCommander import FanCommander
from base_logger import logger, set_logger_level
from config import ConfigReader

BASEDIR_NAME = os.path.dirname(__file__)
BASEDIR_PATH = os.path.abspath(BASEDIR_NAME)
WEBPAGE_ROOT = os.path.join(BASEDIR_PATH, 'webpage')


class BaseHandler(RequestHandler):
    def initialize(self, handler, config):
        self.handler = handler
        self.config = config

    def send_response(self, status, message='', data=None):
        self.write({'status': status, 'message': message, 'data': data})
        return self.finish()

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET')
        self.set_header('Content-Type', 'application/json')

    def is_valid_fan_index(self, index):
        try:
            if int(index) >=0 and int(index) <= 9:
                return True
            return False
        except ValueError:
            raise False

class RootHandler(BaseHandler):
    def get(self):
        logger.debug("Root handler")
        resp = {'status': 'ok', 'message': 'Karanovic Research Fan Controller API Server v0.1'}
        self.write(resp)

class FanProfile_List(BaseHandler):
    def get(self):
        logger.info("Request:FANPROFILE_LIST")
        profiles = self.config.get_all_fan_profiles()
        self.send_response(status='ok', message=f'There are {len(profiles)} FAN profiles available.', data=profiles)

class FanProfile_Add(BaseHandler):
    def post(self):
        logger.info("Request:FANPROFILE_ADD")

        profile_name = self.get_argument('name', None)
        profile_type = self.get_argument('type', None)
        profile_values_str = self.get_argument('values', None)
        error = False

        if profile_name is None:
            error = True
            message = 'Fan profile name can not be empty!'
        if profile_type is None:
            error = True
            message='Fan profile type can not be empty!'
        if profile_values_str is None:
            error = True
            message='Fan profile values can not be empty!'
        if profile_type.lower() != 'pwm' and profile_type.lower() != 'rpm':
            error = True
            message='Fan profile type can be either "pwm" or "rpm".'

        if error:
            return self.send_response(status='fail', message=message, data=None)

        fan_profile = profile_values_str.split(';')
        try:
            fan_profile = [int(i) for i in fan_profile]
        except Exception as e:
            logger.error(f'FanProfile_Add error: {e}')
            return self.send_response(status='fail', message='Fan profile can only contain integer values!', data=None)

        if len(fan_profile) != 10:
            return self.send_response(status='fail', message=f'Fan profile expects exactly 10 values! ({len(fan_profile)} given)', data=None)

        if self.config.update_fan_profile(profile_name, profile_type, fan_profile):
            return self.send_response(status='ok', message='Profile added', data=None)
        return self.send_response(status='fail', message='Failed to add profile!', data=None)

class FanProfile_Remove(BaseHandler):
    def get(self):
        logger.info("Request:FANPROFILE_REMOVE")

        name = self.get_argument('name', None)
        if name is None:
            return self.send_response(status='fail', message='Name can not be empty!', data=None)

        res = self.config.remove_fan_profile(name)
        if res is True:
            return self.send_response(status='ok', message='Profile removed', data=None)
        return self.send_response(status='ok', message='Profile does not exist', data=None)

class FanProfile_Set(BaseHandler):
    def get(self):
        logger.info("Request:FANPROFILE_SET")

        name = self.get_argument('name', None)
        if name is None:
            return self.send_response(status='fail', message='Name can not be empty!', data=None)

        profile = self.config.get_fan_profile(name)
        if not profile:
            return self.send_response(status='fail', message='Profile does not exist! (Names are case-sensitive!)', data=None)

        profile_type = profile['type'].upper()
        if profile_type not in ["PWM", "RPM"]:
            return self.send_response(
                                      status='fail',
                                      message=f'Malformed profile type! (expected "pwm" or "rpm". "{profile_type}" received.)',
                                      data=None)

        profile_values = profile['values']

        msg = ""
        for index, pwm in enumerate(profile_values):
            logger.debug(f"Setting fan {index} to {pwm} {profile_type}")
            msg = msg + f" Fan{index+1}={pwm} {profile_type}"

            if profile_type == 'PWM':
                self.handler.set_fan_pwm(index, pwm)
            else:
                self.handler.set_fan_rpm(index, pwm)

        return self.send_response(status='ok', message=f'Profile `{name}` activated.{msg}.', data=None)

class FanStatus_Handler(BaseHandler):
    def get(self):
        logger.info("Request:STATUS")

        rpm = self.handler.get_all_fan_rpm()
        return self.send_response(status='ok', message='', data=rpm)

class FanSetALLPWM(BaseHandler):
    def get(self):
        value = self.get_argument('value', 0)
        value = int(float(value))
        if value > 100:
            value = 100
        elif value < 0:
            value = 0

        logger.info(f"Request:SET - FAN: ALL To:{value}%")
        self.handler.set_all_fan_pwm(value)
        return self.send_response(status='ok', message=f'Update queued. Setting ALL fans to PWM:{value}%', data=None)

class FanSetPWM_Handler(BaseHandler):
    def get(self, fan_index=-1):
        if not self.is_valid_fan_index(fan_index):
            return self.send_response(status='fail', message=f'Invalid fan index (0<=`{fan_index}`<=9)', data=None)

        value = self.get_argument('value', 0)
        value = int(float(value))
        if value > 100:
            value = 100
        elif value < 0:
            value = 0

        fan_index = int(fan_index)
        logger.info(f"Request:SET - FAN:{fan_index} To:{value}% ({value})")
        self.handler.set_fan_pwm(fan_index, value)
        return self.send_response(status='ok', message=f'Update queued. Setting fan #{fan_index} to PWM:{value}%', data=None)

class FanSetRPM_Handler(BaseHandler):
    def get(self, fan_index=-1):
        if not self.is_valid_fan_index(fan_index):
            return self.send_response(status='fail', message=f'Invalid fan index (0<=`{fan_index}`<=9)', data=None)

        value = int(self.get_argument('value', 0))
        if value > 16000:
            value = 16000
        elif value < 480:
            value = 0

        # Fan index is specified
        fan_index = int(fan_index)
        logger.info(f"Request:SET RPM - FAN:{fan_index} To:{value} RPM")
        self.handler.set_fan_rpm(fan_index, value)
        return self.send_response(status='ok', message=f'Update queued. Fan:{fan_index} RPM:{value}', data=None)

class FanAliasAll_Handler(BaseHandler):
    def get(self):
        logger.info(f"Request:GET ALL FAN Aliases")
        aliases = self.config.get_fan_alias(-1)
        fan_data = {}
        for fan_index, alias in aliases.items():
            fan_data[fan_index] = alias

        return self.send_response(status='ok', message='', data=fan_data)

class FanAliasGet_Handler(BaseHandler):
    def get(self, fan_index=-1):
        if not self.is_valid_fan_index(fan_index):
            return self.send_response(status='fail', message=f'Invalid fan index (0<=`{fan_index}`<=9)', data=None)

        # Fan index is specified
        fan_index = int(fan_index)
        logger.info(f"Request:GET FAN Alias - FAN:{fan_index}")
        fan_data = { 'fan_id': fan_index, 'alias': self.config.get_fan_alias(fan_index)}
        return self.send_response(status='ok', message='', data=fan_data)

class FanAliasSet_Handler(BaseHandler):
    def get(self, fan_index=-1):
        if not self.is_valid_fan_index(fan_index):
            return self.send_response(status='fail', message=f'Invalid fan index (0<=`{fan_index}`<=9)', data=None)

        value = self.get_argument('value', None)
        if value is None:
            return self.send_response(status='fail', message=f'Fan alias can not be none!', data=None)
        if re.search("^[a-z0-9\-_\.# ]*?$", value, re.MULTILINE | re.IGNORECASE) is None:
            return self.send_response(status='fail', message=f'Fan alias can only contain `A-Z`, `0-9`, `-`, `_`, `#` and `<space>` characters!', data=None)

        # Fan index is specified
        fan_index = int(fan_index)
        logger.info(f"Request:SET FAN #{fan_index} alias to: `{value}`")
        if self.config.set_fan_alias(fan_index, value):
            return self.send_response(status='ok', message=f'Fan #{fan_index} alias set to:`{value}`', data=None)
        return self.send_response(status='fail', message=f'Failed to set fan alias. (`{fan_index}:{value}`)', data=None)

class Info_Handler(BaseHandler):
    def get(self):

        data = {}
        data['hardware'] = self.handler.get_hw_info()
        data['firmware'] = self.handler.get_hw_info()
        data['software'] = "Version: 0.2\r\nBuild: 2024-06-01"

        return self.send_response(status='ok', message='System information', data=data)

# -- Default 404 --
class Default_404_Handler(RequestHandler):
    # Override prepare() instead of get() to cover all possible HTTP methods.
    def prepare(self):
        self.set_status(404)
        resp = {'status': 'fail', 'message': 'Unsupported method'}
        self.write(resp)
        raise Finish()

class FileHandler(RequestHandler):
    def get(self, path=None):
        logger.debug(f"Requesting: {path}")
        if path:
            file_location = os.path.join(WEBPAGE_ROOT, path)
        else:
            file_location = os.path.join(WEBPAGE_ROOT, 'index.html')

        if not os.path.isfile(file_location):
            logger.error(f"Requested file can not be found: {path}")
            raise HTTPError(status_code=404)
        content_type, _ = guess_type(file_location)
        self.add_header('Content-Type', content_type)
        with open(file_location, encoding="utf8") as source_file:
            self.write(source_file.read())



class FAN_API_Service(Application):
    def __init__(self):

        # OpenFAN config file (ie `config.yaml`) path can be set through `OPENFANCONFIG` environment variable
        # or if it's not set, the default `config.yaml` from this directory will be used.
        config_file = os.getenv('OPENFANCONFIG', default='config.yaml')
        self.config = ConfigReader(config_file)

        # API service will look for OpenFAN serial port in the following order
        # 1. Check if `hardware->port` entry is specified in `config.yaml`
        # 2. Check if `OPENFANCOMPORT` is specified in OS environment variable
        # 3. Try to find OpenFAN controller by searching for USB VID and PID

        hardware_config = self.config.get_hardware_config()
        cfg_port = hardware_config.get('port', None)
        env_port = os.getenv('OPENFANCOMPORT', default=None)

        if cfg_port:
            self.serialPort = cfg_port
            logger.info(f"Using COM port `{self.serialPort}` (specified in `config.yaml` file).")
        elif env_port is not None:
            self.serialPort = env_port
            logger.info(f"Using COM port `{self.serialPort}` (specified in `OPENFANCOMPORT` env variable).")
        else:
            self.serialPort = FanCommander.find_fan_controller()
            if self.serialPort is None:
                logger.error("Could not find Fan controller. Please make sure it's plugged in and (if necessary) drivers are installed.")
                raise Exception("Could not find Fan controller. Please make sure it's plugged in and (if necessary) drivers are installed.")

            logger.info(f"Using COM port `{self.serialPort}` (Found through USB VID:PID).")

        logger.info("Fan Controller port: {}".format(self.serialPort))
        self.fan_commander = FanCommander(self.serialPort)

        self.handlers = [
            (r"/api/v0/profiles/list", FanProfile_List, {"handler":self.fan_commander, "config":self.config}),
            (r"/api/v0/profiles/add", FanProfile_Add, {"handler":self.fan_commander, "config":self.config}),
            (r"/api/v0/profiles/remove", FanProfile_Remove, {"handler":self.fan_commander, "config":self.config}),
            (r"/api/v0/profiles/set", FanProfile_Set, {"handler":self.fan_commander, "config":self.config}),
            (r"/api/v0/fan/status", FanStatus_Handler, {"handler":self.fan_commander, "config":self.config}),
            (r"/api/v0/fan/all/set", FanSetALLPWM, {"handler":self.fan_commander, "config":self.config}),
            # `/api/v0/fan/([0-9])/set` is now deprecated. Please use `/api/v0/fan/([0-9])/pwm`
            (r"/api/v0/fan/([0-9])/set", FanSetPWM_Handler, {"handler":self.fan_commander, "config":self.config}),
            (r"/api/v0/fan/([0-9])/pwm", FanSetPWM_Handler, {"handler":self.fan_commander, "config":self.config}),
            (r"/api/v0/fan/([0-9])/rpm", FanSetRPM_Handler, {"handler":self.fan_commander, "config":self.config}),
            (r"/api/v0/alias/all/get", FanAliasAll_Handler, {"handler":self.fan_commander, "config":self.config}),
            (r"/api/v0/alias/([0-9])/get", FanAliasGet_Handler, {"handler":self.fan_commander, "config":self.config}),
            (r"/api/v0/alias/([0-9])/set", FanAliasSet_Handler, {"handler":self.fan_commander, "config":self.config}),
            (r"/api/v0/info", Info_Handler, {"handler":self.fan_commander, "config":self.config}),
            (r"/", FileHandler),
            (r'/(.*)', StaticFileHandler, {'path': WEBPAGE_ROOT}),
        ]

        self.server_settings = {
            "debug": True,
            "autoreload": False,
            # "autoreload": True,
            "default_handler_class": Default_404_Handler,
        }

    def run_forever(self):
        logger.info("Karanovic Research OpenFan - Starting API server")
        app = Application(self.handlers, **self.server_settings)

        server_config = self.config.get_server_config()
        port = server_config.get('port', 3000)
        logger.info(f"Listening on port {port}")
        app.listen(port)

        IOLoop.instance().start()


def signal_handler(signal, frame):
    IOLoop.current().add_callback_from_signal(shutdown)
    print('\r\nYou pressed Ctrl+C!')
    sys.exit(0)

def shutdown():
    logger.info('Stopping API server')
    logger.info('Will shutdown in 3 seconds ...')
    io_loop = IOLoop.instance()
    deadline = time.time() + 3

    def stop_loop():
        now = time.time()
        if now < deadline and (io_loop._callbacks or io_loop._timeouts):
            io_loop.add_timeout(now + 1, stop_loop)
        else:
            io_loop.stop()
            logger.info('Shutdown')
    stop_loop()


def main(cmd_args):
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    set_logger_level(cmd_args.logging)
    try:
        FAN_API_Service().run_forever()
    except Exception:
        logger.exception("OpenFan API service crashed during setup.")
    os._exit(0)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Karanovic Research - Fan Controller API service')
    parser.add_argument('-l', '--logging', type=str, default='info')
    args = parser.parse_args()
    main(args)
