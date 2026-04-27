import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
import httpx

from r8s_mcp.commons.log_helper import get_logger

_LOG = get_logger(__name__)


class AuthManager:
    """Manages authentication tokens and automatic refresh"""

    def __init__(
        self,
        username: str,
        password: str,
        auth_endpoint: str,
        refresh_endpoint: str,
    ):
        self.username = username
        self.password = password
        self.auth_endpoint = auth_endpoint
        self.refresh_endpoint = refresh_endpoint
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._refresh_lock = asyncio.Lock()

    def get_auth_headers(self, token: Optional[str] = None) -> Dict[str, str]:
        """Get authentication headers, preferring bearer token over basic auth"""
        if not token and not self._access_token:
            raise ValueError('No access token available')
        return {'Authorization': f'Bearer {token or self._access_token}'}

    async def get_bearer_token(self, client: httpx.AsyncClient) -> str:
        """Get or refresh bearer token"""
        async with self._refresh_lock:
            if self._is_token_valid():
                return self._access_token

            if self._refresh_token:
                try:
                    await self._refresh_access_token(client)
                    return self._access_token
                except Exception as e:
                    _LOG.warning(f'Failed to refresh token: {e}')

            await self._authenticate(client)
            return self._access_token

    def _is_token_valid(self) -> bool:
        """Check if the current access token is valid and not expired"""
        if not self._access_token or not self._token_expires_at:
            return False

        return (
            datetime.now(timezone.utc) + timedelta(minutes=5)
            < self._token_expires_at
        )

    async def _authenticate(self, client: httpx.AsyncClient) -> None:
        """Authenticate using username and password, storing tokens"""
        _LOG.debug('Authenticating with username and password')

        try:
            response = await client.post(
                self.auth_endpoint,
                headers={},
                json={'username': self.username, 'password': self.password},
            )
            response.raise_for_status()

            data = response.json()
            items = data.get('items', [])
            if isinstance(items, list) and items:
                target_data = items[0]
                self._access_token = target_data.get('id_token')
                self._refresh_token = target_data.get('refresh_token')

                expires_in = target_data.get('expires_in', 3600)
                self._token_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=expires_in
                )

                _LOG.debug('Successfully authenticated and received tokens')

        except httpx.HTTPError as e:
            _LOG.error(f'Authentication failed: {e}')
            raise
        except KeyError as e:
            _LOG.error(f'Invalid response format: missing {e}')
            raise ValueError(
                f'Authentication response missing required field: {e}'
            )

    async def _refresh_access_token(self, client: httpx.AsyncClient) -> None:
        """Refresh the access token using the refresh token"""
        if not self._refresh_token:
            raise ValueError('No refresh token available')

        _LOG.debug('Refreshing access token')

        try:
            response = await client.post(
                self.refresh_endpoint,
                headers={'Authorization': f'Bearer {self._refresh_token}'},
                json={'refresh_token': self._refresh_token},
            )
            response.raise_for_status()

            data = response.json()
            self._access_token = data.get('access_token')

            if 'refresh_token' in data:
                self._refresh_token = data['refresh_token']

            expires_in = data.get('expires_in', 3600)
            self._token_expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=expires_in
            )

            _LOG.debug('Successfully refreshed access token')

        except httpx.HTTPError as e:
            _LOG.error(f'Token refresh failed: {e}')
            self.clear_tokens()
            raise

    def clear_tokens(self) -> None:
        """Clear all stored tokens"""
        self._access_token = None
        self._refresh_token = None
        self._token_expires_at = None
        _LOG.debug('Cleared all authentication tokens')
