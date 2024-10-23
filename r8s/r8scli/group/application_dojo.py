import click

from r8scli.group import cli_response, ViewCommand
from r8scli.service.constants import ALLOWED_PROTOCOLS, \
    PROTOCOL_HTTPS


@click.group(name='dojo')
def dojo():
    """Manages DEFECT_DOJO Application Entity"""


@dojo.command(cls=ViewCommand, name='describe')
@click.option('--application_id', '-aid', type=str, required=False,
              help='Id of the application to describe.')
@cli_response()
def describe(application_id=None):
    """
    Describes a DEFECT_DOJO Application.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().application_dojo_get(
        application_id=application_id)


@dojo.command(cls=ViewCommand, name='add')
@click.option('--customer_id', '-cid', type=str, required=True,
              help='Maestro Customer name.')
@click.option('--description', '-d', type=str, required=True,
              help='Application description.')
@click.option('--host', '-h', required=True, type=str,
              help='Defect Dojo API host')
@click.option('--port', '-p', type=int, default=443, required=False,
              help='DefectDojo API port.')
@click.option('--protocol', '-pr', type=click.Choice(ALLOWED_PROTOCOLS),
              default=PROTOCOL_HTTPS, required=False,
              help='Protocol name')
@click.option('--stage', '-s', type=str, required=False,
              help='API Stage')
@click.option('--api_key', '-ak', type=str,
              required=True, hide_input=True, prompt=True,
              help='Defect Dojo API Key.')
@cli_response()
def add(customer_id, description, host, port, protocol, stage, api_key):
    """
    Creates Maestro RIGHTSIZER Application
    """
    from r8scli.service.initializer import init_configuration

    return init_configuration().application_dojo_post(
        customer=customer_id,
        description=description,
        host=host,
        port=port,
        protocol=protocol,
        stage=stage,
        api_key=api_key
    )


@dojo.command(cls=ViewCommand, name='delete')
@click.option('--application_id', '-aid', type=str, required=True,
              help='Id of the application to delete.')
@click.option('--force', '-f', is_flag=True,
              help='To completely delete Application from db.')
@cli_response()
def delete(application_id, force):
    """
    Deletes DEFECT_DOJO Application.
    """
    from r8scli.service.initializer import init_configuration
    if force:
        click.confirm(
            f'Do you really want to completely '
            f'delete application {application_id}?',
            abort=True
        )
    return init_configuration().application_dojo_delete(
        application_id=application_id)
