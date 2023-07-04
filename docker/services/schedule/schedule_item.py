from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional


@dataclass
class ScheduleItem:
    weekdays: List[str]
    start: str
    stop: Optional[str] = None
    probability: Optional[float] = None

    @property
    def duration_minutes(self):
        if not self.start or not self.stop:
            return 0
        start_date = datetime.strptime(self.start, '%H:%M')
        stop_date = datetime.strptime(self.stop, '%H:%M')

        if self.stop == '00:00':
            stop_date = stop_date + timedelta(days=1)

        duration_minutes = (stop_date - start_date).total_seconds() // 60
        if self.weekdays:
            duration_minutes *= len(self.weekdays)
        return round(duration_minutes)

    @property
    def start_datetime(self):
        dt = datetime.strptime(self.start, '%H:%M')
        dt = dt.replace(month=1, day=1)
        return dt

    @property
    def stop_datetime(self):
        dt = datetime.strptime(self.stop, '%H:%M')
        dt = dt.replace(month=1, day=1)
        return dt

    @property
    def is_filled(self):
        return self.start and self.stop

    def is_similar(self, other, max_diff_second):
        if not isinstance(other, ScheduleItem):
            return False

        delta_start = self.start_datetime - other.start_datetime
        delta_start = abs(delta_start.total_seconds())

        delta_stop = self.stop_datetime - other.stop_datetime
        delta_stop = abs(delta_stop.total_seconds())

        return delta_start <= max_diff_second and \
            delta_stop <= max_diff_second

    def as_dict(self):
        item = {
            'weekdays': self.weekdays,
            'start': self.start,
            'stop': self.stop,
        }
        if self.stop == '00:00':
            item['stop'] = '23:50'
        if self.probability:
            item['probability'] = self.probability
        return item

    @staticmethod
    def get_common_start_stop(day_schedules):
        min_start_dt = None
        max_stop_dt = None

        for day_schedule in day_schedules:
            start_dt = day_schedule.start_datetime
            stop_dt = day_schedule.stop_datetime

            if not min_start_dt or start_dt < min_start_dt:
                min_start_dt = start_dt

            if not max_stop_dt or stop_dt > max_stop_dt:
                max_stop_dt = stop_dt
        min_start = min_start_dt.strftime('%H:%M')
        max_stop = max_stop_dt.strftime('%H:%M')
        return min_start, max_stop
