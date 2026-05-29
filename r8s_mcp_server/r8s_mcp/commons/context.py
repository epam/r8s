from contextlib import asynccontextmanager
from contextvars import ContextVar, Token
from typing import Final, Literal, TypeAlias, TypeGuard, get_args

from r8s_mcp.commons.config import Config
from r8s_mcp.commons.log_helper import get_logger

_LOG = get_logger(__name__)

# Context variable for per-request output format
OutputFormat: TypeAlias = Literal['markdown', 'json', 'yaml']
VALID_OUTPUT_FORMATS: Final = get_args(OutputFormat)

DEFAULT_OUTPUT_FORMAT: Final[OutputFormat] = 'markdown'

_output_format_ctx = \
    ContextVar[OutputFormat]('output_format', default=DEFAULT_OUTPUT_FORMAT)

OUTPUT_FORMAT_HEADER: Final = 'x-r8s-output-format'

# Optional MCP caller identity, forwarded to R8S API (HTTP transports only)
MCP_USERNAME_HEADER: Final = 'x-r8s-mcp-user-name'

_mcp_username_ctx: ContextVar[str | None] = ContextVar(
    'mcp_username', default=None
)

_mcp_config_ctx: ContextVar[Config | None] = ContextVar(
    'r8s_mcp_config', default=None
)

# Fallback when tools run outside the asyncio context that received
# ``set_mcp_config`` (e.g. FastMCP parent mounting this server).
_default_mcp_config: Config | None = None


def get_mcp_config() -> Config:
    """Return the active server :class:`~r8s_mcp.commons.config.Config`."""
    _LOG.info(
        f'Getting MCP server configuration.')
    c = _mcp_config_ctx.get()
    if c is not None:
        return c
    if _default_mcp_config is not None:
        return _default_mcp_config
    raise RuntimeError(
        'MCP server configuration is not bound to this context.'
    )


def set_mcp_config(config: Config) -> Token[Config | None]:
    """Bind *config* for the current context (used at server startup)."""
    _LOG.info(f'Setting MCP server configuration.')
    return _mcp_config_ctx.set(config)


def set_default_mcp_config(config: Config | None) -> None:
    """Bind *config* for the process when ContextVar is unset (e.g. mounted MCP)."""
    global _default_mcp_config
    _default_mcp_config = config


def reset_mcp_config(token: Token[Config | None]) -> None:
    """Restore the previous config value (e.g. in tests)."""
    _mcp_config_ctx.reset(token)


def is_valid_output_format(fmt: str) -> TypeGuard[OutputFormat]:
    """Type guard to validate if string is a valid OutputFormat."""
    return fmt in VALID_OUTPUT_FORMATS


def get_output_format() -> OutputFormat:
    """Get current output format from context."""
    return _output_format_ctx.get()


def set_output_format(fmt: str) -> None:
    """Set output format in context with validation."""
    validated: OutputFormat = \
        fmt if is_valid_output_format(fmt) else DEFAULT_OUTPUT_FORMAT
    _output_format_ctx.set(validated)


def reset_output_format() -> None:
    """Reset output format to default."""
    _output_format_ctx.set(DEFAULT_OUTPUT_FORMAT)


def get_mcp_username() -> str | None:
    """Inbound ``X-R8S-MCP-USER-NAME`` value for this request, if any."""
    return _mcp_username_ctx.get()


def _normalize_mcp_username(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    return s or None


@asynccontextmanager
async def mcp_username_request_scope(raw_header_value: str | None):
    """
    Bind optional MCP username for the duration of one HTTP request
    (starlette handler + awaited work in the same task context).
    """
    val = _normalize_mcp_username(raw_header_value)
    token = _mcp_username_ctx.set(val)
    try:
        yield
    finally:
        _mcp_username_ctx.reset(token)
