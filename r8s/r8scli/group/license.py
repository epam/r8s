import click

from r8scli.group import cli_response, ViewCommand


@click.group(name='license')
def license():
    """Manages RIGHTSIZER License Entity"""


@license.command(cls=ViewCommand, name='sync')
@click.option('--application_id', '-aid', type=str, required=True,
              help='RIGHTSIZER_LICENSES application to sync license.')
@cli_response()
def sync(application_id: str):
    """
    Synchronizes a RIGHTSIZER License.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().license_sync_post(
        application_id=application_id)
