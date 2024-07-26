import pandas as pd
from cron_converter import Cron

from commons.constants import ALLOWED_ACTIONS, ACTION_SCALE_DOWN, \
    ACTION_SCALE_UP, ACTION_EMPTY, ACTION_SHUTDOWN, ACTION_SPLIT, \
    ACTION_SCHEDULE
from commons.log_helper import get_logger
from models.base_model import CloudEnum
from services.os_service import OSService
from tests_executor.constants import POINTS_IN_DAY
from tests_executor.utils import generate_timestamp_series, constant_to_series, \
    generate_constant_metric_series, generate_split_series, \
    generate_scheduled_metric_series

_LOG = get_logger('r8s_mocked_data_service')

TAG_TEST_CASE = 'r8s_test_case'
TAG_PERIOD_DAYS = 'r8s_period_days'
TAG_CPU = 'r8s_cpu_load'
TAG_MEMORY = 'r8s_memory_load'
TAG_AVG_DISK_IOPS = 'r8s_avg_disk_iops'
TAG_MAX_DISK_IOPS = 'r8s_max_disk_iops'
TAG_NET_OUTPUT_LOAD = 'r8s_net_output_load'
TAG_STD = 'r8s_std'
TAG_CRON_START = 'r8s_cron_start'
TAG_CRON_STOP = 'r8s_cron_stop'
TAG_PROBABILITY = 'r8s_probability'

ALLOWED_TAGS = [TAG_TEST_CASE, TAG_PERIOD_DAYS, TAG_CPU, TAG_MEMORY,
                TAG_AVG_DISK_IOPS, TAG_MAX_DISK_IOPS, TAG_NET_OUTPUT_LOAD,
                TAG_STD, TAG_CRON_START, TAG_CRON_STOP, TAG_PROBABILITY]
NUMBER_TAGS = [TAG_PERIOD_DAYS, TAG_CPU, TAG_MEMORY, TAG_AVG_DISK_IOPS,
               TAG_MAX_DISK_IOPS, TAG_NET_OUTPUT_LOAD, TAG_STD,
               TAG_PROBABILITY]
DEFAULT_CONFIG = {
    ACTION_SCALE_DOWN: {
        TAG_PERIOD_DAYS: 14,
        TAG_CPU: 20,
        TAG_MEMORY: 20,
        TAG_AVG_DISK_IOPS: -1,
        TAG_MAX_DISK_IOPS: -1,
        TAG_NET_OUTPUT_LOAD: -1,
        TAG_STD: 2,
    },
    ACTION_SCALE_UP: {
        TAG_PERIOD_DAYS: 14,
        TAG_CPU: 80,
        TAG_MEMORY: 80,
        TAG_AVG_DISK_IOPS: -1,
        TAG_MAX_DISK_IOPS: -1,
        TAG_NET_OUTPUT_LOAD: -1,
        TAG_STD: 2,
    },
    ACTION_EMPTY: {
        TAG_PERIOD_DAYS: 14,
        TAG_CPU: 45,
        TAG_MEMORY: 55,
        TAG_AVG_DISK_IOPS: -1,
        TAG_MAX_DISK_IOPS: -1,
        TAG_NET_OUTPUT_LOAD: -1,
        TAG_STD: 2,
    },
    ACTION_SHUTDOWN: {
        TAG_PERIOD_DAYS: 14,
        TAG_CPU: 5,
        TAG_MEMORY: 3,
        TAG_AVG_DISK_IOPS: -1,
        TAG_MAX_DISK_IOPS: -1,
        TAG_NET_OUTPUT_LOAD: -1,
        TAG_STD: 1,
    },
    ACTION_SPLIT: {
        TAG_PERIOD_DAYS: 14,
        TAG_CPU: [25, 80],
        TAG_MEMORY: [25, 80],
        TAG_AVG_DISK_IOPS: -1,
        TAG_MAX_DISK_IOPS: -1,
        TAG_NET_OUTPUT_LOAD: -1,
        TAG_PROBABILITY: [50, 50],
        TAG_STD: 1,
    },
    ACTION_SCHEDULE: {
        TAG_PERIOD_DAYS: 14,
        TAG_CPU: 50,
        TAG_MEMORY: 50,
        TAG_AVG_DISK_IOPS: -1,
        TAG_MAX_DISK_IOPS: -1,
        TAG_NET_OUTPUT_LOAD: -1,
        TAG_STD: 1,
        TAG_CRON_START: '0 9 * * 0-4',
        TAG_CRON_STOP: '0 18 * * 0-4',
    },
}


class MockedDataService:
    """
    Allows to replace actual instance metrics with mocked data based on
    instance meta tags.Supported tags:
    - r8s_test_case: SCALE_UP/SCALE_DOWN/SHUTDOWN/SCHEDULE/SPLIT -
        contains resulted action
    - r8s_period_days: mocked data period
    - r8s_cpu_load: average cpu load on instance
    - r8s_memory_load: average memory load on instance
    - r8s_std: standard deviation, used to modify load
    - r8s_cron_start (SCHEDULE only): cron that will be used to generate
        instance load
    - r8s_cron_stop (SCHEDULE only):cron that will be used to generate
        instance load
    - r8s_probability (SPLIT only): to split load by speficic percentages
    """

    def __init__(self, os_service: OSService):
        self.os_service = os_service

        self.action_generator_mapping = {
            ACTION_EMPTY: self.generate_constant_load_metrics,
            ACTION_SHUTDOWN: self.generate_constant_load_metrics,
            ACTION_SCALE_UP: self.generate_constant_load_metrics,
            ACTION_SCALE_DOWN: self.generate_constant_load_metrics,
            ACTION_SCHEDULE: self.generate_schedule_load_metrics,
            ACTION_SPLIT: self.generate_split_load_metrics,
        }

    def process(self, instance_meta_mapping, metric_file_paths):
        instance_tags_mapping = self.parse_tags(
            instance_meta_mapping=instance_meta_mapping)

        meta_mapping = {k: v for k, v in instance_tags_mapping.items()
                        if TAG_TEST_CASE in v}
        file_to_meta_mapping = {}

        for file in metric_file_paths:
            instance_id = self.os_service.path_to_instance_id(file_path=file)
            if instance_id in meta_mapping:
                file_to_meta_mapping[file] = meta_mapping[instance_id]

        if not file_to_meta_mapping:
            _LOG.warning(f'No instances with tag \'{TAG_TEST_CASE}\' found.')
            return

        for file_path, instance_meta in file_to_meta_mapping.items():
            _LOG.debug(f'Going to replace metrics by path \'{file_path}\' '
                       f'with mocked metrics by tags: {instance_meta}')
            self.process_instance(instance_meta=instance_meta,
                                  metric_file_path=file_path)

    def process_instance(self, instance_meta, metric_file_path):
        _LOG.debug(f'Filtering instance meta')
        instance_meta = {k: v for k, v in instance_meta.items()
                         if k in ALLOWED_TAGS}
        _LOG.debug(f'Converting tag values to numbers')
        instance_meta = self.values_to_number(instance_meta=instance_meta)

        test_case = instance_meta.get(TAG_TEST_CASE).upper()
        if test_case not in ALLOWED_ACTIONS:
            _LOG.error(f'Invalid test case specified: \'{test_case}\'. '
                       f'Allowed test cases: {ALLOWED_ACTIONS}')
            return

        test_config = DEFAULT_CONFIG.get(test_case).copy()

        for key, value in instance_meta.items():
            if key not in test_config:
                continue
            default_value = test_config.get(key)
            if isinstance(default_value, list) and not isinstance(value, list):
                _LOG.warning(f'Expected \'list\' value for key \'{key}\', '
                             f'skipping')
                continue
            if isinstance(default_value, int) and not isinstance(value,
                                                                 (int, float)):
                _LOG.warning(f'Expected \'int\' value for key \'{key}\', '
                             f'skipping')
                continue
            test_config[key] = value
        generator = self.action_generator_mapping.get(test_case)
        generator(test_config, metric_file_path)

    @staticmethod
    def values_to_number(instance_meta):
        for k, v in instance_meta.items():
            if v and k in NUMBER_TAGS:
                try:
                    if '/' in v:
                        values = v.split('/')
                        values = [int(i) for i in values]
                        instance_meta[k] = values
                    instance_meta[k] = int(v)
                except (TypeError, ValueError):
                    _LOG.error(f'Invalid value specified for \'{k}\' tag, '
                               f'skipping')
        return instance_meta

    def generate_constant_load_metrics(self, config, metric_file_path):
        period_days = config.get(TAG_PERIOD_DAYS)
        length = POINTS_IN_DAY * period_days

        instance_id_series, instance_type_series, timestamp_series = (
            self.generate_common_columns(
            metric_file_path=metric_file_path, length=length
        ))

        deviation = config.get(TAG_STD)
        cpu_avg = config.get(TAG_CPU)
        memory_avg = config.get(TAG_MEMORY)
        avg_iops_avg = config.get(TAG_AVG_DISK_IOPS)
        max_iops_avg = config.get(TAG_MAX_DISK_IOPS)
        net_output_avg = config.get(TAG_NET_OUTPUT_LOAD)

        cpu_load_series = generate_constant_metric_series(
            distribution='normal',
            loc=cpu_avg,
            scale=deviation,
            size=length
        )
        memory_load_series = generate_constant_metric_series(
            distribution='normal',
            loc=memory_avg,
            scale=deviation,
            size=length
        )
        net_output_load_series = generate_constant_metric_series(
            distribution='normal',
            loc=net_output_avg,
            scale=deviation,
            size=length
        )
        avg_iops_series = generate_constant_metric_series(
            distribution='normal',
            loc=avg_iops_avg,
            scale=deviation,
            size=length
        )
        max_iops_series = generate_constant_metric_series(
            distribution='normal',
            loc=max_iops_avg,
            scale=deviation,
            size=length
        )
        df_data = {
            'instance_id': instance_id_series,
            'instance_type': instance_type_series,
            'timestamp': timestamp_series,
            'cpu_load': cpu_load_series,
            'memory_load': memory_load_series,
            'net_output_load': net_output_load_series,
            'avg_disk_iops': avg_iops_series,
            'max_disk_iops': max_iops_series,
        }
        df = pd.DataFrame(df_data)
        df.to_csv(metric_file_path, sep=',', index=False)

    def generate_schedule_load_metrics(self, config, metric_file_path):
        period_days = config.get(TAG_PERIOD_DAYS)
        length = POINTS_IN_DAY * period_days

        instance_id_series, instance_type_series, timestamp_series = (
            self.generate_common_columns(
            metric_file_path=metric_file_path, length=length
        ))

        deviation = config.get(TAG_STD)
        cpu_avg = config.get(TAG_CPU)
        memory_avg = config.get(TAG_MEMORY)
        avg_iops_avg = config.get(TAG_AVG_DISK_IOPS)
        max_iops_avg = config.get(TAG_MAX_DISK_IOPS)
        net_output_avg = config.get(TAG_NET_OUTPUT_LOAD)
        cron_start = config.get(TAG_CRON_START)
        cron_stop = config.get(TAG_CRON_STOP)

        cron_start_list = self._cron_to_list(cron_start)
        cron_stop_list = self._cron_to_list(cron_stop)

        if not cron_start_list or not cron_stop_list:
            _LOG.error(f'Some of the specified cron strings are not valid')
            return

        work_days, work_hours = self._get_work_days_hours(
            cron_start_list=cron_start_list, cron_stop_list=cron_stop_list)

        cpu_load_series = generate_scheduled_metric_series(
            distribution='normal',
            timestamp_series=timestamp_series,
            work_days=work_days,
            work_hours=work_hours,
            work_kwargs=dict(loc=cpu_avg, scale=deviation),
            idle_kwargs=dict(loc=3, scale=deviation)
        )
        memory_load_series = generate_scheduled_metric_series(
            distribution='normal',
            timestamp_series=timestamp_series,
            work_days=work_days,
            work_hours=work_hours,
            work_kwargs=dict(loc=memory_avg, scale=deviation),
            idle_kwargs=dict(loc=3, scale=deviation)
        )
        net_output_load_series = generate_constant_metric_series(
            distribution='normal',
            loc=net_output_avg,
            scale=deviation,
            size=length
        )
        avg_iops_series = generate_constant_metric_series(
            distribution='normal',
            loc=avg_iops_avg,
            scale=deviation,
            size=length
        )
        max_iops_series = generate_constant_metric_series(
            distribution='normal',
            loc=max_iops_avg,
            scale=deviation,
            size=length
        )
        df_data = {
            'instance_id': instance_id_series,
            'instance_type': instance_type_series,
            'timestamp': timestamp_series,
            'cpu_load': cpu_load_series,
            'memory_load': memory_load_series,
            'net_output_load': net_output_load_series,
            'avg_disk_iops': avg_iops_series,
            'max_disk_iops': max_iops_series,
        }
        df = pd.DataFrame(df_data)
        df.to_csv(metric_file_path, sep=',', index=False)

    def generate_split_load_metrics(self, config, metric_file_path):
        period_days = config.get(TAG_PERIOD_DAYS)
        length = POINTS_IN_DAY * period_days

        instance_id_series, instance_type_series, timestamp_series = (
            self.generate_common_columns(
            metric_file_path=metric_file_path, length=length
        ))

        deviation = config.get(TAG_STD)
        cpu_avg = config.get(TAG_CPU)
        memory_avg = config.get(TAG_MEMORY)
        avg_iops_avg = config.get(TAG_AVG_DISK_IOPS)
        max_iops_avg = config.get(TAG_MAX_DISK_IOPS)
        net_output_avg = config.get(TAG_NET_OUTPUT_LOAD)
        probability = config.get(TAG_PROBABILITY)

        cpu_load_series = generate_split_series(
            distribution='normal',
            avg_loads=cpu_avg,
            probabilities=probability,
            scale=deviation,
            size=length
        )
        memory_load_series = generate_split_series(
            distribution='normal',
            avg_loads=memory_avg,
            probabilities=probability,
            scale=deviation,
            size=length
        )
        net_output_load_series = generate_constant_metric_series(
            distribution='normal',
            loc=net_output_avg,
            scale=deviation,
            size=length
        )
        avg_iops_series = generate_constant_metric_series(
            distribution='normal',
            loc=avg_iops_avg,
            scale=deviation,
            size=length
        )
        max_iops_series = generate_constant_metric_series(
            distribution='normal',
            loc=max_iops_avg,
            scale=deviation,
            size=length
        )

        df_data = {
            'instance_id': instance_id_series,
            'instance_type': instance_type_series,
            'timestamp': timestamp_series,
            'cpu_load': cpu_load_series,
            'memory_load': memory_load_series,
            'net_output_load': net_output_load_series,
            'avg_disk_iops': avg_iops_series,
            'max_disk_iops': max_iops_series,
        }
        df = pd.DataFrame(df_data)
        df.to_csv(metric_file_path, sep=',', index=False)

    def generate_common_columns(self, metric_file_path, length):
        timestamp_series = generate_timestamp_series(
            length=length
        )

        shape_cloud_mapping = {
            CloudEnum.CLOUD_AWS.value: 'c5.4xlarge',
            CloudEnum.CLOUD_AZURE.value: 'Standard_D8_v5',
            CloudEnum.CLOUD_GOOGLE.value: 'n2-standard-8',
        }

        instance_id = self.os_service.path_to_instance_id(
            file_path=metric_file_path)
        cloud = self.os_service.path_to_cloud(file_path=metric_file_path)
        instance_id_series = constant_to_series(
            value=instance_id,
            length=length
        )
        instance_type_series = constant_to_series(
            value=shape_cloud_mapping.get(cloud.upper()),
            length=length
        )

        return instance_id_series, instance_type_series, timestamp_series

    @staticmethod
    def _cron_to_list(cron_str):
        try:
            cron = Cron(cron_str)
            return cron.to_list()
        except ValueError:
            _LOG.error(f'Invalid cron string specified: \'{cron_str}\'')

    @staticmethod
    def _get_work_days_hours(cron_start_list, cron_stop_list):
        start_hours = cron_start_list[1]
        stop_hours = cron_stop_list[1]

        start_week_days = cron_start_list[-1]
        stop_week_days = cron_stop_list[-1]

        work_hours = [list(range(start, stop)) for start, stop in
                      zip(start_hours, stop_hours)]
        work_hours = list(set([item for sublist in work_hours
                               for item in sublist]))
        work_days = list(set(start_week_days + stop_week_days))
        return work_days, work_hours

    @staticmethod
    def parse_tags(instance_meta_mapping: dict):
        result = {}

        for instance_id, instance_meta in instance_meta_mapping.items():
            _LOG.debug(f'Parsing instance tags from meta: \'{instance_meta}\'')
            tags_list = instance_meta.get('tags')
            if not tags_list or tags_list and not isinstance(tags_list, list):
                result[instance_id] = {}
                continue
            instance_tags = {}
            for item in tags_list:
                if not isinstance(item, dict):
                    continue
                key = item.get('key')
                value = item.get('value')

                if not isinstance(key, str) or not isinstance(value, str):
                    _LOG.warning(f'Both tag key and value must be strings: '
                                 f'{key}:{value}')
                    continue
                instance_tags[key] = value
            result[instance_id] = instance_tags
        return result
