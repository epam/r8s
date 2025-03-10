from mongoengine import DoesNotExist, ValidationError

from models.shape import Shape
from functools import lru_cache


class ShapeService:

    @staticmethod
    def list(cloud=None, resource_type=None):
        query = {}
        if cloud:
            query['cloud'] = cloud
        if resource_type:
            query['resource_type'] = resource_type
        if query:
            return Shape.objects(**query)
        return Shape.objects.all()

    @staticmethod
    @lru_cache(maxsize=256)
    def get(name):
        try:
            return Shape.objects.get(name=name)
        except (DoesNotExist, ValidationError):
            return None

    @staticmethod
    def create(shape_data):
        return Shape(**shape_data)

    @staticmethod
    def save(shape: Shape):
        shape.save()

    @staticmethod
    def delete(shape: Shape):
        shape.delete()
