import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Union

import pymongo
from modular_sdk.models.application import Application
from modular_sdk.models.customer import Customer
from modular_sdk.models.parent import Parent
from modular_sdk.models.region import RegionModel
from modular_sdk.models.tenant import Tenant
from modular_sdk.models.tenant_settings import TenantSettings

from commons.constants import SETTING_IAM_PERMISSIONS
from commons.log_helper import get_logger
from scripts.configure_environment import generate_password

_LOG = get_logger(__name__)

MAIN_DYNAMODB_INDEX_KEY = 'main'
GLOBAL_SECONDARY_INDEXES = 'global_secondary_indexes'
LOCAL_SECONDARY_INDEXES = 'local_secondary_indexes'
INDEX_NAME_ATTR, KEY_SCHEMA_ATTR = 'index_name', 'key_schema'

ATTRIBUTE_NAME_ATTR, KEY_TYPE_ATTR = 'AttributeName', 'KeyType'
HASH_KEY_TYPE, RANGE_KEY_TYPE = 'HASH', 'RANGE'


def convert_index(key_schema: dict) -> Union[str, List[Tuple]]:
    if len(key_schema) == 1:
        _LOG.info('Only hash key found for the index')
        return key_schema[0][ATTRIBUTE_NAME_ATTR]
    elif len(key_schema) == 2:
        _LOG.info('Both hash and range keys found for the index')
        result = [None, None]
        for key in key_schema:
            if key[KEY_TYPE_ATTR] == HASH_KEY_TYPE:
                _i = 0
            elif key[KEY_TYPE_ATTR] == RANGE_KEY_TYPE:
                _i = 1
            else:
                raise ValueError(f'Unknown key type: {key[KEY_TYPE_ATTR]}')
            result[_i] = (key[ATTRIBUTE_NAME_ATTR], pymongo.DESCENDING)
        return result
    else:
        raise ValueError(f'Unknown key schema: {key_schema}')


def create_indexes_for_model(model):
    table_name = model.Meta.table_name
    collection = model.mongodb_handler().mongodb.collection(table_name)
    collection.drop_indexes()

    hash_key = getattr(model._hash_key_attribute(), 'attr_name', None)
    range_key = getattr(model._range_key_attribute(), 'attr_name', None)
    _LOG.info(f'Creating main indexes for \'{table_name}\'')
    if hash_key and range_key:
        collection.create_index([(hash_key, pymongo.ASCENDING),
                                 (range_key, pymongo.ASCENDING)],
                                name=MAIN_DYNAMODB_INDEX_KEY)
    elif hash_key:
        collection.create_index(hash_key, name=MAIN_DYNAMODB_INDEX_KEY)
    else:
        _LOG.error(f'Table \'{table_name}\' has no hash_key and range_key')

    indexes = model._get_schema()  # GSIs & LSIs,  # only PynamoDB 5.2.1+
    gsi = indexes.get(GLOBAL_SECONDARY_INDEXES)
    lsi = indexes.get(LOCAL_SECONDARY_INDEXES)
    if gsi:
        _LOG.info(f'Creating global indexes for \'{table_name}\'')
        for i in gsi:
            index_name = i[INDEX_NAME_ATTR]
            _LOG.info(f'Processing index \'{index_name}\'')
            collection.create_index(
                convert_index(i[KEY_SCHEMA_ATTR]), name=index_name)
            _LOG.info(f'Index \'{index_name}\' was created')
        _LOG.info(f'Global indexes for \'{table_name}\' were created!')
    if lsi:
        pass  # write this part if at least one LSI is used


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
    password = generate_password()
    if auth_client._get_user('SYSTEM_ADMIN'):
        _LOG.debug(f'Admin user already exist')
        return
    auth_client.sign_up(
        username='SYSTEM_ADMIN',
        customer='admin',
        password=password,
        role='admin_role'
    )
    _LOG.warning('User has been created.')
    _LOG.warning(f'r8s login --username SYSTEM_ADMIN --password {password}')


def create_customer():
    customer_name = os.environ.get('CUSTOMER_NAME')
    if not customer_name:
        _LOG.debug('Customer not specified')
        return
    from modular_sdk.services.customer_service import CustomerService
    if CustomerService().get(customer_name):
        _LOG.debug(f'Customer \'{customer_name}\' already exist.')
        return
    _LOG.debug(f'Creating Customer \'{customer_name}\'')
    Customer(name=customer_name, display_name=customer_name).save()


def create_tenant():
    tenant_name = os.environ.get('TENANT_NAME')
    customer_name = os.environ.get('CUSTOMER_NAME')
    if not tenant_name:
        _LOG.debug('Tenant not specified')
        return
    if not customer_name:
        _LOG.debug('Customer not specified')
        return
    from modular_sdk.services.tenant_service import TenantService
    if TenantService().get(tenant_name):
        _LOG.debug(f'Tenant \'{tenant_name}\' already exist.')
        return
    _LOG.debug(f'Creating Tenant \'{tenant_name}\'')
    Tenant(name=tenant_name, display_name=tenant_name,
           cloud="AWS", customer_name=customer_name).save()


def init_mongo():
    mcdm_models = [
        Customer, Tenant, Parent, RegionModel, TenantSettings, Application
    ]
    for model in mcdm_models:
        create_indexes_for_model(model)

    create_iam_permissions_settings()
    create_admin_role()
    create_admin_user()
    create_customer()
    create_tenant()


if __name__ == '__main__':
    init_mongo()
