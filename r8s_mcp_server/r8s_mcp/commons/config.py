from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from r8s_mcp.commons.constants import MCPEnv


def _default_resource_path() -> str:
    """
    Markdown docs live next to the package (``r8s_mcp/resources``), not relative
    to the process cwd — so modular-mcp and other parents still find them when
    they import ``create_mcp_server`` from another working directory.
    """
    return str(Path(__file__).resolve().parent.parent / 'resources')


def parse_demo_tenant_names(raw: str | None) -> frozenset[str]:
    if not raw or not raw.strip():
        return frozenset()
    return frozenset(part.strip() for part in raw.split(',') if part.strip())


@dataclass
class Config:
    """Configuration for the R8S MCP server"""

    api_base_url: str | None = None
    api_username: str | None = None
    api_password: str | None = None
    auth_endpoint: str = '/signin'
    refresh_endpoint: str = '/refresh'
    timeout: float = 10.0
    max_retries: int = 3
    resource_path: str = field(default_factory=_default_resource_path)
    demo_tenant_names: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_env_and_args(
            cls,
            api_base_url: Optional[str] = None,
            username: Optional[str] = None,
            password: Optional[str] = None,
            demo_tenant_names: frozenset[str] = field(default_factory=frozenset)
    ) -> 'Config':
        """Create config from environment variables and command line arguments"""

        base_url = api_base_url or MCPEnv.R8S_API_URL.get()
        if not base_url:
            raise ValueError(
                'API base URL must be provided via --r8s-api-base-url '
                'or R8S_API_URL environment variable'
            )

        api_username = username or MCPEnv.R8S_USERNAME.get()
        if not api_username:
            raise ValueError(
                'Username must be provided via --username '
                'or R8S_USERNAME environment variable'
            )

        api_password = password or MCPEnv.R8S_PASSWORD.get()
        if not api_password:
            raise ValueError(
                'Password must be provided via --password '
                'or R8S_PASSWORD environment variable'
            )

        resource_path = MCPEnv.R8S_MCP_RESOURCE_PATH.get() or _default_resource_path()

        return cls(
            api_base_url=base_url.rstrip('/'),
            api_username=api_username,
            api_password=api_password,
            timeout=float(MCPEnv.R8S_API_TIMEOUT.get()),
            max_retries=int(MCPEnv.R8S_API_MAX_RETRIES.get()),
            resource_path=resource_path,
            demo_tenant_names=parse_demo_tenant_names(
                MCPEnv.R8S_DEMO_TENANT_NAMES.get()
            ),
        )
