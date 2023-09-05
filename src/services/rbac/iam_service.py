from mongoengine.errors import ValidationError, DoesNotExist

from models.policy import Policy
from models.role import Role


class IamService:
    @staticmethod
    def role_get(role_name):
        try:
            return Role.objects.get(name=role_name)
        except (DoesNotExist, ValidationError):
            return None

    @staticmethod
    def policy_get(policy_name: str):
        try:
            return Policy.objects.get(name=policy_name)
        except (DoesNotExist, ValidationError):
            return None

    @staticmethod
    def policy_batch_get(keys: list):
        return list(Policy.objects(name__in=keys))

    @staticmethod
    def role_batch_get(keys: list):
        return list(Role.objects(name__in=keys))

    @staticmethod
    def list_policies():
        return list(Policy.objects.all())

    @staticmethod
    def list_roles():
        return list(Role.objects.all())
