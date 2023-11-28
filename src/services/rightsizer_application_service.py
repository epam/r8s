from typing import List

from modular_sdk.models.application import Application
from modular_sdk.services.application_service import ApplicationService
from modular_sdk.services.customer_service import CustomerService
from pynamodb.attributes import MapAttribute

from commons.constants import APPLICATION_ID_ATTR, \
    MAESTRO_RIGHTSIZER_APPLICATION_TYPE, RIGHTSIZER_APPLICATION_TYPES, \
    MAESTRO_RIGHTSIZER_LICENSES_APPLICATION_TYPE
from models.application_attributes import RightsizerApplicationMeta, \
    ConnectionAttribute
from models.storage import Storage
from services.abstract_api_handler_lambda import PARAM_USER_CUSTOMER
from services.ssm_service import SSMService

APPLICATION_SECRET_NAME_TEMPLATE = 'm3.app.{application_id}'


class RightSizerApplicationService(ApplicationService):
    def __init__(self, customer_service: CustomerService,
                 ssm_service: SSMService):
        self.ssm_service = ssm_service
        self._excess_attributes_cache = {}
        super().__init__(customer_service=customer_service)

    def create_rightsizer_application(self, customer_id: str, description: str,
                                      input_storage: Storage,
                                      output_storage: Storage,
                                      connection: ConnectionAttribute,
                                      password: str):
        application = self.create(
            customer_id=customer_id,
            type=MAESTRO_RIGHTSIZER_APPLICATION_TYPE,
            description=description
        )
        application_meta = RightsizerApplicationMeta(
            input_storage=input_storage.name,
            output_storage=output_storage.name,
            connection=connection
        )
        application.meta = application_meta

        secret_name = self._create_application_secret(
            application_id=application.application_id,
            password=password
        )
        application.secret = secret_name
        return application

    def update_rightsizer_application(
            self, application: Application, description=None,
            input_storage=None, output_storage=None,
            connection=None, password=None):
        if description is not None:
            application.description = description
        meta: RightsizerApplicationMeta = self.get_application_meta(
            application=application)
        if input_storage:
            meta.input_storage = input_storage.name
        if output_storage:
            meta.output_storage = output_storage.name
        if connection:
            meta.connection = connection
        if password:
            if application.secret:
                self.ssm_service.delete_secret(
                    secret_name=application.secret)
            secret_name = self._create_application_secret(
                application_id=application.application_id,
                password=password
            )
            application.secret = secret_name

        self.set_application_meta(
            application=application,
            meta=meta
        )
        return application

    def get_application_meta(self,
                             application: Application) -> RightsizerApplicationMeta:
        meta: MapAttribute = application.meta
        if meta:
            meta_dict = meta.as_dict()
            allowed_keys = list(RightsizerApplicationMeta._attributes.keys())
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
            application_meta_obj = RightsizerApplicationMeta(**meta_dict_filtered)
        else:
            application_meta_obj = RightsizerApplicationMeta()
        return application_meta_obj

    def set_application_meta(self, application: Application,
                             meta: RightsizerApplicationMeta):
        meta_dict = meta.as_dict()

        excess_attributes = self._excess_attributes_cache.get(
            application.application_id)
        if excess_attributes:
            meta_dict.update(excess_attributes)

        application.meta = meta_dict

    def filter_by_cloud(self, applications: List[Application], cloud: str):
        filtered = []

        for application in applications:
            app_cloud = self.get_application_meta(
                application=application).cloud
            if cloud.upper() == app_cloud:
                filtered.append(application)
        return filtered

    def resolve_application(self, event: dict,
                            type_=MAESTRO_RIGHTSIZER_LICENSES_APPLICATION_TYPE) -> List[Application]:
        user_customer = event.get(PARAM_USER_CUSTOMER)
        event_application = event.get(APPLICATION_ID_ATTR)

        if user_customer == 'admin':
            # get application regardless of user customer
            if event_application:
                application = self.get_application_by_id(
                    application_id=event_application)
                if application and application.type == type_ \
                        and not application.is_deleted:
                    return [application]
                return []
            applications = self.list(_type=type_)
            # return all application of RIGHTSIZER type
            return [app for app in applications
                    if app.type == type_
                    and not app.is_deleted]

        if event_application:
            # return application by id if it's customer matches with
            # user customer
            application = self.get_application_by_id(
                application_id=event_application)
            if application and application.customer_id == user_customer and \
                    application.type == type_ \
                    and not application.is_deleted:
                return [application]
            return []

        # return all customer applications
        return list(self.i_get_application_by_customer(
            customer_id=user_customer,
            application_type=type_,
            deleted=False
        ))

    def _create_application_secret(self, application_id: str, password: str):
        secret_name = APPLICATION_SECRET_NAME_TEMPLATE.format(
            application_id=application_id)
        self.ssm_service.create_secret_value(
            secret_name=secret_name,
            secret_value=password
        )
        return secret_name
