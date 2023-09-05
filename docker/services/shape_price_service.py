from mongoengine import DoesNotExist, ValidationError

from models.shape_price import ShapePrice, DEFAULT_CUSTOMER, OSEnum


class ShapePriceService:

    @staticmethod
    def list(cloud=None):
        if cloud:
            return ShapePrice.objects(cloud=cloud)
        return ShapePrice.objects.all()

    def get(self, customer, name, region, os=None):
        shape_price = self._get(customer=customer, name=name,
                                region=region, os=os)
        if shape_price:
            return shape_price
        return self._get(customer=DEFAULT_CUSTOMER, name=name,
                         region=region, os=os)

    @staticmethod
    def _get(customer, name, region, os):
        try:
            return ShapePrice.objects.get(customer=customer, name=name,
                                          region=region, os=os)
        except (DoesNotExist, ValidationError):
            return None
