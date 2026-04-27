import os
from enum import Enum
from itertools import chain
from typing import Callable, Literal, MutableMapping, TypeVar
from typing_extensions import Self

from r8s_mcp.commons.__version__ import __version__

APP_NAME = 'syndicate-rightsizer-mcp-server'
VERSION = __version__

PARAM_ID = 'id'
PARAM_NAME = 'name'
PARAM_LIMIT = 'limit'
PARAM_TYPES = 'types'
PARAM_APPLICATION_ID = 'application_id'
PARAM_PARENT_ID = 'parent_id'
PARAM_TENANTS = 'tenants'
PARAM_SCAN_FROM_DATE = 'scan_from_date'
PARAM_SCAN_TO_DATE = 'scan_to_date'
PARAM_FORCE_RESCAN = 'force_rescan'
PARAM_INSTANCE_ID = 'instance_id'
PARAM_RECOMMENDATION_TYPE = 'recommendation_type'
PARAM_CUSTOMER = 'customer'
PARAM_JOB_ID = 'job_id'

CheckHealthType = Literal[
    'APPLICATION', 'PARENT', 'STORAGE', 'SHAPE', 'OPERATION_MODE',
    'SHAPE_UPDATE_DATE'
]


RecommendationType = Literal[
    'SCHEDULE', 'SHUTDOWN', 'SCALE_UP', 'SCALE_DOWN', 'CHANGE_SHAPE', 'SPLIT'
]

class R8SEndpoint(str, Enum):
    """
    Should correspond to Api gateway models
    """

    SIGNIN = '/signin'
    HEALTH_CHECK = '/health-check'
    REFRESH = '/refresh'
    JOBS = '/jobs'
    RECOMMENDATIONS = 'recommendations'



    @classmethod
    def match(cls, resource: str) -> Self | None:
        """
        Tries to resolve endpoint from our enum from Api Gateway resource.
        Enum contains endpoints without stage. Though in general trailing
        slashes matter and endpoints with and without such slash are
        considered different we ignore this and consider such paths equal:
        - /path/to/resource
        - /path/to/resource/
        This method does the following:
        >>> CustodianEndpoint.match('/jobs/{job_id}') == CustodianEndpoint.JOBS_JOB
        >>> CustodianEndpoint.match('jobs/{job_id}') == CustodianEndpoint.JOBS_JOB
        >>> CustodianEndpoint.match('jobs/{job_id}/') == CustodianEndpoint.JOBS_JOB
        :param resource:
        :return:
        """
        raw = resource.strip('/')  # without trailing slashes
        for case in (raw, f'/{raw}', f'{raw}/', f'/{raw}/'):
            try:
                return cls(case)
            except ValueError:
                pass
        return


_SENTINEL = object()
_E = TypeVar('_E')


class EnvEnum(str, Enum):
    """
    Abstract enumeration class for holding environment variables
    """

    _default: str | Callable[[type['EnvEnum']], str | None] | None
    aliases: tuple[str, ...]

    @staticmethod
    def source() -> MutableMapping:
        return os.environ

    def __new__(
        cls,
        value: str,
        aliases: tuple[str, ...] | str = (),
        default: str | Callable[[type['EnvEnum']], str | None] = None,  # pyright: ignore
    ):
        """
        All environment variables and optionally their default values.
        Since envs always have string type the default value also should be
        of string type and then converted to the necessary type in code.
        There is no default value if not specified (default equal to unset)
        """
        obj = str.__new__(cls, value)
        obj._value_ = value

        obj._default = default
        obj.aliases = (aliases,) if isinstance(aliases, str) else aliases
        return obj

    def __str__(self) -> str:
        return self.value

    @property
    def default(self) -> str | None:
        if self._default is None:
            return
        if callable(self._default):
            return self._default(self.__class__)
        return self._default

    def get(self, default=_SENTINEL, /) -> str | None:
        # TODO: improve typing
        source = self.source()
        for k in chain((self.value,), self.aliases):
            if k in source:
                return source[k]

        if default is _SENTINEL:
            default = self.default
        if default is not None:
            default = str(default)
        return default

    def discard(self) -> None:
        self.source().pop(self.value, None)

    def set(self, val: str | None, /):
        if val is None:
            self.discard()
        else:
            self.source()[self.value] = str(val)

    def alias(self, n: int = 0, /) -> str | None:
        try:
            return self.aliases[n]
        except IndexError:
            return

    def is_set(self) -> bool:
        """
        Checks whether this environment variable is set
        """
        return self.get() is not None

    def as_bool(
        self, allowed: str | tuple[str, ...] = ('y', 'yes', 'true', '1'), /
    ) -> bool:
        """
        Treats env as boolean variable
        """
        allowed = (allowed,) if isinstance(allowed, str) else tuple(allowed)
        return str(self.get()).lower() in allowed

    def as_str(self) -> str:
        """
        Makes sure that the env exists. Supposed to be used with envs
        that are requires to be set otherwise there's no even need to start
        the server
        """
        val = self.get()
        if val is None:
            raise RuntimeError(f'Env {self.value} is required')
        return val

    def as_int(self) -> int:
        val = self.as_str()
        try:
            return int(float(val))
        except (ValueError, OverflowError):
            raise RuntimeError(f'Env {self.value} must contain integer')

    def as_float(self) -> float:
        val = self.as_str()
        try:
            return float(val)
        except ValueError:
            raise RuntimeError(f'Env {self.value} must contain float')

    def as_enum(self, typ: type[_E], /) -> _E:
        val = self.as_str()
        try:
            return typ(val)
        except ValueError:
            raise RuntimeError(
                f'Env {self.value} must be one of: {[i.value for i in typ]}'
            )


class MCPEnv(EnvEnum):
    """
    MCP environment variables
    """

    R8S_API_URL = 'R8S_API_URL', ()
    R8S_USERNAME = 'R8S_USERNAME', ()
    R8S_PASSWORD = 'R8S_PASSWORD', ()
    R8S_MCP_RESOURCE_PATH = 'R8S_MCP_RESOURCE_PATH', ()
    R8S_API_TIMEOUT = 'R8S_API_TIMEOUT', (), '30.0'
    R8S_API_MAX_RETRIES = 'R8S_API_MAX_RETRIES', (), '3'
    R8S_OUTPUT_FORMAT = 'SRE_OUTPUT_FORMAT', (), 'markdown'
    LOG_LEVEL = 'LOG_LEVEL', (), 'DEBUG'
