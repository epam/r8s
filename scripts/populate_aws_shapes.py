import argparse
import json
import os
import sys
from pathlib import Path

ALLOWED_REGIONS = ['us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
                   'ca-central-1', 'eu-west-1', 'eu-central-1', 'eu-west-2',
                   'eu-west-3', 'eu-north-1', 'ap-northeast-1',
                   'ap-northeast-2', 'ap-southeast-1', 'ap-southeast-2',
                   'ap-south-1', 'sa-east-1']
ALLOWED_OS = ['Linux', 'Windows']


def parse_args():
    parser = argparse.ArgumentParser(
        description='Script for r8s Shape/Shape Price '
                    'collections population')
    parser.add_argument('-ak', '--access_key', help='AWS Access Key',
                        required=False)
    parser.add_argument('-sk', '--secret_key', help='AWS Secret Access Key',
                        required=False)
    parser.add_argument('-t', '--session_token', help='AWS Session Token',
                        required=False)
    parser.add_argument('-r', '--region', help='AWS Region',
                        required=False, choices=ALLOWED_REGIONS, default='eu-central-1')
    parser.add_argument('-uri', '--r8s_mongodb_connection_uri',
                        help='MongoDB Connection string', required=False)
    parser.add_argument('-pr', '--price_region', action='append',
                        required=False, choices=ALLOWED_REGIONS,
                        default=ALLOWED_REGIONS,
                        help='List of AWS regions to populate price for')
    parser.add_argument('-os', '--operating_system', action='append',
                        required=False, choices=ALLOWED_OS, default=ALLOWED_OS,
                        help='List of AWS operation systems '
                             'to populate price for')
    args = vars(parser.parse_args())
    if not args.get('price_region'):
        args['price_region'] = ALLOWED_REGIONS
    if not args.get('operating_system'):
        args['operating_system'] = ALLOWED_OS
    return args


def export_args(access_key, secret_key, session_token,
                region, r8s_mongodb_connection_uri, *args, **kwargs):
    if access_key and secret_key:
        os.environ['AWS_ACCESS_KEY_ID'] = access_key
        os.environ['AWS_SECRET_ACCESS_KEY'] = secret_key
    if session_token:
        os.environ['AWS_SESSION_TOKEN'] = session_token
    os.environ['AWS_DEFAULT_REGION'] = region
    os.environ['AWS_REGION'] = region
    if r8s_mongodb_connection_uri:
        os.environ['r8s_mongodb_connection_uri'] = r8s_mongodb_connection_uri


def export_src_path():
    dir_path = Path(os.path.dirname(os.path.realpath(__file__))).parent
    src_path = os.path.join(dir_path, 'src')
    sys.path.append(src_path)


def load_local_json_file(file_name):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(dir_path, file_name)

    if not os.path.exists(file_path):
        print(f"File \'{file_path}\' does not exist")
        sys.exit(1)

    with open(file_path, 'r') as f:
        return json.load(f)


def populate_shapes(shapes_data):
    from mongoengine import NotUniqueError
    from models.shape import Shape

    shape_mapping = {k['name']: k for k in shapes_data}

    for shape_name, shape_data in shape_mapping.items():
        print(f'Processing shape: {shape_name}')

        if shape_name.startswith('db.'):
            resource_type = 'RDS'
        else:
            resource_type = 'VM'

        shape_obj_data = {
            'name': shape_name,
            'resource_type': resource_type,
            'cloud': shape_data.get('cloud'),
            'cpu': shape_data.get('cpu'),
            'memory': shape_data.get('memory'),
            'network_throughput': shape_data.get('network_throughput'),
            'iops': shape_data.get('iops'),
            'family_type': shape_data.get('family_type'),
            'physical_processor': shape_data.get('physical_processor'),
            'architecture': shape_data.get('architecture'),
        }
        shape_obj = Shape(**shape_obj_data)
        try:
            shape_obj.save()
        except NotUniqueError:
            print(f"Shape {shape_obj.name} already exist, rewriting")
            old_shape = Shape.objects.get(name=shape_name)
            old_shape.delete()
            shape_obj.save()


def populate_prices(os_list, region_list, customer):
    import boto3

    client = boto3.client('pricing', region_name='us-east-1')
    paginator = client.get_paginator('get_products')

    for region in region_list:
        for os_ in os_list:
            print(f'Processing region: {region}, os: {os_}')
            items = _populate_prices(paginator=paginator, customer=customer,
                                     os=os_, region=region)
            print(f'Saved \'{len(items)}\' prices for region \'{region}\', '
                  f'os: {os_}')


def _populate_prices(paginator, customer, os, region):
    from mongoengine import NotUniqueError
    from models.shape_price import ShapePrice
    from models.base_model import CloudEnum
    pages = paginator.paginate(ServiceCode='AmazonEC2', Filters=[
        {'Type': 'TERM_MATCH', 'Field': 'operatingSystem',
         'Value': os},
        {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'},
        {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
        {'Type': 'TERM_MATCH', 'Field': 'regionCode',
         'Value': region},
        {'Type': 'TERM_MATCH', 'Field': 'capacityStatus', 'Value': 'Used'},
        {'Type': 'TERM_MATCH', 'Field': 'serviceCode', 'Value': 'AmazonEC2'},
        {'Type': 'TERM_MATCH', 'Field': 'licenseModel',
         'Value': 'No License required'},
    ])

    entries = []
    for page in pages:
        entries.extend(page['PriceList'])
    result = []
    for entry in entries:
        obj = json.loads(entry)

        attributes = obj.get("product", {}).get('attributes', {})

        if not attributes:
            continue
        instance_type = attributes.get('instanceType')
        instance_region = attributes.get('regionCode')
        instance_os = attributes.get('operatingSystem')

        on_demand = obj.get('terms', {}).get('OnDemand')
        if not on_demand:
            continue
        # extract value by unknown dict key
        first_key = list(on_demand)[0]
        price_dimensions = on_demand[first_key]['priceDimensions']

        # extract value by unknown dict key
        first_key = list(price_dimensions)[0]
        price_per_unit = price_dimensions[first_key][
            'pricePerUnit']['USD']
        price_per_unit = float(price_per_unit)
        if price_per_unit == 0:
            continue

        price_item = ShapePrice(
            customer=customer,
            cloud=CloudEnum.CLOUD_AWS.value,
            name=instance_type,
            region=instance_region,
            os=instance_os.upper(),
            on_demand=price_per_unit
        )
        try:
            price_item.save()
        except NotUniqueError:
            print(f"Price {price_item.name} already exist, rewriting")
            old_price = ShapePrice.objects.get(name=price_item.name,
                                               customer=price_item.customer,
                                               region=price_item.region,
                                               os=price_item.os)
            old_price.delete()
            price_item.save()
        result.append(price_item)
    return result


def update_last_update_date():
    from services.setting_service import SettingsService
    from models.base_model import CloudEnum

    setting_service = SettingsService()

    setting = setting_service.update_shape_update_date(
        cloud=CloudEnum.CLOUD_AWS.value
    )
    print(f"Updated setting: {setting.value}")


def main():
    print("Parsing arguments")
    args = parse_args()

    print('Exporting path to src')
    export_src_path()

    print('Exporting env variables')
    export_args(**args)

    print('Loading shapes data')
    shapes_data = load_local_json_file(file_name='aws_instances_data.json')

    print('Populating Shapes')
    populate_shapes(shapes_data=shapes_data)

    print('Populating Shape Prices')
    populate_prices(os_list=args['operating_system'],
                    region_list=args['price_region'],
                    customer='DEFAULT')

    print("Updating \'LAST_SHAPE_UPDATE\' setting.")
    update_last_update_date()


if __name__ == '__main__':
    main()
