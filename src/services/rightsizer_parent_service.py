from typing import List, Union

from modular_sdk.commons import generate_id
from modular_sdk.commons.constants import RIGHTSIZER_PARENT_TYPE, \
    TENANT_PARENT_MAP_RIGHTSIZER_TYPE
from modular_sdk.models.parent import Parent
from modular_sdk.models.tenant import Tenant
from modular_sdk.services.customer_service import CustomerService
from modular_sdk.services.parent_service import ParentService
from modular_sdk.services.tenant_service import TenantService
from pynamodb.attributes import MapAttribute

from commons import ApplicationException, RESPONSE_RESOURCE_NOT_FOUND_CODE
from commons.log_helper import get_logger
from models.algorithm import Algorithm
from models.parent_attributes import ParentMeta, ShapeRule

_LOG = get_logger('r8s-parent-service')


class RightSizerParentService(ParentService):
    def __init__(self, tenant_service: TenantService,
                 customer_service: CustomerService):
        self._excess_attributes_cache = {}
        super(RightSizerParentService, self).__init__(
            tenant_service=tenant_service,
            customer_service=customer_service
        )

    def create_rightsizer_parent(self, application_id, customer_id,
                                 description, cloud: str,
                                 algorithm: Algorithm,
                                 scope: str, license_key:str = None):
        meta = ParentMeta(
            cloud=cloud,
            algorithm=algorithm.name,
            shape_rules=[],
            scope=scope
        )
        if license_key:
            meta.license_key = license_key
        parent = self.create(
            application_id=application_id,
            customer_id=customer_id,
            description=description,
            is_deleted=False,
            parent_type=RIGHTSIZER_PARENT_TYPE,
            meta=meta.as_dict()
        )
        return parent

    @staticmethod
    def list_rightsizer_parents(only_active=True):
        if only_active:
            return list(Parent.scan(
                filter_condition=(Parent.type == RIGHTSIZER_PARENT_TYPE) &
                                 (Parent.is_deleted == False)
            ))
        return list(Parent.scan(
            filter_condition=(Parent.type == RIGHTSIZER_PARENT_TYPE)
        ))

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

    def set_parent_meta(self, parent: Parent,
                        meta: ParentMeta):
        meta_dict = meta.as_dict()

        excess_attributes = self._excess_attributes_cache.get(
            parent.parent_id)
        if excess_attributes:
            meta_dict.update(excess_attributes)

        parent.meta = meta_dict

    def update_cloud(self, parent: Parent, cloud: str):
        parent_meta = self.get_parent_meta(parent=parent)
        parent_meta.cloud = cloud
        self.set_parent_meta(parent=parent,
                             meta=parent_meta)

    def update_algorithm(self, parent: Parent, algorithm: str):
        parent_meta = self.get_parent_meta(parent=parent)
        parent_meta.algorithm = algorithm
        self.set_parent_meta(parent=parent,
                             meta=parent_meta)

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
    def create_shape_rule(action, condition, field, value) -> ShapeRule:
        return ShapeRule(rule_id=generate_id(),
                         action=action, condition=condition,
                         field=field, value=value)

    def add_shape_rule_to_meta(self, parent_meta: ParentMeta,
                               shape_rule: ShapeRule):
        shape_rules = self.list_shape_rules(parent_meta=parent_meta)
        if not shape_rules:
            shape_rules = list()
            parent_meta.shape_rules = shape_rules

        parent_meta.shape_rules.append(shape_rule)

    def update_shape_rule_in_application(self,
                                         parent_meta: ParentMeta,
                                         shape_rule: ShapeRule):
        shape_rules = self.list_shape_rules(parent_meta=parent_meta)
        if not shape_rules:
            return
        for index, existing_rule in enumerate(shape_rules):
            if existing_rule.rule_id == shape_rule.rule_id:
                parent_meta.shape_rules[index] = shape_rule.as_dict()
                return
        raise ApplicationException(
            code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
            content=f'Shape rule with id \'{shape_rule.rule_id}\' '
                    f'does not exist'
        )

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

    def remove_shape_rule_from_application(self,
                                           parent_meta: ParentMeta,
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

    def list_activated_tenants(self, parent: Parent) -> List[Tenant]:
        tenants = self.tenant_service.i_get_tenant_by_customer(
            customer_id=parent.customer_id,
            active=True,
            attributes_to_get=[Tenant.name, Tenant.parent_map]
        )
        linked_tenants = []

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
                linked_tenants.append(tenant)
        return linked_tenants
