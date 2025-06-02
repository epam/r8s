import os

from modular_sdk.services.tenant_service import TenantService

from commons import RESPONSE_BAD_REQUEST_CODE, build_response, \
    RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params, RESPONSE_FORBIDDEN_CODE
from commons.constants import GET_METHOD, TENANT_ATTR, \
    CUSTOMER_ATTR, DATA_SOURCE_ATTR, REGION_ATTR, \
    INSTANCE_ID_ATTR, CLOUD_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.abstract_api_handler_lambda import PARAM_USER_CUSTOMER
from services.storage_service import StorageService

_LOG = get_logger('r8s-storage-data-processor')

TIMESTAMP_ATTR = 'timestamp'


class StorageDataProcessor(AbstractCommandProcessor):
    def __init__(self, storage_service: StorageService,
                 tenant_service: TenantService):
        self.storage_service = storage_service
        self.tenant_service = tenant_service
        self.method_to_handler = {
            GET_METHOD: self.get,
        }
        self.metric_item_template = {
            CUSTOMER_ATTR: '',
            TENANT_ATTR: '',
            REGION_ATTR: '',
            TIMESTAMP_ATTR: '',
            INSTANCE_ID_ATTR: '',
        }

    def get(self, event):
        _LOG.debug(f'Sign up event: {event}')

        validate_params(event=event, required_params_list=(DATA_SOURCE_ATTR,
                                                           TENANT_ATTR))

        customer = event.get(PARAM_USER_CUSTOMER)
        if customer == 'admin':
            customer = event.get(CUSTOMER_ATTR)

        if not customer:
            _LOG.error(f'\'{CUSTOMER_ATTR}\' must be '
                       f'specified for admin users.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'\'{CUSTOMER_ATTR}\' must be '
                        f'specified for admin users.'
            )

        data_source_name = event.get(DATA_SOURCE_ATTR)
        filter_customer = event.get(CUSTOMER_ATTR)
        filter_tenant = event.get(TENANT_ATTR)
        filter_region = event.get(REGION_ATTR)
        filter_timestamp = event.get(TIMESTAMP_ATTR)
        filter_instance_id = event.get(INSTANCE_ID_ATTR)

        tenant_name = event.get(TENANT_ATTR)

        _LOG.debug(f'Describing tenant \'{tenant_name}\'')
        tenant = self.tenant_service.get(tenant_name=tenant_name)
        if not tenant:
            _LOG.error(f'Tenant \'{tenant_name}\' does not exist.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Tenant \'{tenant_name}\' does not exist.'
            )

        if tenant.customer_name != customer:
            _LOG.error(f'Tenant \'{tenant_name}\' does not belong to '
                       f'customer \'{customer}\'.')
            return build_response(
                code=RESPONSE_FORBIDDEN_CODE,
                content=f'Tenant \'{tenant_name}\' does not belong to '
                        f'customer \'{customer}\'.'
            )

        _LOG.debug(f'Extracting storage \'{data_source_name}\'')
        data_source = self.storage_service.get(identifier=data_source_name)
        if not data_source:
            _LOG.error(f'Storage \'{data_source_name}\' does not exist')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Storage with name \'{data_source_name}\' '
                        f'does not exist'
            )
        if filter_region:
            regions = [filter_region]
        else:
            regions = [region.native_name for region in tenant.regions]
        _LOG.debug(f'Searching for metric files')
        files = self.storage_service.list_metric_files(
            data_source=data_source,
            customer=customer,
            cloud=tenant.cloud.lower(),
            tenant=tenant.name,
            regions=regions,
            timestamp=filter_timestamp,
        )
        _LOG.debug(f'Formatting')
        result = []
        for file in files:
            file_key = file.get('Key')
            path_items = file_key.split(os.sep)
            if len(path_items) < 5:
                # not following customer/tenant/region/timestamp structure
                _LOG.warning(f'Invalid folder structure for file: {file_key}')
                continue
            customer, cloud, tenant, region, timestamp, instance_id = \
                path_items[-6:]
            instance_id = instance_id.replace('.csv', '')

            file_item = self.metric_item_template.copy()
            file_item[CUSTOMER_ATTR] = customer
            file_item[CLOUD_ATTR] = cloud
            file_item[TENANT_ATTR] = tenant
            file_item[REGION_ATTR] = region
            file_item[TIMESTAMP_ATTR] = timestamp
            file_item[INSTANCE_ID_ATTR] = instance_id
            result.append(file_item)

        _LOG.debug(f'Filtering results')
        result = self._filter_metric_list(
            metrics=result,
            customer=filter_customer,
            tenant=filter_tenant,
            timestamp=filter_timestamp,
            instance_id=filter_instance_id
        )
        _LOG.debug(f'Response: {result}')
        if not result:
            _LOG.debug(f'No metric files found matching given query.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'No metric files found matching given query.'
            )
        return build_response(code=RESPONSE_OK_CODE,
                              content=result)

    def _filter_metric_list(self, metrics: list, customer=None, tenant=None,
                            timestamp=None, instance_id=None):
        filtered = []
        for metric_item in metrics:
            metric_customer = metric_item.get(CUSTOMER_ATTR)
            metric_tenant = metric_item.get(TENANT_ATTR)
            metric_timestamp = metric_item.get(TIMESTAMP_ATTR)
            metric_instance_id = metric_item.get(INSTANCE_ID_ATTR)
            if customer and not self._is_lower_equal(customer,
                                                     metric_customer):
                continue
            if tenant and not self._is_lower_equal(tenant,
                                                   metric_tenant):
                continue
            if timestamp and not self._is_lower_equal(timestamp,
                                                      metric_timestamp):
                continue
            if instance_id and not self._is_lower_equal(instance_id,
                                                        metric_instance_id):
                continue
            filtered.append(metric_item)
        return filtered

    @staticmethod
    def _is_lower_equal(s1: str, s2: str):
        if s1.lower() == s2.lower():
            return True
        return False
