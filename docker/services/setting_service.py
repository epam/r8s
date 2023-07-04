from commons.constants import SETTING_IAM_PERMISSIONS, \
    SETTING_MAESTRO_APPLICATION_ID
from models.setting import Setting


class SettingsService:
    @staticmethod
    def get(name):
        setting = Setting.objects.get(name=name)
        if setting:
            return setting.value

    @staticmethod
    def save(setting: Setting):
        return setting.save()

    def get_iam_permissions(self):
        return self.get(name=SETTING_IAM_PERMISSIONS)

    def get_maestro_application_id(self):
        return self.get(name=SETTING_MAESTRO_APPLICATION_ID)
