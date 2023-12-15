from datetime import datetime, timedelta
from typing import Optional, Union, List

from commons.constants import SETTING_LAST_SHAPE_UPDATE
from commons.log_helper import get_logger
from services.health_checks.abstract_health_check import AbstractHealthCheck
from services.health_checks.check_result import CheckResult
from services.setting_service import SettingsService

_LOG = get_logger(__name__)

SHAPE_CHECK_UPDATE_DATE_ID = 'LAST_SHAPE_UPDATE_DATE'


class ShapeLastUpdateDateCheckCheck(AbstractHealthCheck):

    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service

    def identifier(self) -> str:
        return SHAPE_CHECK_UPDATE_DATE_ID

    def remediation(self) -> Optional[str]:
        return 'Please contact the support team to ' \
               'update shapes/pricing info for the specified clouds.'

    def impact(self) -> Optional[str]:
        return 'RIGHTSIZER recommendations may contain outdated info about ' \
               'available shapes/their prices.'

    def check(self) -> Union[List[CheckResult], CheckResult]:
        _LOG.debug(f'Describing setting \'{SETTING_LAST_SHAPE_UPDATE}\'')

        setting: dict = self.settings_service.get(
            name=SETTING_LAST_SHAPE_UPDATE)

        if not setting:
            return self.not_ok_result(
                details={
                    'message': 'None of the shapes haven\'t been updated yet. '
                               'Please contact the support team to '
                               'update shapes/pricing info for all clouds.'}
            )

        outdated_clouds = {}
        target_date = datetime.utcnow() - timedelta(days=31)
        for cloud, last_updated_str in setting.items():
            last_updated_date = datetime.fromisoformat(last_updated_str)

            if last_updated_date < target_date:
                outdated_clouds[cloud] = f'Last updated: {last_updated_str}'

        if outdated_clouds:
            _LOG.debug(f'Info about shape specs/prices for some '
                       f'clouds is outdated.: {outdated_clouds}')
            return self.not_ok_result(
                details=outdated_clouds
            )
        return self.ok_result(details=setting)


class ShapeUpdateDateCheckHandler:
    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service

    def check(self):
        return [ShapeLastUpdateDateCheckCheck(
            settings_service=self.settings_service).check().as_dict()]
