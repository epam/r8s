from math import inf
from typing import List

from commons.constants import JOB_STEP_GENERATE_REPORTS, ACTION_SPLIT, \
    CLOUD_ATTR, PROBABILITY
from commons.exception import ExecutorException
from commons.log_helper import get_logger
from models.algorithm import ShapeSorting
from models.base_model import CloudEnum
from models.parent_attributes import LicensesParentMeta
from models.recommendation_history import RecommendationHistory, \
    FeedbackStatusEnum
from models.shape import Shape
from services.customer_preferences_service import CustomerPreferencesService
from services.resize.resize_trend import MIN_LIMIT_PERC, MAX_LIMIT_PERC
from services.resize.shape_compatibility_filter import ShapeCompatibilityFilter
from services.shape_price_service import ShapePriceService
from services.shape_service import ShapeService

_LOG = get_logger('r8s-resize-service')

SHAPES_COUNT_TO_ADJUST = 3


class ResizeService:
    def __init__(self,
                 customer_preferences_service: CustomerPreferencesService,
                 shape_service: ShapeService,
                 shape_price_service: ShapePriceService):
        self.customer_preferences_service = customer_preferences_service

        self.shape_service = shape_service
        self.shape_price_service = shape_price_service

    def recommend_size(self, trend, instance_type, resize_action,
                       cloud, algorithm, instance_meta=None,
                       allow_recursion=True,
                       max_results=5, parent_meta=None,
                       shape_compatibility_rule=None,
                       past_resize_recommendations: List[
                           RecommendationHistory] = None):
        current_shape: Shape = self.shape_service.get(
            name=instance_type)

        if not current_shape:
            _LOG.error(f'Unknown instance type: {instance_type}')
            raise ExecutorException(
                step_name=JOB_STEP_GENERATE_REPORTS,
                reason=f'Unknown instance type: {instance_type}'
            )

        if not trend.requires_resize():
            if resize_action == ACTION_SPLIT:
                result_shape = current_shape.get_dto()
                result_shape[PROBABILITY] = trend.probability
                return [result_shape]
            return []

        cpu_min, cpu_max = trend.get_metric_ranges(
            metric=trend.cpu_load,
            provided=current_shape.cpu)
        memory_min, memory_max = trend.get_metric_ranges(
            metric=trend.memory_load,
            provided=current_shape.memory)

        net_output_min, _ = self.get_suitable_ranges(
            perc90=trend.net_output_load.threshold,
            provided=current_shape.network_throughput
        )
        net_output_min, _ = trend.get_metric_ranges(
            metric=trend.net_output_load,
            provided=current_shape.network_throughput,
            only_for_non_empty=True
        )
        disk_iops_min, _ = trend.get_metric_ranges(
            metric=trend.avg_disk_iops,
            provided=current_shape.iops,
            only_for_non_empty=True
        )
        _LOG.debug(f'Searching for available shapes for cloud: '
                   f'{current_shape.cloud.value}, '
                   f'for resource type {algorithm.resource_type}')
        all_shapes = self.shape_service.list(
            cloud=current_shape.cloud.value,
            resource_type=algorithm.resource_type
        )
        _LOG.debug(f'{len(all_shapes)} shapes available '
                   f'for cloud {current_shape.cloud.value}, '
                   f'resource type {algorithm.resource_type}')

        if parent_meta:
            _LOG.debug(f'Applying parent meta: '
                       f'{parent_meta.as_dict()}')
            all_shapes = self.customer_preferences_service. \
                get_allowed_instance_types(
                cloud=current_shape.cloud.value,
                instances_data=all_shapes,
                parent_meta=parent_meta
            )
            _LOG.debug(f'Shapes available after shape '
                       f'rule filters: {len(all_shapes)}')

        _LOG.debug(f'Applying algorithm shape compatibility rule: '
                   f'{shape_compatibility_rule}')
        all_shapes = ShapeCompatibilityFilter().apply_compatibility_filter(
            current_shape=current_shape,
            shapes=all_shapes,
            compatibility_rule=shape_compatibility_rule
        )
        _LOG.debug(f'Shapes available after algorithm compatibility rule: '
                   f'{len(all_shapes)}')

        if past_resize_recommendations:
            _LOG.debug(f'Applying feedback-based shape adjustments')
            all_shapes = self.apply_adjustment(
                shapes=all_shapes,
                recommendations=past_resize_recommendations)
            _LOG.debug(f'Shapes available after feedback-based adjustments: '
                       f'{len(all_shapes)}')

        forbid_change_series = algorithm.recommendation_settings. \
            forbid_change_series
        forbid_change_family = algorithm.recommendation_settings. \
            forbid_change_family
        prioritized_shapes = self.divide_by_priority(
            sizes=all_shapes,
            current_shape=current_shape,
            cloud=cloud,
            resize_action=resize_action,
            parent_meta=parent_meta,
            forbid_change_series=forbid_change_series,
            forbid_change_family=forbid_change_family
        )

        suitable_shapes = self.find_suitable_shapes(
            cpu_min=cpu_min,
            cpu_max=cpu_max,
            memory_min=memory_min,
            memory_max=memory_max,
            net_output_min=net_output_min,
            disk_iops_min=disk_iops_min,
            prioritized_shapes=prioritized_shapes
        )
        suitable_shapes = self._remove_shape_duplicates(
            shapes=suitable_shapes)

        for shape in suitable_shapes:
            prob = self.calculate_shape_probability(
                current_shape=current_shape,
                shape=shape, trend=trend
            )
            shape[PROBABILITY] = prob

        if not suitable_shapes or len(suitable_shapes) < max_results:
            if allow_recursion:
                _LOG.warning('No suitable same-series shape found. '
                             'Going to discard requirement for metric '
                             'with scale down.')

                trend.discard_optional_requirements()
                recs = self.recommend_size(
                    trend=trend,
                    instance_type=instance_type,
                    resize_action=resize_action,
                    algorithm=algorithm,
                    cloud=cloud,
                    instance_meta=instance_meta,
                    parent_meta=parent_meta,
                    allow_recursion=False,
                    shape_compatibility_rule=shape_compatibility_rule,
                    past_resize_recommendations=past_resize_recommendations)

                return self._remove_shape_duplicates(
                    shapes=suitable_shapes + recs,
                    max_results=max_results
                )
            elif suitable_shapes and len(suitable_shapes) < max_results:
                _LOG.warning('Not enough suitable shapes found.')
                return suitable_shapes
            else:
                _LOG.warning('No suitable shapes found')
                return []
        if resize_action == ACTION_SPLIT:
            probability = trend.probability
            for shape in suitable_shapes:
                shape[PROBABILITY] = probability

        result = self._remove_shape_duplicates(
            shapes=suitable_shapes,
            max_results=max_results)

        return result

    def calculate_shape_probability(self, current_shape, shape, trend):
        metric_to_shape_key = {
            'cpu_load': 'cpu',
            'memory_load': 'memory',
            'net_output_load': 'network_throughput',
            'avg_disk_iops': 'iops',
        }
        shape_prob = []
        for metric_name, metric_trend in trend.metric_trends.items():
            if metric_trend.mean == -1:
                continue
            shape_key = metric_to_shape_key.get(metric_name)

            current_value = current_shape.get_json().get(shape_key)
            expected_value = shape.get(shape_key)
            if not current_value or not expected_value:
                continue
            metric_prob = self.calculate_shape_metric_probability(
                current_value=current_value,
                expected_value=expected_value,
                percentiles=metric_trend.percentiles
            )
            shape_prob.append(metric_prob)
        return round(sum(shape_prob) / len(shape_prob) / 100, 2)

    @staticmethod
    def calculate_shape_metric_probability(current_value: float,
                                           expected_value: float,
                                           percentiles: list[float]):
        percentiles_abs = [current_value * i / 100 for i in percentiles]

        min_abs = MIN_LIMIT_PERC * expected_value / 100
        max_abs = MAX_LIMIT_PERC * expected_value / 100

        matching = [i for i in percentiles_abs if min_abs <= i <= max_abs]
        return round(len(matching) / len(percentiles) * 100)

    @staticmethod
    def _remove_shape_duplicates(shapes, max_results: int = None):
        result = []
        for shape in shapes:
            if shape not in result:
                result.append(shape)
        if max_results and len(result) > max_results:
            result = result[:max_results]
        return result

    @staticmethod
    def sort_shapes(shapes: list, sort_option: ShapeSorting = None):
        if not sort_option or \
                sort_option == ShapeSorting.SORT_BY_PERFORMANCE:
            return shapes
        if sort_option == ShapeSorting.SORT_BY_PRICE:
            # in order: from lowest price to highest, then without price
            return sorted(shapes, key=lambda shape: shape.get('price', inf))
        return shapes

    def add_price(self, instances: list, customer, region,
                  price_type='on_demand', os=None):
        for instance in instances:
            shape_name = instance.get('name')
            shape_price = self.shape_price_service.get(
                customer=customer,
                name=shape_name,
                region=region,
                os=os
            )
            if not shape_price:
                _LOG.warning(f'Missing price for shape \'{shape_name}\' '
                             f'in region \'{region}\'')
                continue
            price = getattr(shape_price, price_type, None)
            if not price:
                continue
            instance['price'] = price
        return instances

    def apply_adjustment(self, shapes: List[Shape],
                         recommendations: List[RecommendationHistory]) -> List[Shape]:
        status_handler_mapping = {
            FeedbackStatusEnum.TOO_SMALL: self._adjust_too_small,
            FeedbackStatusEnum.TOO_LARGE: self._adjust_too_large,
            FeedbackStatusEnum.WRONG: self._adjust_wrong,
            FeedbackStatusEnum.DONT_RECOMMEND: lambda *args, **kwargs: [],
        }

        for recommendation in recommendations:
            feedback_status = recommendation.feedback_status

            if feedback_status in status_handler_mapping:
                handler = status_handler_mapping.get(feedback_status)
                shapes = handler(shapes=shapes, recommendation=recommendation)

        return shapes

    def _adjust_too_small(self, shapes: List[Shape],
                          recommendation: RecommendationHistory):
        recommended_shapes_data = self._get_recommended_shapes(
            recommendation=recommendation,
            max_items=SHAPES_COUNT_TO_ADJUST
        )
        recommended_cpu = [item.get('cpu') for item in recommended_shapes_data
                           if isinstance(item.get('cpu'), (int, float))]
        recommended_memory = [item.get('memory') for item in
                              recommended_shapes_data
                              if isinstance(item.get('memory'), (int, float))]

        threshold_cpu = max(recommended_cpu)
        threshold_memory = max(recommended_memory)

        result_shapes = []
        for shape in shapes:

            # shape cpu/memory must be >=, but
            # at least one of them must be higher than a threshold value
            if shape.cpu >= threshold_cpu and shape.memory >= threshold_memory \
                    and (shape.cpu != threshold_cpu
                         or threshold_memory != shape.memory):
                result_shapes.append(shape)
        return result_shapes

    def _adjust_too_large(self, shapes: List[Shape],
                          recommendation: RecommendationHistory):
        recommended_shapes_data = self._get_recommended_shapes(
            recommendation=recommendation,
            max_items=SHAPES_COUNT_TO_ADJUST
        )
        recommended_cpu = [item.get('cpu') for item in recommended_shapes_data
                           if isinstance(item.get('cpu'), (int, float))]
        recommended_memory = [item.get('memory') for item in
                              recommended_shapes_data
                              if isinstance(item.get('memory'), (int, float))]

        threshold_cpu = min(recommended_cpu)
        threshold_memory = min(recommended_memory)

        result_shapes = []
        for shape in shapes:

            # shape cpu/memory must be <=, but
            # at least one of them must be smaller than a threshold value
            if shape.cpu <= threshold_cpu and shape.memory <= threshold_memory \
                    and (shape.cpu != threshold_cpu
                         or threshold_memory != shape.memory):
                result_shapes.append(shape)
        return result_shapes

    def _adjust_wrong(self, shapes: List[Shape],
                      recommendation: RecommendationHistory):
        recommended_shapes_data = self._get_recommended_shapes(
            recommendation=recommendation,
            max_items=SHAPES_COUNT_TO_ADJUST
        )
        names_to_exclude = [shape_data.get('name') for shape_data
                                  in recommended_shapes_data
                                  if shape_data.get('name')]

        return [shape for shape in shapes if shape.name not in names_to_exclude]

    @staticmethod
    def get_suitable_ranges(perc90, provided, minimum_load_threshold=5,
                            lowest_minimum=1, lowest_maximum=1):
        if provided:
            provided = float(provided)
        else:
            return None, None

        if perc90 < minimum_load_threshold:
            perc90 = minimum_load_threshold
        currently_used = provided / 100 * perc90

        min_limit_perc = 30
        max_limit_perc = 70

        absolute_max = currently_used * 100 / min_limit_perc
        absolute_min = currently_used * 100 / max_limit_perc

        if absolute_min < lowest_minimum:
            absolute_min = lowest_minimum
        if absolute_max < lowest_maximum:
            absolute_max = lowest_maximum

        return round(absolute_min, 2), round(absolute_max, 2)

    @staticmethod
    def find_suitable_shapes(cpu_min, cpu_max, memory_min, memory_max,
                             net_output_min,
                             disk_iops_min,
                             prioritized_shapes):
        suitable_shapes = []

        for shapes in prioritized_shapes:
            for shape in shapes:
                shape_cpu = getattr(shape, 'cpu', -1)
                shape_memory = getattr(shape, 'memory', -1)

                cpu_suits = True
                memory_suits = True
                net_output_suits = True
                iops_suits = True

                if cpu_min and cpu_max:
                    cpu_suits = cpu_min <= shape_cpu <= cpu_max
                if memory_min and memory_max:
                    memory_suits = memory_min <= shape_memory <= memory_max

                if net_output_min:
                    shape_net_output = shape.network_throughput
                    net_output_suits = shape_net_output \
                                       and net_output_min <= shape_net_output
                if disk_iops_min:
                    shape_iops = shape.iops
                    iops_suits = shape_iops and disk_iops_min <= shape_iops

                if cpu_suits and memory_suits and iops_suits \
                        and net_output_suits:
                    suitable_shapes.append(shape)
        return [shape.get_dto() for shape in suitable_shapes]

    def divide_by_priority(self, sizes, cloud, current_shape: Shape, resize_action,
                           parent_meta: LicensesParentMeta = None,
                           forbid_change_series=True,
                           forbid_change_family=True):
        current_size_name = current_shape.name
        current_series_prefix = self._get_series_prefix(
            shape_name=current_size_name, cloud=cloud)

        prioritised = []
        if parent_meta:
            shape_rules = parent_meta.shape_rules
            _LOG.debug(f'Filtering shape rules for cloud: {cloud}')
            shape_rules = [rule for rule in shape_rules
                           if rule.get(CLOUD_ATTR) == cloud]
            _LOG.debug(f'Rule to apply: {shape_rules}')
            if shape_rules:
                prioritised = self.customer_preferences_service. \
                    process_priority_filters(
                        instances_data=sizes,
                        shape_rules=shape_rules
                    )
        if resize_action == ACTION_SPLIT:  # if its split action,
            # allow to use same shape
            same_series = self._get_same_series(
                sizes=sizes,
                series_prefix=current_series_prefix)
        else:
            same_series = self._get_same_series(
                sizes=sizes,
                series_prefix=current_series_prefix,
                exclude_shape_names=(current_size_name,))

        same_series_shape_names = [i['name'] for i in same_series]

        same_family = []
        if not forbid_change_series:
            same_family = self._get_same_family(
                sizes=sizes,
                cloud=cloud,
                current_shape=current_shape,
                exclude_shapes=same_series_shape_names
            )
        same_family_shape_names = [i['name'] for i in same_family]

        other_shapes = []
        if not forbid_change_series and not forbid_change_family:
            other_shapes = self._get_other_shapes(
                sizes=sizes,
                exclude_shapes=same_series_shape_names + same_family_shape_names)

        return prioritised, same_series, same_family, other_shapes

    @staticmethod
    def _get_series_prefix(shape_name, cloud):
        if cloud == CloudEnum.CLOUD_AWS.value:
            return shape_name.split('.')[0] + '.'
        if cloud == CloudEnum.CLOUD_AZURE.value:
            parts = shape_name.split('_')
            index = 0
            for index, ch in enumerate(parts[1]):
                if not ch.isalpha():
                    break
            return f'{parts[0]}_{parts[1][0:index]}'
        if cloud == CloudEnum.CLOUD_GOOGLE.value:
            return shape_name.split('-')[0]

    def _get_same_series(self, sizes, series_prefix,
                         exclude_shape_names=()):
        shapes = [shape for shape in sizes
                  if shape.name.startswith(series_prefix)
                  and shape.name not in exclude_shape_names]
        return self._sort_shapes(shapes=shapes)

    def _get_same_family(self, sizes: List[Shape], current_shape, cloud,
                         exclude_shapes: List[Shape]):
        if cloud == CloudEnum.CLOUD_AZURE.value:
            family_prefix = current_shape.name.split('_')[0]
            same_family = [shape for shape in sizes
                           if shape.name.startswith(family_prefix) and
                           shape.name not in exclude_shapes]
        else:
            same_family = [shape for shape in sizes
                           if shape.family_type == current_shape.family_type and
                           shape.name not in exclude_shapes]
        return self._sort_shapes(shapes=same_family)

    def _get_other_shapes(self, sizes: List[Shape],
                          exclude_shapes: List[Shape]):
        shapes = [shape for shape in sizes if shape.name
                  not in exclude_shapes]
        return self._sort_shapes(shapes=shapes)

    @staticmethod
    def _sort_shapes(shapes: List[Shape]):
        return sorted(shapes, key=lambda x: (x.cpu, x.memory))

    @staticmethod
    def _get_recommended_shapes(recommendation: RecommendationHistory,
                                max_items: int = None) -> List[dict]:
        recommended_shapes_data = recommendation.recommendation
        if not recommended_shapes_data:
            return []
        if max_items and len(recommended_shapes_data) > max_items:
            recommended_shapes_data = recommended_shapes_data[0:max_items]

        return recommended_shapes_data
