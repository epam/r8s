import datetime
import glob
import json
import os
from typing import List

import numpy as np
import pandas
import pandas as pd
import pytz
from pytz import UnknownTimeZoneError

from commons import dateparse
from commons.constants import JOB_STEP_PROCESS_METRICS, META_FILE_NAME, \
    JOB_STEP_INITIALIZE_ALGORITHM, JOB_STEP_VALIDATE_METRICS, COLUMN_CPU_LOAD, \
    CSV_EXTENSION
from commons.exception import ExecutorException
from commons.log_helper import get_logger
from commons.profiler import profiler
from models.algorithm import Algorithm
from models.recommendation_history import RecommendationHistory
from services.clustering_service import ClusteringService
from services.resize.resize_trend import ResizeTrend

_LOG = get_logger('r8s-metrics-service')

TIMESTAMP_FREQUENCY = '5Min'
DAY_RECORDS = 144

META_KEY_RESOURCE_ID = 'resourceId'
META_KEY_CREATE_DATE_TIMESTAMP = 'createDateTimestamp'
MINIMUM_DAYS_TO_CUT_INCOMPLETE_EDGE_DAYS = 14

INSUFFICIENT_DATA_ERROR_TEMPLATE = """Insufficient data. Analysed period 
must be larger than a full {days} day(s) with 5-min frequency 
of records."""


class MetricsService:

    def __init__(self, clustering_service: ClusteringService):
        self.clustering_service = clustering_service

    def calculate_instance_trend(self, df, algorithm: Algorithm) \
            -> ResizeTrend:
        metric_attrs = set(list(algorithm.metric_attributes))

        resize_trend = ResizeTrend()

        for metric in metric_attrs:
            metric_column = self.get_column(metric_name=metric, df=df)

            resize_trend.add_metric_trend(
                metric_name=metric,
                column=metric_column
            )
        return resize_trend

    def calculate_instance_trend_multiple(
            self, algorithm: Algorithm, non_straight_periods,
            total_length) -> List[ResizeTrend]:
        result = []

        for period_list in non_straight_periods:
            concat_dt = pd.concat(period_list)
            period_trend = self.calculate_instance_trend(
                df=concat_dt, algorithm=algorithm)
            period_trend.probability = round(
                len(concat_dt) / total_length, 2)
            result.append(period_trend)
        if not result:
            return result
        metric_attrs = set(list(algorithm.metric_attributes))
        # removes duplicated trends with same metric resize directions
        result = ResizeTrend.remove_duplicates(trends=result,
                                               metric_attrs=metric_attrs)
        return result

    @staticmethod
    def get_threshold_value(column):
        return column.quantile(.9)

    @staticmethod
    def get_column(metric_name, df):
        try:
            column = df[metric_name]
            return column
        except Exception as e:
            _LOG.error(f'Invalid metric format. Exception: {e}')
            raise ExecutorException(
                step_name=JOB_STEP_PROCESS_METRICS,
                reason=f'Invalid metric format. Exception: {e}'
            )

    @staticmethod
    def get_last_period(df, days=7):
        range_max = df.index.max()
        range_min = range_max - datetime.timedelta(days=days)

        # take slice with final N days of data
        sliced_df = df[(df.index >= range_min) &
                       (df.index <= range_max)]
        return sliced_df

    @staticmethod
    def fill_missing_timestamps(df, diff=TIMESTAMP_FREQUENCY):
        instance_id = df['instance_id'][0]
        instance_type = df['instance_type'][0]
        df = df[~df.index.duplicated(keep='last')]

        complete_index = pd.date_range(df.index.min(), df.index.max(),
                                       freq=TIMESTAMP_FREQUENCY)
        missing_timestamps = complete_index.difference(df.index)
        missing_df = pd.DataFrame(index=missing_timestamps, columns=df.columns)
        missing_df['cpu_load'].fillna(0, inplace=True)
        missing_df['memory_load'].fillna(0, inplace=True)
        missing_df['net_output_load'].fillna(0, inplace=True)
        missing_df['avg_disk_iops'].fillna(-1, inplace=True)
        missing_df['avg_disk_iops'].fillna(-1, inplace=True)
        df = pd.concat([df, missing_df]).sort_index()
        df = df.assign(instance_id=instance_id)
        df = df.assign(instance_type=instance_type)
        df = df.resample(diff).ffill()
        return df

    def validate_metric_file(self, algorithm: Algorithm, metric_file_path):
        try:
            df = self.read_metrics(metric_file_path=metric_file_path,
                                   algorithm=algorithm, parse_index=False)
        except Exception as e:
            _LOG.warning(f'Metric file can not be read: Exception: {e}')
            raise ExecutorException(
                step_name=JOB_STEP_VALIDATE_METRICS,
                reason=f'Metric file can not be read: Exception: {e}'
            )
        column_names = list(df.columns)

        required_columns_set = set(list(algorithm.required_data_attributes))
        file_columns_set = set(column_names)

        missing_columns = list(required_columns_set - file_columns_set)
        excess_columns = list(file_columns_set - required_columns_set)
        if missing_columns or excess_columns:
            _LOG.error(f'File \'{metric_file_path}\' does not match the '
                       f'required set of columns')
        error_message = []
        if missing_columns:
            _LOG.error(f'Missing columns: \'{missing_columns}\'')
            error_message.append(f'Missing columns: \'{missing_columns}\'')
        if excess_columns:
            _LOG.error(f'Excess columns: \'{excess_columns}\'')

        if error_message:
            raise ExecutorException(
                step_name=JOB_STEP_VALIDATE_METRICS,
                reason=';'.join(error_message)
            )
        absent_metric_attrs = []
        metric_attrs = list(algorithm.metric_attributes)
        for metric_attr in metric_attrs:
            if (df[metric_attr] == -1).all():
                absent_metric_attrs.append(metric_attr)
        if set(absent_metric_attrs) == set(metric_attrs):
            _LOG.warning(f'Metric file must contain data for at '
                         f'least one metric: {", ".join(metric_attrs)}')
            raise ExecutorException(
                step_name=JOB_STEP_INITIALIZE_ALGORITHM,
                reason=f'Metric file must contain data for at '
                       f'least one metric: {", ".join(metric_attrs)}'
            )

    def load_df(self, path, algorithm: Algorithm,
                applied_recommendations: List[RecommendationHistory] = None,
                instance_meta: dict = None, max_days: int = None):
        all_attrs = set(list(algorithm.required_data_attributes))
        metric_attrs = set(list(algorithm.metric_attributes))
        non_metric = all_attrs - metric_attrs
        non_metric.remove(algorithm.timestamp_attribute)
        try:
            df = self.read_metrics(metric_file_path=path, algorithm=algorithm)
            df = self.trim_from_appliance_date(
                df=df, applied_recommendations=applied_recommendations)
            recommendation_settings = algorithm.recommendation_settings
            timezone_name = recommendation_settings.target_timezone_name
            if timezone_name:
                _LOG.debug(f'Converting to timezone \'{timezone_name}\'')
                try:
                    df = df.tz_convert(timezone_name)
                except UnknownTimeZoneError:
                    _LOG.error(f'Unknown timezone \'{timezone_name}\'')
            df = self.fill_missing_timestamps(df=df)
            df.sort_index(ascending=True, inplace=True)
            for attr in non_metric:
                df.drop(attr, inplace=True, axis=1)
            df = self.discard_start(
                df=df,
                algorithm=algorithm,
                instance_meta=instance_meta
            )
            df_duration_days = (df.index.max() - df.index.min()).days
            min_allowed_days = (algorithm.recommendation_settings.
                                min_allowed_days)
            if np.isnan(df_duration_days) or \
                    df_duration_days < min_allowed_days:
                message = INSUFFICIENT_DATA_ERROR_TEMPLATE.format(
                    days=min_allowed_days
                )
                _LOG.error(message)
                raise ExecutorException(
                    step_name=JOB_STEP_INITIALIZE_ALGORITHM,
                    reason=message
                )
            max_days = max_days or recommendation_settings.max_days
            df = self.get_last_period(df,
                                      days=max_days)
            df = self.group_by_time(
                df=df,
                step_minutes=recommendation_settings.record_step_minutes,
                optimized_threshold_days=
                recommendation_settings.optimized_aggregation_threshold_days,
                optimized_step_minutes=
                recommendation_settings.optimized_aggregation_step_minutes
            )
            return df
        except ExecutorException as e:
            raise e
        except Exception as e:
            _LOG.error(f'Error occurred while reading metrics file: {str(e)}')
            raise ExecutorException(
                step_name=JOB_STEP_PROCESS_METRICS,
                reason=f'Unable to read metrics file'
            )

    @staticmethod
    def discard_start(df: pd.DataFrame,
                      algorithm: Algorithm, instance_meta=None):
        if instance_meta and 'creationDateTimestamp' in instance_meta:
            try:
                creation_date_timestamp = instance_meta[
                    'creationDateTimestamp']
                _LOG.debug(f'Discarding metrics before timestamp: '
                           f'{creation_date_timestamp}')
                creation_dt = datetime.datetime.utcfromtimestamp(
                    creation_date_timestamp // 1000)
                creation_dt = creation_dt.astimezone(
                    pytz.timezone(str(df.index.max().tz)))
                return df[(df.index >= creation_dt)]
            except Exception as e:
                _LOG.debug(f'Failed to discard metrics before timestamp. '
                           f'Exception: {e}')
        if algorithm.recommendation_settings.discard_initial_zeros:
            _LOG.debug(
                f'Going to discard metrics without load from the start.')
            metric_attrs = algorithm.metric_attributes
            try:
                for index, row in df.iterrows():
                    if not all(row[attr] in (0, -1) for attr in metric_attrs):
                        _LOG.debug(f'Metrics before {index} will be discarded')
                        return df[df.index >= index]
            except Exception as e:
                _LOG.debug(f'Failed to discard leading metrics with zeros. '
                           f'Exception: {e}')
        return df

    def merge_metric_files(self, metrics_folder_path, algorithm: Algorithm):
        metric_files = [y for x in os.walk(metrics_folder_path)
                        for y in glob.glob(os.path.join(x[0], '*.csv'))]
        instance_id_date_mapping = {}

        for file in metric_files:
            path_items = file.split(os.sep)[::-1]
            instance_id, date = path_items[0:2]
            instance_id = instance_id.replace(CSV_EXTENSION, '')
            if instance_id in instance_id_date_mapping:
                instance_id_date_mapping[instance_id].append(file)
            else:
                instance_id_date_mapping[instance_id] = [file]
        resulted_files = []
        for instance_id, files in instance_id_date_mapping.items():
            if len(files) == 1:
                resulted_files.append(files[0])
                continue
            most_recent = max(files)
            files = sorted(files)

            csv_to_combine = [self.read_metrics(f, algorithm=algorithm,
                                                parse_index=False)
                              for f in files]
            combined_csv = pd.concat(csv_to_combine)
            combined_csv.sort_values(algorithm.timestamp_attribute)
            combined_csv.to_csv(most_recent, index=False)
            resulted_files.append(most_recent)

        for file in metric_files:
            if file not in resulted_files:
                os.remove(file)
        return resulted_files

    @profiler(execution_step=f'instance_clustering')
    def divide_on_periods(self, df, algorithm: Algorithm):
        r_settings = algorithm.recommendation_settings
        df = self.divide_by_days(
            df, skip_incomplete_corner_days=True,
            step_minutes=r_settings.record_step_minutes,
            optimized_aggregation_threshold_days=
            r_settings.optimized_aggregation_threshold_days,
            optimized_step_minutes=
            r_settings.optimized_aggregation_step_minutes)
        shutdown_periods = []
        low_util_periods = []
        good_util_periods = []
        over_util_periods = []
        centroids = []
        for index, df_day in enumerate(df):
            shutdown, low, medium, high, day_centroids = self.process_day(
                df=df_day, algorithm=algorithm)
            shutdown_periods.extend(shutdown)
            low_util_periods.extend(low)
            good_util_periods.extend(medium)
            over_util_periods.extend(high)
            centroids.extend(day_centroids)

        return shutdown_periods, low_util_periods, \
            good_util_periods, over_util_periods, centroids

    @staticmethod
    def group_by_time(df, step_minutes: int,
                      optimized_threshold_days: int = None,
                      optimized_step_minutes: int = None):
        if not optimized_threshold_days and not optimized_step_minutes:
            return df.groupby(pd.Grouper(freq=f'{step_minutes}Min')).mean()

        threshold_date = df.index.max().date() - datetime.timedelta(
            days=optimized_threshold_days)
        threshold_date_str = threshold_date.isoformat()

        latest_df = df[df.index >= threshold_date_str]
        old_df = df[df.index < threshold_date_str]

        latest_df = latest_df.groupby(pd.Grouper(
            freq=f'{step_minutes}Min')).mean()
        old_df = old_df.groupby(pd.Grouper(
            freq=f'{optimized_step_minutes}Min')).mean()

        return pd.concat([old_df, latest_df])

    @staticmethod
    def divide_by_days(df, skip_incomplete_corner_days: bool,
                       step_minutes: int,
                       optimized_aggregation_threshold_days: int = None,
                       optimized_step_minutes: int = None):
        df_list = [group[1] for group in df.groupby(df.index.date)]
        if not df_list:
            return df_list
        if len(df_list) < MINIMUM_DAYS_TO_CUT_INCOMPLETE_EDGE_DAYS \
                and not skip_incomplete_corner_days:
            return df_list
        last_day_df = df_list[-1]
        if len(last_day_df) < 24 * 60 // step_minutes:
            df_list = df_list[:-1]
        first_day_df = df_list[0]

        if optimized_aggregation_threshold_days and optimized_step_minutes:
            diff_days = abs(first_day_df.index.max().date() -
                            last_day_df.index.max().date()).days
            # to verify that optimized aggregation is used for the first day
            if diff_days > optimized_aggregation_threshold_days:
                step_minutes = optimized_step_minutes
        if len(first_day_df) < 24 * 60 // step_minutes:
            df_list = df_list[1:]
        return df_list

    def process_day(self, df: pandas.DataFrame, algorithm: Algorithm):
        shutdown = []
        low_util = []
        good_util = []
        over_util = []

        df_, centroids = self.clustering_service.cluster(
            df=df,
            algorithm=algorithm)

        _LOG.debug(f'Clusters centroids: {centroids}')
        r_settings = algorithm.recommendation_settings
        thresholds = r_settings.thresholds

        for index, centroid in enumerate(centroids):
            if not centroid:
                continue
            cluster: pd.DataFrame = df.loc[df['cluster'] == index]
            cluster.drop('cluster', axis=1, inplace=True)
            if centroid[0] < thresholds[0]:
                shutdown.append(cluster)
            elif thresholds[0] <= centroid[0] < \
                    thresholds[1]:
                low_util.append(cluster)
            elif thresholds[1] <= centroid[0] < \
                    thresholds[2]:
                good_util.append(cluster)
            else:
                over_util.append(cluster)

        shutdown = pd.concat(shutdown) if shutdown else None
        low_util = pd.concat(low_util) if low_util else None
        good_util = pd.concat(good_util) if good_util else None
        over_util = pd.concat(over_util) if over_util else None

        step_minutes_options = [r_settings.record_step_minutes]
        if (r_settings.optimized_aggregation_threshold_days
                and r_settings.optimized_aggregation_step_minutes):
            step_minutes_options.append(
                r_settings.optimized_aggregation_step_minutes)

        # compare algorithm-allowed step minutes with actual in df,
        # leave real one if matches
        record_step_minutes = self.get_diff_minutes(df.index[1], df.index[0])
        if record_step_minutes in step_minutes_options:
            step_minutes_options = [record_step_minutes]

        result = [self.get_time_ranges(
            cluster, step_minutes_options=step_minutes_options) for cluster in
            (shutdown, low_util, good_util, over_util)]
        result.append(centroids)
        return result

    @staticmethod
    def get_non_empty_attrs(df: pd.DataFrame, attrs):
        non_empty = []
        for attr in attrs:
            is_empty = all(value == -1 for value in list(df[attr]))
            if not is_empty:
                non_empty.append(attr)
        return non_empty

    @staticmethod
    def filter_by_ranges(row, periods):
        row_time = row.name.time()
        for period in periods:
            if period[0] <= row_time <= period[1]:
                return row

    def get_time_ranges(self, df, step_minutes_options: List[int]):
        if not isinstance(df, pd.DataFrame) or len(df) == 0:
            return []

        period_start_row_index = None
        period_end_row_index = None
        dfs_ = []
        last_row = None

        if not df.index.is_monotonic_increasing:
            df.sort_index(inplace=True)
        for row in df.itertuples():
            if not period_start_row_index:
                period_start_row_index = row.Index
            else:
                diff_minutes = self.get_diff_minutes(
                    row.Index, last_row.Index
                )
                if diff_minutes in step_minutes_options:
                    period_end_row_index = row.Index
                elif period_end_row_index:
                    dfs_.append(df[(df.index >= period_start_row_index) &
                                   (df.index <= period_end_row_index)])
                    period_start_row_index = row.Index
                    period_end_row_index = None
            last_row = row
        if period_start_row_index and period_end_row_index:
            dfs_.append(df[(df.index >= period_start_row_index) & (
                    df.index <= period_end_row_index)])

        for index, df_ in enumerate(dfs_):
            step_minutes = (df_.index[1] - df_.index[0]).seconds // 60
            if step_minutes != min(step_minutes_options):
                dfs_[index] = df_.asfreq(
                    freq=f'{min(step_minutes_options)}Min',
                    method='ffill')
        return dfs_

    @staticmethod
    def get_diff_minutes(t1: pd.Timestamp, t2: pd.Timestamp):
        return int((t1 - t2).total_seconds() // 60)

    @staticmethod
    def filter_short_periods(periods, min_length_sec=1800):
        periods = [df for df in periods
                   if (df.index.max() - df.index.min()).total_seconds()
                   >= min_length_sec]
        periods.sort(key=lambda df: df.index.min())
        return periods

    def get_instance_type(self, metric_file_path, algorithm: Algorithm,
                          instance_type_attr='instance_type'):
        try:
            df = self.read_metrics(metric_file_path=metric_file_path,
                                   algorithm=algorithm, parse_index=False)
            return df[instance_type_attr][0]
        except Exception as e:
            _LOG.error(f'Failed to extract instance type from metric file. '
                       f'Error: {e}')
            raise ExecutorException(
                step_name=JOB_STEP_PROCESS_METRICS,
                reason=f'Failed to extract instance type from metric file. '
                       f'Error: {e}'
            )

    @staticmethod
    def read_metrics(metric_file_path, algorithm: Algorithm = None,
                     parse_index=True):
        try:
            if not parse_index:
                return pd.read_csv(metric_file_path,
                                   **algorithm.read_configuration)
            return pd.read_csv(
                metric_file_path, parse_dates=True,
                date_parser=dateparse,
                index_col=algorithm.timestamp_attribute,
                **algorithm.read_configuration)
        except Exception as e:
            _LOG.error(f'Error occurred while reading metrics file: {str(e)}')
            raise ExecutorException(
                step_name=JOB_STEP_PROCESS_METRICS,
                reason=f'Unable to read metrics file'
            )

    def read_meta(self, metrics_folder):
        instance_meta_mapping = {}

        files = list(glob.iglob(metrics_folder + f'**/**/{META_FILE_NAME}',
                                recursive=True))
        _LOG.debug(f'Found \'{len(files)}\' meta files, extracting meta')
        for file in files:
            instance_meta_mapping = self._read_meta_file(
                meta_file_path=file,
                instance_meta_mapping=instance_meta_mapping)

        _LOG.debug(f'Loaded meta: {instance_meta_mapping}')
        return instance_meta_mapping

    @staticmethod
    def trim_from_appliance_date(df: pandas.DataFrame,
                                 applied_recommendations:
                                 List[RecommendationHistory]):
        if not applied_recommendations:
            return df

        last_applied_date = max(item.feedback_dt for item in
                                applied_recommendations)
        _LOG.debug(f'Trimming metrics from date '
                   f'\'{last_applied_date.isoformat()}\'')
        if df.index.tz:
            last_applied_date = last_applied_date.replace(tzinfo=pytz.UTC)
        return df[df.index > last_applied_date]

    @staticmethod
    def _read_meta_file(meta_file_path: str, instance_meta_mapping: dict):
        _LOG.debug(f'Processing meta file \'{meta_file_path}\'')
        try:
            with open(meta_file_path, 'r') as f:
                file_meta = json.load(f)
        except json.decoder.JSONDecodeError:
            _LOG.error(f'Unable to read meta file \'{meta_file_path}\', '
                       f'skipping')
            return instance_meta_mapping
        if not isinstance(file_meta, list):
            _LOG.error(f'Invalid meta format: must be a valid list')
            return instance_meta_mapping

        for resource_meta in file_meta:
            resource_id = resource_meta.get(META_KEY_RESOURCE_ID)
            if not resource_id:
                continue
            if resource_id not in instance_meta_mapping:
                instance_meta_mapping[resource_id] = resource_meta
                continue
            timestamp = resource_meta.get(META_KEY_CREATE_DATE_TIMESTAMP)

            instance_timestamp = instance_meta_mapping[
                resource_id].get(META_KEY_CREATE_DATE_TIMESTAMP)

            # overwrite instance meta with latest meta found
            if timestamp and instance_timestamp and \
                    timestamp > instance_timestamp \
                    or not instance_timestamp:
                instance_meta_mapping[resource_id].update(resource_meta)
        return instance_meta_mapping
