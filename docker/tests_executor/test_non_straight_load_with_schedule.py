import os
from unittest.mock import patch

import pandas as pd

from commons.constants import ACTION_SCHEDULE, ACTION_SPLIT
from tests_executor.base_executor_test import BaseExecutorTest
from tests_executor.constants import POINTS_IN_DAY
from tests_executor.utils import constant_to_series, \
    generate_timestamp_series, generate_scheduled_metric_series, dateparse


class TestNonStraightLoadWIthSchedule(BaseExecutorTest):
    def setUp(self) -> None:
        super().setUp()

        self.instance_id = 'non_straight_load_schedule'

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
            work_days=(0, 1, 2, 3),
            work_hours=(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11),
            work_kwargs=dict(loc=60, scale=5),
            idle_kwargs=dict(loc=5, scale=1)
        )
        cpu_load_series = generate_scheduled_metric_series(
            distribution='normal',
            timestamp_series=timestamp_series,
            series=cpu_load_series,
            work_days=(4, 5, 6),
            work_hours=(12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23),
            work_kwargs=dict(loc=20, scale=2),
            idle_kwargs=dict(loc=5, scale=1)
        )

        memory_load_series = generate_scheduled_metric_series(
            distribution='normal',
            timestamp_series=timestamp_series,
            work_days=(0, 1, 2, 3),
            work_hours=(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11),
            work_kwargs=dict(loc=60, scale=5),
            idle_kwargs=dict(loc=5, scale=1)
        )
        memory_load_series = generate_scheduled_metric_series(
            distribution='normal',
            timestamp_series=timestamp_series,
            series=memory_load_series,
            work_days=(4, 5, 6),
            work_hours=(12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23),
            work_kwargs=dict(loc=20, scale=2),
            idle_kwargs=dict(loc=5, scale=1)
        )
        net_output_load_series = constant_to_series(-1, length)
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
    def test_non_straight_load_schedule(self):
        result = self.recommendation_service.process_instance(
            metric_file_path=self.metrics_file_path,
            algorithm=self.algorithm,
            reports_dir=self.reports_path
        )

        self.assertEqual(result.get('instance_id'), self.instance_id)

        schedule = result.get('schedule')
        self.assertEqual(len(schedule), 2)

        # first schedule part [Thursday - Sunday]
        schedule_item = schedule[0]
        weekdays = schedule_item.get('weekdays')

        self.assertIn(schedule_item.get('start'), ('11:50', '12:00', '12:10'))
        self.assertEqual(schedule_item.get('stop'), '23:50')
        self.assertEqual(set(weekdays), {'Friday', 'Saturday', 'Sunday'})

        # second schedule part [Thursday]
        schedule_item = schedule[1]
        weekdays = schedule_item.get('weekdays')

        self.assertEqual(schedule_item.get('start'), '00:00')
        self.assertIn(schedule_item.get('stop'), ('11:50', '12:00', '12:10'))
        self.assertEqual(set(weekdays), {'Monday', 'Tuesday', 'Wednesday',
                                         'Thursday'})

        recommended_shapes = result.get('recommended_shapes')
        self.assertEqual(len(recommended_shapes), 2)

        probabilities = [shape.get('probability') for shape in
                         recommended_shapes]
        self.assertEqual(sum(probabilities), 1)
        self.assertEqual(len(probabilities), 2)

        self.assert_stats(result=result)
        self.assert_action(result=result, expected_actions=[ACTION_SCHEDULE,
                                                            ACTION_SPLIT])
