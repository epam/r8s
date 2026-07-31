import base64
import binascii
import json

from commons.log_helper import get_logger

_LOG = get_logger(__name__)


class MCPUserContext:
    __slots__ = '_token'

    def __init__(self, token: str):
        self._token = token

    def _decode(self) -> dict:
        try:
            return json.loads(base64.b64decode(self._token))
        except binascii.Error:
            _LOG.warning(f'Failed to base64-decode MCP user context token')
        except json.JSONDecodeError:
            _LOG.warning(f'Failed to parse MCP user context JSON')
        return {}

    @property
    def email(self) -> str | None:
        return self._decode().get('email')

    @property
    def customer_id(self) -> str | None:
        return self._decode().get('customer_id')

    @property
    def assignments(self) -> list:
        return self._decode().get('assignments', [])

    @property
    def tenants(self) -> tuple:
        tenants = set()
        for assignment in self.assignments:
            if tenant := assignment.get('tenant'):
                tenants.add(tenant)
        return tuple(tenants)
