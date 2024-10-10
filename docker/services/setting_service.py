from mongoengine import DoesNotExist

from models.setting import Setting
from commons.constants import SETTING_LM_GRACE_CONFIG

KEY_ACCESS_DATA_LM = 'ACCESS_DATA_LM'
KEY_LM_CLIENT_KEY = 'LM_CLIENT_KEY'


class SettingsService:
    @staticmethod
    def get(name, value: bool = True):
        try:
            setting = Setting.objects.get(name=name)
            if setting and value:
                return setting.value
            elif setting:
                return setting
        except DoesNotExist:
            return

    def get_license_manager_access_data(self, value: bool = True):
        return self.get(name=KEY_ACCESS_DATA_LM, value=value)

    def get_license_manager_client_key_data(self, value: bool = True):
        return self.get(name=KEY_LM_CLIENT_KEY, value=value)

    def lm_grace_is_job_allowed(self):
        grace_config = self.get(SETTING_LM_GRACE_CONFIG)
        if not grace_config:
            return False
        grace_config = dict(grace_config)
        grace_period_count = grace_config.get('grace_period_count')
        failed_count = grace_config.get('failed_count')
        if failed_count > grace_period_count:
            return False
        return True
