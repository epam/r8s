import re

from commons import RESPONSE_OK_CODE
from commons.constants import KID_ATTR, ALG_ATTR, CLIENT_TOKEN_ATTR, \
    TOKEN_ATTR, EXPIRATION_ATTR
from commons.log_helper import get_logger
from services.clients.license_manager import LicenseManagerClient
from services.environment_service import EnvironmentService
from services.ssm_service import SSMService
from services.token_service import TokenService
from typing import Optional, List

from commons.time_helper import utc_datetime
from datetime import timedelta, datetime
from requests.exceptions import RequestException, ConnectionError, Timeout

CHECK_PERMISSION_PATH = '/jobs/check-permission'
JOB_PATH = '/jobs'
SET_CUSTOMER_ACTIVATION_DATE_PATH = '/customers/set-activation-date'

CONNECTION_ERROR_MESSAGE = f'Can\'t establish connection with ' \
                           f'License Manager. Please contact the support team.'

CLIENT_TYPE_SAAS = 'SAAS'
CLIENT_TYPE_ONPREM = 'ONPREM'

STATUS_CODE_ATTR = 'status_code'
SSM_LM_TOKEN_KEY = 'r8s_lm_auth_token_{customer}'

_LOG = get_logger(__name__)


class LicenseManagerService:
    def __init__(self, license_manager_client: LicenseManagerClient,
                 token_service: TokenService, ssm_service: SSMService,
                 environment_service: EnvironmentService):
        self.license_manager_client = license_manager_client
        self.token_service = token_service
        self.ssm_service = ssm_service
        self.environment_service = environment_service

    def synchronize_license(self, license_key: str, customer: str):
        """
        Mandates License synchronization request, delegated to prepare
        a rightsizer service-token, given the Service is the SaaS installation.
        For any request related exception, returns the respective instance
        to handle on.
        :parameter license_key: str,
        :parameter customer: str,
        :return: Union[Response, ConnectionError, RequestException]
        """
        auth = self._get_client_token(
            customer=customer
        )
        if not auth:
            _LOG.warning('Client authorization token could be established.')
            return None

        try:
            response = self.license_manager_client.license_sync(
                license_key=license_key, auth=auth
            )

        except (ConnectionError, Timeout) as _ce:
            _LOG.warning(f'Connection related error has occurred: {_ce}.')
            _error = 'Connection to LicenseManager can not be established.'
            response = ConnectionError(CONNECTION_ERROR_MESSAGE)

        except RequestException as _re:
            _LOG.warning(f'An exception occurred, during the request: {_re}.')
            response = RequestException(CONNECTION_ERROR_MESSAGE)

        return response

    def get_allowance_map(self, customer: str, tenants: List[str],
                          tenant_license_keys: List[str]):
        auth = self._get_client_token(
            customer=customer
        )
        if not auth:
            _LOG.warning('Client authorization token could be established.')
            return None

        response = self.license_manager_client.job_get_allowance_map(
            customer=customer, tenants=tenants,
            tenant_license_keys=tenant_license_keys, auth=auth
        )
        if not response.status_code == RESPONSE_OK_CODE:
            return
        _json = self.license_manager_client.retrieve_json(response=response)
        _json = _json or dict()
        response = _json.get('items') or []
        return response[0] if len(response) == 1 else {}

    def update_job_in_license_manager(self, job_id, created_at, started_at,
                                      stopped_at, status, customer):

        auth = self._get_client_token(
            customer=customer
        )
        if not auth:
            _LOG.warning('Client authorization token could be established.')
            return None

        response = self.license_manager_client.update_job(
            job_id=job_id, created_at=created_at, started_at=started_at,
            stopped_at=stopped_at, status=status, auth=auth
        )

        return getattr(response, STATUS_CODE_ATTR, None)

    def activate_tenant(self, customer: str, tenant: str,
                        tlk: str) -> Optional[dict]:
        auth = self._get_client_token(
            customer=customer
        )
        if not auth:
            _LOG.warning('Client authorization token could be established.')
            return None

        _empty_response = {}
        response = self.license_manager_client.activate_tenant(
            tenant=tenant, tlk=tlk, auth=auth
        )
        if getattr(response, STATUS_CODE_ATTR, None) != RESPONSE_OK_CODE:
            return _empty_response

        _json = self.license_manager_client.retrieve_json(response=response)
        _json = _json or dict()
        response = _json.get('items') or []
        return response[0] if len(response) == 1 else {}

    def activate_customer(self, customer: str, tlk: str) -> Optional[dict]:
        auth = self._get_client_token(customer=customer)
        if not auth:
            _LOG.warning('Client authorization token could be established.')
            return None
        _empty_response = {}
        response = self.license_manager_client.activate_customer(
            customer=customer, tlk=tlk, auth=auth
        )
        if getattr(response, STATUS_CODE_ATTR, None) != RESPONSE_OK_CODE:
            return _empty_response

        _json = self.license_manager_client.retrieve_json(response=response)
        _json = _json or dict()
        response = _json.get('items') or []
        return response[0] if len(response) == 1 else {}

    def _get_client_token(self, customer: str):
        secret_name = self.get_ssm_auth_token_name(customer=customer)
        cached_auth = self.ssm_service.get_secret_value(
            secret_name=secret_name) or {}
        cached_token = cached_auth.get(TOKEN_ATTR)
        cached_token_expiration = cached_auth.get(EXPIRATION_ATTR)

        if (cached_token and cached_token_expiration and
                not self.is_expired(expiration=cached_token_expiration)):
            _LOG.debug(f'Using cached lm auth token.')
            return cached_token
        _LOG.debug(f'Cached lm auth token are not found or expired. '
                   f'Generating new token.')
        lifetime_minutes = self.environment_service.lm_token_lifetime_minutes()
        token = self._generate_client_token(
            expires=dict(
                minutes=lifetime_minutes
            ),
            customer=customer
        )
        if not token:
            return

        _LOG.debug(f'Updating lm auth token in SSM.')
        expiration_timestamp = int((datetime.utcnow() +
                                    timedelta(minutes=30)).timestamp())
        secret_data = {
            EXPIRATION_ATTR: expiration_timestamp,
            TOKEN_ATTR: token
        }
        self.ssm_service.create_secret_value(
            secret_name=secret_name,
            secret_value=secret_data
        )
        return token

    @staticmethod
    def is_expired(expiration: int):
        now = int(datetime.utcnow().timestamp())
        return now >= expiration

    def _generate_client_token(self, expires: dict, customer: str):
        """
        Delegated to derive a rightsizer-service-token, encoding any given
        payload key-value pairs into the claims.
        :parameter expires: dict, meant to store timedelta kwargs
        :return: Union[str, Type[None]]
        """
        token_type = CLIENT_TOKEN_ATTR
        key_data = self.license_manager_client.client_key_data
        kid, alg = key_data.get(KID_ATTR), key_data.get(ALG_ATTR)
        if not (kid and alg):
            _LOG.warning('LicenseManager Client-Key data is missing.')
            return

        t_head = f'\'{token_type}\''
        encoder = self.token_service.derive_encoder(
            token_type=CLIENT_TOKEN_ATTR,
            customer=customer
        )

        if not encoder:
            return None

        # Establish a kid reference to a key.
        encoder.prk_id = self.derive_client_private_key_id(
            kid=kid
        )
        _LOG.info(f'{t_head} - {encoder.prk_id} private-key id has been '
                  f'assigned.')

        encoder.kid = kid
        _LOG.info(f'{t_head} - {encoder.kid} token \'kid\' has been assigned.')

        encoder.alg = alg
        _LOG.info(f'{t_head} - {encoder.alg} token \'alg\' has been assigned.')

        encoder.expire(utc_datetime() + timedelta(**expires))
        try:
            token = encoder.product
        except (Exception, BaseException) as e:
            _LOG.error(f'{t_head} could not be encoded, due to: {e}.')
            token = None

        if not token:
            _LOG.warning(f'{t_head} token could not be encoded.')
        return token

    @staticmethod
    def derive_client_private_key_id(kid: str):
        return f'cs_lm_client_{kid}_prk'

    @staticmethod
    def get_ssm_auth_token_name(customer: str):
        customer = re.sub(r"[\s-]", '_', customer.lower())
        return SSM_LM_TOKEN_KEY.format(customer=customer)
