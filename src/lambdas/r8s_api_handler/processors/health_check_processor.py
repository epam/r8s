from modular_sdk.services.tenant_service import TenantService

from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_OK_CODE
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import TYPES_ATTR, CHECK_TYPES, \
    CHECK_TYPE_APPLICATION, CHECK_TYPE_PARENT, CHECK_TYPE_STORAGE, \
    CHECK_TYPE_SHAPE, CHECK_TYPE_SHAPE_UPDATE_DATE, \
    CHECK_TYPE_OPERATION_MODE, POST_METHOD
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.algorithm_service import AlgorithmService
from services.clients.api_gateway_client import ApiGatewayClient
from services.clients.s3 import S3Client
from services.environment_service import EnvironmentService
from services.health_checks.application_check import ApplicationCheckHandler
from services.health_checks.operation_mode_check import \
    OperationModeCheckHandler
from services.health_checks.parent_check import ParentCheckHandler
from services.health_checks.shape_check import ShapeCheckHandler
from services.health_checks.shape_update_date_check import \
    ShapeUpdateDateCheckHandler
from services.health_checks.storage_check import StorageCheckHandler
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService
from services.setting_service import SettingsService
from services.shape_price_service import ShapePriceService
from services.shape_service import ShapeService
from services.ssm_service import SSMService
from services.storage_service import StorageService
from services.user_service import CognitoUserService

_LOG = get_logger('r8s-health-check-processor')


class HealthCheckProcessor(AbstractCommandProcessor):
    def __init__(self,
                 application_service: RightSizerApplicationService,
                 tenant_service: TenantService,
                 shape_service: ShapeService,
                 shape_price_service: ShapePriceService,
                 parent_service: RightSizerParentService,
                 storage_service: StorageService,
                 ssm_service: SSMService,
                 api_gateway_client: ApiGatewayClient,
                 user_service: CognitoUserService,
                 algorithm_service: AlgorithmService,
                 settings_service: SettingsService,
                 s3_client: S3Client,
                 environment_service: EnvironmentService):
        self.application_service = application_service
        self.tenant_service = tenant_service
        self.shape_service = shape_service
        self.shape_price_service = shape_price_service
        self.parent_service = parent_service
        self.storage_service = storage_service
        self.api_gateway_client = api_gateway_client
        self.ssm_service = ssm_service
        self.user_service = user_service
        self.algorithm_service = algorithm_service
        self.s3_client = s3_client
        self.settings_service = settings_service
        self.environment_service = environment_service

        self.method_to_handler = {
            POST_METHOD: self.post,
        }
        self.check_type_handler_mapping = {
            CHECK_TYPE_APPLICATION: self._init_application_check_handler,
            CHECK_TYPE_PARENT: self._init_parent_check_handler,
            CHECK_TYPE_STORAGE: self._init_storage_check_handler,
            CHECK_TYPE_SHAPE: self._init_shape_check_handler,
            CHECK_TYPE_OPERATION_MODE: self._init_operation_mode_handler,
            CHECK_TYPE_SHAPE_UPDATE_DATE: self._init_shape_update_date_handler
        }

    def process(self, event) -> dict:
        method = event.get(PARAM_HTTP_METHOD)
        command_handler = self.method_to_handler.get(method)
        if not command_handler:
            message = f'Unable to handle command {method} in ' \
                      f'job processor'
            _LOG.error(f'status code: {RESPONSE_BAD_REQUEST_CODE}, '
                       f'process error: {message}')
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        return command_handler(event=event)

    def post(self, event):
        _LOG.debug(f'Health Check event: {event}')

        check_types = event.get(TYPES_ATTR)
        if check_types:
            _LOG.debug(f'Filtering check types \'{check_types}\'')
            checks_to_execute = [check.upper() for check in check_types
                                 if check.upper() in CHECK_TYPES]
        else:
            _LOG.debug(f'Going to execute all available checks: {CHECK_TYPES}')
            checks_to_execute = list(CHECK_TYPES)

        if not checks_to_execute:
            _LOG.error(f'Invalid types specified. Valid values are: '
                       f'\'{", ".join(CHECK_TYPES)}\'')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Invalid types specified. Valid values are: '
                        f'\'{", ".join(CHECK_TYPES)}\''
            )

        result = []
        for check_type in checks_to_execute:
            handler_instance = self.check_type_handler_mapping.get(check_type)
            if not handler_instance:
                _LOG.debug(f'No handler found for check: \'{check_type}\'')
                continue
            check_result = handler_instance().check()
            _LOG.debug(f'Check \'{check_type}\' result: {check_result}')
            result.extend(check_result)

        _LOG.debug(f'Response: {result}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=result
        )

    def _init_application_check_handler(self):
        return ApplicationCheckHandler(
            application_service=self.application_service,
            api_gateway_client=self.api_gateway_client,
            user_service=self.user_service,
            ssm_service=self.ssm_service,
            storage_service=self.storage_service,
            environment_service=self.environment_service
        )

    def _init_parent_check_handler(self):
        return ParentCheckHandler(
            application_service=self.application_service,
            parent_service=self.parent_service,
            algorithm_service=self.algorithm_service,
            tenant_service=self.tenant_service
        )

    def _init_storage_check_handler(self):
        return StorageCheckHandler(
            storage_service=self.storage_service,
            s3_client=self.s3_client
        )

    def _init_shape_check_handler(self):
        return ShapeCheckHandler(
            shape_service=self.shape_service,
            shape_price_service=self.shape_price_service
        )

    def _init_operation_mode_handler(self):
        return OperationModeCheckHandler(
            application_service=self.application_service,
            parent_service=self.parent_service,
            tenant_service=self.tenant_service
        )

    def _init_shape_update_date_handler(self):
        return ShapeUpdateDateCheckHandler(
            settings_service=self.settings_service
        )
