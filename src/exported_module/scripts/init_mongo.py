from typing import List, Tuple, Union

import pymongo
from modular_sdk.models.application import Application
from modular_sdk.models.customer import Customer
from modular_sdk.models.parent import Parent
from modular_sdk.models.region import RegionModel
from modular_sdk.models.tenant import Tenant
from modular_sdk.models.tenant_settings import TenantSettings

from commons.log_helper import get_logger

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


def init_mongo():
    mcdm_models = [
        Customer, Tenant, Parent, RegionModel, TenantSettings, Application
    ]
    for model in mcdm_models:
        create_indexes_for_model(model)


if __name__ == '__main__':
    init_mongo()
