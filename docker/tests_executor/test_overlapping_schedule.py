import os
from unittest.mock import patch

import pandas as pd

from commons.constants import ACTION_SCHEDULE
from tests_executor.base_executor_test import BaseExecutorTest
from tests_executor.constants import (POINTS_IN_DAY, RECOMMENDATION_KEY,
                                      SCHEDULE_KEY, WEEKDAYS_KEY,
                                      START_KEY, STOP_KEY)
from tests_executor.utils import (generate_scheduled_metric_series,
                                  constant_to_series,
                                  generate_timestamp_series, dateparse)


class TestOverlappingSchedule(BaseExecutorTest):
    def setUp(self) -> None:
        super().setUp()

        self.instance_id = 'schedule_overlap'

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
            work_hours=(8, 9, 10, 11),
            work_kwargs=dict(loc=60, scale=5),
            idle_kwargs=dict(loc=5, scale=1)
        )
        cpu_load_series = generate_scheduled_metric_series(
            distribution='normal',
            timestamp_series=timestamp_series,
            series=cpu_load_series,
            work_days=(3, 4, 5, 6),
            work_hours=(15, 16, 17, 18),
            work_kwargs=dict(loc=40, scale=5),
            idle_kwargs=dict(loc=5, scale=1)
        )

        memory_load_series = generate_scheduled_metric_series(
            distribution='normal',
            timestamp_series=timestamp_series,
            work_days=(0, 1, 2, 3, 4),
            work_hours=(8, 9, 10, 11),
            work_kwargs=dict(loc=60, scale=5),
            idle_kwargs=dict(loc=7, scale=1),
        )
        memory_load_series = generate_scheduled_metric_series(
            distribution='normal',
            timestamp_series=timestamp_series,
            series=memory_load_series,
            work_days=(3, 4, 5, 6),
            work_hours=(15, 16, 17, 18),
            work_kwargs=dict(loc=40, scale=5),
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
    def test_overlapping_schedule(self):
        result, _ = self.recommendation_service.process_instance(
            metric_file_path=self.metrics_file_path,
            algorithm=self.algorithm,
            reports_dir=self.reports_path
        )

        self.assert_resource_id(
            result=result,
            resource_id=self.instance_id
        )
        recommendation = result.get(RECOMMENDATION_KEY, {})
        schedule = recommendation.get(SCHEDULE_KEY)

        self.assertEqual(len(schedule), 2)

        # first schedule part [Thursday - Sunday]
        schedule_item = schedule[0]
        weekdays = schedule_item.get(WEEKDAYS_KEY)

        self.assert_time_between(
            time_str=schedule_item.get(START_KEY),
            from_time_str='14:45',
            to_time_str='15:15'
        )
        self.assert_time_between(
            time_str=schedule_item.get(STOP_KEY),
            from_time_str='18:45',
            to_time_str='19:15'
        )
        self.assertEqual(set(weekdays), {'Thursday', 'Friday', 'Saturday',
                                         'Sunday'})

        # second schedule part [Monday - Friday]
        schedule_item = schedule[1]
        weekdays = schedule_item.get(WEEKDAYS_KEY)

        self.assert_time_between(
            time_str=schedule_item.get(START_KEY),
            from_time_str='07:45',
            to_time_str='08:15'
        )
        self.assert_time_between(
            time_str=schedule_item.get(STOP_KEY),
            from_time_str='11:45',
            to_time_str='12:15'
        )
        self.assertEqual(set(weekdays), {'Monday', 'Tuesday', 'Wednesday',
                                         'Thursday', 'Friday'})

        self.assert_stats(result=result)
        self.assert_action(result=result, expected_actions=[ACTION_SCHEDULE])
