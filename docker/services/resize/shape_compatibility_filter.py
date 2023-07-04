from typing import List

from models.algorithm import ShapeCompatibilityRule
from models.shape import Shape


class ShapeCompatibilityFilter:
    def __init__(self):
        self.rule_handler_mapping = {
            ShapeCompatibilityRule.RULE_ONLY_COMPATIBLE: self.__rule_compatible,
            ShapeCompatibilityRule.RULE_ONLY_SAME: self.__rule_same,
        }
        self.manufacturers = ['Intel', 'AMD', 'AWS']
        self.architectures = [32, 64]

    def apply_compatibility_filter(self, current_shape: Shape,
                                   shapes: List[Shape],
                                   compatibility_rule: ShapeCompatibilityRule):
        handler = self.rule_handler_mapping.get(compatibility_rule)
        if not handler:
            return shapes
        return handler(current_shape=current_shape, shapes=shapes)

    def __rule_same(self, current_shape: Shape, shapes: List[Shape]):
        filter_manufacturer = self._get_shape_manufacturer(
            shape=current_shape
        )
        filter_architecture = self._get_shape_architecture(
            shape=current_shape
        )

        filtered_shapes = []

        for shape in shapes:
            if filter_manufacturer and \
                    self._get_shape_manufacturer(shape) != filter_manufacturer:
                continue
            if filter_architecture and \
                    self._get_shape_architecture(shape) != filter_architecture:
                continue
            filtered_shapes.append(shape)
        return filtered_shapes

    def __rule_compatible(self, current_shape: Shape, shapes: List[Shape]):
        manufacturer = self._get_shape_manufacturer(
            shape=current_shape
        )
        compatible_manufacturers = self._get_compatible_manufacturers(
            manufacturer=manufacturer
        )
        architecture = self._get_shape_architecture(
            shape=current_shape
        )

        filtered_shapes = []

        for shape in shapes:
            shape_manufacturer = self._get_shape_manufacturer(shape)
            if compatible_manufacturers and shape_manufacturer \
                    not in compatible_manufacturers:
                continue
            shape_arch = self._get_shape_architecture(shape)
            if architecture and shape_arch != architecture:
                continue
            filtered_shapes.append(shape)
        return filtered_shapes

    def _get_shape_manufacturer(self, shape: Shape):
        processor = shape.physical_processor
        for manufacturer in self.manufacturers:
            if processor and manufacturer in processor:
                return manufacturer

    def _get_shape_architecture(self, shape: Shape):
        architecture = shape.architecture
        if not architecture:
            return
        if all(str(arch) in architecture for arch in self.architectures):
            return
        for arch in self.architectures:
            if architecture and str(arch) in architecture:
                return str(arch)

    @staticmethod
    def _get_compatible_manufacturers(manufacturer=None):
        if not manufacturer:
            return []
        if manufacturer == 'AWS':
            return ['AWS']
        return ['Intel', 'AMD']

