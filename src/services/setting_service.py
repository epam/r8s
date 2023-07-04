from datetime import datetime

from mongoengine.errors import DoesNotExist

from commons.constants import SETTING_IAM_PERMISSIONS, \
    SETTING_LAST_SHAPE_UPDATE
from models.setting import Setting


class SettingsService:
    @staticmethod
    def get(name):
        try:
            setting = Setting.objects.get(name=name)
            if setting:
                return setting.value
        except DoesNotExist:
            return

    @staticmethod
    def create(name: str, value):
        return Setting(name=name, value=value)

    @staticmethod
    def save(setting: Setting):
        return setting.save()

    def get_iam_permissions(self):
        return self.get(name=SETTING_IAM_PERMISSIONS)

    @staticmethod
    def update_shape_update_date(cloud: str):
        try:
            setting = Setting.objects.get(name=SETTING_LAST_SHAPE_UPDATE)
        except DoesNotExist:
            setting = Setting(name=SETTING_LAST_SHAPE_UPDATE, value={})

        setting.value[cloud] = datetime.utcnow().isoformat()
        setting.save(setting=setting)
        return setting
