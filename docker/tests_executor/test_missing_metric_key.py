import os
from unittest.mock import patch

import pandas as pd

from commons.exception import ExecutorException
from tests_executor.base_executor_test import BaseExecutorTest
from tests_executor.constants import POINTS_IN_DAY
from tests_executor.utils import (generate_constant_metric_series,
                                  constant_to_series,
                                  generate_timestamp_series, dateparse)


class TestMissingMetricKey(BaseExecutorTest):
    def setUp(self) -> None:
        super().setUp()

        self.instance_id = 'missing_metric_key'

        length = POINTS_IN_DAY * 14
        instance_id_series = constant_to_series(
            value=self.instance_id,
            length=length
        )
        instance_type_series = constant_to_series(
            value='t2.medium',
            length=length
        )
        timestamp_series = generate_timestamp_series(length=length)
        cpu_load_series = generate_constant_metric_series(
            distribution='normal',
            loc=50,
            scale=1,
            size=length
        )
        memory_load_series = generate_constant_metric_series(
            distribution='normal',
            loc=60,
            scale=0.8,
            size=length
        )
        max_disk_iops = constant_to_series(-1, length)
        df_data = {
            'instance_id': instance_id_series,
            'instance_type': instance_type_series,
            'timestamp': timestamp_series,
            'cpu_load': cpu_load_series,
            'memory_load': memory_load_series,
            'max_disk_iops': max_disk_iops,
        }
        df = pd.DataFrame(df_data)
        self.metrics_file_path = os.path.join(self.metrics_dir,
                                              f'{self.instance_id}.csv')
        df.to_csv(self.metrics_file_path, sep=',', index=False)
        self.df = pd.read_csv(self.metrics_file_path, parse_dates=True,
                              date_parser=dateparse, index_col='timestamp')
        self.create_plots()

    @patch.dict(os.environ, {'KMP_DUPLICATE_LIB_OK': "TRUE"})
    def test_missing_metric_key(self):
        with self.assertRaises(ExecutorException) as context:
            self.metrics_service.validate_metric_file(
                algorithm=self.algorithm,
                metric_file_path=self.metrics_file_path)
        excepted_error_str = ['Missing columns', 'net_output_load',
                              'avg_disk_iops']
        self.assertTrue(all(s in context.exception.reason
                            for s in excepted_error_str))
