import getpass
import os
import traceback
from logging import (DEBUG, getLogger, Formatter, StreamHandler, INFO,
                     NullHandler)

FILE_NAME = 'r8s.log'
LOG_FOLDER = 'logs'

user_name = getpass.getuser()

r8s_logger = getLogger('r8s')
r8s_logger.propagate = False

debug_mode = os.getenv('r8s_DEBUG') == 'true'
if debug_mode:
    console_handler = StreamHandler()
    console_handler.setLevel(DEBUG)
    logFormatter = Formatter('%(asctime)s [USER: {}] %(message)s'.format(
        user_name))
    console_handler.setFormatter(logFormatter)
    r8s_logger.addHandler(console_handler)
else:
    r8s_logger.addHandler(NullHandler())

# define user logger to print messages
r8s_user_logger = getLogger('m3cli.user')
# console output
console_handler = StreamHandler()
console_handler.setLevel(INFO)
console_handler.setFormatter(Formatter('%(message)s'))
r8s_user_logger.addHandler(console_handler)


def get_logger(log_name, level=DEBUG):
    module_logger = r8s_logger.getChild(log_name)
    if level:
        module_logger.setLevel(level)
    return module_logger


def get_user_logger(log_name, level=INFO):
    module_logger = r8s_user_logger.getChild(log_name)
    if level:
        module_logger.setLevel(level)
    return module_logger


def exception_handler_formatter(exception_type, exception, exc_traceback):
    if debug_mode:
        r8s_logger.error('%s: %s', exception_type.__name__, exception)
        traceback.print_tb(tb=exc_traceback, limit=15)
