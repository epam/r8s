from unittest.mock import MagicMock

from modular_sdk.commons.constants import ApplicationType
from modular_sdk.models.application import Application
from modular_sdk.services.tenant_service import TenantService

from services.algorithm_service import AlgorithmService
from services.environment_service import EnvironmentService
from services.license_manager_service import LicenseManagerService
from services.license_service import LicenseService
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService
from services.ssm_service import SSMService
from tests.test_handlers.abstract_test_processor_handler import \
    AbstractTestProcessorHandler


class TestLicensesApplicationHandler(AbstractTestProcessorHandler):
    @property
    def processor_name(self):
        return 'application_licenses_processor'

    def build_processor(self):
        self.algorithm_service = AlgorithmService()
        self.customer_service = MagicMock()
        self.tenant_service = TenantService(
            customer_service=self.customer_service
        )
        self.environment_service = EnvironmentService()

        self.ssm_client = MagicMock()
        self.ssm_service = SSMService(client=self.ssm_client)

        self.application_service = RightSizerApplicationService(
            customer_service=self.customer_service,
            ssm_service=self.ssm_service
        )

        self.parent_service = RightSizerParentService(
            tenant_service=self.tenant_service,
            customer_service=self.customer_service,
            environment_service=self.environment_service
        )

        self.license_manager_client = MagicMock()
        self.token_service = MagicMock()

        self.license_manager_service = LicenseManagerService(
            license_manager_client=self.license_manager_client,
            token_service=self.token_service,
            environment_service=self.environment_service,
            ssm_service=self.ssm_service
        )
        self.license_service = LicenseService()

        return self.handler_module.ApplicationLicensesProcessor(
            algorithm_service=self.algorithm_service,
            customer_service=self.customer_service,
            application_service=self.application_service,
            parent_service=self.parent_service,
            license_service=self.license_service,
            license_manager_service=self.license_manager_service
        )

    def init_data(self):
        self.host_application = Application(
            application_id='host_application',
            customer_id='customer',
            type=ApplicationType.RIGHTSIZER,
            description='test',
            is_deleted=False,
            meta={
                'input_storage': 'input',
                'output_storage': 'output',
                'connection': {
                    'host': 'host',
                    'port': 443,
                    'protocol': 'HTTPS',
                    'username': 'user'
                }
            }
        )
        self.license_application1 = Application(
            application_id='license_application1',
            customer_id='customer',
            type=ApplicationType.RIGHTSIZER_LICENSES,
            description='test',
            is_deleted=False,
            meta={
                'cloud': 'AWS',
                'algorithm': 'algorithm',
                'license_key': 'license',
                'tenants': ['*']
            }
        )
        self.license_application2 = Application(
            application_id='license_application2',
            customer_id='customer',
            type=ApplicationType.RIGHTSIZER_LICENSES,
            description='test',
            is_deleted=False,
            meta={
                'cloud': 'AWS',
                'algorithm': 'algorithm',
                'license_key': 'license',
                'tenants': ['*']
            }
        )

        self.application_service.list = MagicMock(
            return_value=[
                self.license_application1,
                self.license_application2
            ]
        )
        self.application_service.resolve_application = MagicMock(
            return_value=[
                self.license_application1,
                self.license_application2
            ]
        )

        self.application_service.mark_deleted = MagicMock()
        self.application_service.force_delete = MagicMock()
        self.application_service.save = MagicMock()
        self.parent_service.save = MagicMock()
        self.license_manager_service._get_client_token = MagicMock(
            return_value='token')
