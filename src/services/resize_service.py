from math import inf
from typing import List

from commons.constants import ACTION_SPLIT
from commons.log_helper import get_logger
from models.algorithm import ShapeSorting
from models.base_model import CloudEnum
from models.parent_attributes import LicensesParentMeta
from models.recommendation_history import RecommendationHistory
from models.shape import Shape
from services.customer_preferences_service import CustomerPreferencesService
from services.shape_service import ShapeService

_LOG = get_logger('r8s-resize-service')

SHAPES_COUNT_TO_ADJUST = 3


class ResizeService:
    def __init__(self, shape_service: ShapeService,
                 customer_preferences_service: CustomerPreferencesService):
        self.customer_preferences_service = customer_preferences_service
        self.shape_service = shape_service

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

    def divide_by_priority(self, sizes, cloud, current_shape: Shape,
                           resize_action,
                           parent_meta: LicensesParentMeta = None,
                           forbid_change_series=True,
                           forbid_change_family=True):
        current_size_name = current_shape.name
        current_series_prefix = self.get_series_prefix(
            shape_name=current_size_name, cloud=cloud)

        prioritised = []
        if parent_meta:
            shape_rules = parent_meta.shape_rules
            if shape_rules:
                prioritised = self.customer_preferences_service. \
                    process_priority_filters(
                    instances_data=sizes,
                    shape_rules=shape_rules
                )
        if resize_action == ACTION_SPLIT:  # if its split action,
            # allow to use same shape
            same_series = self.get_same_series(
                sizes=sizes,
                series_prefix=current_series_prefix)
        else:
            same_series = self.get_same_series(
                sizes=sizes,
                series_prefix=current_series_prefix,
                exclude_shape_names=(current_size_name,))

        same_series_shape_names = [i['name'] for i in same_series]

        same_family = []
        if not forbid_change_series:
            same_family = self.get_same_family(
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
    def get_series_prefix(shape_name, cloud):
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

    def get_same_series(self, sizes, series_prefix,
                        exclude_shape_names=()):
        shapes = [shape for shape in sizes
                  if shape.name.startswith(series_prefix)
                  and shape.name not in exclude_shape_names]
        return self._sort_shapes(shapes=shapes)

    def get_same_family(self, sizes: List[Shape], current_shape, cloud,
                        exclude_shapes: List[Shape]):
        if cloud == CloudEnum.CLOUD_AZURE.value:
            family_prefix = current_shape.name.split('_')[0]
            same_family = [shape for shape in sizes
                           if shape.name.startswith(family_prefix) and
                           shape.name not in exclude_shapes]
        else:
            same_family = [shape for shape in sizes
                           if
                           shape.family_type == current_shape.family_type and
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
