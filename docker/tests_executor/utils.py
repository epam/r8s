import random
from datetime import datetime, timedelta, timezone
from functools import wraps
import time

from pandas.tseries import offsets

from tests_executor.constants import DAYS_IN_WEEK, POINTS_IN_DAY
from tests_executor.distributions import Distributions


def get_start_date(first_monday=True):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0,
                                               microsecond=0)
    year_start = today - offsets.YearBegin()
    if not first_monday:
        return year_start.to_pydatetime()
    return today - timedelta(days=today.weekday())


def generate_timestamp_series(length, start_date=get_start_date(),
                              dif_sec=5 * 60):
    timestamps = []

    start_timestamp = int(start_date.timestamp())
    for index in range(length):
        timestamps.append(start_timestamp + (dif_sec * index))

    return timestamps


def constant_to_series(value, length):
    return [value] * length


def generate_constant_metric_series(distribution, non_negative=True, **kwargs):
    lst = Distributions.generate(distribution=distribution, **kwargs)
    if non_negative:
        lst = [round(i, 2) if i > 0 else 0 for i in lst]
    return lst


def generate_scheduled_metric_series(distribution, timestamp_series, work_days,
                                     work_hours, work_kwargs, idle_kwargs,
                                     series=None):
    result = series if series else []
    for index, timestamp in enumerate(timestamp_series):
        dt = datetime.utcfromtimestamp(timestamp)

        weekday = dt.weekday()
        hour = dt.hour

        if weekday in work_days and hour in work_hours:
            value = Distributions.generate(distribution=distribution,
                                           **work_kwargs)
            if series:
                result[index] = round(value, 2)
            else:
                result.append(round(value, 2))
        else:
            value = Distributions.generate(distribution=distribution,
                                           **idle_kwargs)
            if not series:
                result.append(round(value, 2))
    return [i if i > 0 else abs(i) for i in result]


def generate_split_series(distribution, avg_loads, probabilities, size,
                          scale):
    prob_list = [[load] * int(prob) for load,prob in zip(avg_loads,
                                                         probabilities)]
    prob_list = [item for sublist in prob_list for item in sublist]

    result = []

    for _ in range(size):
        base_value = random.choice(prob_list)
        value = Distributions.generate(distribution=distribution,
                                       loc=base_value, scale=scale)
        result.append(round(value, 2))

    return sorted(result)


def dateparse(time_in_secs):
    dt = datetime.fromtimestamp(float(time_in_secs))
    dt = dt.replace(tzinfo=timezone.utc)
    return dt


def timeit(func):
    @wraps(func)
    def timeit_wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        total_time = end_time - start_time
        print(
            f'Function {func.__name__}{args} {kwargs} '
            f'Took {total_time:.4f} seconds')
        return result
    return timeit_wrapper
