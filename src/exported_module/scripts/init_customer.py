import argparse

from typing import Optional, List
from commons.log_helper import get_logger

from modular_sdk.modular import Modular
from modular_sdk.models.customer import Customer
from modular_sdk.models.tenant import Tenant

_LOG = get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Script for r8s Customer/tenant creation')
    parser.add_argument('-name', '--customer_name',
                        help='AWS MP Customer name',
                        required=True)

    return vars(parser.parse_args())


def create_customer(customer_name: str,
                    admins: Optional[List[str]] = None):
    """
    Creates a customer with given params. Is the customer already exists,
    the creation will be skipped, no attributes will be changed.
    """
    _service = Modular().customer_service()
    if _service.get(customer_name):
        _LOG.warning(f"\'{customer_name}'\' customer already "
                     f"exists. His attributes won`t be changed")
        return
    customer = Customer(
        name=customer_name,
        display_name=customer_name.title().replace('_', ' '),
        admins=admins or []
    )
    customer.save()
    _LOG.info(f'Customer "{customer_name}" created.')


def create_tenant(customer_name: str, tenant_name: str):
    _service = Modular().tenant_service()
    if _service.get(tenant_name):
        _LOG.warning(f"\'{tenant_name}'\' tenant already "
                     f"exists. His attributes won`t be changed")
        return
    display_name = tenant_name.title().replace('_', ' ')
    tenant = Tenant(
        name=tenant_name,
        display_name=display_name,
        display_name_to_lower=display_name.lower(),
        is_active=True,
        customer_name=customer_name,
        cloud='AWS'
    )
    tenant.save()
    _LOG.info(f'Tenant "{tenant_name}" created.')


def main():
    args = parse_args()
    customer_name = args['customer_name']
    create_customer(customer_name)
    if customer_name.startswith('Marketplace '):
        tenant_name = customer_name.split()[1].strip()
        create_tenant(customer_name, tenant_name)


if __name__ == '__main__':
    main()
