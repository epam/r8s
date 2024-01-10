from unittest.mock import MagicMock

from modular_sdk.commons.constants import ApplicationType, ParentType, \
    ParentScope
from modular_sdk.models.application import Application
from modular_sdk.models.parent import Parent
from modular_sdk.services.tenant_service import TenantService

from services.algorithm_service import AlgorithmService
from services.environment_service import EnvironmentService
from services.license_service import LicenseService
from services.rightsizer_parent_service import RightSizerParentService
from services.setting_service import SettingsService
from services.ssm_service import SSMService
from tests.test_handlers.abstract_test_processor_handler import \
    AbstractTestProcessorHandler


class TestParentHandler(AbstractTestProcessorHandler):
    @property
    def processor_name(self):
        return 'parent_processor'

    def build_processor(self):
        self.algorithm_service = AlgorithmService()
        self.customer_service = MagicMock()
        self.tenant_service = TenantService(
            customer_service=self.customer_service
        )
        self.settingsService = SettingsService()
        self.environment_service = EnvironmentService()
        self.license_service = LicenseService()
        self.license_manager_service = MagicMock()
        self.ssm_client = MagicMock()
        self.ssm_service = SSMService(client=self.ssm_client)
        self.application_service = MagicMock()

        self.parent_service = RightSizerParentService(
            tenant_service=self.tenant_service,
            customer_service=self.customer_service,
            environment_service=self.environment_service
        )

        return self.handler_module.ParentProcessor(
            algorithm_service=self.algorithm_service,
            customer_service=self.customer_service,
            application_service=self.application_service,
            parent_service=self.parent_service,
            tenant_service=self.tenant_service,
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
        self.license_application = Application(
            application_id='license_application',
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

        self.application_service.list.return_value = [
            self.license_application
        ]
        self.application_service.resolve_application.return_value = [
            self.license_application
        ]

        self.parent1 = Parent(
            parent_id='parent1',
            customer_id=self.license_application.customer_id,
            application_id=self.license_application.application_id,
            type=ParentType.RIGHTSIZER_LICENSES_PARENT,
            description='test',
            is_deleted=False,
            meta={},
            type_scope=f'{self.license_application.customer_id}#'
                       f'{ParentScope.ALL.value}#'

        )
        self.parent2 = Parent(
            parent_id='parent2',
            customer_id=self.license_application.customer_id,
            application_id=self.license_application.application_id,
            type=ParentType.RIGHTSIZER_LICENSES_PARENT,
            description='test',
            is_deleted=False,
            meta={},
            type_scope=f'{self.license_application.customer_id}#'
                       f'{ParentScope.SPECIFIC.value}#tenant'

        )
        self.parent_service.list.return_value = [
            self.parent1, self.parent2
        ]
        self.parent_service.list_application_parents.return_value = [
            self.parent1, self.parent2
        ]
        self.parent_service.mark_deleted = MagicMock(return_value=True)
        self.parent_service.force_delete = MagicMock(return_value=True)
        self.parent_service.save = MagicMock(return_value=True)
