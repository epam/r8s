from typing import Optional, Union, List

from commons.constants import MAESTRO_RIGHTSIZER_APPLICATION_TYPE, \
    CHECK_TYPE_APPLICATION
from commons.log_helper import get_logger
from models.application_attributes import ConnectionAttribute
from services.clients.api_gateway_client import ApiGatewayClient
from services.health_checks.abstract_health_check import AbstractHealthCheck
from services.health_checks.check_result import CheckResult, \
    CheckCollectionResult

from services.environment_service import EnvironmentService
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.ssm_service import SSMService
from services.storage_service import StorageService
from services.user_service import CognitoUserService

_LOG = get_logger('application-check')

ERROR_NO_APPLICATION_FOUND = 'NO_APPLICATION'

CHECK_ID_CONNECTION_CHECK = 'CONNECTION_CHECK'
CHECK_ID_STORAGE_CHECK = 'STORAGE_CHECK'


class ApplicationConnectionCheck(AbstractHealthCheck):

    def __init__(self, application_service: RightSizerApplicationService,
                 api_gateway_client: ApiGatewayClient,
                 user_service: CognitoUserService,
                 ssm_service: SSMService,
                 environment_service: EnvironmentService):
        self.application_service = application_service
        self.api_gateway_client = api_gateway_client
        self.user_service = user_service
        self.ssm_service = ssm_service
        self.environment_service = environment_service

        self.r8s_api_host = None
        if not self.environment_service.is_docker():
            self.api_gateway_client.get_r8s_api_host()

    def identifier(self) -> str:
        return CHECK_ID_CONNECTION_CHECK

    def remediation(self) -> Optional[str]:
        return f'Update your application with valid r8s connection data'

    def impact(self) -> Optional[str]:
        return f'You won\'t be able to submit scans through this application'

    def check(self, application) -> Union[List[CheckResult], CheckResult]:
        application_meta = self.application_service.get_application_meta(
            application=application
        )
        connection = getattr(application_meta, 'connection', None)
        if not connection:
            return self.not_ok_result(
                {'error': "\'Connection\' does not exist"}
            )
        if isinstance(connection, ConnectionAttribute):
            connection = connection.as_dict()

        required_keys = ('host', 'port', 'protocol', 'username')
        missing_keys = [key for key in required_keys if key not in connection]
        if missing_keys:
            _LOG.error(f'Missing keys: {missing_keys}')
            return self.not_ok_result(
                details={'error': f'Missing connection attributes: '
                                  f'{", ".join(missing_keys)}'}
            )

        if self.environment_service.is_docker():
            _LOG.debug(f'Host and user credentials checks '
                       f'are skipped in onprem mode')
            return self.ok_result()

        host = connection.get('host')
        if self.r8s_api_host and host != self.r8s_api_host:
            _LOG.error(f'Host {host} does not equals to current host '
                       f'{self.r8s_api_host}')
            return self.not_ok_result(
                details={'error': f'Invalid host. Current host '
                                  f'is \'{self.r8s_api_host}\''}
            )

        username = connection.get('username')
        if not self.user_service.get_user(user_id=username):
            _LOG.error(f'User \'{username}\' does not exist.')
            return self.not_ok_result(
                details={'error': f'User \'{username}\' does not exist.'}
            )

        application_secret = application.secret
        secret_value = self.ssm_service.get_secret_value(
            secret_name=application_secret)
        if not secret_value:
            _LOG.error(f'Application secret \'{application_secret}\' does '
                       f'not exist.')
            return self.not_ok_result(
                details={'error': f'Application secret '
                                  f'\'{application_secret}\' does not exist.'}
            )
        return self.ok_result()


class ApplicationStorageCheck(AbstractHealthCheck):

    def __init__(self, application_service: RightSizerApplicationService,
                 storage_service: StorageService):
        self.application_service = application_service
        self.storage_service = storage_service

    def identifier(self) -> str:
        return CHECK_ID_STORAGE_CHECK

    def remediation(self) -> Optional[str]:
        return f'Update your application with valid storage name'

    def impact(self) -> Optional[str]:
        return f'You won\'t be able to submit scans through this application'

    def check(self, application) -> Union[List[CheckResult], CheckResult]:
        application_meta = self.application_service.get_application_meta(
            application=application)

        errors = []

        input_storage = getattr(application_meta, 'input_storage', None)
        if not input_storage or not self.storage_service.get(input_storage):
            errors.append(f'Input storage \'{input_storage}\' does not exist.')

        output_storage = getattr(application_meta, 'output_storage', None)
        if not output_storage or not self.storage_service.get(output_storage):
            errors.append(f'Input storage \'{input_storage}\' does not exist.')

        _LOG.debug(f'Errors: {errors}')
        if errors:
            return self.not_ok_result(details={'errors': ", ".join(errors)})
        return self.ok_result()


class ApplicationCheckHandler:
    def __init__(self, application_service: RightSizerApplicationService,
                 api_gateway_client: ApiGatewayClient,
                 user_service: CognitoUserService,
                 ssm_service: SSMService,
                 storage_service: StorageService,
                 environment_service: EnvironmentService):
        self.application_service = application_service
        self.api_gateway_client = api_gateway_client
        self.user_service = user_service
        self.ssm_service = ssm_service
        self.storage_service = storage_service
        self.environment_service = environment_service

        self.checks = [
            ApplicationConnectionCheck(application_service=application_service,
                                       api_gateway_client=api_gateway_client,
                                       user_service=user_service,
                                       ssm_service=ssm_service,
                                       environment_service=environment_service),
            ApplicationStorageCheck(application_service=application_service,
                                    storage_service=storage_service)
        ]

    def check(self):
        _LOG.debug(f'Listing applications')
        applications = self.application_service.list(
            _type=MAESTRO_RIGHTSIZER_APPLICATION_TYPE, deleted=False)
        if not applications:
            _LOG.warning(f'No active RIGHTSIZER applications found')
            result = CheckCollectionResult(
                id='NONE',
                type=CHECK_TYPE_APPLICATION,
                details=[]
            )
            return result.as_dict()

        result = []

        for application in applications:
            application_checks = []
            for check_instance in self.checks:
                check_result = check_instance.check(application=application)
                application_checks.append(check_result)

            application_result = CheckCollectionResult(
                id=application.application_id,
                type=CHECK_TYPE_APPLICATION,
                details=application_checks
            )

            result.append(application_result.as_dict())
        return result
