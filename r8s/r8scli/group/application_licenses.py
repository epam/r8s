import click

from r8scli.group import cli_response, ViewCommand
from r8scli.service.constants import ALLOWED_PROTOCOLS, \
    PROTOCOL_HTTPS, AVAILABLE_CLOUDS


@click.group(name='licenses')
def licenses():
    """Manages RIGHTSIZER_LICENSES Application Entity"""


@licenses.command(cls=ViewCommand, name='describe')
@click.option('--application_id', '-aid', type=str, required=False,
              help='Id of the application to describe.')
@cli_response()
def describe(application_id=None):
    """
    Describes a RIGHTSIZER_LICENSES Application.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().application_licenses_get(
        application_id=application_id)


@licenses.command(cls=ViewCommand, name='add')
@click.option('--customer_id', '-cid', type=str, required=True,
              help='Maestro Customer name.')
@click.option('--description', '-d', type=str, required=True,
              help='Application description.')
@click.option('--cloud', '-c', required=True,
              type=click.Choice(AVAILABLE_CLOUDS),
              help='Price cloud.')
@click.option('--tenant_license_key', '-tlk', required=True, type=str,
              help='Tenant license key.')
@cli_response()
def add(customer_id, description, cloud, tenant_license_key):
    """
    Creates Maestro RIGHTSIZER_LICENSES Application
    """
    from r8scli.service.initializer import init_configuration

    return init_configuration().application_licenses_post(
        customer=customer_id,
        description=description,
        cloud=cloud,
        tenant_license_key=tenant_license_key
    )


@licenses.command(cls=ViewCommand, name='delete')
@click.option('--application_id', '-aid', type=str, required=True,
              help='Id of the application to delete.')
@click.option('--force', '-f', is_flag=True,
              help='To completely delete Application from db.')
@cli_response()
def delete(application_id, force):
    """
    Deletes RIGHTSIZER_LICENSES Application.
    """
    from r8scli.service.initializer import init_configuration
    if force:
        click.confirm(
            f'Do you really want to completely '
            f'delete application {application_id}?',
            abort=True
        )
    return init_configuration().application_licenses_delete(
        application_id=application_id, force=force)
