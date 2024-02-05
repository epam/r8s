import argparse
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from mongoengine import NotUniqueError

rds = boto3.client('rds')
ec2 = boto3.client('ec2')

ENGINES = [
    'aurora-mysql',
    'aurora-postgresql',
    'custom-oracle-ee',
    'db2-ae',
    'db2-se',
    'mariadb',
    'mysql',
    'oracle-ee',
    'oracle-ee-cdb',
    'oracle-se2',
    'oracle-se2-cdb',
    'postgres',
    'sqlserver-ee',
    'sqlserver-se',
    'sqlserver-ex',
    'sqlserver-web',
]


def parse_args():
    parser = argparse.ArgumentParser(
        description='Script for r8s AWS RDS Shape population')
    parser.add_argument('-ak', '--access_key', help='AWS Access Key',
                        required=True)
    parser.add_argument('-sk', '--secret_key', help='AWS Secret Access Key',
                        required=True)
    parser.add_argument('-t', '--session_token', help='AWS Session Token',
                        required=True)
    parser.add_argument('-r', '--region', help='AWS Region',
                        required=True)
    parser.add_argument('-uri', '--r8s_mongodb_connection_uri',
                        help='MongoDB Connection string', required=True)
    return vars(parser.parse_args())


def export_args(access_key, secret_key, session_token,
                region, r8s_mongodb_connection_uri, *args, **kwargs):
    os.environ['AWS_ACCESS_KEY_ID'] = access_key
    os.environ['AWS_SECRET_ACCESS_KEY'] = secret_key
    os.environ['AWS_SESSION_TOKEN'] = session_token
    os.environ['AWS_DEFAULT_REGION'] = region
    os.environ['AWS_REGION'] = region
    os.environ['r8s_mongodb_connection_uri'] = r8s_mongodb_connection_uri


def export_src_path():
    dir_path = Path(os.path.dirname(os.path.realpath(__file__))).parent
    src_path = os.path.join(dir_path, 'src')
    sys.path.append(src_path)


def build_shape_map():
    from services import SERVICE_PROVIDER
    from services.shape_service import ShapeService

    shape_service: ShapeService = SERVICE_PROVIDER.shape_service()

    aws_shapes = shape_service.list('AWS')

    return {shape.name: shape for shape in aws_shapes}


def get_rds_types(engine):
    print(f'Querying {engine} engine instance types')
    result = []
    try:
        response = rds.describe_orderable_db_instance_options(
            Engine=engine,
            LicenseModel='general-public-license'
        )
        marker = response.get('Marker')
        request_options = response.get('OrderableDBInstanceOptions', [])
    except ClientError as e:
        print(e)
        return []
    while request_options and marker:
        for option in request_options:
            result.append(option)
        response = rds.describe_orderable_db_instance_options(
            Engine=engine,
            LicenseModel='general-public-license',
            Marker=marker)
        marker = response.get('Marker')
        request_options = response.get('OrderableDBInstanceOptions', [])
    return result


def add_vm_specs(shapes_data: list[dict], shape_map: dict):
    from services import SERVICE_PROVIDER
    from models.shape import ResourceTypeEnum
    shape_service = SERVICE_PROVIDER.shape_service()

    result = []
    for shape_data in shapes_data:
        instance_type = shape_data.get('name')
        instance_type_ec2 = instance_type.replace('db.', '')

        shape = shape_map.get(instance_type_ec2)

        if shape:
            vm_dto = shape_service.get_dto(shape)

            result_item = vm_dto.copy()
            result_item.update(shape_data)
            result_item[
                'resource_type'] = ResourceTypeEnum.RESOURCE_TYPE_RDS.value
            result_item['name'] = instance_type

            result.append(result_item)
        else:
            print(f'No ec2 shape specs available for {instance_type_ec2}')
    return result


def populate_shapes(shapes_data):
    from models.shape import Shape
    for shape_data in shapes_data:
        shape_obj = Shape(**shape_data)
        try:
            shape_obj.save()
            print(f"Shape {shape_obj.name} saved")
        except NotUniqueError:
            print(f"Shape {shape_obj.name} already exist, rewriting")
            old_shape = Shape.objects.get(name=shape_obj.name)
            old_shape.delete()
            shape_obj.save()


def to_shape_data(data: list):
    result = {}

    for item in data:
        instance_type = item['DBInstanceClass']
        if instance_type not in result:
            result[instance_type] = {
                'name': instance_type,
                'engines': [item['Engine']],
                'storage_types': [item['StorageType']]
            }
        else:
            current_item = result[instance_type]
            engine = item['Engine']
            if engine not in current_item['engines']:
                current_item['engines'].append(engine)
            storage_type = item['StorageType']
            if storage_type not in current_item['storage_types']:
                current_item['storage_types'].append(storage_type)
    return list(result.values())


def main():
    print("Parsing arguments")
    args = parse_args()

    print('Exporting path to src')
    export_src_path()

    print('Exporting env variables')
    export_args(**args)

    print('Building shape map')
    shape_map = build_shape_map()

    data = []
    for engine in ENGINES:
        engine_data = get_rds_types(engine=engine)
        data.extend(engine_data)

    print('Aggregating obtained results')
    shapes_data = to_shape_data(data=data)

    print('Adding vm specs')
    shapes_data = add_vm_specs(shapes_data=shapes_data,
                               shape_map=shape_map)

    print('Saving to db')
    populate_shapes(shapes_data=shapes_data)


if __name__ == '__main__':
    main()
