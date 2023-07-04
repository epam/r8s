import importlib
import os
import unittest
from unittest.mock import patch, MagicMock

from models.storage import Storage, StorageServiceEnum, StorageTypeEnum
from services.storage_service import StorageService
from tests.import_helper import add_src_to_path

add_src_to_path()

from commons import ApplicationException


class TestStorageHandler(unittest.TestCase):
    HANDLER_IMPORT_PATH = 'src.lambdas.r8s_api_handler.processors.' \
                          'storage_processor'
    HANDLER = None

    @patch.dict(os.environ, {'AWS_REGION': 'eu-central-1',
                             'r8s_mongodb_connection_uri':
                                 "mongomock://localhost/testdb"})
    def setUp(self) -> None:
        self.handler = importlib.import_module(self.HANDLER_IMPORT_PATH)
        self.mocked_s3_client = MagicMock()
        storage_service = StorageService(self.mocked_s3_client)
        self.HANDLER = self.handler.StorageProcessor(
            storage_service=storage_service
        )

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

        self.common_event = {}
        if not self.TESTED_METHOD_NAME:
            raise AssertionError(f"'TESTED_METHOD_NAME' must be specified in "
                                 f"class: '{self.__class__.__name__}'")
        self.TESTED_METHOD = getattr(self.HANDLER, self.TESTED_METHOD_NAME)

    def tearDown(self) -> None:
        storages = list(Storage.objects.all())
        for storage in storages:
            storage.delete()

    def assert_status(self, response, status=200):
        response = response['code']
        self.assertEqual(response, status)

    def assert_exception_with_content(self, event, content):
        with self.assertRaises(ApplicationException) as context:
            self.TESTED_METHOD(event=event)
        self.assertIn(content, context.exception.content)
