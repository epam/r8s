from mongoengine import DoesNotExist

from models.setting import Setting

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
