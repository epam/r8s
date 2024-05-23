import os

from modular_sdk.services.customer_service import CustomerService
from modular_sdk.services.tenant_service import TenantService

from commons.constants import ENV_SERVICE_MODE
from services.algorithm_service import AlgorithmService
from services.clients.s3 import S3Client
from services.clients.ssm import SSMClient
from services.clustering_service import ClusteringService
from services.customer_preferences_service import CustomerPreferencesService
from services.environment_service import EnvironmentService
from services.job_service import JobService
from services.meta_service import MetaService
from services.metrics_service import MetricsService
from services.mocked_data_service import MockedDataService
from services.os_service import OSService
from services.recomendation_service import RecommendationService
from services.recommendation_history_service import \
    RecommendationHistoryService
from services.reformat_service import ReformatService
from services.resize.resize_service import ResizeService
from services.resource_group_service import ResourceGroupService
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService
from services.saving.saving_service import SavingService
from services.schedule.schedule_service import ScheduleService
from services.setting_service import SettingsService
from services.shape_price_service import ShapePriceService
from services.shape_service import ShapeService
from services.ssm_service import SSMService
from services.storage_service import StorageService

SERVICE_MODE = os.getenv(ENV_SERVICE_MODE)
is_docker = SERVICE_MODE == 'docker'


class ServiceProvider:
    class __Services:
        # clients
        __s3_conn = None
        __ssm_conn = None
        __license_manager_conn = None
        __standalone_key_management = None

        # services
        __environment_service = None
        __ssm_service = None
        __algorithm_service = None
        __storage_service = None
        __settings_service = None
        __job_service = None
        __os_service = None
        __metrics_service = None
        __schedule_service = None
        __resize_service = None
        __reformat_service = None
        __recommendation_service = None
        __customer_preferences_service = None
        __mocked_data_service = None
        __clustering_service = None
        __saving_service = None
        __shape_service = None
        __shape_price_service = None
        __meta_service = None
        __recommendation_history_service = None
        __resource_group_service = None

        # modular services
        __customer_service = None
        __tenant_service = None
        __application_service = None
        __parent_service = None

        # license manager services
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

        def settings_service(self):
            if not self.__settings_service:
                self.__settings_service = SettingsService()
            return self.__settings_service

        def job_service(self):
            if not self.__job_service:
                self.__job_service = JobService(
                    environment_service=self.environment_service(),
                    license_manager_service=self.license_manager_service()
                )
            return self.__job_service

        def os_service(self):
            if not self.__os_service:
                self.__os_service = OSService()
            return self.__os_service

        def metrics_service(self):
            if not self.__metrics_service:
                self.__metrics_service = MetricsService(
                    clustering_service=self.clustering_service()
                )
            return self.__metrics_service

        def schedule_service(self):
            if not self.__schedule_service:
                self.__schedule_service = ScheduleService(
                    metrics_service=self.metrics_service()
                )
            return self.__schedule_service

        def resize_service(self):
            if not self.__resize_service:
                self.__resize_service = ResizeService(
                    customer_preferences_service=
                    self.customer_preferences_service(),
                    shape_service=self.shape_service(),
                    shape_price_service=self.shape_price_service()
                )
            return self.__resize_service

        def saving_service(self):
            if not self.__saving_service:
                self.__saving_service = SavingService(
                    shape_price_service=self.shape_price_service()
                )
            return self.__saving_service

        def reformat_service(self):
            if not self.__reformat_service:
                self.__reformat_service = ReformatService(
                    shape_service=self.shape_service(),
                    metrics_service=self.metrics_service()
                )
            return self.__reformat_service

        def recommendation_service(self):
            if not self.__recommendation_service:
                self.__recommendation_service = RecommendationService(
                    metrics_service=self.metrics_service(),
                    schedule_service=self.schedule_service(),
                    resize_service=self.resize_service(),
                    environment_service=self.environment_service(),
                    saving_service=self.saving_service(),
                    meta_service=self.meta_service(),
                    shape_service=self.shape_service(),
                    recommendation_history_service=
                    self.recommendation_history_service()
                )
            return self.__recommendation_service

        def customer_preferences_service(self):
            if not self.__customer_preferences_service:
                self.__customer_preferences_service = \
                    CustomerPreferencesService()
            return self.__customer_preferences_service

        def customer_service(self):
            if not self.__customer_service:
                self.__customer_service = CustomerService()
            return self.__customer_service

        def tenant_service(self):
            if not self.__tenant_service:
                self.__tenant_service = TenantService()
            return self.__tenant_service

        def application_service(self):
            if not self.__application_service:
                self.__application_service = \
                    RightSizerApplicationService(
                        customer_service=self.customer_service()
                    )
            return self.__application_service

        def parent_service(self):
            if not self.__parent_service:
                self.__parent_service = RightSizerParentService(
                    tenant_service=self.tenant_service(),
                    customer_service=self.customer_service(),
                    environment_service=self.environment_service()
                )
            return self.__parent_service

        def mocked_data_service(self):
            if not self.__mocked_data_service:
                self.__mocked_data_service = MockedDataService(
                    os_service=self.os_service()
                )
            return self.__mocked_data_service

        def clustering_service(self):
            if not self.__clustering_service:
                self.__clustering_service = ClusteringService()
            return self.__clustering_service

        def shape_service(self):
            if not self.__shape_service:
                self.__shape_service = ShapeService()
            return self.__shape_service

        def shape_price_service(self):
            if not self.__shape_price_service:
                self.__shape_price_service = ShapePriceService()
            return self.__shape_price_service

        def meta_service(self):
            if not self.__meta_service:
                self.__meta_service = MetaService(
                    environment_service=self.environment_service()
                )
            return self.__meta_service

        def recommendation_history_service(self):
            if not self.__recommendation_history_service:
                self.__recommendation_history_service = \
                    RecommendationHistoryService()
            return self.__recommendation_history_service

        def resource_group_service(self):
            if not self.__resource_group_service:
                self.__resource_group_service = ResourceGroupService(
                    schedule_service=self.schedule_service()
                )
            return self.__resource_group_service

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
                    environment_service=self.environment_service(),
                    ssm_service=self.ssm_service()
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
