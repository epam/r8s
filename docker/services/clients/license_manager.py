from functools import cached_property
from json import JSONDecodeError
from typing import Optional
from typing import Union, List, Type, Dict

from modular_sdk.services.impl.maestro_credentials_service import AccessMeta
from requests import request, Response
from requests.exceptions import RequestException

from commons import secure_event
from commons.constants import POST_METHOD, PATCH_METHOD, \
    STATUS_ATTR, TENANT_ATTR, AUTHORIZATION_PARAM, CUSTOMER_ATTR, \
    SERVICE_TYPE_ATTR, SERVICE_TYPE_RIGHTSIZER, ALGORITHM_MAPPING_ATTR
from commons.log_helper import get_logger
from services.setting_service import SettingsService

SET_TENANT_ACTIVATION_DATE_PATH = '/tenants/set-activation-date'
SET_CUSTOMER_ACTIVATION_DATE_PATH = '/customers/set-activation-date'
JOB_CHECK_PERMISSION_PATH = '/jobs/check-permission'
SYNC_LICENSE_PATH = '/license/sync'
JOBS_PATH = '/jobs'

HOST_KEY = 'host'

JOB_ID = 'job_id'
CREATED_AT_ATTR = 'created_at'
STARTED_AT_ATTR = 'started_at'
STOPPED_AT_ATTR = 'stopped_at'

_LOG = get_logger(__name__)


class LicenseManagerClient:

    def __init__(self, setting_service: SettingsService):
        self.setting_service = setting_service
        self._access_data = None
        self._client_key_data = None

    @cached_property
    def access_data(self) -> dict:
        return self.setting_service.get_license_manager_access_data() or {}

    @property
    def host(self) -> Optional[str]:
        return AccessMeta.from_dict(self.access_data).url

    @property
    def client_key_data(self):
        if not self._client_key_data:
            self._client_key_data = \
                self.setting_service.get_license_manager_client_key_data()
            self._client_key_data = self._client_key_data or {}
        return self._client_key_data

    def post_job(self, job_id: str, customer: str, tenant: str,
                 algorithm_map: Dict[str, List[str]], auth: str):
        """
        Delegated to instantiate a licensed Job, bound to a tenant within a
        customer utilizing rulesets which are grouped by tenant-license-keys,
        allowing to request for a ruleset-content-source collection.
        :parameter job_id: str
        :parameter customer: str
        :parameter tenant: str
        :parameter auth: str, authorization token
        :parameter algorithm_map: Dict[str, List[str]]
        :return: Union[Response, Type[None]]
        """
        host, method = self.host, POST_METHOD
        if not host:
            _LOG.error('CustodianLicenceManager access data has not been'
                       ' provided.')
            return None

        host = host.strip('/')
        url = host + JOBS_PATH

        payload = {
            SERVICE_TYPE_ATTR: SERVICE_TYPE_RIGHTSIZER,
            JOB_ID: job_id,
            CUSTOMER_ATTR: customer,
            TENANT_ATTR: tenant,
            ALGORITHM_MAPPING_ATTR: algorithm_map
        }

        headers = {
            AUTHORIZATION_PARAM: auth
        }

        return self._send_request(
            url=url, method=method, payload=payload, headers=headers
        )

    def patch_job(self, job_id: str, auth: str, created_at: str = None,
                  started_at: str = None, stopped_at: str = None,
                  status: str = None):
        host = self.host
        if not any([created_at, started_at, stopped_at, status]):
            _LOG.warning('No attributes to update provided. Skipping')
            return
        if not host:
            _LOG.error('CustodianLicenceManager access data has not been'
                       ' provided.')
            return
        url = host.strip('/') + JOBS_PATH
        payload = {
            JOB_ID: job_id,
            CREATED_AT_ATTR: created_at,
            STARTED_AT_ATTR: started_at,
            STOPPED_AT_ATTR: stopped_at,
            STATUS_ATTR: status
        }

        headers = {
            AUTHORIZATION_PARAM: auth
        }

        payload = {k: v for k, v in payload.items()
                   if isinstance(v, (bool, int)) or v}
        return self._send_request(
            url=url, method=PATCH_METHOD, payload=payload, headers=headers
        )

    @classmethod
    def _send_request(
            cls, url: str, method: str, payload: dict,
            headers: Optional[dict] = None
    ) -> Optional[Response]:
        """
        Meant to commence a request to a given url, by deriving a
        proper delegated handler. Apart from that, catches any risen
        request related exception.
        :parameter url: str
        :parameter method:str
        :parameter payload: dict
        :return: Union[Response, Type[None]]
        """
        _injectable_payload = cls._request_payload_injector(method, payload)
        try:
            _input = f'data - {secure_event(_injectable_payload)}'
            if headers:
                _input += f', headers: {headers}'

            _LOG.debug(f'Going to send \'{method}\' request to \'{url}\''
                       f' with the following {_input}.')

            response = request(
                url=url, method=method, headers=headers, **_injectable_payload
            )
            _LOG.debug(f'Response from {url}: {response}')
            return response
        except (RequestException, Exception) as e:
            _LOG.error(f'Error occurred while executing request. Error: {e}')
            return

    @classmethod
    def _request_payload_injector(cls, method: str, payload: dict):
        _map = cls._define_method_injection_map(payload)
        return _map.get(method, payload) if method in _map else None

    @staticmethod
    def retrieve_json(response: Response) -> Union[Dict, Type[None]]:
        _json = None
        try:
            _json = response.json()
        except JSONDecodeError as je:
            _LOG.warning(f'JSON response from \'{response.url}\' not be '
                         f'decoded. An exception has occurred: {je}')
        return _json

    @staticmethod
    def _define_method_injection_map(payload):
        return {POST_METHOD: dict(json=payload),
                PATCH_METHOD: dict(json=payload)}
