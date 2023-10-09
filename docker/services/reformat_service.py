from commons.constants import JOB_STEP_VALIDATE_METRICS
from commons.exception import ExecutorException
from commons.log_helper import get_logger
from models.algorithm import Algorithm
from models.shape import Shape
from services.metrics_service import MetricsService
from services.shape_service import ShapeService

_LOG = get_logger('r8s-reformat-service')


class ReformatService:
    def __init__(self, shape_service: ShapeService,
                 metrics_service: MetricsService):
        self.shape_service = shape_service
        self.metrics_service = metrics_service

    def to_relative_values(self, metrics_file_path, algorithm: Algorithm):
        _LOG.debug(f'Reformatting metrics file \'{metrics_file_path}\'')
        df = self.metrics_service.read_metrics(
            metric_file_path=metrics_file_path,
            algorithm=algorithm,
            parse_index=False)

        native_shape_name = df['instance_type'][0]
        shape_data = self.shape_service.get(name=native_shape_name)
        if not shape_data:
            _LOG.error(f'Unknown instance type \'{native_shape_name}\' '
                       f'specified for \'{metrics_file_path}\'')
            raise ExecutorException(
                step_name=JOB_STEP_VALIDATE_METRICS,
                reason=f'Unknown instance type \'{native_shape_name}\' '
                       f'specified.'
            )
        df['net_output_load'] = df['net_output_load'].apply(
            func=self.convert_net_output,
            args=(shape_data,)
        )
        df['avg_disk_iops'] = df['avg_disk_iops'].apply(
            func=self.convert_iops,
            args=(shape_data,)
        )
        df['max_disk_iops'] = df['max_disk_iops'].apply(
            func=self.convert_iops,
            args=(shape_data,)
        )
        df.to_csv(metrics_file_path, index=False)
        return metrics_file_path

    @staticmethod
    def convert_net_output(value, shape: Shape):
        provisioned_mb = shape.network_throughput
        if not provisioned_mb or value == -1:
            return -1

        provisioned_mb = float(provisioned_mb)
        absolute_value_mb = value / 1024 / 1024

        percentage = round(absolute_value_mb / provisioned_mb, 2)
        return int(percentage * 100)

    @staticmethod
    def convert_iops(value, shape: Shape):
        provisioned_iops = shape.iops
        if not provisioned_iops or value == -1:
            return -1
        percentage = round(value / provisioned_iops)
        return int(percentage * 100)
