import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import string
import secrets

from commons.constants import SETTING_IAM_PERMISSIONS, ENV_SYSTEM_USER_PASSWORD
from commons.log_helper import get_logger

_LOG = get_logger(__name__)

MAIN_DYNAMODB_INDEX_KEY = 'main'
GLOBAL_SECONDARY_INDEXES = 'global_secondary_indexes'
LOCAL_SECONDARY_INDEXES = 'local_secondary_indexes'
INDEX_NAME_ATTR, KEY_SCHEMA_ATTR = 'index_name', 'key_schema'

ATTRIBUTE_NAME_ATTR, KEY_TYPE_ATTR = 'AttributeName', 'KeyType'
HASH_KEY_TYPE, RANGE_KEY_TYPE = 'HASH', 'RANGE'


def generate_password():
    alphabet = string.ascii_letters + string.digits + '&*<>-_'
    password = ''.join(secrets.choice(alphabet) for _ in range(20))
    return password


def resolve_scripts_path():
    current_path = Path(os.path.dirname(os.path.realpath(__file__)))
    root_path = current_path.parent.parent.parent
    scripts_path = root_path / 'scripts'
    return scripts_path


def read_json(dir_path, file_name):
    file_path = os.path.join(dir_path, file_name)
    if not os.path.exists(file_path):
        return None
    with open(file_path, 'r') as f:
        return json.load(f)


def create_iam_permissions_settings():
    from services import SERVICE_PROVIDER
    from models.setting import Setting
    settings_service = SERVICE_PROVIDER.settings_service()

    if settings_service.get(SETTING_IAM_PERMISSIONS):
        _LOG.debug(f'Setting {SETTING_IAM_PERMISSIONS} already exist.')
        return
    _LOG.debug(f'Creating {SETTING_IAM_PERMISSIONS} setting')
    script_dir_path = resolve_scripts_path()
    iam_permissions_data = read_json(dir_path=script_dir_path,
                                     file_name='iam_permissions.json')
    Setting(**iam_permissions_data).save()


def create_admin_role():
    from services import SERVICE_PROVIDER
    from services.rbac.iam_service import IamService
    from models.policy import Policy
    from models.role import Role

    iam_service: IamService = SERVICE_PROVIDER.iam_service()

    script_dir_path = resolve_scripts_path()
    if not iam_service.policy_get('admin_policy'):
        _LOG.debug(f'Creating admin policy')
        admin_policy_data = read_json(dir_path=script_dir_path,
                                      file_name='admin_policy.json')
        Policy(**admin_policy_data).save()

    if not iam_service.role_get('admin_role'):
        _LOG.debug(f'Creating admin role')
        admin_role = Role(name='admin_role',
                          policies=['admin_policy'],
                          expiration=datetime.now() + timedelta(days=365),
                          resource=[]
                          )
        admin_role.save()


def create_admin_user():
    from services import SERVICE_PROVIDER
    auth_client = SERVICE_PROVIDER.cognito()

    password = (os.environ.get(ENV_SYSTEM_USER_PASSWORD) or
                generate_password())
    if auth_client._get_user('SYSTEM_ADMIN'):
        _LOG.debug(f'Admin user already exist')
        return
    auth_client.sign_up(
        username='SYSTEM_ADMIN',
        customer='admin',
        password=password,
        role='admin_role'
    )
    print(f'r8s login --username SYSTEM_ADMIN --password "{password}"')


def init_system_user():
    create_iam_permissions_settings()
    create_admin_role()
    create_admin_user()


if __name__ == '__main__':
    init_system_user()
