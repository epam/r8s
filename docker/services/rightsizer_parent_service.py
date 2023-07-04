from typing import List, Union

from modular_sdk.commons.constants import RIGHTSIZER_PARENT_TYPE
from modular_sdk.models.parent import Parent
from modular_sdk.services.customer_service import CustomerService
from modular_sdk.services.parent_service import ParentService
from modular_sdk.services.tenant_service import TenantService
from pynamodb.attributes import MapAttribute

from commons.constants import PARENT_SCOPE_ALL_TENANTS, \
    JOB_STEP_INITIALIZATION, TENANT_PARENT_MAP_RIGHTSIZER_TYPE, ALL
from commons.exception import ExecutorException
from commons.log_helper import get_logger
from models.parent_attributes import ParentMeta, ShapeRule

_LOG = get_logger('r8s-parent-service')


class RightSizerParentService(ParentService):
    def __init__(self, tenant_service: TenantService,
                 customer_service: CustomerService):
        self._excess_attributes_cache = {}
        super(RightSizerParentService, self).__init__(
            customer_service=customer_service,
            tenant_service=tenant_service
        )

    @staticmethod
    def list_application_parents(application_id, only_active=True):
        if only_active:
            return list(Parent.scan(
                filter_condition=
                (Parent.type == RIGHTSIZER_PARENT_TYPE) &
                (Parent.application_id == application_id) &
                (Parent.is_deleted == False)))
        return list(Parent.scan(
            filter_condition=(Parent.application_id == application_id) &
                             (Parent.type == RIGHTSIZER_PARENT_TYPE)))

    def get_parent_meta(self, parent: Parent) -> ParentMeta:
        meta: MapAttribute = parent.meta
        if meta:
            meta_dict = meta.as_dict()
            allowed_keys = list(ParentMeta._attributes.keys())
            excess_attributes = {}
            meta_dict_filtered = {}
            for key, value in meta_dict.items():
                if key not in allowed_keys:
                    excess_attributes[key] = value
                else:
                    meta_dict_filtered[key] = value
            if excess_attributes:
                self._excess_attributes_cache[parent.parent_id] = \
                    excess_attributes
            application_meta_obj = ParentMeta(**meta_dict_filtered)
        else:
            application_meta_obj = ParentMeta()
        return application_meta_obj

    @staticmethod
    def list_shape_rules(parent_meta: ParentMeta) -> \
            List[ShapeRule]:
        if not parent_meta.shape_rules:
            return []
        return [ShapeRule(**rule) for rule in parent_meta.shape_rules]

    def get_shape_rule(self, parent_meta: ParentMeta,
                       rule_id: str) -> Union[ShapeRule, None]:
        rules = self.list_shape_rules(parent_meta=parent_meta)
        if not rules:
            return
        for rule in rules:
            if rule.rule_id == rule_id:
                return rule

    @staticmethod
    def get_shape_rule_dto(shape_rule: ShapeRule):
        return shape_rule.as_dict()

    def resolve_scan_tenants_list(self, scan_tenants, parent: Parent):
        linked_tenant_names = []

        parent_meta = self.get_parent_meta(parent=parent)
        if not parent_meta.scope:
            _LOG.error(f'Invalid configuration. Scope does not exist '
                       f'in parent \'{parent.parent_id}\' meta')
            raise ExecutorException(
                step_name=JOB_STEP_INITIALIZATION,
                reason=f'Invalid configuration. Scope does not exist '
                       f'in parent \'{parent.parent_id}\' meta'
            )
        if parent_meta.scope == PARENT_SCOPE_ALL_TENANTS:
            _LOG.debug(f'Scan is allowed for all tenants of customer '
                       f'\'{parent.customer_id}\'')
            return scan_tenants if scan_tenants else [ALL]
        _LOG.debug(f'Listing parent \'{parent.parent_id}\' tenants')
        tenants = self.tenant_service.i_get_tenant_by_customer(
            customer_id=parent.customer_id,
            active=True
        )
        for tenant in tenants:
            _LOG.debug(f'Processing tenant \'{tenant.name}\'')
            parent_map = tenant.parent_map.as_dict()
            if TENANT_PARENT_MAP_RIGHTSIZER_TYPE not in parent_map:
                _LOG.debug(f'Tenant \'{tenant.name}\' does not have linked '
                           f'RIGHTSIZER parent, skipping.')
                continue
            linked_parent_id = parent_map.get(
                TENANT_PARENT_MAP_RIGHTSIZER_TYPE)
            if parent.parent_id == linked_parent_id:
                _LOG.debug(f'Tenant {tenant.name} is linked to target parent '
                           f'\'{parent.parent_id}\'')
                linked_tenant_names.append(tenant.name)

        if not scan_tenants:
            return linked_tenant_names
        return [tenant_name for tenant_name in scan_tenants
                if tenant_name in linked_tenant_names]
