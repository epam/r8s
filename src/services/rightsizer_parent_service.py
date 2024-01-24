from typing import List, Union

from modular_sdk.commons import generate_id
from modular_sdk.commons.constants import RIGHTSIZER_PARENT_TYPE, \
    TENANT_PARENT_MAP_RIGHTSIZER_TYPE, RIGHTSIZER_LICENSES_PARENT_TYPE, \
    TENANT_PARENT_MAP_RIGHTSIZER_LICENSES_TYPE, ParentScope, ParentType
from modular_sdk.models.parent import Parent
from modular_sdk.services.customer_service import CustomerService
from modular_sdk.services.parent_service import ParentService
from modular_sdk.services.tenant_service import TenantService
from pynamodb.attributes import MapAttribute

from commons.log_helper import get_logger
from models.parent_attributes import ShapeRule, LicensesParentMeta
from services.environment_service import EnvironmentService

_LOG = get_logger('r8s-parent-service')


class RightSizerParentService(ParentService):
    def __init__(self, tenant_service: TenantService,
                 customer_service: CustomerService,
                 environment_service: EnvironmentService):
        self._excess_attributes_cache = {}

        self.parent_type_tenant_pid_mapping = {
            RIGHTSIZER_PARENT_TYPE: TENANT_PARENT_MAP_RIGHTSIZER_TYPE,
            RIGHTSIZER_LICENSES_PARENT_TYPE:
                TENANT_PARENT_MAP_RIGHTSIZER_LICENSES_TYPE
        }
        self.environment_service = environment_service
        super(RightSizerParentService, self).__init__(
            tenant_service=tenant_service,
            customer_service=customer_service
        )

    def get_parent_meta(self, parent: Parent) -> LicensesParentMeta:
        meta: MapAttribute = parent.meta
        if meta:
            meta_dict = meta.as_dict()
            allowed_keys = list(LicensesParentMeta._attributes.keys())
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
            application_meta_obj = LicensesParentMeta(**meta_dict_filtered)
        else:
            application_meta_obj = LicensesParentMeta()
        return application_meta_obj

    def set_parent_meta(self, parent: Parent,
                        meta: LicensesParentMeta):
        meta_dict = meta.as_dict()

        excess_attributes = self._excess_attributes_cache.get(
            parent.parent_id)
        if excess_attributes:
            meta_dict.update(excess_attributes)

        parent.meta = meta_dict

    @staticmethod
    def list_shape_rules(parent_meta: LicensesParentMeta) -> \
            List[ShapeRule]:
        if not parent_meta.shape_rules:
            return []
        return [ShapeRule(**rule) for rule in parent_meta.shape_rules]

    def get_shape_rule(self, parent_meta: LicensesParentMeta,
                       rule_id: str) -> Union[ShapeRule, None]:
        rules = self.list_shape_rules(parent_meta=parent_meta)
        if not rules:
            return
        for rule in rules:
            if rule.rule_id == rule_id:
                return rule

    @staticmethod
    def create_shape_rule(action, cloud, condition, field, value) -> ShapeRule:
        return ShapeRule(rule_id=generate_id(),
                         action=action, cloud=cloud, condition=condition,
                         field=field, value=value)

    def add_shape_rule_to_meta(self, parent_meta: LicensesParentMeta,
                               shape_rule: ShapeRule):
        shape_rules = self.list_shape_rules(parent_meta=parent_meta)
        if not shape_rules:
            shape_rules = list()
            parent_meta.shape_rules = shape_rules

        parent_meta.shape_rules.append(shape_rule)

    def update_shape_rule_in_parent(self,
                                    parent_meta: LicensesParentMeta,
                                    shape_rule: ShapeRule):
        shape_rules = self.list_shape_rules(parent_meta=parent_meta)
        if not shape_rules:
            return
        for index, existing_rule in enumerate(shape_rules):
            if existing_rule.rule_id == shape_rule.rule_id:
                parent_meta.shape_rules[index] = shape_rule.as_dict()
                return

    @staticmethod
    def update_shape_rule(shape_rule: ShapeRule, action=None, field=None,
                          condition=None, value=None) -> None:
        if action:
            shape_rule.action = action
        if condition:
            shape_rule.condition = condition
        if field:
            shape_rule.field = field
        if value:
            shape_rule.value = value

    def remove_shape_rule_from_meta(self,
                                    parent_meta: LicensesParentMeta,
                                    rule_id: str) -> None:
        shape_rules = self.list_shape_rules(parent_meta=parent_meta)
        if not shape_rules:
            return
        for index, existing_rule in enumerate(shape_rules):
            if existing_rule.rule_id == rule_id:
                del parent_meta.shape_rules[index]
                return

    @staticmethod
    def get_shape_rule_dto(shape_rule: ShapeRule):
        return shape_rule.as_dict()

    def filter_directly_linked_tenants(self, tenant_names: List[str],
                                       parent: Parent):
        specific_parents = self.query_by_scope_index(
            customer_id=parent.customer_id,
            type_=parent.type,
            scope=ParentScope.SPECIFIC,
            is_deleted=False
        )
        disabled_parents = self.query_by_scope_index(
            customer_id=parent.customer_id,
            type_=parent.type,
            scope=ParentScope.DISABLED,
            is_deleted=False
        )
        parents = [*list(specific_parents), *list(disabled_parents)]
        exclude_tenant_names = {parent.tenant_name for parent
                                in parents if parent.tenant_name}
        _LOG.debug(f'Tenants will be excluded from scan: '
                   f'{exclude_tenant_names}')
        return list(set(tenant_names) - exclude_tenant_names)

    def resolve_tenant_names(self, parents: List[Parent], cloud) -> List[str]:
        tenant_names = []
        to_exclude = []

        for parent in parents:
            if parent.scope == ParentScope.DISABLED:
                to_exclude.append(parent.tenant_name)
            elif parent.scope == ParentScope.SPECIFIC:
                tenant_names.append(parent.tenant_name)
            elif parent.scope == ParentScope.ALL:
                tenants = list(self.tenant_service.i_get_tenant_by_customer(
                    customer_id=parent.customer_id,
                    active=True,
                    cloud=cloud
                ))
                tenant_names.extend([tenant.name for tenant in tenants])
        tenant_names = list(set(tenant_names))
        return [name for name in tenant_names if name not in to_exclude]
