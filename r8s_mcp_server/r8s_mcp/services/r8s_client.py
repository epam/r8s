import asyncio
import httpx
from typing import Any, Dict, Optional

from r8s_mcp.commons.constants import PARAM_TYPES, R8SEndpoint, PARAM_ID, \
    PARAM_NAME, \
    PARAM_LIMIT, PARAM_APPLICATION_ID, PARAM_PARENT_ID, PARAM_TENANTS, \
    PARAM_SCAN_FROM_DATE, PARAM_SCAN_TO_DATE, PARAM_FORCE_RESCAN, \
    RecommendationType, PARAM_INSTANCE_ID, PARAM_RECOMMENDATION_TYPE, \
    PARAM_CUSTOMER, PARAM_JOB_ID, PARAM_TENANT
from r8s_mcp.commons.config import Config
from r8s_mcp.commons.context import get_mcp_config, get_mcp_username, \
    MCP_USERNAME_OUTBOUND_HEADER
from r8s_mcp.commons.exceptions import ConnectionError
from r8s_mcp.services.auth_manager import AuthManager
from r8s_mcp.commons.log_helper import get_logger

_LOG = get_logger(__name__)

# Reusable error response builders
def _connect_error_response(
        e: httpx.ConnectError,
        url: str,
) -> Dict[str, Any]:
    _LOG.error(f'Failed to connect to R8S API at {url}: {e}')
    return {
        'error': f'Cannot connect to R8S API at {url}. Is the service running?'
    }


def _unavailable_response(
        e: httpx.HTTPStatusError,
) -> Dict[str, Any]:
    _LOG.error('R8S API is unavailable')
    return e.response.json()


class R8SClient:
    def __init__(self, config: Config | None = None):
        resolved = config if config is not None else get_mcp_config()
        self.config = resolved
        self.auth_manager = AuthManager(
            resolved.api_username,
            resolved.api_password,
            resolved.auth_endpoint,
            resolved.refresh_endpoint,
        )
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            base_url=self.config.api_base_url,
            timeout=self.config.timeout,
            headers={'Content-Type': 'application/json'},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        use_bearer_token: bool = True,
    ) -> Dict[str, Any]:
        """Make authenticated API request with retry logic"""
        if not self.client:
            raise RuntimeError(
                'Client not initialized. Use async context manager.'
            )

        headers = {}
        if use_bearer_token:
            try:
                token = await self.auth_manager.get_bearer_token(self.client)
                headers.update(self.auth_manager.get_auth_headers(token))
            except Exception as e:
                _LOG.warning(
                    f'Failed to get bearer token, falling back to basic auth: {e}'
                )

        mcp_user = get_mcp_username()
        if mcp_user:
            headers[MCP_USERNAME_OUTBOUND_HEADER] = mcp_user

        last_exception = None
        for attempt in range(self.config.max_retries):
            try:
                response = await self.client.request(
                    method=method,
                    url=endpoint,
                    json=data if data is not None else {},
                    params=params,
                    headers=headers,
                )

                if (
                    response.status_code == 401
                    and attempt < self.config.max_retries - 1
                ):
                    self.auth_manager.clear_tokens()
                    continue

                response.raise_for_status()
                return response.json() if response.content else {}

            except httpx.HTTPError as e:
                _LOG.error(f'HTTP error on attempt {attempt + 1}: {e}')
                last_exception = e
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(2**attempt)  # Exponential backoff
                    continue
                break

        raise last_exception or ConnectionError('Max retries exceeded')

    @staticmethod
    def _sifted(params: dict) -> dict:
        return {
            k: v for k, v in params.items() if isinstance(v, (bool, int)) or v
        }

    async def health_check(
            self,
            types: list[str] | None = None,
    ) -> Dict[str, Any]:
        """Check the health status of the R8S API"""
        data: Dict[str, Any] | None = None
        if types:
            data = {PARAM_TYPES: types}
        try:
            return await self._make_request(
                'POST', R8SEndpoint.HEALTH_CHECK.value, data=data,
            )
        except httpx.ConnectError as e:
            return _connect_error_response(e, self.config.api_base_url)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 503:
                return _unavailable_response(e)
            raise

    async def get_jobs(
            self,
            job_id: str | None = None,
            job_name: str | None = None,
            limit: int | None = None,
    ) -> Dict[str, Any]:
        """Retrieve jobs from the R8S API"""
        params = {
            PARAM_ID: job_id,
            PARAM_NAME: job_name,
            PARAM_LIMIT: limit,
        }

        try:
            return await self._make_request(
                method='GET',
                endpoint=R8SEndpoint.JOBS.value,
                params=self._sifted(params),
            )
        except httpx.ConnectError as e:
            return _connect_error_response(e, self.config.api_base_url)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 503:
                return _unavailable_response(e)
            raise

    async def submit_job(
            self,
            application_id: str | None = None,
            parent_id: str | None = None,
            scan_tenants: list[str] | None = None,
            scan_from_date: str | None = None,
            scan_to_date: str | None = None,
            force_rescan: bool | None = None,
    ) -> Dict[str, Any]:
        """Submit a new job to the R8S API"""
        params = {
            PARAM_APPLICATION_ID: application_id,
            PARAM_PARENT_ID: parent_id,
            PARAM_TENANTS: scan_tenants,
            PARAM_SCAN_FROM_DATE: scan_from_date,
            PARAM_SCAN_TO_DATE: scan_to_date,
            PARAM_FORCE_RESCAN: force_rescan
        }

        try:
            return await self._make_request(
                method='POST',
                endpoint=R8SEndpoint.JOBS.value,
                data=self._sifted(params)
            )
        except httpx.ConnectError as e:
            return _connect_error_response(e, self.config.api_base_url)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 503:
                return _unavailable_response(e)
            raise

    async def get_recommendations(
            self,
            instance_id: str | None = None,
            recommendation_type: RecommendationType = None,
            job_id: str | None = None,
            customer_id: str | None = None,
    ) -> Dict[str, Any]:
        """Retrieve recommendation from the R8S API"""
        params = {
            PARAM_INSTANCE_ID: instance_id,
            PARAM_RECOMMENDATION_TYPE: recommendation_type,
            PARAM_CUSTOMER: customer_id,
            PARAM_JOB_ID: job_id
        }

        try:
            return await self._make_request(
                method='GET',
                endpoint=R8SEndpoint.RECOMMENDATIONS.value,
                params=self._sifted(params)
            )
        except httpx.ConnectError as e:
            return _connect_error_response(e, self.config.api_base_url)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 503:
                return _unavailable_response(e)
            raise

    async def get_tenants(
            self,
            name: str | None = None,
    ) -> Dict[str, Any]:
        """Retrieve tenants from the R8S API"""
        params = {
            PARAM_TENANT: name,
        }

        try:
            return await self._make_request(
                method='GET',
                endpoint=R8SEndpoint.TENANTS.value,
                params=self._sifted(params)
            )
        except httpx.ConnectError as e:
            return _connect_error_response(e, self.config.api_base_url)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 503:
                return _unavailable_response(e)
            raise
