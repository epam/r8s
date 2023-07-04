from commons.constants import JOB_STEP_VALIDATE_METRICS
from commons.exception import ExecutorException
from commons.log_helper import get_logger
from models.algorithm import Algorithm
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
        for index, row in df.iterrows():
            provisioned_mb = shape_data.network_throughput
            if provisioned_mb:
                provisioned_mb = float(provisioned_mb)
                net_output_perc = self._convert_net_output(
                    absolute_value_bytes=row['net_output_load'],
                    provisioned_mb=provisioned_mb)
                df.at[index, 'net_output_load'] = net_output_perc
            else:
                df.at[index, 'net_output_load'] = -1
            provisioned_iops = shape_data.iops
            if provisioned_iops:
                provisioned_iops = int(provisioned_iops)
                df.at[index, 'avg_disk_iops'] = self._convert_iops(
                    value=row['avg_disk_iops'],
                    provisioned_iops=provisioned_iops
                )
                df.at[index, 'max_disk_iops'] = self._convert_iops(
                    value=row['max_disk_iops'],
                    provisioned_iops=provisioned_iops
                )
            else:
                df.at[index, 'avg_disk_iops'] = -1
                df.at[index, 'max_disk_iops'] = -1
        df.to_csv(metrics_file_path, index=False)
        return metrics_file_path

    @staticmethod
    def _convert_net_output(absolute_value_bytes, provisioned_mb):
        if absolute_value_bytes == -1:
            return -1
        absolute_value_mb = absolute_value_bytes / 1024 / 1024

        percentage = round(absolute_value_mb / provisioned_mb, 2)
        return int(percentage * 100)

    @staticmethod
    def _convert_iops(value, provisioned_iops):
        if value == -1:
            return -1
        percentage = round(value / provisioned_iops)
        return int(percentage * 100)
