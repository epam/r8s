from typing import List, Union

from modular_sdk.commons.constants import RIGHTSIZER_PARENT_TYPE, \
    RIGHTSIZER_LICENSES_PARENT_TYPE, \
    TENANT_PARENT_MAP_RIGHTSIZER_LICENSES_TYPE, ParentScope, ParentType
from modular_sdk.models.parent import Parent
from modular_sdk.models.tenant import Tenant
from modular_sdk.services.customer_service import CustomerService
from modular_sdk.services.parent_service import ParentService
from modular_sdk.services.tenant_service import TenantService
from pynamodb.attributes import MapAttribute

from commons.constants import TENANT_PARENT_MAP_RIGHTSIZER_TYPE, \
    PARENT_SCOPE_ALL_TENANTS, PARENT_SCOPE_SPECIFIC_TENANT
from commons.log_helper import get_logger
from models.parent_attributes import ParentMeta, ShapeRule, LicensesParentMeta
from services.environment_service import EnvironmentService

_LOG = get_logger('r8s-parent-service')


class RightSizerParentService(ParentService):
    def __init__(self, tenant_service: TenantService,
                 customer_service: CustomerService,
                 environment_service: EnvironmentService):
        self.environment_service = environment_service
        self.parent_type_meta_mapping = {
            RIGHTSIZER_PARENT_TYPE: ParentMeta,
            RIGHTSIZER_LICENSES_PARENT_TYPE: LicensesParentMeta
        }
        self.parent_type_tenant_pid_mapping = {
            RIGHTSIZER_PARENT_TYPE: TENANT_PARENT_MAP_RIGHTSIZER_TYPE,
            RIGHTSIZER_LICENSES_PARENT_TYPE:
                TENANT_PARENT_MAP_RIGHTSIZER_LICENSES_TYPE
        }
        self._excess_attributes_cache = {}
        super(RightSizerParentService, self).__init__(
            customer_service=customer_service,
            tenant_service=tenant_service
        )

    def resolve(self, licensed_parent: Parent,
                scan_tenants: list = None) -> Parent:
        """
        Resolves RIGHTSIZER parent from RIGHTSIZER_LICENSES.

        Depends on the RIGHTSIZER_LICENSES scope, RIGHTSIZER
        parent will be resolved in different ways:

        ALL_TENANTS: first RIGHTSIZER parent linked to same
        application with ALL_TENANTS scope and
        matching cloud will be taken

        SPECIFIC_TENANTS: RIGHSIZER parent will be taken from scan_tenants,
        from Tenant.pid map

        :param licensed_parent: Parent of RIGHTSIZER_LICENSES type
        :param scan_tenants: list of tenants to scan -
        required for SPECIFIC_TENANTS scope

        :return: Parent with RIGHTSIZER type
        """
        _LOG.debug(f'Searching for RIGHTSIZER parent for licensed parent '
                   f'\'{licensed_parent.parent_id}\'')
        licensed_parent_meta = self.get_parent_meta(parent=licensed_parent)

        if licensed_parent.scope == ParentScope.ALL.value:
            _LOG.debug(f'Licensed scope: {ParentScope.ALL.value}. '
                       f'Going to search for Parent directly')
            parents = self.list_application_parents(
                application_id=licensed_parent.application_id,
                only_active=True,
                type_=ParentType.RIGHTSIZER_PARENT.value
            )

            for parent in parents:
                if parent.scope == ParentScope.ALL.value and \
                        licensed_parent.cloud == parent.cloud:
                    return parent
        elif licensed_parent.scope == ParentScope.SPECIFIC.value \
                and scan_tenants:
            _LOG.debug(f'Licensed scope: {ParentScope.SPECIFIC.value}. '
                       f'Validating tenant {licensed_parent.tenant_name}')
            tenant = self.tenant_service.get(
                tenant_name=licensed_parent.tenant_name)

            parent_map = tenant.parent_map.as_dict()

            linked_parent_id = parent_map.get(
                TENANT_PARENT_MAP_RIGHTSIZER_TYPE)
            linked_licensed_parent_id = parent_map.get(
                TENANT_PARENT_MAP_RIGHTSIZER_LICENSES_TYPE
            )
            if linked_licensed_parent_id != licensed_parent.parent_id:
                return
            if not linked_parent_id:
                _LOG.warning(f'Tenant \'{licensed_parent.tenant_name}\' '
                             f'don\'t have RIGHTSIZER type linkage.')
                return
            return self.get_parent_by_id(parent_id=linked_parent_id)

    @staticmethod
    def list_application_parents(application_id, type_: str,
                                 only_active=True):
        if only_active:
            return list(Parent.scan(
                filter_condition=
                (Parent.type == type_) &
                (Parent.application_id == application_id) &
                (Parent.is_deleted == False)))
        return list(Parent.scan(
            filter_condition=(Parent.application_id == application_id) &
                             (Parent.type == type_)))

    def get_parent_meta(self, parent: Parent) -> \
            Union[ParentMeta, LicensesParentMeta]:
        meta: MapAttribute = parent.meta
        meta_model = self.parent_type_meta_mapping.get(parent.type,
                                                       RIGHTSIZER_PARENT_TYPE)
        if meta:
            meta_dict = meta.as_dict()
            allowed_keys = list(meta_model._attributes.keys())
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
            application_meta_obj = meta_model(**meta_dict_filtered)
        else:
            application_meta_obj = meta_model()
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

    def list_activated_tenants(self, parent: Parent, cloud: str,
                               rate_limit: int = None) -> List[Tenant]:
        tenants = self.tenant_service.i_get_tenant_by_customer(
            customer_id=parent.customer_id,
            active=True,
            attributes_to_get=[Tenant.name, Tenant.parent_map],
            cloud=cloud,
            rate_limit=rate_limit
        )
        linked_tenants = []
        target_pid_key = self.parent_type_tenant_pid_mapping.get(
            parent.type, RIGHTSIZER_PARENT_TYPE)
        for tenant in tenants:
            _LOG.debug(f'Processing tenant \'{tenant.name}\'')
            parent_map = tenant.parent_map.as_dict()
            if target_pid_key not in parent_map:
                _LOG.debug(f'Tenant \'{tenant.name}\' does not have linked '
                           f'RIGHTSIZER parent, skipping.')
                continue
            linked_parent_id = parent_map.get(target_pid_key)
            if parent.parent_id == linked_parent_id:
                _LOG.debug(f'Tenant {tenant.name} is linked to '
                           f'parent \'{parent.parent_id}\'')
                linked_tenants.append(tenant)
        return linked_tenants

