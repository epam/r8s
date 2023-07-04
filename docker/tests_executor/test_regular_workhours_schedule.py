import os
from unittest.mock import patch

import pandas as pd

from commons.constants import ACTION_SCHEDULE
from tests_executor.base_executor_test import BaseExecutorTest
from tests_executor.constants import POINTS_IN_DAY, WORK_DAYS
from tests_executor.utils import constant_to_series, \
    generate_timestamp_series, generate_scheduled_metric_series, dateparse


class TestRegularWorkhoursSchedule(BaseExecutorTest):
    def setUp(self) -> None:
        super().setUp()

        self.instance_id = 'schedule_workhours'

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
        cpu_load_series = generate_scheduled_metric_series(
            distribution='normal',
            timestamp_series=timestamp_series,
            work_days=(0, 1, 2, 3, 4),
            work_hours=(9, 10, 11, 12, 13, 14, 15, 16, 17),
            work_kwargs=dict(loc=50, scale=5),
            idle_kwargs=dict(loc=5, scale=1)
        )
        memory_load_series = generate_scheduled_metric_series(
            distribution='normal',
            timestamp_series=timestamp_series,
            work_days=(0, 1, 2, 3, 4),
            work_hours=(9, 10, 11, 12, 13, 14, 15, 16, 17),
            work_kwargs=dict(loc=60, scale=5),
            idle_kwargs=dict(loc=7, scale=1),
        )
        net_output_load_series = generate_scheduled_metric_series(
            distribution='normal',
            timestamp_series=timestamp_series,
            work_days=(0, 1, 2, 3, 4),
            work_hours=(9, 10, 11, 12, 13, 14, 15, 16, 17),
            work_kwargs=dict(loc=30, scale=3),
            idle_kwargs=dict(loc=2, scale=0.3),
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
    def test_workhours_schedule(self):
        result = self.recommendation_service.process_instance(
            metric_file_path=self.metrics_file_path,
            algorithm=self.algorithm,
            reports_dir=self.reports_path
        )

        self.assertEqual(result.get('instance_id'), self.instance_id)

        schedule = result.get('schedule')
        self.assertEqual(len(schedule), 1)

        schedule_item = schedule[0]

        start = schedule_item.get('start')
        stop = schedule_item.get('stop')
        weekdays = schedule_item.get('weekdays')

        self.assertTrue(start in ('08:50', '09:00', '09:10'))
        self.assertTrue(stop in ('17:50', '18:00', '18:10'))

        self.assertEqual(set(weekdays), set(WORK_DAYS))

        self.assert_stats(result=result)
        self.assert_action(result=result, expected_actions=[ACTION_SCHEDULE])
