import json
from typing import TypedDict

from modular_sdk.commons import ModularException
from modular_sdk.commons.constants import ApplicationType, SUCCESS_STATUS
from modular_sdk.models.application import Application
from modular_sdk.modular import Modular
from modular_sdk.services.impl.maestro_credentials_service import (
    MaestroCredentialsService,
    RabbitMQCredentials,
)
from modular_sdk.services.impl.maestro_rabbit_transport_service import (
    MaestroRabbitConfig,
    MaestroRabbitMQTransport,
)

from commons.log_helper import get_logger

_LOG = get_logger(__name__)

RIGHTSIZER_RABBITMQ_TYPE = 'RIGHTSIZER_RABBITMQ'
GET_USER_POSITIONS_COMMAND = 'GET_USER_POSITIONS'


class UserPositionMapping(TypedDict):
    tenant: str
    positions: list[str]


class RabbitMQService:
    def __init__(self, modular_client: Modular):
        self._modular_client = modular_client
        self._customer_rabbit_cache: dict[str, MaestroRabbitMQTransport] = {}

    def get_rabbitmq_application(
        self, customer: str, legacy: bool = False
    ) -> Application | None:
        aps = self._modular_client.application_service()
        app_type = ApplicationType.RABBITMQ.value if legacy else RIGHTSIZER_RABBITMQ_TYPE
        _LOG.debug(f'Getting {app_type} application for customer: {customer}')
        return next(
            aps.list(customer=customer, _type=app_type, deleted=False, limit=1),
            None,
        )

    def build_maestro_mq_transport(
        self, application: Application
    ) -> MaestroRabbitMQTransport | None:
        mcs = MaestroCredentialsService.build()
        creds: RabbitMQCredentials = mcs.get_by_application(application)
        if not creds:
            return None
        maestro_config = MaestroRabbitConfig(
            request_queue=creds.request_queue,
            response_queue=creds.response_queue,
            rabbit_exchange=creds.rabbit_exchange,
            sdk_access_key=creds.sdk_access_key,
            sdk_secret_key=creds.sdk_secret_key,
            maestro_user=creds.maestro_user,
        )
        return self._modular_client.rabbit_transport_service(
            connection_url=creds.connection_url,
            config=maestro_config,
            timeout=30,
        )

    def get_customer_rabbitmq(
        self, customer: str
    ) -> MaestroRabbitMQTransport | None:
        if rabbitmq := self._customer_rabbit_cache.get(customer):
            _LOG.debug(f'RabbitMQ transport for {customer!r} found in cache')
            return rabbitmq

        application = self.get_rabbitmq_application(customer)
        if not application:
            application = self.get_rabbitmq_application(customer, legacy=True)
            if not application:
                _LOG.warning(
                    f'No {RIGHTSIZER_RABBITMQ_TYPE} or '
                    f'{ApplicationType.RABBITMQ.value} application found '
                    f'for customer {customer!r}'
                )
                return None
            _LOG.warning(
                f'Using legacy {ApplicationType.RABBITMQ.value} application '
                f'for customer {customer!r}'
            )

        rabbitmq = self.build_maestro_mq_transport(application)
        if not rabbitmq:
            _LOG.warning(
                f'Could not build RabbitMQ transport for customer {customer!r}'
            )
            return None
        self._customer_rabbit_cache[customer] = rabbitmq
        return rabbitmq

    def get_user_positions(
        self, customer: str, claims: dict
    ) -> list[UserPositionMapping] | None:
        rabbitmq = self.get_customer_rabbitmq(customer)
        if not rabbitmq:
            _LOG.warning(
                f'No RabbitMQ configured for customer {customer!r}, '
                f'cannot fetch user positions from Maestro'
            )
            return None
        email = claims.get('email')
        if not email:
            _LOG.warning(
                'MCP token does not contain email, '
                'cannot fetch user positions from Maestro'
            )
            return None
        _LOG.info(
            f'Sending {GET_USER_POSITIONS_COMMAND} to RabbitMQ '
            f'for user {email!r}'
        )
        try:
            code, status, data = rabbitmq.send_sync(
                command_name=GET_USER_POSITIONS_COMMAND,
                parameters={'email': email},
                is_flat_request=False,
                async_request=False,
                secure_parameters=None,
            )
        except ModularException:
            _LOG.exception(
                f'Could not send {GET_USER_POSITIONS_COMMAND} to Maestro'
            )
            return None
        _LOG.debug(
            f'{GET_USER_POSITIONS_COMMAND} response: '
            f'code={code}, status={status}'
        )
        if status != SUCCESS_STATUS:
            _LOG.warning(
                f'Non-successful response from Maestro for '
                f'{GET_USER_POSITIONS_COMMAND}: {code} {status}'
            )
            return None
        try:
            raw = json.loads(data) if isinstance(data, str) else data
        except json.JSONDecodeError:
            _LOG.warning(
                f'{GET_USER_POSITIONS_COMMAND} returned invalid JSON: {data}'
            )
            return None
        mappings = raw.get('mappings') if isinstance(raw, dict) else None
        if not isinstance(mappings, list):
            _LOG.warning(
                f'{GET_USER_POSITIONS_COMMAND} returned unexpected '
                f'mappings type: {type(mappings).__name__}'
            )
            return None
        return mappings
