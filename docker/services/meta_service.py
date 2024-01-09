from datetime import datetime, timezone, timedelta
import copy
from typing import List
import itertools

from commons.constants import TAG_GROUP_ID
from commons.exception import ProcessingPostponedException
from commons.log_helper import get_logger
from models.recommendation_history import RecommendationHistory, \
    FeedbackStatusEnum, RecommendationTypeEnum
from services.environment_service import EnvironmentService

_LOG = get_logger('r8s-meta-service')

POSTPONE_SETTINGS_KEY = 'postponeSettings'


class MetaService:
    def __init__(self, environment_service: EnvironmentService):
        self.environment_service = environment_service
        self.postponed_key = self.environment_service.meta_postponed_key()
        self.postponed_for_actions_key = self.environment_service. \
            meta_postponed_for_actions_key()

    def to_adjustments(self, instance_meta: dict) \
            -> List[RecommendationHistory]:

        instance_meta = copy.deepcopy(instance_meta)
        if not instance_meta or not isinstance(instance_meta, dict):
            return []
        postpone_settings = self.get_postponed_settings(
            instance_meta=instance_meta)

        if not postpone_settings:
            return []

        allowed_actions = RecommendationTypeEnum.list()
        emulated_appliance_date = datetime.now(timezone.utc)  \
                                  - timedelta(days=180)
        affected_actions = [action.get(self.postponed_for_actions_key)
                            for action in postpone_settings]
        target_dts = [action.get(self.postponed_key)
                             for action in postpone_settings]
        affected_actions = list(itertools.chain.from_iterable(affected_actions))
        if set(affected_actions) == set(allowed_actions):
            _LOG.debug(f'Instance processing is postponed for all actions.')
            postponed_till_dt = min(target_dts)
            raise ProcessingPostponedException(
                postponed_till=postponed_till_dt.isoformat())

        _LOG.debug(f'Next actions will be postponed for instance: '
                   f'\'{affected_actions}\'')

        history_items = []
        for postpone_setting in postpone_settings:
            setting_dt = postpone_setting.get(self.postponed_key)
            setting_actions = postpone_setting.get(
                self.postponed_for_actions_key)
            setting_actions = [item for item in setting_actions
                               if item in allowed_actions]
            if not setting_dt or not self.is_postponed(
                    postponed_till_dt=setting_dt):
                continue

            for postponed_action in setting_actions:
                item = RecommendationHistory(
                    recommendation_type=postponed_action,
                    instance_meta=instance_meta,
                    feedback_status=FeedbackStatusEnum.DONT_RECOMMEND,
                    feedback_dt=emulated_appliance_date
                )
                history_items.append(item)
        return history_items

    def get_postponed_actions(self, tags_mapping):
        postponed_actions = tags_mapping.get(self.postponed_for_actions_key)
        result_actions = []
        options = RecommendationTypeEnum.list()
        if not postponed_actions:
            return options

        for action in postponed_actions.split(','):
            action = action.upper()

            if action in options:
                result_actions.append(action)
            elif action == 'RESIZE':
                resize_actions = RecommendationTypeEnum.resize()
                for resize_action in resize_actions:
                    result_actions.extend(resize_action.value)
        return list(set(result_actions))

    def is_postponed(self, postponed_till_dt: datetime):
        if not postponed_till_dt:
            return False

        try:
            now = datetime.now()

            if postponed_till_dt >= now:
                return True
        except (TypeError, ValueError) as e:
            _LOG.warning(
                f'Invalid \'{self.postponed_key}\' specified: {e}')
        return False

    @staticmethod
    def parse_tags(instance_meta: dict):
        result = {}

        instance_id = instance_meta.get('resourceId')
        tags_list = instance_meta.get('tags')
        if not tags_list or tags_list and not isinstance(tags_list, list):
            result[instance_id] = {}
            return result
        for item in tags_list:
            if not isinstance(item, dict):
                continue
            key = item.get('key')
            value = item.get('value')

            if not isinstance(key, str) or not isinstance(value, str):
                _LOG.warning(f'Both tag key and value must be strings: '
                             f'{key}:{value}')
                continue
            result[key] = value
        return result

    def get_postponed_settings(self, instance_meta: dict):
        postpone_settings = instance_meta.get(POSTPONE_SETTINGS_KEY)
        if not postpone_settings or not isinstance(postpone_settings, list):
            return []
        active_settings = []

        for postpone_setting in postpone_settings:
            target_timestamp = postpone_setting.get(self.postponed_key)
            try:
                postpone_dt = datetime.fromtimestamp(target_timestamp // 1000)
                postpone_setting[self.postponed_key] = postpone_dt
            except Exception as e:
                _LOG.error(f'Can\'t convert \'{target_timestamp}\' '
                           f'to datetime. Error: {str(e)}')
                continue
            target_actions = postpone_setting.get(
                self.postponed_for_actions_key, RecommendationTypeEnum.list())

            target_actions = [action for action in target_actions
                              if action in RecommendationTypeEnum.list()]
            postpone_setting[self.postponed_for_actions_key] = target_actions
            if target_timestamp and target_actions and\
                    self.is_postponed(postponed_till_dt=postpone_dt):
                active_settings.append(postpone_setting)

        return active_settings

    def get_resource_group_id(self, instance_meta: dict):
        if not instance_meta:
            return
        tags = self.parse_tags(instance_meta=instance_meta)
        return tags.get(TAG_GROUP_ID)
