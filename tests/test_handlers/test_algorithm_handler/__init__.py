from tests.import_helper import add_src_to_path

add_src_to_path()
import importlib
import os
import unittest
from unittest.mock import patch, MagicMock

from src.services.algorithm_service import AlgorithmService
from src.models.algorithm import Algorithm, CloudEnum


class TestAlgorithmHandler(unittest.TestCase):
    HANDLER_IMPORT_PATH = 'src.lambdas.r8s_api_handler.processors.' \
                          'algorithm_processor'
    HANDLER = None

    @patch.dict(os.environ, {'AWS_REGION': 'eu-central-1',
                             'r8s_mongodb_connection_uri':
                                 "mongomock://localhost/testdb"})
    def setUp(self) -> None:

        self.handler = importlib.import_module(self.HANDLER_IMPORT_PATH)
        self.HANDLER = self.handler.AlgorithmProcessor(
            algorithm_service=AlgorithmService(),
            customer_service=MagicMock()
        )
        data_attributes = ['instance_id', 'instance_type', 'timestamp',
                           'cpu_load', 'memory_load', 'net_output_load',
                           'avg_disk_iops', 'max_disk_iops']
        metric_attributes = ['cpu_load', 'memory_load', 'net_output_load',
                             'avg_disk_iops', 'max_disk_iops']
        algorithm = Algorithm(name='test_algorithm', customer="test",
                              cloud=CloudEnum.CLOUD_AWS,
                              required_data_attributes=data_attributes,
                              metric_attributes=metric_attributes,
                              timestamp_attribute='timestamp',
                              format_version='1.0')
        algorithm.save()

        algorithm2 = Algorithm(name='test_algorithm2', customer="test",
                               cloud=CloudEnum.CLOUD_AWS,
                               required_data_attributes=data_attributes,
                               metric_attributes=metric_attributes,
                               timestamp_attribute='timestamp',
                               format_version='1.0')
        algorithm2.save()
        self.algorithm1 = algorithm
        self.algorithm2 = algorithm2

        self.common_event = {}
        if not self.TESTED_METHOD_NAME:
            raise AssertionError(f"'TESTED_METHOD_NAME' must be specified in "
                                 f"class: '{self.__class__.__name__}'")
        self.TESTED_METHOD = getattr(self.HANDLER, self.TESTED_METHOD_NAME)

    def tearDown(self) -> None:

        algorithms = list(Algorithm.objects.all())
        for algorithm in algorithms:
            algorithm.delete()

    def assert_status(self, response, status=200):
        response = response['code']
        self.assertEqual(response, status)

    def assert_exception_with_content(self, event, content):
        with self.assertRaises(Exception) as context:
            self.TESTED_METHOD(event=event)
        self.assertIn(content, str(context.exception))
