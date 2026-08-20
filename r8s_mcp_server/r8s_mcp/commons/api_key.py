"""
API-key utilities for R8S MCP Server.

Flow
----
  Generator  ->  produces  KEY  +  SHA-256(KEY)
  Server env ->  stores    SHA-256(KEY)          (R8S_MCP_SECRET_API_KEY_HASH)
  Client     ->  sends     KEY                   (X-R8S-MCP-SECRET-API-KEY)
  Middleware ->  hashes incoming KEY, compares with stored hash
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets

# -- public constants ----------------------------------------------------------
SECRET_API_KEY_HEADER = "X-R8S-MCP-SECRET-API-KEY"
SECRET_API_KEY_HASH_ENV = "R8S_MCP_SECRET_API_KEY_HASH"


# -- key helpers ---------------------------------------------------------------

def generate_api_key(prefix: str = "r8s") -> str:
    """
    Generate a cryptographically secure random API key.

    Example output: ``sre_3Fk9...`` (prefix + 43 URL-safe base64 chars)
    """
    return f"{prefix}_{secrets.token_urlsafe(32)}"


def hash_api_key(key: str) -> str:
    """Return the SHA-256 hex-digest of *key*."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def validate_api_key(provided_key: str, expected_hash: str) -> bool:
    """
    Compare *provided_key* against *expected_hash* in constant time.

    Constant-time comparison prevents timing-based enumeration attacks.
    """
    return hmac.compare_digest(hash_api_key(provided_key), expected_hash)


def load_expected_hash() -> str | None:
    """Return the hash stored in ``R8S_MCP_SECRET_API_KEY_HASH``, or *None*."""
    value = os.environ.get(SECRET_API_KEY_HASH_ENV, "").strip()
    return value or None
