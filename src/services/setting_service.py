from datetime import datetime
from typing import Optional

from modular_sdk.services.impl.maestro_credentials_service import AccessMeta
from mongoengine.errors import DoesNotExist

from commons.constants import SETTING_IAM_PERMISSIONS, \
    SETTING_LAST_SHAPE_UPDATE, SETTING_LM_GRACE_CONFIG
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

    @staticmethod
    def create(name: str, value):
        return Setting(name=name, value=value)

    @staticmethod
    def save(setting: Setting):
        return setting.save()

    @staticmethod
    def delete(setting: Setting):
        setting.delete()

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

    def get_license_manager_access_data(self, value: bool = True):
        return self.get(name=KEY_ACCESS_DATA_LM, value=value)

    def create_license_manager_access_data_configuration(
            self, host: str,
            port: Optional[int] = None,
            protocol: Optional[str] = None,
            stage: Optional[str] = None) -> Setting:
        model = AccessMeta.from_dict({})
        model.update_host(host=host, port=port, protocol=protocol, stage=stage)
        setting = self.create(
            name=KEY_ACCESS_DATA_LM, value=model.dict()
        )
        self.save(setting=setting)
        return setting

    def get_license_manager_client_key_data(self, value: bool = True):
        return self.get(name=KEY_LM_CLIENT_KEY, value=value)

    def create_license_manager_client_key_data(self, kid: str, alg: str
                                               ) -> Setting:
        """
        :param kid: str, id of a key, delegated by the License Manager
        :param alg: str, algorithm to use with a key,
        delegated by the License Manager

        Note: kid != id of a key within a persistence, such as parameter store.
        Ergo, kid is used to derive reference to the persisted data.
        """
        setting = self.create(
            name=KEY_LM_CLIENT_KEY, value=dict(
                kid=kid,
                alg=alg
            )
        )
        self.save(setting=setting)
        return setting

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

    def lm_grace_increment_failed(self):
        grace_config = self.get(SETTING_LM_GRACE_CONFIG, value=False)
        if not grace_config:
            return
        grace_config.value['failed_count'] += 1
        grace_config.save()

    def lm_grace_reset(self):
        grace_config = self.get(SETTING_LM_GRACE_CONFIG, value=False)
        if not grace_config:
            return
        grace_config.value['failed_count'] = 0
        grace_config.save()
