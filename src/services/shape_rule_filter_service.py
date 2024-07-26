import re
from typing import List

from commons.constants import CLOUD_ATTR
from commons.log_helper import get_logger
from models.parent_attributes import LicensesParentMeta
from models.shape import Shape

_LOG = get_logger('r8s-shape-rules-filter-service')

FIELD_ATTR = 'field'
VALUE_ATTR = 'value'
ACTION_ATTR = 'action'
CONDITION_ATTR = 'condition'
ALLOW = 'allow'
DENY = 'deny'
PRIORITIZE = 'prioritize'

CONDITION_MATCH = 'match'
CONDITION_CONTAINS = 'contains'
CONDITION_NOT_CONTAINS = 'not_contains'
CONDITION_EQUAL = 'equal'


class ShapeRulesFilterService:

    def __init__(self):
        self.condition_processor_mapping = {
            CONDITION_MATCH: self._match_condition,
            CONDITION_CONTAINS: self._contains_condition,
            CONDITION_NOT_CONTAINS: self._not_contains_condition,
            CONDITION_EQUAL: self._equal_condition,
        }

    def get_allowed_instance_types(self, cloud: str,
                                   parent_meta: LicensesParentMeta,
                                   instances_data: List[Shape]):
        shape_rules = parent_meta.shape_rules

        shape_rules = [rule for rule in shape_rules
                       if rule.get(CLOUD_ATTR) == cloud]

        allow_filters = self.filter_by_action(
            shape_rules=shape_rules,
            action=ALLOW
        )
        deny_filters = self.filter_by_action(
            shape_rules=shape_rules,
            action=DENY
        )
        allowed_instances = self.process_allow_filters(
            instances_data=instances_data,
            filters=allow_filters
        )
        allowed_instances = self.process_exclude_filters(
            instances_data=allowed_instances,
            filters=deny_filters
        )
        return allowed_instances

    def process_allow_filters(self, instances_data, filters: list = None):
        if not filters:
            return instances_data
        allowed_instances = []

        for filter_ in filters:
            matching_instances = self._find_matching(
                instances_data=instances_data, filter_=filter_
            )
            allowed_instances.extend(matching_instances)
        return allowed_instances

    def process_exclude_filters(self, instances_data, filters: list = None):
        if not filters:
            return instances_data
        names_to_exclude = set()
        for filter_ in filters:
            matching_instances = self._find_matching(
                instances_data=instances_data, filter_=filter_
            )
            filter_names_to_exclude = [item.name for item in
                                       matching_instances]
            names_to_exclude.update(filter_names_to_exclude)

        return [instance for instance in instances_data
                if instance.name not in names_to_exclude]

    def process_priority_filters(self, instances_data, shape_rules):
        priority_filter = self.filter_by_action(shape_rules=shape_rules,
                                                action=PRIORITIZE)
        if not priority_filter:
            return instances_data
        priority_instances = []

        for filter_ in priority_filter:
            matching_instances = self._find_matching(
                instances_data=instances_data, filter_=filter_
            )
            priority_instances.extend(matching_instances)
        return priority_instances

    def _find_matching(self, instances_data, filter_):
        matching_instances = []

        for instance in instances_data:

            matches = self._instance_match(
                instance_data=instance,
                filter_=filter_)
            if matches:
                matching_instances.append(instance)
        return matching_instances

    def _instance_match(self, instance_data, filter_):
        filter_key = filter_.get(FIELD_ATTR)
        filter_value = filter_.get(VALUE_ATTR)
        instance_value = getattr(instance_data, filter_key, None)
        condition = filter_.get(CONDITION_ATTR)

        if not filter_value or not instance_value:
            return False
        processor = self.condition_processor_mapping.get(condition)
        if not processor:
            return False
        return processor(instance_value=instance_value, value=filter_value)

    @staticmethod
    def filter_by_action(shape_rules: list, action):
        if not shape_rules:
            return []
        return [f for f in shape_rules if f.get(ACTION_ATTR) == action]

    @staticmethod
    def _match_condition(instance_value: str, value: str):
        value = value.replace('.', r'\.').replace('*', '.+')
        return bool(re.match(value, instance_value))

    @staticmethod
    def _contains_condition(instance_value: str, value: str):
        if not value or not isinstance(value, str):
            return False
        return value.lower() in instance_value.lower()

    @staticmethod
    def _not_contains_condition(instance_value: str, value: str):
        if not value or not isinstance(value, str):
            return False
        return value.lower() not in instance_value.lower()

    @staticmethod
    def _equal_condition(instance_value: str, value: str):
        if not value or not isinstance(value, str):
            return False
        return value.lower() == instance_value.lower()
