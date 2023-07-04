from modular_sdk.models.application import Application
from modular_sdk.services.application_service import ApplicationService
from modular_sdk.services.customer_service import CustomerService
from pynamodb.attributes import MapAttribute

from models.application_attributes import ApplicationMeta


class RightSizerApplicationService(ApplicationService):
    def __init__(self, customer_service: CustomerService):
        self._excess_attributes_cache = {}
        super().__init__(customer_service=customer_service)

    def get_application_meta(self,
                             application: Application) -> ApplicationMeta:
        meta: MapAttribute = application.meta
        if meta:
            meta_dict = meta.as_dict()
            allowed_keys = list(ApplicationMeta._attributes.keys())
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
            application_meta_obj = ApplicationMeta(**meta_dict_filtered)
        else:
            application_meta_obj = ApplicationMeta()
        return application_meta_obj
