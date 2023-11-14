from typing import List, Dict, Optional
from datetime import datetime, timedelta
import re

from commons.constants import RESPONSE_OK_CODE, \
    ITEMS_PARAM, MESSAGE_PARAM, CLIENT_TOKEN_ATTR, \
    KID_ATTR, ALG_ATTR, RESPONSE_FORBIDDEN_CODE, \
    RESPONSE_RESOURCE_NOT_FOUND_CODE, TOKEN_ATTR, EXPIRATION_ATTR
from commons.log_helper import get_logger
from models.shape_price import DEFAULT_CUSTOMER
from services.environment_service import EnvironmentService
from services.ssm_service import SSMService
from services.clients.license_manager import LicenseManagerClient
from services.token_service import TokenService
from commons.time_helper import utc_datetime

_LOG = get_logger(__name__)

GENERIC_JOB_LICENSING_ISSUE = 'Job:\'{id}\' could not be granted by the ' \
                              'License Manager Service.'
SSM_LM_TOKEN_KEY = 'r8s_lm_auth_token_{customer}'


class BalanceExhaustion(Exception):
    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return self.message


class InaccessibleAssets(Exception):
    def __init__(
            self, message: str, assets: Dict[str, List[str]],
            hr_sep: str, ei_sep: str, i_sep: str, i_wrap: Optional[str] = None
    ):
        self._assets = self._dissect(
            message=message, assets=assets, hr_sep=hr_sep, ei_sep=ei_sep,
            i_sep=i_sep, i_wrap=i_wrap
        )

    @staticmethod
    def _dissect(
            message: str, assets: Dict[str, List[str]],
            hr_sep: str, ei_sep: str, i_sep: str, i_wrap: Optional[str] = None
    ):
        """
        Dissects License Manager response of entity(ies)-not-found message.
        Such as: TenantLicense or Ruleset(s):$id(s) - $reason.
        param message: str - maintains the raw response message
        param assets: Dict[str, List[str]] - source of assets to
        param hr_sep: str - head-reason separator, within the response message
        param ei_sep: str - entity type - id(s) separator, within the head of
        the message
        param i_sep: str - separator of entity-identifier(s), within the raw
        id(s).
        param i_wrap: Optional[str] - quote-type wrapper of each identifier.
        """
        each_template = 'Each of {} license-subscription'
        head, *_ = message.rsplit(hr_sep, maxsplit=1)
        head = head.strip(' ')
        if not head:
            _LOG.error(f'Response message is not separated by a \'{hr_sep}\'.')
            return

        entity, *ids = head.split(ei_sep, maxsplit=1)
        ids = ids[0] if len(ids) == 1 else ''
        if 's' in entity and entity.index('s') == len(entity) - 1:
            ids = ids.split(i_sep)

        ids = [each.strip(i_wrap or '') for each in ids.split(i_sep)]

        if 'TenantLicense' in entity:
            ids = [
                asset
                for tlk in ids
                if tlk in assets
                for asset in assets[tlk] or [each_template.format(tlk)]
            ]

        return ids

    def __str__(self):
        head = 'Ruleset'

        if len(self._assets) > 1:
            head += 's'
        scope = ', '.join(f'"{each}"' for each in self._assets)
        reason = 'are' if len(self._assets) > 1 else 'is'
        reason += ' no longer accessible'
        return f'{head}:{scope} - {reason}.'

    def __iter__(self):
        return iter(self._assets)


class LicenseManagerService:

    def __init__(
            self, license_manager_client: LicenseManagerClient,
            token_service: TokenService,
            environment_service: EnvironmentService,
            ssm_service: SSMService
    ):
        self.license_manager_client = license_manager_client
        self.token_service = token_service
        self.environment_service = environment_service
        self.ssm_service = ssm_service

    def update_job_in_license_manager(
            self, job_id: str, customer: str = None, created_at: str = None,
            started_at: str = None, stopped_at: str = None, status: str = None
    ):
        auth = self._get_client_token(
            customer=customer
        )
        if not auth:
            _LOG.warning('Client authorization token could be established.')
            return None

        response = self.license_manager_client.patch_job(
            job_id=job_id, created_at=created_at, started_at=started_at,
            stopped_at=stopped_at, status=status, auth=auth
        )

        if response and response.status_code == RESPONSE_OK_CODE:
            return self.license_manager_client.retrieve_json(response)
        return

    def instantiate_licensed_job_dto(
            self, job_id: str, customer: str, tenant: str,
            algorithm_map: Dict[str, List[str]]
    ):
        """
        Mandates licensed Job data transfer object retrieval,
        by successfully interacting with LicenseManager providing the
        following parameters.

        :parameter job_id: str
        :parameter customer: str
        :parameter tenant: str
        :parameter algorithm_map: Union[Type[None], List[str]]

        :raises: InaccessibleAssets, given the requested content is not
        accessible
        :raises: BalanceExhaustion, given the job-balance has been exhausted
        :return: Optional[Dict]
        """
        auth = self._get_client_token(
            customer=customer
        )
        if not auth:
            _LOG.warning('Client authorization token could be established.')
            return None
        response = self.license_manager_client.post_job(
            job_id=job_id, customer=customer, tenant=tenant,
            algorithm_map=algorithm_map, auth=auth
        )
        if response is None:
            return

        decoded = self.license_manager_client.retrieve_json(response) or {}
        if response.status_code == RESPONSE_OK_CODE:
            items = decoded.get(ITEMS_PARAM, [])
            if len(items) != 1:
                _LOG.warning(f'Unexpected License Manager response: {items}.')
                item = None
            else:
                item = items.pop()
            return item

        else:
            message = decoded.get(MESSAGE_PARAM)
            if response.status_code == RESPONSE_RESOURCE_NOT_FOUND_CODE:
                raise InaccessibleAssets(
                    message=message, assets=algorithm_map,
                    hr_sep='-', ei_sep=':', i_sep=', ', i_wrap='\''
                )
            elif response.status_code == RESPONSE_FORBIDDEN_CODE:
                raise BalanceExhaustion(message)

    def _get_client_token(self, customer: str = None):
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
    def _default_instance(value, _type: type, *args, **kwargs):
        return value if isinstance(value, _type) else _type(*args, **kwargs)

    @staticmethod
    def get_ssm_auth_token_name(customer: str = None):
        if not customer:
            customer = DEFAULT_CUSTOMER
        customer = re.sub(r"[\s-]", '_', customer.lower())
        return SSM_LM_TOKEN_KEY.format(customer=customer)
