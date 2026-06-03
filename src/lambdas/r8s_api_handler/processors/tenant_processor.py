from modular_sdk.services.tenant_service import TenantService

from commons import build_response, RESPONSE_OK_CODE, \
    RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_FORBIDDEN_CODE
from commons.constants import GET_METHOD, TENANT_ATTR, PARAM_USER_TENANT_ACCESS
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.abstract_api_handler_lambda import PARAM_USER_CUSTOMER

_LOG = get_logger('r8s-tenant-processor')


class TenantProcessor(AbstractCommandProcessor):
    def __init__(self, tenant_service: TenantService):
        self.tenant_service = tenant_service
        self.method_to_handler = {
            GET_METHOD: self.get,
        }

    @classmethod
    def build(cls):
        from services import SERVICE_PROVIDER
        return cls(
            tenant_service=SERVICE_PROVIDER.tenant_service()
        )

    def get(self, event):
        _LOG.debug(f'Describe tenant event: {event}')
        tenant_name = event.get(TENANT_ATTR)
        user_customer = event.get(PARAM_USER_CUSTOMER)
        tap = event.get(PARAM_USER_TENANT_ACCESS)

        if tenant_name:
            _LOG.debug(f'Describing tenant by name \'{tenant_name}\'')
            if tap and not tap.is_allowed_for_all_tenants():
                if not tap.is_allowed_for(tenant_name):
                    _LOG.warning(
                        f'Access to tenant \'{tenant_name}\' is not allowed')
                    return build_response(
                        code=RESPONSE_FORBIDDEN_CODE,
                        content=f'Access to tenant \'{tenant_name}\' '
                                f'is not allowed'
                    )
            tenant = self.tenant_service.get(tenant_name=tenant_name)
            if not tenant:
                _LOG.debug(f'Tenant \'{tenant_name}\' not found')
                return build_response(
                    code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                    content=f'Tenant \'{tenant_name}\' not found'
                )
            tenants = [tenant]
        else:
            _LOG.debug(f'Listing all tenants for customer \'{user_customer}\'')
            is_admin = user_customer == 'admin'
            if is_admin:
                tenants = list(self.tenant_service.i_scan_tenants())
            else:
                tenants = list(
                    self.tenant_service.i_get_tenant_by_customer(
                        customer_id=user_customer
                    )
                )
            if tap and not tap.is_allowed_for_all_tenants():
                tenants = [t for t in tenants if tap.is_allowed_for(t.name)]

        if not tenants:
            _LOG.debug('No tenants found matching given query')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content='No tenants found matching given query'
            )

        tenants_dto = [TenantService.get_dto(t) for t in tenants]
        _LOG.debug(f'Tenants to return: {tenants_dto}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=tenants_dto
        )
