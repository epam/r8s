from modular_sdk.commons.constants import ApplicationType
from modular_sdk.models.application import Application
from modular_sdk.services.application_service import ApplicationService
from modular_sdk.services.customer_service import CustomerService
from pynamodb.attributes import MapAttribute

from commons.constants import MAESTRO_RIGHTSIZER_APPLICATION_TYPE, \
    MAESTRO_RIGHTSIZER_LICENSES_APPLICATION_TYPE, TENANTS_ATTR
from models.application_attributes import (RightsizerApplicationMeta,
                                           RightsizerLicensesApplicationMeta)


class RightSizerApplicationService(ApplicationService):
    def __init__(self, customer_service: CustomerService):
        self._excess_attributes_cache = {}
        super().__init__(customer_service=customer_service)

    def get_dojo_application(self, customer):
        applications = list(self.list(
            customer=customer,
            _type=ApplicationType.DEFECT_DOJO,
            deleted=False,
            limit=1
        ))
        return applications[0] if applications else None

    def get_host_application(self, customer):
        applications = list(self.list(
            customer=customer,
            _type=ApplicationType.RIGHTSIZER,
            deleted=False,
            limit=1
        ))
        return applications[0] if applications else None

    def get_application_meta(self, application: Application):
        meta: MapAttribute = application.meta

        meta_attr_class = None
        if application.type == MAESTRO_RIGHTSIZER_APPLICATION_TYPE:
            meta_attr_class = RightsizerApplicationMeta
        elif application.type == MAESTRO_RIGHTSIZER_LICENSES_APPLICATION_TYPE:
            meta_attr_class = RightsizerLicensesApplicationMeta

        if meta:
            meta_dict = meta.as_dict()
            allowed_keys = list(meta_attr_class._attributes.keys())
            excess_attributes = {}
            meta_dict_filtered = {}
            for key, value in meta_dict.items():
                if key not in allowed_keys:
                    excess_attributes[key] = value
                else:
                    meta_dict_filtered[key] = value
            if excess_attributes:
                self._excess_attributes_cache[application.application_id] = \
                    excess_attributes
            application_meta_obj = meta_attr_class(**meta_dict_filtered)
        else:
            application_meta_obj = meta_attr_class()
        return application_meta_obj

    def get_by_license_key(self, customer, license_key: str):
        applications = self.list(
            customer=customer,
            _type=MAESTRO_RIGHTSIZER_LICENSES_APPLICATION_TYPE,
            deleted=False
        )
        for application in applications:
            app_meta = self.get_application_meta(application=application)
            if app_meta.license_key == license_key:
                return application

    def list_allowed_license_tenants(self, application: Application):
        app_meta = self.get_application_meta(application=application)
        customer_map = app_meta.customers.get(application.customer_id)
        if not customer_map:
            return
        return list(customer_map.get(TENANTS_ATTR, []))
