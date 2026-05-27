from mongoengine.errors import ValidationError, DoesNotExist

from models.policy import Policy
from models.role import Role


class IamService:
    @staticmethod
    def role_get(role_name: str, customer: str = None) -> Role | None:
        try:
            kwargs = {'name': role_name}
            if customer:
                kwargs['customer'] = customer
            return Role.objects.get(**kwargs)
        except (DoesNotExist, ValidationError):
            return None

    @staticmethod
    def policy_get(policy_name: str, customer: str = None) -> Policy | None:
        try:
            kwargs = {'name': policy_name}
            if customer:
                kwargs['customer'] = customer
            return Policy.objects.get(**kwargs)
        except (DoesNotExist, ValidationError):
            return None

    @staticmethod
    def policy_batch_get(keys: list, customer: str = None) -> list:
        kwargs = {'name__in': keys}
        if customer and customer != 'admin':
            kwargs['customer'] = customer
        return list(Policy.objects(**kwargs))

    @staticmethod
    def role_batch_get(keys: list, customer: str = None) -> list:
        kwargs = {'name__in': keys}
        if customer and customer != 'admin':
            kwargs['customer'] = customer
        return list(Role.objects(**kwargs))

    @staticmethod
    def list_policies(customer: str = None) -> list:
        if customer:
            return list(Policy.objects(customer=customer))
        return list(Policy.objects.all())

    @staticmethod
    def list_roles(customer: str = None) -> list:
        if customer:
            return list(Role.objects(customer=customer))
        return list(Role.objects.all())
