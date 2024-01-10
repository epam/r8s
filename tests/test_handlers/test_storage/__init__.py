from unittest.mock import MagicMock

from tests.test_handlers.abstract_test_processor_handler import \
    AbstractTestProcessorHandler

from models.storage import Storage, StorageServiceEnum, StorageTypeEnum
from services.storage_service import StorageService


class TestStorageHandler(AbstractTestProcessorHandler):

    @property
    def processor_name(self):
        return 'storage_processor'

    def build_processor(self):
        self.mocked_s3_client = MagicMock()
        storage_service = StorageService(self.mocked_s3_client)
        return self.handler_module.StorageProcessor(
            storage_service=storage_service
        )

    def init_data(self):
        storage1 = Storage(name='test_storage',
                           service=StorageServiceEnum.S3_BUCKET,
                           type=StorageTypeEnum.STORAGE)
        storage1.save()

        storage2 = Storage(name='test_storage2',
                           service=StorageServiceEnum.S3_BUCKET,
                           type=StorageTypeEnum.DATA_SOURCE)
        storage2.save()
        self.storage1 = storage1
        self.storage2 = storage2

    def tearDown(self) -> None:
        storages = list(Storage.objects.all())
        for storage in storages:
            storage.delete()
