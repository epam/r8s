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

MCP_USER_CONTEXT_HEADER: Final = 'x-mcp-user-context'
MCP_USER_CONTEXT_OUTBOUND_HEADER: Final = 'X-Mcp-User-Context'

_mcp_username_ctx: ContextVar[str | None] = ContextVar(
    'mcp_username', default=None
)

_mcp_config_ctx: ContextVar[Config | None] = ContextVar(
    'r8s_mcp_config', default=None
)

# Fallback when tools run outside the asyncio context that received
# ``set_mcp_config`` (e.g. FastMCP parent mounting this server).
_default_mcp_config: Config | None = None


_user_context_ctx: ContextVar[str | None] = ContextVar(
    'user_context', default=None
)

def get_mcp_config() -> Config:
    """Return the active server :class:`~r8s_mcp.commons.config.Config`."""
    _LOG.info('Getting MCP server configuration.')
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
    _LOG.info('Setting MCP server configuration.')
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


def get_mcp_user_context() -> str | None:
    return _user_context_ctx.get()


def bind_mcp_user_context(header_value: str | None) -> Token[str | None]:
    """Bind inbound user context for the current request."""
    return _user_context_ctx.set(header_value)


def reset_mcp_user_context(token: Token[str | None]) -> None:
    """Restore the previous user-context value."""
    _user_context_ctx.reset(token)


def preserve_context_through_response(response, token: Token, reset_fn) :
    """
    Keep a ContextVar alive until the HTTP response has fully finished.

    ``BaseHTTPMiddleware`` returns from ``call_next`` before tools run;
    context managers around ``call_next`` therefore reset too early.
    """
    original_call = response.__call__

    async def __call__(scope, receive, send):
        try:
            await original_call(scope, receive, send)
        finally:
            reset_fn(token)

    response.__call__ = __call__
    return response
