from unittest.mock import MagicMock

from models.algorithm import Algorithm, CloudEnum
from services.algorithm_service import AlgorithmService
from tests.test_handlers.abstract_test_processor_handler import \
    AbstractTestProcessorHandler


class TestAlgorithmHandler(AbstractTestProcessorHandler):
    processor_name = 'algorithm_processor'

    def build_processor(self):
        return self.handler_module.AlgorithmProcessor(
            algorithm_service=AlgorithmService(),
            customer_service=MagicMock()
        )

    def init_data(self):
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

    def tearDown(self) -> None:
        algorithms = list(Algorithm.objects.all())
        for algorithm in algorithms:
            algorithm.delete()
