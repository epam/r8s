from dataclasses import dataclass
from statistics import quantiles

from commons.constants import ACTION_SPLIT, ACTION_SCALE_DOWN, ACTION_SCALE_UP, \
    ACTION_CHANGE_SHAPE

MIN_LIMIT_PERC = 30
MAX_LIMIT_PERC = 70


@dataclass
class MetricTrend:
    mean: float
    threshold: float
    result: float
    percentiles: list[float]


class ResizeTrend:
    def __init__(self):
        self.metric_trends = {}
        self.probability = None
        self._default_metric_trend = MetricTrend(
            mean=-1, percentiles=quantiles([-1, -1], n=100),
            result=0, threshold=0)

    def __getitem__(self, item):
        return self.metric_trends.get(item, self._default_metric_trend)

    def __getattr__(self, item):
        return self.metric_trends.get(item, self._default_metric_trend)

    def add_metric_trend(self, metric_name, column):
        mean = column.mean()
        threshold = column.quantile(.9)
        percentiles = quantiles(column, n=100)
        result_direction = self.__get_result_direction(
            mean=mean,
            threshold=threshold
        )
        metric_trend = MetricTrend(
            mean=mean,
            percentiles=percentiles,
            threshold=threshold,
            result=result_direction
        )
        self.metric_trends[metric_name] = metric_trend

    def discard_optional_requirements(self):
        """
        Discard non-essential resize requirements if size selection based
        on all parameters failed
        """
        cpu_dir = self.cpu_load.result
        memory_dir = self.memory_load.result

        if cpu_dir < 0 < memory_dir:
            self.cpu_load.result = abs(cpu_dir)
            self.cpu_load.threshold = 60
        else:
            self.memory_load.result = abs(memory_dir)
            self.memory_load.threshold = 60
        self.avg_disk_iops.result = 0
        self.net_output_load.result = 0

    @staticmethod
    def get_resize_action(trends: list):
        if len(trends) > 1:
            return ACTION_SPLIT
        trend = trends[0]
        cpu = trend.cpu_load.result
        memory = trend.memory_load.result
        net_output = trend.net_output_load.result
        iops = trend.avg_disk_iops.result

        iops_net_out_scale_up = net_output > 0 or iops > 0
        if not trend.requires_resize():
            direction = None
        elif cpu <= 0 and memory <= 0 and \
                not iops_net_out_scale_up:
            direction = ACTION_SCALE_DOWN
        elif cpu > 0 and memory >= 0:
            direction = ACTION_SCALE_UP
        else:
            direction = ACTION_CHANGE_SHAPE
        return direction

    def requires_resize(self):
        cpu_resize = self.cpu_load.result != 0
        memory_resize = self.memory_load.result != 0
        net_resize = self.net_output_load.result > 0
        iops_resize = self.avg_disk_iops.result > 0

        return any((cpu_resize, memory_resize, net_resize, iops_resize))

    @staticmethod
    def get_metric_ranges(metric: MetricTrend, provided,
                          only_for_non_empty=False,
                          minimum_load_threshold=5,
                          lowest_minimum=1, lowest_maximum=1):
        if only_for_non_empty and metric.result == 0:
            return None, None
        if provided:
            provided = float(provided)
        else:
            return None, None

        threshold = metric.threshold

        if threshold < minimum_load_threshold:
            threshold = minimum_load_threshold
        currently_used = provided / 100 * threshold

        absolute_max = currently_used * 100 / MIN_LIMIT_PERC
        absolute_min = currently_used * 100 / MAX_LIMIT_PERC

        if absolute_min < lowest_minimum:
            absolute_min = lowest_minimum
        if absolute_max < lowest_maximum:
            absolute_max = lowest_maximum

        return round(absolute_min, 2), round(absolute_max, 2)

    @staticmethod
    def remove_duplicates(trends: list, metric_attrs):
        result = []
        trend_directions = []
        for trend in trends.copy():
            trend_direction = tuple([trend[key].result for
                                     key in metric_attrs])
            if trend_direction not in trend_directions:
                result.append(trend)
                trend_directions.append(trend_direction)
        return result

    @staticmethod
    def __get_result_direction(mean, threshold):
        if mean == -1:
            return 0
        result = 0
        if threshold <= 20:  # under utilized
            result = -1
        elif 20 < threshold < 30:  # maybe under utilized
            result = -0.5
        elif 30 <= threshold <= 70:
            result = 0
        elif 70 < threshold < 80:  # maybe over utilized
            result = 0.5
        elif threshold >= 80:  # over utilized
            result = 1
        return result
