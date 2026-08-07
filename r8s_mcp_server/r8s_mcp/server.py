from typing import Literal

from fastmcp import FastMCP
from fastmcp.tools import FunctionTool
from fastmcp.tools import Tool as FastMCPTool
from mcp.server.transport_security import TransportSecuritySettings, \
    TransportSecurityMiddleware
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from r8s_mcp.commons.constants import APP_NAME, VERSION
from r8s_mcp.commons.log_helper import get_logger
from r8s_mcp.commons.config import Config
from r8s_mcp.commons.exceptions import ConnectionError
from r8s_mcp.commons.context import (
    OUTPUT_FORMAT_HEADER,
    VALID_OUTPUT_FORMATS,
    set_default_mcp_config,
    set_mcp_config,
    set_output_format,
    OutputFormat, MCP_USER_CONTEXT_HEADER, bind_mcp_user_context,
    preserve_context_through_response, reset_mcp_user_context,
)
from r8s_mcp.commons.api_key import (
    SECRET_API_KEY_HEADER,
    load_expected_hash,
    validate_api_key,
)
from r8s_mcp.services.resource_manager import ResourceManager
from r8s_mcp.tools import tools_mapping

_LOG = get_logger(__name__)

TransportMode = Literal['stdio', 'sse', 'streamable-http']


# -- middleware ----------------------------------------------------------------

class OutputFormatMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware to extract X-R8S-Output-Format header.
    """
    def __init__(self, app, default_format: OutputFormat = 'markdown'):
        super().__init__(app)
        self.default_format = default_format

    async def dispatch(self, request: Request, call_next):
        output_format = request.headers.get(
            OUTPUT_FORMAT_HEADER, self.default_format,
        )
        if output_format not in VALID_OUTPUT_FORMATS:
            output_format = self.default_format

        _LOG.debug(f'Request output format: {output_format}')
        set_output_format(output_format)
        return await call_next(request)


class McpUserContextHeaderMiddleware(BaseHTTPMiddleware):
    """
    Capture ``X-MCP-USER-CONTEXT`` on inbound MCP HTTP requests so
    it can be included in the request to SRE API.
    """
    async def dispatch(self, request: Request, call_next):
        header = request.headers.get(MCP_USER_CONTEXT_HEADER)
        _LOG.debug(f'Inbound MCP user context header: {header}')
        token = bind_mcp_user_context(header)
        response = await call_next(request)
        return preserve_context_through_response(
            response, token, reset_mcp_user_context,
        )


class SecretAPIKeyMiddleware(BaseHTTPMiddleware):
    """
    Validate the ``X-R8S-MCP-SECRET-API-KEY`` request header.

    Behavior
    ---------
    * If *expected_hash* is ``None`` (env var not set) -> validation is
      **skipped** so the server stays usable without a key configured.
    * If *expected_hash* is present -> every HTTP request **must** carry the
      matching API key in the header, otherwise ``401 Unauthorized`` is
      returned immediately.
    * The comparison is constant-time (``hmac.compare_digest``) to prevent
      timing attacks.
    """

    def __init__(self, app, expected_hash: str | None = None):
        super().__init__(app)
        self.expected_hash = expected_hash

        if expected_hash:
            _LOG.info(
                "SecretAPIKeyMiddleware: API-key validation ENABLED "
                f"(header: {SECRET_API_KEY_HEADER})"
            )
        else:
            _LOG.warning(
                "SecretAPIKeyMiddleware: API-key validation DISABLED - set "
                "{load_expected_hash.__module__}.SECRET_API_KEY_HASH_ENV to "
                "enable it"
            )

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.expected_hash:
            return await call_next(request)

        provided_key = request.headers.get(SECRET_API_KEY_HEADER, "")

        if not provided_key or not validate_api_key(provided_key, self.expected_hash):
            client = getattr(request.client, "host", "unknown")
            _LOG.warning(
                f"Unauthorized request: path={request.url.path!r} "
                f"client={client!r} key_present={bool(provided_key)}"
            )
            return Response(
                content='{"error": "Unauthorized: invalid or missing API key"}',
                status_code=401,
                media_type="application/json",
            )

        return await call_next(request)


class McpTransportSecurityHTTPMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: TransportSecuritySettings):
        super().__init__(app)
        self._mcp_security = TransportSecurityMiddleware(settings)

    async def dispatch(self, request: Request, call_next):
        is_post = request.method == "POST"
        error_response = await self._mcp_security.validate_request(request, is_post=is_post)
        if error_response is not None:
            return error_response
        return await call_next(request)


def build_http_middlewares(
        secret_api_key_hash: str | None = None,
        default_output_format: OutputFormat = 'markdown',
        transport_security: TransportSecuritySettings | None = None,
) -> list[Middleware]:
    """Build ASGI middlewares for FastMCP HTTP transports."""
    middlewares: list[Middleware] = [
        Middleware(
            cls=SecretAPIKeyMiddleware,
            expected_hash=secret_api_key_hash,
        ),
    ]
    if transport_security is not None:
        middlewares.insert(
            0,
            Middleware(
                cls=McpTransportSecurityHTTPMiddleware,
                settings=transport_security,
            ),
        )
    middlewares.append(
        Middleware(
            cls=OutputFormatMiddleware,
            default_format=default_output_format,
        )
    )
    middlewares.append(
        Middleware(cls=McpUserContextHeaderMiddleware)
    )
    return middlewares


def register_tools(
    mcp_server: FastMCP,
) -> None:
    """Register each entry in *tool_mapping* on *mcp_server*.

    Mapping keys are exposed MCP tool names. Values may be plain callables
    (wrapped as FastMCP function tools) or pre-built :class:`FastMCPTool`
    instances.
    """
    for name, tool_obj in tools_mapping.items():
        if isinstance(tool_obj, FastMCPTool):
            mcp_server.add_tool(tool_obj)
        elif callable(tool_obj):
            mcp_server.add_tool(FunctionTool.from_function(tool_obj, name=name))
        else:
            raise TypeError(
                f"Tool {name!r}: expected callable or FastMCP Tool, got {type(tool_obj)!r}"
            )


# -- factory -------------------------------------------------------------------

def get_middlewares() -> list[Middleware]:
    """Get list of middlewares to use at Modular-MCP"""
    return [
        Middleware(cls=McpUserContextHeaderMiddleware),
    ]


def create_mcp_server(
        api_base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
) -> FastMCP:
    """Create and configure the MCP server."""

    config = Config.from_env_and_args(api_base_url, username, password)

    set_mcp_config(config)
    set_default_mcp_config(config)

    resource_manager = ResourceManager(config.resource_path)

    mcp = FastMCP(
        name=APP_NAME,
        instructions=(
            "Manage and interact with Syndicate RightSizer (R8S) through API. "
            "Before answering any user question about R8S, review the documentation"
        )
    )

    register_tools(mcp)
    resource_manager.register_resources(mcp)

    return mcp


# -- entry-point ---------------------------------------------------------------

def main(
        api_base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        transport: TransportMode = 'stdio',
        host: str = '0.0.0.0',
        port: int = 8080,
        allowed_hosts: list[str] | None = None,
        default_output_format: OutputFormat = 'markdown',
):
    """Run the MCP server."""
    try:

        # Configure transport security settings
        transport_security = None
        if allowed_hosts:
            # Build allowed hosts patterns with wildcard ports
            allowed_host_patterns = [f"{h}:*" for h in allowed_hosts]
            # Also add without port for exact matches
            allowed_host_patterns.extend(allowed_hosts)
            _LOG.info(f'Configuring allowed hosts: {allowed_host_patterns}')
            transport_security = TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=allowed_host_patterns,
                allowed_origins=(
                        [f"http://{h}:*" for h in allowed_hosts]
                        + [f"https://{h}:*" for h in allowed_hosts]
                ),
            )

        # -- resolve API-key hash ----------------------------------------------
        secret_api_key_hash = load_expected_hash()

        _LOG.info(f'Starting {APP_NAME} server version {VERSION}')
        _LOG.info(f'Tools: {len(tools_mapping)}')
        _LOG.info(f'Transport: {transport}')
        _LOG.info(f'Host: {host}:{port}')
        _LOG.info(f'Default output format: {default_output_format}')
        _LOG.info(
            f'API-key protection: {"ENABLED" if secret_api_key_hash else "DISABLED"}'
        )

        mcp = create_mcp_server(
            api_base_url=api_base_url,
            username=username,
            password=password,
        )

        if transport == 'stdio':
            set_output_format(default_output_format)

        _LOG.info(
            f'Output format header: {OUTPUT_FORMAT_HEADER.upper()} '
            f'(default: {default_output_format})'
        )

        mcp.run(
            host=host,
            port=port,
            transport=transport,
            stateless_http=True,
            middleware=build_http_middlewares(
                secret_api_key_hash=secret_api_key_hash,
                default_output_format=default_output_format,
                transport_security=transport_security,
            ),
            show_banner=False,
        )

    except ConnectionError as e:
        _LOG.error(f"Can't reach API server: {e}")
    except Exception as e:
        _LOG.error(f'Failed to start server: {e}', exc_info=True)
        raise
