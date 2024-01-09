from typing import List, Dict

from commons.constants import GENERAL_ACTIONS, ACTION_CHANGE_SHAPE, \
    ACTION_SCALE_DOWN, ACTION_SCALE_UP, ACTION_SHUTDOWN, ACTION_SCHEDULE, \
    ACTION_SPLIT, ACTION_EMPTY, ACTION_ERROR, RECOMMENDATION, SCHEDULE_ATTR
from commons.log_helper import get_logger
from models.recommendation_history import RecommendationHistory
from services.schedule.schedule_service import ScheduleService

_LOG = get_logger('resource-group-service')

SCHEDULE_SIMILARITY_THRESHOLD = 0.95


class ResourceGroupService:
    def __init__(self, schedule_service: ScheduleService):
        self.schedule_service = schedule_service

    def filter(self, group_results: Dict[str, List],
               group_history_items: List[RecommendationHistory]):
        filtered_reports = []
        for group_id, results in group_results.items():
            filtered_group_reports = self._filter_group(
                group_results=results)
            filtered_reports.extend(filtered_group_reports)

        filtered_resource_ids = [item.get('resource_id')
                                 for item in filtered_reports]
        filtered_history = [item for item in group_history_items
                            if item.instance_id in filtered_resource_ids]
        return filtered_reports, filtered_history

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
        return filtered

    def _filter_schedule(self, results: list):
        _LOG.debug(f'Filtering schedule results in group: {results}')
        always_run = []
        custom = []
        filtered = []

        for resource in results:
            schedule = resource[RECOMMENDATION].get(SCHEDULE_ATTR)
            if schedule and schedule == self.schedule_service.get_always_run_schedule():
                always_run.append(resource)
            else:
                custom.append(resource)

        if not custom:
            _LOG.debug('No custom schedules detected in group.')
            return results

        for resource in results:
            schedule = resource[RECOMMENDATION].get(SCHEDULE_ATTR)
            if schedule != self.schedule_service.get_always_run_schedule():
                filtered.append(resource)

        if len(custom) == 1:
            _LOG.debug('Only one custom schedule detected in a group')
            return filtered

        resource_runtimes = [
            (resource, self.schedule_service.get_runtime_minutes(
                schedule=resource[RECOMMENDATION].get(SCHEDULE_ATTR)))
            for resource in filtered]
        resource_runtimes.sort(key=lambda x: -x[1])
        _LOG.debug(f'Group schedules with runtime: {resource_runtimes}')

        runtime_threshold = (resource_runtimes[0][1] *
                             SCHEDULE_SIMILARITY_THRESHOLD)
        _LOG.debug(f'Runtime threshold: {runtime_threshold}')

        return [resource[0] for resource in resource_runtimes
                if resource[1] >= runtime_threshold]

    @staticmethod
    def _filter_resize(results: list):
        actions = set()
        acceptable_actions = [ACTION_CHANGE_SHAPE]
        filtered_results = []

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
                filtered_results.append(resource)

        _LOG.debug(f'Filtered resize-related resources: {filtered_results}')
        return filtered_results
