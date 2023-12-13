import importlib
import os
import unittest
from abc import ABC, abstractmethod
from unittest.mock import patch

from commons import ApplicationException
from commons.constants import GET_METHOD
from models.storage import Storage

HANDLER_IMPORT_PATH_TEMPLATE = ('src.lambdas.r8s_api_handler.processors.'
                                '{processor_name}')


class AbstractTestProcessorHandler(ABC, unittest.TestCase):

    @property
    @abstractmethod
    def processor_name(self):
        pass

    @property
    def test_method(self):
        return GET_METHOD

    @patch.dict(os.environ, {'AWS_REGION': 'eu-central-1',
                             'r8s_mongodb_connection_uri':
                                 "mongomock://localhost/testdb"})
    def setUp(self) -> None:
        handler_import_path = HANDLER_IMPORT_PATH_TEMPLATE.format(
            processor_name=self.processor_name)
        self.handler_module = importlib.import_module(handler_import_path)

        self.HANDLER = self.build_processor()
        self.init_data()

        self.common_event = {}
        if not self.test_method:
            raise AssertionError(f"'test_method' must be specified in "
                                 f"class: '{self.__class__.__name__}'")
        self.TESTED_METHOD = getattr(self.HANDLER, self.test_method.lower())

    @abstractmethod
    def build_processor(self):
        pass

    @abstractmethod
    def init_data(self):
        pass

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
