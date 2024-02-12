from typing import List, Dict

from commons.constants import GENERAL_ACTIONS, ACTION_CHANGE_SHAPE, \
    ACTION_SCALE_DOWN, ACTION_SCALE_UP, ACTION_SHUTDOWN, ACTION_SCHEDULE, \
    ACTION_SPLIT, ACTION_EMPTY, ACTION_ERROR, RECOMMENDATION, SCHEDULE_ATTR, \
    SAVINGS, RECOMMENDED_SHAPES, SAVING_OPTIONS_ATTR
from commons.log_helper import get_logger
from models.recommendation_history import RecommendationHistory
from services.schedule.schedule_service import ScheduleService

_LOG = get_logger('resource-group-service')

SCHEDULE_SIMILARITY_THRESHOLD = 0.95


class ResourceGroupService:
    def __init__(self, schedule_service: ScheduleService):
        self.schedule_service = schedule_service

    def filter(self, group_results: Dict[str, List],
               group_history_items: List['RecommendationHistory']):
        processed_reports = []
        for group_id, results in group_results.items():
            filtered_group_reports = self._filter_group(
                group_results=results)
            processed_reports.extend(filtered_group_reports)

        id_report_mapping = {item.get('resource_id'): item
                             for item in processed_reports}
        id_history_mapping = {item.resource_id: item
                              for item in group_history_items}
        for resource_id, resource_report in id_report_mapping.items():
            history_item = id_history_mapping.get(resource_id)
            if history_item:
                self.sync_history_item(
                    recommendation_history=history_item,
                    report=resource_report
                )
        return processed_reports, group_history_items

    @staticmethod
    def sync_history_item(recommendation_history: RecommendationHistory,
                          report: Dict):
        recommendation_history.recommendation_type = report[GENERAL_ACTIONS][0]

        if not report[RECOMMENDATION].get(SAVINGS):
            report[RECOMMENDATION][SAVINGS] = {}
        savings = report[RECOMMENDATION][SAVINGS]
        saving_options = savings.get(
            SAVING_OPTIONS_ATTR)
        if saving_options:
            recommendation_history.savings = saving_options
        else:
            recommendation_history.savings = None

        if shapes := report[RECOMMENDATION].get(RECOMMENDED_SHAPES):
            recommendation_history.recommendation = shapes
        elif schedule := report[RECOMMENDATION].get(SCHEDULE_ATTR):
            recommendation_history.recommendation = schedule

    def _filter_group(self, group_results: List[dict]):
        filtered = []

        resize_resources = []
        schedule_resources = []
        split_resources = []

        for resource_recommendation in group_results:
            resource_actions = resource_recommendation.get(GENERAL_ACTIONS)
            if (ACTION_EMPTY in resource_actions or
                    ACTION_ERROR in resource_actions):
                filtered.append(resource_recommendation)
                continue
            for action in resource_actions:
                if action in (ACTION_SCALE_UP, ACTION_SCALE_DOWN,
                              ACTION_CHANGE_SHAPE, ACTION_SHUTDOWN):
                    resize_resources.append(resource_recommendation)
                if action == ACTION_SCHEDULE:
                    schedule_resources.append(resource_recommendation)
                if action == ACTION_SPLIT:
                    split_resources.append(resource_recommendation)

        filtered.extend(self._filter_resize(resize_resources))
        filtered.extend(self._filter_schedule(schedule_resources))
        return [*filtered, *split_resources]

    def _filter_schedule(self, results: list):
        _LOG.debug(f'Filtering schedule results in group: {results}')
        always_run = []
        custom = []

        for resource in results:
            schedule = resource[RECOMMENDATION].get(SCHEDULE_ATTR)
            if schedule and schedule == self.schedule_service.get_always_run_schedule():
                always_run.append(resource)
            elif schedule:
                custom.append(resource)

        if not custom:
            _LOG.debug('No custom schedules detected in group.')
            return results

        if len(custom) == 1:
            _LOG.debug('Only one custom schedule detected in a group')
            return results

        resource_runtimes = [
            (resource, self.schedule_service.get_runtime_minutes(
                schedule=resource[RECOMMENDATION].get(SCHEDULE_ATTR)))
            for resource in custom]
        resource_runtimes.sort(key=lambda x: -x[1])
        _LOG.debug(f'Group schedules with runtime: {resource_runtimes}')

        runtime_threshold = (resource_runtimes[0][1] *
                             SCHEDULE_SIMILARITY_THRESHOLD)
        _LOG.debug(f'Runtime threshold: {runtime_threshold}')

        for resource, runtime_min in resource_runtimes:
            if runtime_min >= runtime_threshold:
                continue
            else:
                resource[RECOMMENDATION][SCHEDULE_ATTR] = (
                    self.schedule_service.get_always_run_schedule())
                resource[RECOMMENDATION][GENERAL_ACTIONS] = [ACTION_EMPTY]
                resource[RECOMMENDATION][SAVINGS] = None

        return [*[resource[0] for resource in resource_runtimes], *always_run]

    @staticmethod
    def _filter_resize(results: list):
        actions = set()
        acceptable_actions = [ACTION_CHANGE_SHAPE]

        for resource in results:
            actions.update(resource[GENERAL_ACTIONS])

        if ACTION_SCALE_UP in actions:
            # discard SCALE_DOWN/SHUTDOWN recommendation if there is
            # SCALE_UP one for this group
            _LOG.debug(f'{ACTION_SCALE_UP} present in resource group. '
                       f' {ACTION_SCALE_DOWN}, {ACTION_SHUTDOWN} '
                       f'recommendations will be discarded')
            acceptable_actions.append(ACTION_SCALE_UP)
        else:
            acceptable_actions.extend((ACTION_SCALE_DOWN, ACTION_SHUTDOWN))

        for resource in results:
            resource_actions = resource[GENERAL_ACTIONS]

            if any(action in acceptable_actions
                   for action in resource_actions):
                continue
            else:
                resource[RECOMMENDATION][RECOMMENDED_SHAPES] = []
                resource[RECOMMENDATION][SAVINGS] = None
                resource[GENERAL_ACTIONS] = [ACTION_EMPTY]

        _LOG.debug(f'Filtered resize-related resources: {results}')
        return results
