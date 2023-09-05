import click

from r8s_group import cli_response, ViewCommand
from r8s_service.constants import AVAILABLE_CLOUDS


@click.group(name='licenses')
def licenses():
    """Manages RIGHTSIZER_LICENSES Parent Entity"""


@licenses.command(cls=ViewCommand, name='describe')
@click.option('--application_id', '-aid', type=str, required=False,
              help='Id of the application to describe parents.')
@click.option('--parent_id', '-pid', type=str, required=False,
              help='Parent id to describe.')
@cli_response()
def describe(application_id=None, parent_id=None):
    """
    Describes a RIGHTSIZER_LICENSES Parent.
    """
    from r8s_service.initializer import init_configuration
    return init_configuration().parent_licenses_get(
        application_id=application_id,
        parent_id=parent_id
    )


@licenses.command(cls=ViewCommand, name='add')
@click.option('--application_id', '-aid', type=str, required=True,
              help='Maestro application id to create Parent for.')
@click.option('--description', '-d', type=str, required=True,
              help='Parent description.')
@click.option('--cloud', '-c', type=click.Choice(AVAILABLE_CLOUDS),
              required=True, help='Parent cloud')
@click.option('--tenant_license_key', '-tlk', required=True, type=str,
              help=f'Tenant License Key.')
@cli_response()
def add(application_id, description, cloud, tenant_license_key):
    """
    Activates License for Tenants
    """
    from r8s_service.initializer import init_configuration
    return init_configuration().parent_licenses_post(
        application_id=application_id,
        description=description,
        cloud=cloud,
        tenant_license_key=tenant_license_key
    )


@licenses.command(cls=ViewCommand, name='delete')
@click.option('--parent_id', '-pid', type=str, required=True,
              help='Maestro Parent id to delete.')
@cli_response()
def delete(parent_id):
    """
    Deletes Maestro RIGHTSIZER_LICENSES Parent
    """
    from r8s_service.initializer import init_configuration

    return init_configuration().parent_licenses_delete(
        parent_id=parent_id
    )
