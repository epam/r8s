import os

from modular_sdk.services.customer_service import CustomerService
from modular_sdk.services.tenant_service import TenantService

from commons import build_response, RESPONSE_SERVICE_UNAVAILABLE_CODE, \
    ApplicationException
from commons.constants import ENV_SERVICE_MODE
from connections.batch_extension.base_job_client import BaseBatchClient
from commons.log_helper import get_logger
from services.algorithm_service import AlgorithmService
from services.clients.api_gateway_client import ApiGatewayClient
from services.clients.cognito import CognitoClient
from services.clients.lambda_func import LambdaClient
from services.clients.s3 import S3Client
from services.customer_preferences_service import CustomerPreferencesService
from services.environment_service import EnvironmentService
from services.job_service import JobService
from services.rbac.access_control_service import AccessControlService
from services.rbac.iam_service import IamService
from services.recommendation_history_service import \
    RecommendationHistoryService
from services.resize_service import ResizeService
from services.setting_service import SettingsService
from services.shape_price_service import ShapePriceService
from services.shape_rule_filter_service import ShapeRulesFilterService
from services.shape_service import ShapeService
from services.ssm_service import SSMService
from services.storage_service import StorageService
from services.user_service import CognitoUserService

SERVICE_MODE = os.getenv(ENV_SERVICE_MODE)
is_docker = SERVICE_MODE == 'docker'

_LOG = get_logger('service-provider')


class ServiceProvider:
    class __Services:
        # clients
        __s3_conn = None
        __ssm_conn = None
        __cognito = None
        __batch = None
        __api_gateway_client = None
        __lambda_client = None
        __license_manager_conn = None
        __standalone_key_management = None

        # services
        __environment_service = None
        __ssm_service = None
        __algorithm_service = None
        __storage_service = None
        __settings_service = None
        __user_service = None
        __iam_service = None
        __access_control_service = None
        __job_service = None
        __report_service = None
        __customer_service = None
        __tenant_service = None
        __shape_service = None
        __shape_price_service = None
        __shape_rules_filter_service = None
        __rightsizer_application_service = None
        __rightsizer_parent_service = None
        __recommendation_history_service = None
        __maestro_rabbitmq_service = None
        __customer_preferences_service = None
        __resize_service = None
        __token_service = None
        __license_manager_service = None
        __key_management_service = None
        __license_service = None

        def __str__(self):
            return id(self)

        # clients
        def s3(self):
            if not self.__s3_conn:
                self.__s3_conn = S3Client(
                    region=self.environment_service().aws_region())
            return self.__s3_conn

        def ssm(self):
            if not self.__ssm_conn:
                from services.clients.ssm import SSMClient, VaultSSMClient
                _env = self.environment_service()
                if _env.is_docker():
                    self.__ssm_conn = VaultSSMClient(environment_service=_env)
                else:
                    self.__ssm_conn = SSMClient(environment_service=_env)
            return self.__ssm_conn

        def cognito(self):
            if not self.__cognito:
                if self.environment_service().is_docker():
                    from connections.auth_extension.cognito_to_jwt_adapter \
                        import MongoAndSSMAuthClient
                    self.__cognito = MongoAndSSMAuthClient(
                        ssm_service=self.ssm_service()
                    )
                else:
                    self.__cognito = CognitoClient(
                        environment_service=self.environment_service()
                    )
            return self.__cognito

        def batch(self):
            if not self.__batch:
                self.__batch = BaseBatchClient(
                    environment_service=self.environment_service())
            return self.__batch

        def api_gateway_client(self):
            if not self.__api_gateway_client:
                self.__api_gateway_client = ApiGatewayClient(
                    region=self.environment_service().aws_region())
            return self.__api_gateway_client

        def lambda_client(self):
            if not self.__lambda_client:
                self.__lambda_client = LambdaClient(
                    environment_service=self.environment_service())
            return self.__lambda_client

        def license_manager_client(self):
            if not self.__license_manager_conn:
                from services.clients.license_manager import \
                    LicenseManagerClient
                self.__license_manager_conn = LicenseManagerClient(
                    setting_service=self.settings_service()
                )
            return self.__license_manager_conn

        def standalone_key_management(self):
            if not self.__standalone_key_management:
                from services.clients.standalone_key_management import \
                    StandaloneKeyManagementClient
                self.__standalone_key_management = \
                    StandaloneKeyManagementClient(ssm_client=self.ssm())
            return self.__standalone_key_management

        # services

        def environment_service(self):
            if not self.__environment_service:
                self.__environment_service = EnvironmentService()
            return self.__environment_service

        def ssm_service(self):
            if not self.__ssm_service:
                self.__ssm_service = SSMService(client=self.ssm())
            return self.__ssm_service

        def algorithm_service(self):
            if not self.__algorithm_service:
                self.__algorithm_service = AlgorithmService()
            return self.__algorithm_service

        def storage_service(self):
            if not self.__storage_service:
                self.__storage_service = StorageService(
                    s3_client=self.s3()
                )
            return self.__storage_service

        def user_service(self):
            if not self.__user_service:
                self.__user_service = CognitoUserService(
                    client=self.cognito())
            return self.__user_service

        def settings_service(self):
            if not self.__settings_service:
                self.__settings_service = SettingsService()
            return self.__settings_service

        def iam_service(self):
            if not self.__iam_service:
                self.__iam_service = IamService()
            return self.__iam_service

        def access_control_service(self):
            if not self.__access_control_service:
                self.__access_control_service = AccessControlService(
                    iam_service=self.iam_service(),
                    user_service=self.user_service(),
                    setting_service=self.settings_service()
                )
            return self.__access_control_service

        def job_service(self):
            if not self.__job_service:
                self.__job_service = JobService(
                    environment_service=self.environment_service(),
                    batch_client=self.batch()
                )
            return self.__job_service

        def report_service(self):
            if not self.__report_service:
                from services.report_service import ReportService
                self.__report_service = ReportService(
                    storage_service=self.storage_service(),
                    parent_service=self.rightsizer_parent_service(),
                    application_service=self.rightsizer_application_service()
                )
            return self.__report_service

        def customer_service(self):
            if not self.__customer_service:
                self.__customer_service = CustomerService()
            return self.__customer_service

        def tenant_service(self):
            if not self.__tenant_service:
                self.__tenant_service = TenantService()
            return self.__tenant_service

        def shape_service(self):
            if not self.__shape_service:
                self.__shape_service = ShapeService()
            return self.__shape_service

        def shape_price_service(self):
            if not self.__shape_price_service:
                self.__shape_price_service = ShapePriceService()
            return self.__shape_price_service

        def shape_rules_filter_service(self):
            if not self.__shape_rules_filter_service:
                self.__shape_rules_filter_service = ShapeRulesFilterService()
            return self.__shape_rules_filter_service

        def rightsizer_application_service(self):
            from services.rightsizer_application_service import \
                RightSizerApplicationService
            if not self.__rightsizer_application_service:
                self.__rightsizer_application_service = \
                    RightSizerApplicationService(
                        customer_service=self.customer_service(),
                        ssm_service=self.ssm_service()
                    )
            return self.__rightsizer_application_service

        def rightsizer_parent_service(self):
            from services.rightsizer_parent_service import \
                RightSizerParentService
            if not self.__rightsizer_parent_service:
                self.__rightsizer_parent_service = \
                    RightSizerParentService(
                        tenant_service=self.tenant_service(),
                        customer_service=self.customer_service(),
                        environment_service=self.environment_service()
                    )
            return self.__rightsizer_parent_service

        def recommendation_history_service(self):
            if not self.__recommendation_history_service:
                self.__recommendation_history_service = \
                    RecommendationHistoryService()
            return self.__recommendation_history_service

        def maestro_rabbitmq_service(self):
            if is_docker:
                _LOG.error(f'RabbitMQ service is not available in docker mode')
                return
            if not self.__maestro_rabbitmq_service:
                from modular_sdk.modular import Modular
                from modular_sdk.services.impl.maestro_rabbit_transport_service import \
                    MaestroRabbitConfig
                from modular_sdk.services.impl.maestro_credentials_service import \
                    RabbitMQCredentials, MaestroCredentialsService
                app_id = self.environment_service().get_rabbitmq_application_id()
                if not app_id:
                    return build_response(
                        code=RESPONSE_SERVICE_UNAVAILABLE_CODE,
                        content='The service is not configured correctly. '
                                'Please contact the support team.'
                    )
                application = self.rightsizer_application_service(). \
                    get_application_by_id(
                        application_id=app_id
                    )
                if not application:
                    return build_response(
                        code=RESPONSE_SERVICE_UNAVAILABLE_CODE,
                        content='The service is not configured correctly. '
                                'Please contact the support team.'
                    )
                modular = Modular()
                credentials_service = MaestroCredentialsService.build(
                    ssm_service=modular.ssm_service()
                )
                creds: RabbitMQCredentials = credentials_service.\
                    get_by_application(application)
                if not creds:
                    _LOG.error(f'Failed to get RabbitMQ credentials from '
                               f'application {application.application_id}.')
                    raise ApplicationException(
                        code=RESPONSE_SERVICE_UNAVAILABLE_CODE,
                        content=f'Failed to get RabbitMQ credentials from '
                                f'application {application.application_id}.'
                    )
                maestro_config = MaestroRabbitConfig(
                    request_queue=creds.request_queue,
                    response_queue=creds.response_queue,
                    rabbit_exchange=creds.rabbit_exchange,
                    sdk_access_key=creds.sdk_access_key,
                    sdk_secret_key=creds.sdk_secret_key,
                    maestro_user=creds.maestro_user
                )
                self.__maestro_rabbitmq_service = modular. \
                    rabbit_transport_service(
                        connection_url=creds.connection_url,
                        config=maestro_config
                )
            return self.__maestro_rabbitmq_service

        def customer_preferences_service(self):
            if not self.__customer_preferences_service:
                self.__customer_preferences_service = \
                    CustomerPreferencesService()
            return self.__customer_preferences_service

        def resize_service(self):
            if not self.__resize_service:
                self.__resize_service = ResizeService(
                    shape_service=self.shape_service(),
                    customer_preferences_service=self.customer_preferences_service()
                )
            return self.__resize_service

        def token_service(self):
            if not self.__token_service:
                from services.token_service import TokenService
                self.__token_service = TokenService(
                    client=self.standalone_key_management()
                )
            return self.__token_service

        def license_manager_service(self):
            if not self.__license_manager_service:
                from services.license_manager_service import \
                    LicenseManagerService
                self.__license_manager_service = LicenseManagerService(
                    license_manager_client=self.license_manager_client(),
                    token_service=self.token_service(),
                    ssm_service=self.ssm_service(),
                    environment_service=self.environment_service()
                )
            return self.__license_manager_service

        def key_management_service(self):
            if not self.__key_management_service:
                from services.key_management_service import \
                    KeyManagementService
                self.__key_management_service = KeyManagementService(
                    key_management_client=self.standalone_key_management()
                )
            return self.__key_management_service

        def license_service(self):
            if not self.__license_service:
                from services.license_service import \
                    LicenseService
                self.__license_service = LicenseService(
                    settings_service=self.settings_service()
                )
            return self.__license_service

    instance = None

    def __init__(self):
        if not ServiceProvider.instance:
            ServiceProvider.instance = ServiceProvider.__Services()

    def __getattr__(self, item):
        return getattr(self.instance, item)
