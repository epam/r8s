import datetime

from tests_executor.distributions import Distributions


def expand_schedule(timestamp_series, series, work_days, work_hours,
                    delta_minutes, loc):
    relative_index = 0
    for index, (timestamp, value) in enumerate(zip(timestamp_series, series)):
        dt = datetime.datetime.utcfromtimestamp(timestamp)
        if dt.weekday() not in work_days or dt.weekday() in work_days \
                and dt.hour in work_hours:
            continue  # no actions in non-schedule days

        dt_delta = dt + datetime.timedelta(minutes=delta_minutes)
        if dt_delta.hour in work_hours and dt.weekday() in work_days:
            delta_points = delta_minutes / 5

            percent = relative_index / delta_points
            if percent > 1:
                relative_index = 0
                continue
            if percent == 0:
                relative_index += 1
                continue
            new_loc = loc * percent
            new_value = Distributions.generate(distribution='normal',
                                               loc=new_loc,
                                               scale=5)
            relative_index += 1
            series[index] = new_value
        else:
            relative_index = 0
    return series
