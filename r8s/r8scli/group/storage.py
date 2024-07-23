import click

from r8scli.group import cli_response, ViewCommand
from r8scli.service.constants import TYPE_DATASOURCE, \
    TYPE_STORAGE, SERVICE_S3_BUCKET, PARAM_BUCKET_NAME, PARAM_PREFIX


@click.group(name='storage')
def storage():
    """Manages storage entity"""


@storage.command(cls=ViewCommand, name='describe')
@click.option('--storage_name', '-name', type=str,
              help='Storage name to describe.')
@cli_response()
def describe(storage_name=None):
    """
    Describes a R8s storage.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().storage_get(storage_name=storage_name)


@storage.command(cls=ViewCommand, name='add')
@click.option('--storage_name', '-name', type=str, required=True,
              help='Storage name to create.')
@click.option('--type', '-type',
              type=click.Choice((TYPE_DATASOURCE, TYPE_STORAGE)),
              required=True, help='Type of the r8s storage.')
@click.option('--bucket_name', '-bname', type=str, required=True,
              help='S3 bucket name.')
@click.option('--prefix', '-p', type=str,
              help='S3 bucket prefix.')
@cli_response()
def add(storage_name, type, bucket_name, prefix=None):
    """
    Creates a R8s S3 storage.
    """
    from r8scli.service.initializer import init_configuration
    access = {
        PARAM_BUCKET_NAME: bucket_name,
    }
    if prefix:
        access[PARAM_PREFIX] = prefix
    return init_configuration().storage_post(
        storage_name=storage_name,
        service=SERVICE_S3_BUCKET,
        type=type,
        access=access
    )


@storage.command(cls=ViewCommand, name='update')
@click.option('--storage_name', '-name', type=str, required=True,
              help='Storage name to create.')
@click.option('--type', '-type',
              type=click.Choice((TYPE_DATASOURCE, TYPE_STORAGE)),
              help='Type of the r8s storage.')
@click.option('--bucket_name', '-bname', type=str,
              help='S3 bucket name.')
@click.option('--prefix', '-bname', type=str,
              help='S3 bucket prefix.')
@cli_response()
def update(storage_name, type, bucket_name, prefix=None):
    """
    Updates a R8s S3 storage.
    """
    from r8scli.service.initializer import init_configuration
    access = {}
    if bucket_name:
        access[PARAM_BUCKET_NAME]: bucket_name
    if prefix:
        access[PARAM_PREFIX] = prefix
    return init_configuration().storage_patch(
        storage_name=storage_name,
        type=type,
        access=access
    )


@storage.command(cls=ViewCommand, name='delete')
@click.option('--storage_name', '-name', type=str,
              help='Storage name to delete.')
@cli_response()
def delete(storage_name):
    """
    Removes a R8s storage.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().storage_delete(storage_name=storage_name)


@storage.command(cls=ViewCommand, name='describe_metrics')
@click.option('--data_source_name', '-name', type=str, required=True,
              help='Data source name to describe metrics.')
@click.option('--tenant', '-t', required=True,
              help='Tenant metrics to describe.')
@click.option('--region', '-r', required=False,
              help='Describe only metrics for region (native name).')
@click.option('--timestamp', '-ts', required=False,
              help='Describe only metrics for timestamp.')
@click.option('--instance_id', '-id', required=False,
              help='Describe only metrics for instance.')
@click.option('--customer_id', '-cid', type=str, required=False,
              help='Describe metrics of specific customer (admin users only)')
@cli_response()
def describe_metrics(data_source_name, tenant, region=None, timestamp=None,
                     instance_id=None, customer_id=None):
    """
    Describes metric files from data source.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().storage_describe_metrics(
        data_source_name=data_source_name, region=region,
        tenant=tenant, timestamp=timestamp, instance_id=instance_id,
        customer=customer_id, )
