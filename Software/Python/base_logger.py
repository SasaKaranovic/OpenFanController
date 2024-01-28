import os
import sys
import logging

def colorize(data, color):
    colors = {'none': "0",
              'black': "0;30",
              'red': "0;31",
              'green': "0;32",
              'brown': "0;33",
              'blue': "0;34",
              'purple': "0;35",
              'cyan': "0;36",
              'light-gray': "0;37",
              'dark-gray': "1:30",
              'light-red': "1;31",
              'light-green': "1;32",
              'yellow': "1;33",
              'light-blue': "1;34",
              'light-purple': "1;35",
              'light-cyan': "1;36",
              'white': "1;37"}

    if color not in colors:
        raise Exception("No such color: {}".format(color))

    start = '\033[{}m'.format(colors[color])
    end = '\033[{}m'.format(colors['none'])

    return start + data + end


def default_formatter():
    pid = os.getpid()

    pieces = [('%(asctime)s.%(msecs)03d', 'cyan'),
              ('pid:{}'.format(pid), 'light-red'),
              ('%(filename)-22s %(lineno)5d', 'blue'),
              # ('%(funcName)s', 'blue'),
              ('%(levelname)-5s', 'yellow'),
              ('%(message)s', 'green')]

    # platform_system() is 'Windows' on the powershell
    try:
        if sys.stderr.isatty():
            # If running in a TTY, show colored output
            fmt = ' '.join([colorize(x[0], x[1]) for x in pieces])
        else:
            # If being directed or piped, show plaintext
            fmt = ' '.join([x[0] for x in pieces])
    except AttributeError:
        fmt = ' '.join([x[0] for x in pieces])

    return logging.Formatter(fmt, "%b %d %Y %H:%M:%S")

def set_logger_level(level='info'):
    if level.lower() == 'info':
        logging.getLogger('kr_gauge_root').setLevel("INFO")
        logger.info("Logging level: INFO")
    elif level.lower() == 'debug':
        logging.getLogger('kr_gauge_root').setLevel("DEBUG")
        logger.info("Logging level: DEBUG")
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
        logger.info("Logging level: INFO")

'''
    Shared stdout logger and logging to file
'''
# Basic logger setup
log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')

# Shared stdout logger
logger = logging.getLogger('kr_fan_root')
logger.setLevel(logging.DEBUG)
logger.propagate = False
handler = logging.StreamHandler(stream=sys.stderr)
handler.setFormatter(default_formatter())
logger.addHandler(handler)


