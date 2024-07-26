from mongoengine import DoesNotExist, ValidationError

from commons.constants import CUSTOMERS_ATTR, ALGORITHM_MAPPING_ATTR
from commons.constants import TENANTS_ATTR, ATTACHMENT_MODEL_ATTR
from commons.log_helper import get_logger
from commons.time_helper import utc_iso
from models.license import License, AllowanceAttribute
from models.license import PROHIBITED_ATTACHMENT, PERMITTED_ATTACHMENT
from services.setting_service import SettingsService

_LOG = get_logger(__name__)


class LicenseService:
    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service

    @staticmethod
    def get_license(license_id):
        try:
            return License.objects.get(license_key=license_id)
        except (DoesNotExist, ValidationError):
            return None

    @staticmethod
    def dto(_license: License) -> dict:
        data = _license.get_json()
        data.pop(CUSTOMERS_ATTR, None)
        return data

    @staticmethod
    def list():
        return list(License.objects)

    @staticmethod
    def list_licenses(license_key: str = None):
        if license_key:
            license_ = LicenseService.get_license(license_key)
            return iter([license_, ]) if license_ else []
        return LicenseService.list()

    @staticmethod
    def get_all_non_expired_licenses():
        return list(
            License.objects.query(expiration__gt=utc_iso())
        )

    @staticmethod
    def validate_customers(_license: License, allowed_customers: list):
        license_customers = list(_license.customers)
        if not allowed_customers:
            return license_customers
        return list(set(license_customers) & set(allowed_customers))

    @staticmethod
    def create(configuration):
        return License(**configuration)

    @staticmethod
    def delete(license_obj: License):
        return license_obj.delete()

    def is_applicable_for_customer(self, license_key, customer):
        license_ = self.get_license(license_id=license_key)
        if not license_:
            return False
        return customer in license_.customers

    @staticmethod
    def is_subject_applicable(
            entity: License, customer: str, tenant: str = None
    ):
        """
        Predicates whether a subject, such a customer or a tenant within
        said customer has access to provided license entity.

        Note: one must verify whether provided tenant belongs to the
        provided customer, beforehand.
        :parameter entity: License
        :parameter customer: str
        :parameter tenant: Optional[str]
        :return: bool
        """
        customers = entity.customers.as_dict()
        scope: dict = customers.get(customer, dict())

        model = scope.get(ATTACHMENT_MODEL_ATTR)
        tenants = scope.get(TENANTS_ATTR, [])
        retained, _all = tenant in tenants, not tenants
        attachment = (
            model == PERMITTED_ATTACHMENT and (retained or _all),
            model == PROHIBITED_ATTACHMENT and not (retained or _all)
        )
        return (not tenant) or (tenant and any(attachment)) if scope else False

    @staticmethod
    def is_expired(entity: License):
        return entity.expiration <= utc_iso()

    @staticmethod
    def update_license(license_obj: License, license_data: dict):
        allowance = AllowanceAttribute(**license_data.get('allowance'))

        license_obj.allowance = allowance
        license_obj.expiration = license_data.get('valid_until')
        license_obj.customers = license_data.get(CUSTOMERS_ATTR)
        license_obj.algorithm_mapping = license_data.get(
            ALGORITHM_MAPPING_ATTR)
        license_obj.latest_sync = utc_iso()
        license_obj.save()
        return license_obj

    @staticmethod
    def get_dto(license_: License):
        return license_.get_dto()

    @staticmethod
    def list_allowed_tenants(license_obj: License, customer: str):
        customer_map = license_obj.customers.get(customer)
        if not customer_map:
            return
        return list(customer_map.get(TENANTS_ATTR, []))
