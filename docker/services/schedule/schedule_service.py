import statistics
from datetime import datetime, timedelta
from typing import List

import pandas

from commons.constants import WEEK_DAYS
from commons.log_helper import get_logger
from commons.profiler import profiler
from models.algorithm import RecommendationSettings
from models.recommendation_history import RecommendationHistory, \
    RecommendationTypeEnum, FeedbackStatusEnum
from services.metrics_service import MetricsService
from services.schedule.active_schedule_period import ActiveSchedulePeriod
from services.schedule.frequency_map import FrequencyMap
from services.schedule.schedule_item import ScheduleItem

_LOG = get_logger('r8s-schedule-service')

SECONDS_IN_DAY = 86400
MINIMUM_SCHEDULE_DURATION_MINUTES = 120
MAX_GROUPING_DIFFERENCE_SECONDS = 3600


class ScheduleService:
    def __init__(self, metrics_service: MetricsService):
        self.metrics_service = metrics_service

    @profiler(execution_step=f'instance_schedule_generation')
    def generate_schedule(self, recommendation_settings: RecommendationSettings,
                          shutdown_periods, instance_id, df, instance_meta=None,
                          past_recommendations: List[RecommendationHistory] = None):
        # todo process instance meta

        _LOG.debug(f'Checking if schedule is disabled by user adjustments')
        if self._is_schedule_disabled(recommendations=past_recommendations):
            _LOG.debug(f'Schedule action is disabled for instance.')
            return self.get_always_run_schedule()

        _LOG.debug(f'Generating schedule for instance \'{instance_id}\'')

        covered_days = (df.index.max() - df.index.min()).total_seconds()
        covered_days = round(covered_days / SECONDS_IN_DAY)

        min_days = recommendation_settings.min_allowed_days_schedule
        if covered_days < min_days:
            _LOG.warning(f'Minimum {min_days} days of '
                         f'telemetry required for schedule recommendation')
            return self.get_always_run_schedule()

        max_days = recommendation_settings.max_allowed_days_schedule
        if covered_days > max_days:
            _LOG.debug(f'Discarding metrics that are older than {max_days} '
                       f'for schedule calculation')
            threshold = df.index.max().date() - timedelta(days=max_days)
            shutdown_periods = [df for df in shutdown_periods
                                if df.index.max().date() >= threshold]
            df = df[df.index.date >= threshold]

        _LOG.debug(f'Extracting active periods')
        active_schedule_periods = self._get_active_schedule_periods(
            shutdown_periods=shutdown_periods,
            instance_id=instance_id
        )

        _LOG.debug(f'Generating frequency map')
        frequency_map = self._generate_frequency_map(
            active_schedule_periods=active_schedule_periods,
            record_step_minutes=recommendation_settings.record_step_minutes,
            action='shutdown'
        )

        min_duration = recommendation_settings.min_schedule_day_duration_minutes
        _LOG.debug(f'Generating daily schedules')
        day_schedules = self._generate_daily_schedule(
            df=df,
            frequency_map=frequency_map,
            minimum_duration=min_duration
        )
        _LOG.debug(f'Grouping schedules by day')
        schedule_result = self._group_by_days(day_schedules=day_schedules)
        schedule_result = [item.as_dict() for item in schedule_result]

        _LOG.debug(f'Schedule result: \'{schedule_result}\'')
        return schedule_result

    @staticmethod
    def _is_schedule_disabled(recommendations: List[RecommendationHistory]):
        schedule_action = RecommendationTypeEnum.ACTION_SCHEDULE
        dont_recommend_status = FeedbackStatusEnum.DONT_RECOMMEND
        for recommendation in recommendations:
            if recommendation.recommendation_type == schedule_action and \
                    recommendation.feedback_status == dont_recommend_status:
                return True
        return False

    def _get_active_schedule_periods(
            self, shutdown_periods: list,
            instance_id: str) -> List[ActiveSchedulePeriod]:
        active_schedule_periods = []
        for index, period in enumerate(shutdown_periods):
            _LOG.debug(f'Processing period: {index}/{len(shutdown_periods)} '
                       f'for instance \'{instance_id}\'')
            # todo calculate schedule probability
            ml_result = [0.5]
            active_schedule_period = self._get_active_schedule_period(
                instance_id=instance_id,
                df=period,
                ml_result=ml_result,
                model_action="shutdown"
            )
            if active_schedule_period:
                active_schedule_periods.append(active_schedule_period)
        return active_schedule_periods

    def _generate_frequency_map(
            self, active_schedule_periods: List[ActiveSchedulePeriod],
            action: str, record_step_minutes: int) -> FrequencyMap:
        day_time_points = self._get_day_time_points(
            record_step_minutes=record_step_minutes)
        frequency_map = FrequencyMap(action=action,
                                     time_points=day_time_points,
                                     step_minutes=record_step_minutes)

        for period in active_schedule_periods:
            if not period.action:
                continue
            start_index = day_time_points.index(period.time_from)
            end_index = day_time_points.index(period.time_to)
            if end_index == 0:
                end_index = len(day_time_points) - 1

            period_time_points = day_time_points[start_index: end_index + 1]
            weekday = period.weekday

            for period_time_point in period_time_points:
                frequency_map_item = frequency_map[weekday][period_time_point]
                if not frequency_map_item:
                    continue
                frequency_map_item.count += 1
                frequency_map_item.probabilities.append(period.probability)

        return frequency_map

    @staticmethod
    def _get_active_schedule_period(instance_id: str, df: pandas.DataFrame,
                                    ml_result: list,
                                    model_action: str) -> ActiveSchedulePeriod:
        time_from = df.index.min().strftime('%H:%M')
        time_to = df.index.max().strftime('%H:%M')
        weekday = df.index.min().strftime('%A')
        result_avg = statistics.mean(ml_result)
        probability = round(float(result_avg), 2)

        if time_to == '23:50':
            time_to = '00:00'
        return ActiveSchedulePeriod(
            instance_id=instance_id,
            weekday=weekday,
            time_from=time_from,
            time_to=time_to,
            action=model_action,
            probability=probability
        )

    @staticmethod
    def _generate_daily_schedule(
            df: pandas.DataFrame, frequency_map: FrequencyMap,
            minimum_duration=MINIMUM_SCHEDULE_DURATION_MINUTES) \
            -> List[ScheduleItem]:
        df_diff_seconds = (max(df.T) - min(df.T)).total_seconds()
        processed_days = round(df_diff_seconds / SECONDS_IN_DAY)

        daily_schedules = []
        for day in WEEK_DAYS:
            schedule_day = frequency_map[day].get_day_schedule(
                processed_days=processed_days,
                minimum_duration_minutes=minimum_duration)
            daily_schedules.extend(schedule_day)
        return daily_schedules

    @staticmethod
    def _group_by_days(day_schedules: List[ScheduleItem]) -> List[ScheduleItem]:
        day_schedules = sorted(day_schedules, key=lambda d: d.start)

        grouped = []
        processed_periods = []
        processed = []
        for day_schedule in day_schedules:
            if day_schedule in processed:
                continue
            period_key = (day_schedule.start, day_schedule.stop)
            if period_key in processed_periods:
                continue
            same = [i for i in day_schedules if day_schedule.is_similar(
                other=i, max_diff_second=MAX_GROUPING_DIFFERENCE_SECONDS)]
            grouped_weekdays = []
            grouped_prob = []
            for i in same:
                grouped_weekdays.extend(i.weekdays)
                grouped_prob.append(i.probability)
            start, stop = ScheduleItem.get_common_start_stop(
                day_schedules=same)

            grouped_weekdays = list(set(grouped_weekdays))
            grouped_weekdays.sort(key=lambda k: WEEK_DAYS.index(k))

            schedule_item = ScheduleItem(
                start=start,
                stop=stop,
                weekdays=grouped_weekdays,
                probability=round(sum(grouped_prob) / len(grouped_prob), 2)
            )
            processed.extend(same)
            grouped.append(schedule_item)
            processed_periods.append(period_key)

        return sorted(grouped, key=lambda x: x.duration_minutes, reverse=True)

    @staticmethod
    def _get_day_time_points(record_step_minutes: int) -> List[str]:
        points = []

        dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for _ in range(24 * 60 // record_step_minutes):
            points.append(dt.strftime('%H:%M'))
            dt += timedelta(minutes=record_step_minutes)

        return points

    @staticmethod
    def get_always_run_schedule():
        return [{
            'start': '00:00',
            'stop': '00:00',
            'weekdays': WEEK_DAYS
        }]

    def get_runtime_minutes(self, schedule: list):
        runtime_minutes = 0
        day_time_points = self._get_day_time_points(record_step_minutes=5)
        for schedule_part in schedule:
            start = schedule_part.get('start')
            stop = schedule_part.get('stop')

            start_index = day_time_points.index(start)
            stop_index = day_time_points.index(stop)

            covered_points = len(day_time_points[start_index: stop_index])
            runtime_minutes_day = covered_points * 5
            runtime_minutes += (runtime_minutes_day *
                                len(schedule_part.get('weekdays')))
        return runtime_minutes
