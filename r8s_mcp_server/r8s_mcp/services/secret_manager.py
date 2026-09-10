"""
Secret resolution for the R8S MCP Server.

Resolves secrets either from a plain environment variable (always takes
precedence, so local/stdio usage with no Vault configured keeps working
unmodified) or, if unset, from the secrets backend (Vault or AWS SSM)
already implemented by ``modular_sdk`` (``Modular().ssm_service()``),
chosen via the ``MODULAR_SDK_SECRETS_BACKEND`` environment variable. This
is used when the server runs as a module embedded inside Modular-MCP.
"""

from functools import lru_cache
from typing import Dict, List, Union

from modular_sdk.modular import Modular
from modular_sdk.services.ssm_service import SSMClientCachingWrapper

from r8s_mcp.commons.constants import MCPEnv
from r8s_mcp.commons.log_helper import get_logger

_LOG = get_logger(__name__)

SecretValue = Union[Dict, List, str]


@lru_cache(maxsize=1)
def _ssm() -> SSMClientCachingWrapper:
    return Modular().ssm_service()


def get_secret(
    vault_path: str,
    *,
    env_fallback: MCPEnv | None = None,
    required: bool = True,
) -> SecretValue | None:
    """
    Resolve a secret value.

    Resolution order:
      1. ``env_fallback``, if set — always wins over the secrets backend.
      2. the configured secrets backend (Vault or SSM) at ``vault_path``.
    """
    if env_fallback is not None and env_fallback.is_set():
        return env_fallback.get()

    try:
        value = _ssm().get_parameter(vault_path)
    except Exception:
        _LOG.warning(
            f"Failed to read secret '{vault_path}' from the configured "
            'secrets backend',
            exc_info=True,
        )
        value = None
    if value is None:
        if not required:
            return None
        raise RuntimeError(f"Secret '{vault_path}' could not be resolved.")
    return value


def get_secret_field(
    vault_path: str,
    field: str,
    *,
    env_fallback: MCPEnv | None = None,
    required: bool = True,
) -> str | None:
    """
    Like get_secret(), but for one named field of a JSON-object secret
    (e.g. a Vault document holding both a username and a password).

    Resolution order:
      1. ``env_fallback``, if set — always wins over the secrets backend.
      2. the ``field`` key of the JSON document at ``vault_path``.
    """
    if env_fallback is not None and env_fallback.is_set():
        return env_fallback.get()

    document = get_secret(vault_path, required=False)
    value = document.get(field) if isinstance(document, dict) else None
    if value is None:
        if not required:
            return None
        raise RuntimeError(
            f"Secret field '{field}' of '{vault_path}' could not be resolved."
        )
    return value
