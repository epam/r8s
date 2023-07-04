from mongoengine import DoesNotExist, ValidationError

from models.shape import Shape


class ShapeService:

    @staticmethod
    def list(cloud=None):
        if cloud:
            return Shape.objects(cloud=cloud)
        return Shape.objects.all()

    @staticmethod
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
