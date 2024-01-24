from collections import defaultdict
from typing import List, Dict

from modular_sdk.commons.constants import RIGHTSIZER_PARENT_TYPE, \
    TENANT_PARENT_MAP_RIGHTSIZER_TYPE, RIGHTSIZER_LICENSES_PARENT_TYPE, \
    TENANT_PARENT_MAP_RIGHTSIZER_LICENSES_TYPE, ParentScope
from modular_sdk.models.parent import Parent
from modular_sdk.services.customer_service import CustomerService
from modular_sdk.services.parent_service import ParentService
from modular_sdk.services.tenant_service import TenantService
from pynamodb.attributes import MapAttribute

from commons.constants import MAESTRO_RIGHTSIZER_LICENSES_APPLICATION_TYPE
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

    def get_job_parents(self, application_id: str, parent_id: str = None):
        if parent_id:
            return [self.get_parent_by_id(parent_id=parent_id)]
        return self.list_application_parents(
            application_id=application_id,
            only_active=True
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
            parent_meta_obj = LicensesParentMeta(**meta_dict_filtered)
        else:
            parent_meta_obj = LicensesParentMeta()
        return parent_meta_obj

    @staticmethod
    def list_shape_rules(parent_meta: LicensesParentMeta) -> \
            List[ShapeRule]:
        if not parent_meta.shape_rules:
            return []
        return [ShapeRule(**rule) for rule in parent_meta.shape_rules]

    def resolve_tenant_parent_meta_map(
            self, parents: List[Parent]) -> Dict[str, LicensesParentMeta]:
        all_scoped_parents = [parent for parent in parents
                              if parent.scope == ParentScope.ALL.value]
        all_scoped_parent = next(iter(all_scoped_parents), None)

        if all_scoped_parent:
            meta = self.get_parent_meta(all_scoped_parent)
            tenant_meta_map = defaultdict(lambda: meta)
        else:
            tenant_meta_map = defaultdict(lambda: LicensesParentMeta())

        for parent in parents:
            if (parent.scope == ParentScope.SPECIFIC.value and
                    parent.tenant_name):
                tenant_meta_map[parent.tenant_name] = (
                    self.get_parent_meta(parent))
        return tenant_meta_map
