import os
from unittest.mock import patch

import pandas as pd

from commons.constants import ACTION_CHANGE_SHAPE
from tests_executor.base_executor_test import BaseExecutorTest
from tests_executor.constants import POINTS_IN_DAY
from tests_executor.utils import (generate_constant_metric_series,
                                  constant_to_series,
                                  generate_timestamp_series, dateparse)


class TestScaleUpIOPSNoData(BaseExecutorTest):
    def setUp(self) -> None:
        super().setUp()

        self.instance_id = 'scale_up_iops_no_data'

        length = POINTS_IN_DAY * 14
        instance_id_series = constant_to_series(
            value=self.instance_id,
            length=length
        )
        instance_type_series = constant_to_series(
            value='t2.small',  # / 1/2/-/-
            length=length
        )

        timestamp_series = generate_timestamp_series(length=length)
        cpu_load_series = generate_constant_metric_series(
            distribution='normal',
            loc=55,
            scale=1,
            size=length
        )
        memory_load_series = generate_constant_metric_series(
            distribution='normal',
            loc=55,
            scale=0.8,
            size=length
        )
        net_output_load_series = constant_to_series(-1, length)
        avg_disk_iops = generate_constant_metric_series(
            distribution='normal',
            loc=80,
            scale=1,
            size=length
        )
        max_disk_iops = generate_constant_metric_series(
            distribution='normal',
            loc=95,
            scale=1,
            size=length
        )
        df_data = {
            'instance_id': instance_id_series,
            'instance_type': instance_type_series,
            'timestamp': timestamp_series,
            'cpu_load': cpu_load_series,
            'memory_load': memory_load_series,
            'net_output_load': net_output_load_series,
            'avg_disk_iops': avg_disk_iops,
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
    def test_scale_up_iops_no_data(self):
        result, _ = self.recommendation_service.process_instance(
            metric_file_path=self.metrics_file_path,
            algorithm=self.algorithm,
            reports_dir=self.reports_path
        )

        self.assert_resource_id(
            result=result,
            resource_id=self.instance_id
        )
        self.assert_stats(result=result)
        self.assert_action(result=result,
                           expected_actions=[ACTION_CHANGE_SHAPE])
