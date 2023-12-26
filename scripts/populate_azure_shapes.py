import argparse
import concurrent
import concurrent.futures
import os
import sys
from pathlib import Path

import requests

dir_path = Path(os.path.dirname(os.path.realpath(__file__))).parent
src_path = os.path.join(dir_path, 'src')
sys.path.append(src_path)

from commons.log_helper import get_logger

_LOG = get_logger('populate-azure-prices')

AZURE_REGIONS = [
    "eastasia",
    "southeastasia",
    "centralus",
    "eastus",
    "eastus2",
    "westus",
    "northcentralus",
    "southcentralus",
    "northeurope",
    "westeurope",
    "japanwest",
    "japaneast",
    "brazilsouth",
    "australiaeast",
    "australiasoutheast",
    "southindia",
    "centralindia",
    "westindia",
    "canadacentral",
    "canadaeast",
    "uksouth",
    "ukwest",
    "westcentralus",
    "westus2",
    "koreacentral",
    "koreasouth",
    "francecentral",
    "francesouth",
    "australiacentral",
    "australiacentral2",
    "uaecentral",
    "uaenorth",
    "southafricanorth",
    "southafricawest"
]
ACTION_PRICE = 'PRICE'
ACTION_SHAPE = 'SHAPE'
DEFAULT_CONCURRENT_WORKERS = 7


def parse_args():
    parser = argparse.ArgumentParser(
        description='Script for r8s AWS Shape/Shape Price '
                    'collections population')
    parser.add_argument('-uri', '--r8s_mongodb_connection_uri',
                        help='MongoDB Connection string', required=True)
    parser.add_argument('--action', choices=['SHAPE', 'PRICE'],
                        required=True, action='append',
                        help='Determines whether Shape Specs or '
                             'pricing data will be parsed.')
    parser.add_argument('-acid', '--AZURE_CLIENT_ID',
                        help='AZURE Client id. Required for \'SHAPE\' action',
                        required=False)
    parser.add_argument('-atid', '--AZURE_TENANT_ID',
                        help='AZURE Tenant id. Required for \'SHAPE\' action',
                        required=False)
    parser.add_argument('-acs', '--AZURE_CLIENT_SECRET',
                        help='AZURE Client secret. Required for \'SHAPE\' action',
                        required=False)
    parser.add_argument('-asid', '--AZURE_SUBSCRIPTION_ID',
                        help='AZURE Subscription id. Required for \'SHAPE\' action',
                        required=False)
    parser.add_argument('-pr', '--price_region', action='append',
                        required=False, default=AZURE_REGIONS,
                        help='List of AWS regions to populate price for. '
                             'If not specified, all Azure regions will '
                             'be parsed. Required for \'PRICE\' action')
    parser.add_argument('-cw', '--concurrent_workers', type=int,
                        help='Number of concurrent workers for price parsing',
                        required=False, default=DEFAULT_CONCURRENT_WORKERS)
    return dict(vars(parser.parse_args()))


def export_args(**kwargs):
    for key, value in kwargs.items():
        if isinstance(value, str):
            os.environ[key] = value


def get_virtual_machine_info():
    from azure.identity import EnvironmentCredential
    from azure.mgmt.compute import ComputeManagementClient

    subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')

    if not subscription_id:
        _LOG.error('Missing request AZURE_SUBSCRIPTION_ID env')
        sys.exit(1)

    _LOG.debug('Initializing Azure Credentials')
    client = ComputeManagementClient(
        credential=EnvironmentCredential(),
        subscription_id=subscription_id,
    )
    result = []
    _LOG.debug(f'Querying for Azure VM data')
    response = client.resource_skus.list()
    if not response:
        _LOG.warning('Failed to obtain vms info.')
        sys.exit(1)
    for index, item in enumerate(response):
        result.append(item)
    return [item for item in result if item.resource_type == 'virtualMachines']


def populate_shapes():
    from models.shape import Shape
    from mongoengine import NotUniqueError
    _LOG.debug(f'Loading VM Info')
    virtual_machine_info = get_virtual_machine_info()

    _LOG.debug(f'Removing duplicated vm data')
    virtual_machine_info_unique = get_unique_by_name(virtual_machine_info)
    for index, virtual_machine in enumerate(virtual_machine_info_unique):
        _LOG.debug(
            f'Processing {index}/{len(virtual_machine_info_unique)} shape')
        shape = get_shape_data(resource=virtual_machine)
        try:
            shape.save()
            _LOG.debug(f'Shape \'{shape.name}\' has been saved')
        except NotUniqueError:
            _LOG.debug(f'Shape \'{shape.name}\' already exist, replacing.')
            old_shape = Shape.objects.get(name=shape.name)
            old_shape.delete()
            shape.save()


def populate_prices(region, connection_uri):
    os.environ['r8s_mongodb_connection_uri'] = connection_uri
    _LOG.debug(f'Querying for Azure VM Pricing data for region: {region}')
    url = f"https://prices.azure.com/api/retail/prices?$filter=serviceName " \
          f"eq 'Virtual Machines' and priceType eq 'Consumption' and armRegionName eq '{region}'"

    _LOG.debug(f'Processing page 1 for region: {region}')
    response = requests.get(url)
    response = response.json()

    items = response.get('Items')
    items_saved = create_prices(items=items)
    page_count = 1
    while response.get('NextPageLink'):
        page_count += 1
        _LOG.debug(
            f'Processing page {page_count} for region: {region}. '
            f'Region items saved: {items_saved}')
        response = requests.get(response.get('NextPageLink'))
        response = response.json()
        items = response.get('Items')
        items_saved += create_prices(items=items)


def create_prices(items):
    from models.shape_price import ShapePrice
    from mongoengine import NotUniqueError
    filtered_items = []

    for item in items:
        if "Spot" in item.get('skuName'):
            continue
        if "Low Priority" in item.get('meterName'):
            continue
        filtered_items.append(item)

    for item in filtered_items:
        price = get_shape_price(resource=item)
        try:
            price.save()
        except NotUniqueError:
            _LOG.debug(f'Shape Price \'{price.name}\' already exist in '
                       f'region {price.region}, replacing.')
            old_price = ShapePrice.objects.get(name=price.name,
                                               customer=price.customer,
                                               region=price.region,
                                               os=price.os)
            if old_price.on_demand != price.on_demand:
                old_price.on_demand = price.on_demand
                old_price.save()
    return len(filtered_items)


def get_shape_price(resource: dict):
    from models.shape_price import ShapePrice, OSEnum
    from models.base_model import CloudEnum

    is_windows = 'Windows' in resource.get('productName')
    os_ = OSEnum.OS_WINDOWS if is_windows else OSEnum.OS_LINUX

    return ShapePrice(
        customer="DEFAULT",
        cloud=CloudEnum.CLOUD_AZURE.value,
        name=resource.get('armSkuName'),
        region=resource.get('armRegionName'),
        os=os_.value,
        on_demand=resource.get('unitPrice')
    )


def run_populate_prices(regions: list, workers: int, connection_uri: str):
    _LOG.debug(f'Populating Azure Prices data')
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) \
            as executor:
        futures = []
        for region in regions:
            futures.append(
                executor.submit(populate_prices,
                                region=region,
                                connection_uri=connection_uri))
        for future in concurrent.futures.as_completed(futures):
            _LOG.debug(f"Thread finished: {future.result()}")


def get_unique_by_name(resources: list):
    names = []
    result = []
    for resource in resources:
        if resource.name not in names:
            names.append(resource.name)
            result.append(resource)
    return result


def get_shape_data(resource):
    from models.shape import Shape
    from models.base_model import CloudEnum
    capabilities = {item.name: item.value for item in resource.capabilities}

    return Shape(
        name=resource.name,
        cloud=CloudEnum.CLOUD_AZURE.value,
        cpu=float(capabilities.get('vCPUs')),
        memory=float(capabilities.get('MemoryGB')),
        family_type=resource.family,
        architecture=capabilities.get('CpuArchitectureType')
    )


def update_last_update_date():
    from services.setting_service import SettingsService
    from models.base_model import CloudEnum

    setting_service = SettingsService()

    setting = setting_service.update_shape_update_date(
        cloud=CloudEnum.CLOUD_AZURE.value
    )
    print(f"Updated setting: {setting.value}")


def main():
    _LOG.info("Parsing arguments")
    parameters = parse_args()

    _LOG.info('Exporting env variables')
    export_args(**parameters)

    allowed_actions = parameters.get('action')
    if ACTION_SHAPE in allowed_actions:
        _LOG.info('Populating shapes')
        populate_shapes()

    if ACTION_PRICE in allowed_actions:
        _LOG.info('Populating Prices')
        run_populate_prices(
            regions=parameters.get('price_region',
                                   AZURE_REGIONS),
            workers=parameters.get('concurrent_workers',
                                   DEFAULT_CONCURRENT_WORKERS),
            connection_uri=parameters.get('r8s_mongodb_connection_uri')
        )
    update_last_update_date()


if __name__ == "__main__":
    main()
