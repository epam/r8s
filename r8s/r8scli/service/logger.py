import getpass
import logging
import os
import re
import traceback
from functools import cached_property
from logging import (DEBUG, getLogger, StreamHandler, INFO,
                     NullHandler)
from typing import Dict

LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'


class SensitiveFormatter(logging.Formatter):
    """Formatter that removes sensitive information."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._param_to_regex: Dict[str, re.Pattern] = {}

    @cached_property
    def secured_params(self) -> set:
        return {
            'refresh_token', 'id_token', 'password', 'authorization', 'secret',
            'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'git_access_secret',
            'api_key', 'AZURE_CLIENT_ID', 'AZURE_CLIENT_SECRET',
            'GOOGLE_APPLICATION_CREDENTIALS', 'private_key', 'private_key_id',
            'Authorization', 'Authentication', 'client_email'
        }

    @staticmethod
    def _compile_param_regex(param: str) -> re.Pattern:
        """
        It searches for values in JSON objects where key is $param:
        If param is "password" the string '{"password": "blabla"}' will be
        printed as '{"password": "****"}'
        [\'"] - single or double quote; [ ]* - zero or more spaces
        """
        return re.compile(f'[\'"]{param}[\'"]:[ ]*[\'"](.*?)[\'"]')

    def get_param_regex(self, param: str) -> re.Pattern:
        if param not in self._param_to_regex:
            self._param_to_regex[param] = self._compile_param_regex(param)
        return self._param_to_regex[param]

    def _filter(self, string):
        # Hoping that this regex substitutions do not hit performance...
        for param in self.secured_params:
            string = re.sub(self.get_param_regex(param),
                            f'\'{param}\': \'****\'', string)
        return string

    def format(self, record):
        original = logging.Formatter.format(self, record)
        return self._filter(original)


FILE_NAME = 'r8s.log'
LOG_FOLDER = 'logs'

user_name = getpass.getuser()

r8s_logger = getLogger('r8s')
r8s_logger.propagate = False

debug_mode = os.getenv('r8s_DEBUG') == 'true'
if debug_mode:
    console_handler = StreamHandler()
    console_handler.setLevel(DEBUG)
    logFormatter = SensitiveFormatter(
        '%(asctime)s [USER: {}] %(message)s'.format(user_name)
    )
    console_handler.setFormatter(logFormatter)
    r8s_logger.addHandler(console_handler)
else:
    r8s_logger.addHandler(NullHandler())

# define user logger to print messages
r8s_user_logger = getLogger('m3cli.user')
# console output
console_handler = StreamHandler()
console_handler.setLevel(INFO)
console_handler.setFormatter(SensitiveFormatter('%(message)s'))
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
