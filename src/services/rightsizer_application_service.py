import json
from typing import List, Union

from modular_sdk.commons.constants import ApplicationType
from modular_sdk.models.application import Application
from modular_sdk.services.application_service import ApplicationService
from modular_sdk.services.customer_service import CustomerService
from pynamodb.attributes import MapAttribute

from commons import ApplicationException, RESPONSE_INTERNAL_SERVER_ERROR
from commons.constants import APPLICATION_ID_ATTR, \
    MAESTRO_RIGHTSIZER_APPLICATION_TYPE, \
    MAESTRO_RIGHTSIZER_LICENSES_APPLICATION_TYPE, ALGORITHM_MAPPING_ATTR, \
    CUSTOMERS_ATTR, TENANTS_ATTR, \
    APPLICATION_TENANTS_ALL, TENANT_LICENSE_KEY_ATTR
from commons.log_helper import get_logger
from commons.time_helper import utc_iso
from models.application_attributes import RightsizerApplicationMeta, \
    ConnectionAttribute, RightsizerLicensesApplicationMeta, \
    RightSizerDojoApplicationMeta, AllowanceAttribute
from models.storage import Storage
from services.abstract_api_handler_lambda import PARAM_USER_CUSTOMER
from services.ssm_service import SSMService

APPLICATION_SECRET_NAME_TEMPLATE = 'm3.app.{application_id}'

_LOG = get_logger(__name__)


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
                                      password: str, created_by: str):
        application = self.build(
            customer_id=customer_id,
            type=MAESTRO_RIGHTSIZER_APPLICATION_TYPE,
            description=description,
            created_by=created_by
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

    def create_dojo_application(
            self, customer_id: str, description: str, host: str,
            port: int, protocol: str, stage: str,
            created_by: str, api_key: str):
        app_meta = RightSizerDojoApplicationMeta(
            host=host,
            port=port,
            stage=stage,
            protocol=protocol
        )
        application = self.build(
            customer_id=customer_id,
            type=ApplicationType.DEFECT_DOJO,
            description=description,
            created_by=created_by,
            meta=app_meta.as_dict()
        )
        secret_value = json.dumps({'api_key': api_key})
        secret_name = self._create_application_secret(
            application_id=application.application_id,
            password=secret_value
        )
        application.secret = secret_name
        return application

    def update_rightsizer_application(
            self, application: Application, updated_by: str,
            description=None, input_storage=None, output_storage=None,
            connection=None, password=None):
        update_attributes = []

        if description is not None:
            application.description = description
            update_attributes.append(Application.description)
        meta: RightsizerApplicationMeta = self.get_application_meta(
            application=application)
        if input_storage or output_storage or connection:
            update_attributes.append(Application.meta)
        if input_storage:
            meta.input_storage = input_storage.name
        if output_storage:
            meta.output_storage = output_storage.name
        if connection:
            meta.connection = connection
        if password:
            _LOG.debug('New password obtained')
            if application.secret:
                _LOG.debug(f'Deleting old application secret '
                           f'{application.secret}')
                self.ssm_service.delete_secret(
                    secret_name=application.secret)
            _LOG.debug(f'Creating new application secret {application.secret}]')
            secret_name = self._create_application_secret(
                application_id=application.application_id,
                password=password
            )
            application.secret = secret_name
            update_attributes.append(Application.secret)

        self.set_application_meta(
            application=application,
            meta=meta
        )
        self.update(
            application=application,
            attributes=update_attributes,
            updated_by=updated_by
        )
        return application

    def force_delete(self, application: Application):
        _LOG.debug(f'Going to force delete application '
                   f'{application.application_id}')
        self._delete_application_secret(
            application=application
        )
        application.delete()
        _LOG.debug('Application has been deleted')

    def _delete_application_secret(self, application: Application) -> None:
        _LOG.debug(f'Going to delete application {application.application_id} '
                   f'secret')
        secret_name = application.secret
        if not secret_name:
            _LOG.debug(f'Application {application.application_id} '
                       f'secret is not specified.')
            return
        try:
            self.ssm_service.delete_secret(secret_name=secret_name)
            _LOG.debug(f'Application {application.application_id} '
                       f'secret has been deleted.')
        except Exception as e:
            _LOG.error(f'Exception occurred while deleting secret '
                       f'{secret_name}:{e}')

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

        if not meta_attr_class:
            _LOG.error(f'Cant get application meta for type: '
                       f'{application.type}')
            raise ApplicationException(
                code=RESPONSE_INTERNAL_SERVER_ERROR,
                content=f'Invalid application type specified: '
                        f'{application.type}')

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

    def set_application_meta(
            self, application: Application,
            meta: Union[
                RightsizerApplicationMeta, RightsizerLicensesApplicationMeta]
    ):
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

    def resolve_application(
            self, event: dict,
            type_=MAESTRO_RIGHTSIZER_LICENSES_APPLICATION_TYPE
    ) -> List[Application]:
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
            applications = self.list(_type=type_, deleted=False)
            # return all application of RIGHTSIZER type
            return list(applications)

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

    def update_license(self, application: Application, license_data: dict):
        allowance = AllowanceAttribute(**license_data.get('allowance'))
        app_meta = self.get_application_meta(application=application)
        app_meta.allowance = allowance
        app_meta.expiration = license_data.get('valid_until')
        app_meta.algorithm_map = license_data.get(ALGORITHM_MAPPING_ATTR)

        license_customers = license_data.get(CUSTOMERS_ATTR)

        meta_customers = {
            application.customer_id: license_customers.get(
                application.customer_id, {})
        }
        allowed_tenants = meta_customers.get(
            application.customer_id, {}).get(TENANTS_ATTR)
        if not allowed_tenants:
            meta_customers[application.customer_id][TENANTS_ATTR] = [
                APPLICATION_TENANTS_ALL
            ]
        app_meta.customers = meta_customers
        app_meta.latest_sync = utc_iso()
        app_meta.tenant_license_key = meta_customers[application.customer_id][
            TENANT_LICENSE_KEY_ATTR]
        application.meta = app_meta
        self.save(application)

        return application

    def is_license_expired(self, application: Application):
        app_meta = self.get_application_meta(application=application)
        return app_meta.expiration <= utc_iso()

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
