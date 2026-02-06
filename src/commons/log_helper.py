import logging
import os
import re
from functools import cached_property
from sys import stdout
from typing import Dict

try:
    import modular_sdk.commons.log_helper  # noqa: F401
except ImportError:
    pass

LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
MODULAR_SDK_LOG_LEVEL_ENV = 'MODULAR_SDK_LOG_LEVEL'


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


_name_to_level = {
    'CRITICAL': logging.CRITICAL,
    'FATAL': logging.FATAL,
    'ERROR': logging.ERROR,
    'WARNING': logging.WARNING,
    'INFO': logging.INFO,
    'DEBUG': logging.DEBUG
}


def _get_log_level(env_var: str, default: int = logging.INFO) -> int:
    """Get log level from environment variable."""
    level_str = os.environ.get(env_var, '').upper()
    return _name_to_level.get(level_str, default)


# Create shared formatter and handler
_formatter = SensitiveFormatter(LOG_FORMAT)
_console_handler = logging.StreamHandler(stream=stdout)
_console_handler.setFormatter(_formatter)

# Configure main r8s logger
logger = logging.getLogger(__name__)
logger.propagate = False
logger.addHandler(_console_handler)

log_level = _get_log_level('log_level', logging.INFO)
logger.setLevel(log_level)

logging.captureWarnings(True)


def _get_modular_sdk_log_level() -> int | None:
    """
    Get modular_sdk log level if enabled.
    Returns None if MODULAR_SDK_LOG_LEVEL is not set (disabled).
    """
    level_str = os.environ.get(MODULAR_SDK_LOG_LEVEL_ENV)
    if level_str is None:
        return None
    level_str = level_str.upper()
    if level_str not in _name_to_level:
        logger.warning(
            f"Invalid {MODULAR_SDK_LOG_LEVEL_ENV}='{level_str}'. "
            f"Valid: {', '.join(_name_to_level.keys())}. Defaulting to DEBUG"
        )
        return logging.DEBUG
    return _name_to_level[level_str]


# Configure modular_sdk logger if enabled
_sdk_level = _get_modular_sdk_log_level()
if _sdk_level is not None:
    _sdk_logger = logging.getLogger('modular_sdk')
    _sdk_logger.handlers.clear()
    _sdk_logger.addHandler(_console_handler)
    _sdk_logger.setLevel(_sdk_level)
    _sdk_logger.propagate = False


def get_logger(log_name, level=log_level):
    module_logger = logger.getChild(log_name)
    if level:
        module_logger.setLevel(level)
    return module_logger
