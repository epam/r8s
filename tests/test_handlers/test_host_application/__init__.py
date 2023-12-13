from unittest.mock import MagicMock

from modular_sdk.commons.constants import ApplicationType
from modular_sdk.models.application import Application
from modular_sdk.services.tenant_service import TenantService

from models.storage import Storage, StorageServiceEnum, StorageTypeEnum
from services.algorithm_service import AlgorithmService
from services.environment_service import EnvironmentService
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService
from services.ssm_service import SSMService
from services.storage_service import StorageService
from tests.test_handlers.abstract_test_processor_handler import \
    AbstractTestProcessorHandler


class TestHostApplicationHandler(AbstractTestProcessorHandler):
    @property
    def processor_name(self):
        return 'application_processor'

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
            ssm_service=self.ssm_client
        )

        self.parent_service = RightSizerParentService(
            tenant_service=self.tenant_service,
            customer_service=self.customer_service,
            environment_service=self.environment_service
        )
        self.s3_client = MagicMock()
        self.storage_service = StorageService(
            s3_client=self.s3_client)

        self.api_gateway_client = MagicMock()

        return self.handler_module.ApplicationProcessor(
            algorithm_service=self.algorithm_service,
            storage_service=self.storage_service,
            customer_service=self.customer_service,
            application_service=self.application_service,
            parent_service=self.parent_service,
            api_gateway_client=self.api_gateway_client
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

        self.application_service.list = MagicMock(
            return_value=[self.host_application]
        )
        self.application_service.resolve_application = MagicMock(
            return_value=[self.host_application]
        )

        self.application_service.mark_deleted = MagicMock()
        self.application_service.force_delete = MagicMock()
        self.application_service.save = MagicMock()
        self.parent_service.save = MagicMock()
        self.storage_service.get_by_name = MagicMock()
        self.storage_service.get_by_name.side_effect = self._get_storage

    @staticmethod
    def _get_storage(name):
        if name == 'input':
            return Storage(name='input',
                           service=StorageServiceEnum.S3_BUCKET,
                           type=StorageTypeEnum.DATA_SOURCE)
        else:
            return Storage(name='output',
                           service=StorageServiceEnum.S3_BUCKET,
                           type=StorageTypeEnum.STORAGE)
