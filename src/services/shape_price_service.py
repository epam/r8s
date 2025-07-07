from mongoengine import DoesNotExist, ValidationError, NotUniqueError

from commons.constants import CUSTOMER_ATTR, CLOUD_ATTR, NAME_ATTR, \
    REGION_ATTR, OS_ATTR
from models.shape_price import ShapePrice, DEFAULT_CUSTOMER, OSEnum


class ShapePriceService:

    @staticmethod
    def list(customer=None, cloud=None, name=None, region=None, os=None):
        query = {
            CLOUD_ATTR: cloud,
            NAME_ATTR: name,
            REGION_ATTR: region,
            OS_ATTR: os
        }
        if isinstance(customer, list):
            query[f'{CUSTOMER_ATTR}__in'] = customer
        else:
            query[CUSTOMER_ATTR] = customer
        query = {k: v for k, v in query.items() if v is not None}

        if query:
            return ShapePrice.objects(**query)
        return ShapePrice.objects.all()

    def get(self, customer, name, region, os=None,
            use_default_if_missing=True):
        if not os:
            os = OSEnum.OS_LINUX.value
        shape_price = self._get(customer=customer, name=name,
                                region=region, os=os)
        if shape_price:
            return shape_price
        if use_default_if_missing:
            return self._get(customer=DEFAULT_CUSTOMER, name=name,
                             region=region, os=os)

    @staticmethod
    def _get(customer, name, region, os):
        try:
            return ShapePrice.objects.get(customer=customer, name=name,
                                          region=region, os=os)
        except (DoesNotExist, ValidationError):
            return None

    @staticmethod
    def create(shape_price_data: dict) -> ShapePrice:
        return ShapePrice(**shape_price_data)

    @staticmethod
    def save(shape_price: ShapePrice):
        shape_price.save()

    @staticmethod
    def save_force(shape_price: ShapePrice):
        try:
            shape_price.save()
        except (NotUniqueError, ValidationError):
            old_price = ShapePrice.objects.get(
                name=shape_price.name,
                customer=shape_price.customer,
                region=shape_price.region,
                os=shape_price.os)
            old_price.delete()
            shape_price.save()

    @staticmethod
    def count(customer, cloud, count_default=True):
        cloud = cloud.upper()

        count = ShapePrice.objects(customer=customer,
                                   cloud=cloud).count()
        if count_default:
            default_count = ShapePrice.objects(customer=DEFAULT_CUSTOMER,
                                               cloud=cloud).count()
            count += default_count
        return count

    @staticmethod
    def delete(shape_price: ShapePrice):
        shape_price.delete()

    @staticmethod
    def get_dto(shape_price: ShapePrice):
        shape_price_data = shape_price.get_dto()
        shape_price_data.pop('reserved_1y', None)
        shape_price_data.pop('reserved_3y', None)
        shape_price_data.pop('dedicated', None)
        return shape_price_data
