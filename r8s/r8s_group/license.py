import click

from r8s_group import cli_response, ViewCommand
from r8s_service.constants import AVAILABLE_CLOUDS, ALLOWED_PROTOCOLS, \
    PROTOCOL_HTTPS, AVAILABLE_PARENT_SCOPES, PARENT_SCOPE_SPECIFIC_TENANT


@click.group(name='license')
def license():
    """Manages RIGHTSIZER License Entity"""


@license.command(cls=ViewCommand, name='describe')
@click.option('--license_key', '-lk', type=str, required=False,
              help='License key to describe.')
@cli_response()
def describe(license_key=None):
    """
    Describes a RIGHTSIZER License.
    """
    from r8s_service.initializer import init_configuration
    return init_configuration().license_get(
        license_key=license_key)

@license.command(cls=ViewCommand, name='delete')
@click.option('--license_key', '-lk', type=str, required=True,
              help='License key to delete.')
@cli_response()
def delete(license_key=None):
    """
    Deletes a RIGHTSIZER License.
    """
    from r8s_service.initializer import init_configuration
    return init_configuration().license_delete(
        license_key=license_key)

@license.command(cls=ViewCommand, name='sync')
@click.option('--license_key', '-lk', type=str, required=True,
              help='License key to synchronize.')
@cli_response()
def sync(license_key=None):
    """
    Synchronizes a RIGHTSIZER License.
    """
    from r8s_service.initializer import init_configuration
    return init_configuration().license_sync_post(
        license_key=license_key)
