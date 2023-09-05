import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Union, List

from commons.constants import WEEK_DAYS
from services.schedule.schedule_item import ScheduleItem


@dataclass
class FrequencyMapItem:
    action: str
    probabilities: list = field(default_factory=list)
    count: int = 0


class FrequencyMap:
    def __init__(self, action, time_points, step_minutes):
        self.__frequency_map = {}
        for week_day in WEEK_DAYS:
            self.__frequency_map[week_day] = FrequencyMapDay(
                action=action, time_points=time_points, weekday=week_day,
                step_minutes=step_minutes)

    def __getitem__(self, item):
        return self.__frequency_map.get(item)


class FrequencyMapDay:
    def __init__(self, action: str, time_points: list,
                 weekday: Union[List, str], step_minutes: int):
        self.__frequency_map = {}
        self.time_points = time_points
        self.step_minutes = step_minutes

        if not isinstance(weekday, list):
            weekday = [weekday]
        self.weekday = weekday

        for point in time_points:
            self.__frequency_map[point] = FrequencyMapItem(action=action)

    def get_day_schedule(self, processed_days, minimum_duration_minutes=30):
        action_period = self.__get_action_period(
            processed_days=processed_days)
        periods = self.__to_day_schedule(
            action_period=action_period)
        periods = [period for period in periods
                   if period.duration_minutes >= minimum_duration_minutes]
        self.__add_probability(periods=periods)
        return periods

    def __add_probability(self, periods: List[ScheduleItem]):
        for day_schedule in periods:
            start = day_schedule.start
            stop = day_schedule.stop

            start_index = self.time_points.index(start)
            stop_index = self.time_points.index(stop)

            schedule_item_time_points = self.time_points[
                                        start_index:stop_index + 1]
            period_probability = self.__get_period_probability(
                schedule_time_points=schedule_item_time_points
            )
            day_schedule.probability = period_probability
        return periods

    def __get_action_period(self, processed_days):
        action_values = self.__get_action_values()
        threshold_percent = statistics.quantiles(action_values, n=4)[1]

        shutdown_period = [key for key in self.__frequency_map if
                           self.__frequency_map[
                               key].count >= threshold_percent and
                           self.__frequency_map[
                               key].count >= 0.75 * processed_days / 7]

        action_period = [point for point in self.time_points if point
                         not in shutdown_period]
        return action_period

    def __to_day_schedule(self, action_period):
        periods = []
        period = None
        prev_dt = None
        for index, time_point in enumerate(action_period):
            dt = datetime.strptime(time_point, '%H:%M')
            if not period:
                period = ScheduleItem(start=time_point,
                                      weekdays=self.weekday)
            elif period and (dt - prev_dt).seconds == self.step_minutes * 60:
                period.stop = time_point
            else:
                if period.is_filled:
                    periods.append(period)
                period = ScheduleItem(start=time_point,
                                      weekdays=self.weekday)
            prev_dt = dt

        if period and period.is_filled:
            if period.stop == self.time_points[-1]:
                period.stop = '00:00'
            periods.append(period)

        return periods

    def __get_action_values(self):
        items = list(self.__frequency_map.values())
        return [item.count for item in items]

    def __get_period_probability(self, schedule_time_points: List[str]):
        probability_list = []
        shutdown_period_time_points = [point for point in self.time_points
                                       if point not in schedule_time_points]
        for time_point in shutdown_period_time_points:
            frequency_map_item = self.__frequency_map.get(time_point)
            if not frequency_map_item:
                continue
            probability_list.extend(frequency_map_item.probabilities)

        if not probability_list:
            return 0
        return round(sum(probability_list) / len(probability_list), 2)

    def __getitem__(self, item):
        return self.__frequency_map.get(item)
