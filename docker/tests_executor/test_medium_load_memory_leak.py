import os
from unittest.mock import patch

import pandas as pd

from commons.constants import ACTION_SCALE_UP
from tests_executor.base_executor_test import BaseExecutorTest
from tests_executor.constants import (POINTS_IN_DAY, RECOMMENDATION_KEY,
                                      SCHEDULE_KEY)
from tests_executor.decorators.memory_leak import memory_leak
from tests_executor.utils import (generate_constant_metric_series,
                                  constant_to_series, dateparse,
                                  generate_timestamp_series)


class TestConstantMediumLoadMemoryLeak(BaseExecutorTest):
    def setUp(self) -> None:
        super().setUp()

        self.instance_id = 'constant_medium_load_memory_leak'

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
            loc=60,
            scale=1,
            size=length
        )
        cpu_load_series = memory_leak(
            series=cpu_load_series,
            mean=60,
            limit=100,
            cycle_duration_points=1200,
            deviation=10
        )
        memory_load_series = generate_constant_metric_series(
            distribution='normal',
            loc=30,
            scale=0.8,
            size=length
        )
        memory_load_series = memory_leak(
            series=memory_load_series,
            mean=60,
            limit=80,
            cycle_duration_points=1200,
            deviation=20
        )
        net_output_load_series = generate_constant_metric_series(
            distribution='normal',
            loc=30,
            scale=0.8,
            size=length
        )
        avg_disk_iops = constant_to_series(-1, length)
        max_disk_iops = constant_to_series(-1, length)
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
    def test_constant_medium_load_memory_leak(self):
        result, _ = self.recommendation_service.process_instance(
            metric_file_path=self.metrics_file_path,
            algorithm=self.algorithm,
            reports_dir=self.reports_path
        )

        self.assert_resource_id(
            result=result,
            resource_id=self.instance_id
        )

        schedule = result.get(RECOMMENDATION_KEY, {}).get(SCHEDULE_KEY)

        self.assert_always_run_schedule(schedule=schedule)

        self.assert_stats(result=result)
        self.assert_action(result=result, expected_actions=[ACTION_SCALE_UP])
