import argparse
import concurrent
import concurrent.futures
import os
import sys
from pathlib import Path

import requests
from mongoengine import DoesNotExist

dir_path = Path(os.path.dirname(os.path.realpath(__file__))).parent
src_path = os.path.join(dir_path, 'src')
sys.path.append(src_path)
from commons.log_helper import get_logger

_LOG = get_logger('scripts-populate-gcp-shapes')

INFRACOST_API_URL = 'https://pricing.api.infracost.io/graphql'

ZONES = [
    'us-east1-b',
    'us-east1-c',
    'us-east1-d',
    'us-east4-c',
    'us-east4-b',
    'us-east4-a',
    'us-central1-c',
    'us-central1-a',
    'us-central1-f',
    'us-central1-b',
    'us-west1-b',
    'us-west1-c',
    'us-west1-a',
]

QUERY_TEMPLATE = \
    """{
      products(
        filter: {
          vendorName: "gcp",
          service: "Compute Engine",
          productFamily: "Compute Instance",
          region: "%s",
          attributeFilters: [
          ]
        },
      ) {
        attributes { key, value }
        prices(
          filter: {
            purchaseOption: "on_demand"
          },
        ) { USD }
      }
    }
    """

GCP_REGIONS = ["us-west1", "us-west2", "us-west3", "us-west4", "us-central1",
               "us-east1", "us-east4", "northamerica-northeast1",
               "southamerica-east1", "europe-west2", "europe-west1",
               "europe-west4", "europe-west6", "europe-west3", "europe-north1",
               "asia-south1", "asia-southeast1", "asia-southeast2",
               "asia-east2", "asia-east1", "asia-northeast1",
               "asia-northeast2", "australia-southeast1", "asia-northeast3"]

ACTION_PRICE = 'PRICE'
ACTION_SHAPE = 'SHAPE'
DEFAULT_CONCURRENT_WORKERS = 7


def parse_args():
    parser = argparse.ArgumentParser(
        description='Script for r8s GCP Shape/Shape Price '
                    'collections population')
    parser.add_argument('-uri', '--r8s_mongodb_connection_uri',
                        help='MongoDB Connection string', required=True)
    parser.add_argument('--action', choices=['SHAPE', 'PRICE'],
                        required=True, action='append',
                        help='Determines whether Shape Specs or '
                             'pricing data will be parsed.')
    parser.add_argument('-gac', '--GOOGLE_APPLICATION_CREDENTIALS',
                        help='Absolute path to Google application credentials '
                             'file. Required for SHAPE action',
                        required=False)
    parser.add_argument('-token', '--infracost_api_key',
                        help='Infracost API token used to query instance '
                             'prices. Required for PRICE action',
                        required=False)
    parser.add_argument('-pr', '--price_region', action='append',
                        required=False, default=GCP_REGIONS,
                        help='List of GCP regions to populate price for. '
                             'If not specified, all GCP regions will '
                             'be parsed. Required for \'PRICE\' action')
    parser.add_argument('-cw', '--concurrent_workers', type=int,
                        help='Number of concurrent workers for price parsing',
                        required=False, default=DEFAULT_CONCURRENT_WORKERS)
    return dict(vars(parser.parse_args()))


def export_args(**kwargs):
    for key, value in kwargs.items():
        if isinstance(value, str):
            os.environ[key] = value


def create_shapes_for_zone(zone):
    import google.auth
    from googleapiclient import discovery
    from models.shape import Shape, CloudEnum

    _LOG.debug(f'Initializing GCP credentials')
    credentials, project = google.auth.default()
    service = discovery.build('compute', 'v1', credentials=credentials)

    _LOG.debug(f'Updating shapes, using zone \'{zone}\'')
    created_count = 0
    request = service.machineTypes().list(project=project, zone=zone)
    while request is not None:
        response = request.execute()

        for index, machine_type in enumerate(response['items']):
            _LOG.debug(f'Processing {index}/{len(response["items"])}')
            machine_type_name = machine_type.get('name')
            machine_type_cpu = machine_type.get('guestCpus')
            machine_type_ram = machine_type.get('memoryMb') // 1024

            try:
                Shape.objects.get(name=machine_type_name)
            except DoesNotExist:
                _LOG.debug(
                    f'Shape \'{machine_type_name}\' does not exist yet, '
                    f'creating.')
                shape = Shape(
                    name=machine_type_name,
                    cloud=CloudEnum.CLOUD_GOOGLE,
                    cpu=machine_type_cpu,
                    memory=machine_type_ram,
                    family_type=get_family_type(machine_type_name)
                )
                shape.save()
                created_count += 1

        request = service.machineTypes().list_next(previous_request=request,
                                                   previous_response=response)
    _LOG.debug(f'Created shapes for zone \'{zone}\': {created_count}')


def get_family_type(machine_type_name):
    name_type_mapping = {
        "c2": "Compute-optimized",
        "c2d": "Compute-optimized",
        "m1": "Memory-optimized",
        "m2": "Memory-optimized",
        "m3": "Memory-optimized",
        "a2": "Accelerator-optimized",
        "g2": "Accelerator-optimized"
    }
    default = 'General-purpose workloads'

    for key in name_type_mapping.keys():
        if machine_type_name.startswith(key):
            return name_type_mapping.get(key)
    return default


def create_prices(region, connection_uri, api_key):
    os.environ['r8s_mongodb_connection_uri'] = connection_uri
    response = requests.post(
        url=INFRACOST_API_URL,
        json={"query": QUERY_TEMPLATE % region},
        headers={'x-api-key': api_key}
    )
    if not response.status_code == 200:
        _LOG.error(f'Unsuccessful response from Infracost obtained. Status: '
                   f'{response.status_code}. Content: {response.content}')
        return
    products = response.json().get('data', {}).get('products', [])
    processed_count = 0
    for product in products:
        product_name = get_product_name(product_data=product)
        product_price = get_product_price(product_data=product,
                                          product_name=product_name)
        if product_name and product_price:
            shape_price = create_shape_price(
                product_name=product_name,
                product_price=product_price,
                region=region
            )
            if shape_price:
                processed_count += 1
    _LOG.debug(f'Processed {processed_count} prices for region {region}')


def run_populate_prices(regions: list, workers: int, connection_uri: str,
                        api_key: str):
    _LOG.debug(f'Populating GCP Prices data')
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) \
            as executor:
        futures = []
        for region in regions:
            futures.append(
                executor.submit(create_prices,
                                region=region,
                                api_key=api_key,
                                connection_uri=connection_uri))
        for future in concurrent.futures.as_completed(futures):
            _LOG.debug(f"Thread finished: {future.result()}")


def create_shape_price(product_name, product_price, region):
    from models.shape_price import ShapePrice
    from models.shape import CloudEnum
    from mongoengine import NotUniqueError
    try:
        shape_price = ShapePrice(
            customer="DEFAULT",
            cloud=CloudEnum.CLOUD_GOOGLE.value,
            name=product_name,
            region=region,
            on_demand=product_price
        )
        shape_price.save()
        _LOG.debug(f'{product_name}:{region} Saved')
        return shape_price
    except NotUniqueError:
        _LOG.debug(f'Shape price \'{product_name}\' already exist, replacing.')
        old_shape = ShapePrice.objects.get(
            name=product_name,
            customer='DEFAULT',
            region=region)
        if old_shape.on_demand != product_price:
            old_shape.on_demand = product_price
            old_shape.save()
            _LOG.debug(f'{product_name}:{region} Updated')
        return old_shape


def get_product_name(product_data):
    attributes = product_data.get('attributes', [])
    for attribute in attributes:
        if attribute.get('key') == 'machineType':
            return attribute.get('value')


def get_product_price(product_data, product_name):
    prices = product_data.get('prices')
    if len(prices) > 1:
        _LOG.warning(f'Several prices obtained for product \'{product_name}\'')
    for price in prices:
        return float(price.get('USD'))


def update_last_update_date():
    from services.setting_service import SettingsService
    from models.base_model import CloudEnum

    setting_service = SettingsService()

    setting = setting_service.update_shape_update_date(
        cloud=CloudEnum.CLOUD_GOOGLE.value
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
        for index, zone in enumerate(ZONES):
            _LOG.info(f'Processing {index+1}/{len(ZONES)} zone: {zone}')
            create_shapes_for_zone(
                zone=zone
            )

    if ACTION_PRICE in allowed_actions:
        _LOG.info('Populating Prices')
        run_populate_prices(
            regions=parameters.get('price_region',
                                   GCP_REGIONS),
            workers=parameters.get('concurrent_workers',
                                   DEFAULT_CONCURRENT_WORKERS),
            connection_uri=parameters.get('r8s_mongodb_connection_uri'),
            api_key=parameters.get('infracost_api_key')
        )
    update_last_update_date()


if __name__ == '__main__':
    main()
