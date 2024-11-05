import click

from r8scli.group import cli_response, ViewCommand
from r8scli.group.application_licenses import licenses
from r8scli.group.application_policies import policies
from r8scli.group.application_dojo import dojo
from r8scli.service.constants import ALLOWED_PROTOCOLS, \
    PROTOCOL_HTTPS


@click.group(name='application')
def application():
    """Manages RIGHTSIZER Application Entity"""


@application.command(cls=ViewCommand, name='describe')
@click.option('--application_id', '-aid', type=str, required=False,
              help='Id of the application to describe.')
@cli_response()
def describe(application_id=None):
    """
    Describes a RIGHTSIZER Application.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().application_get(
        application_id=application_id)


@application.command(cls=ViewCommand, name='add')
@click.option('--customer_id', '-cid', type=str, required=True,
              help='Maestro Customer name.')
@click.option('--description', '-d', type=str, required=True,
              help='Application description.')
@click.option('--input_storage', '-is', required=True, type=str,
              help='Name of Storage that will be used as metric source.')
@click.option('--output_storage', '-os', required=True, type=str,
              help='Name of Storage that will be used as '
                   'recommendation destination.')
@click.option('--username', '-u', type=str,
              required=True,
              help='R8s user username.')
@click.option('--password', '-pwd', type=str,
              required=True, hide_input=True, prompt=True,
              help='R8s user password.')
@click.option('--host', '-h', required=False, type=str,
              help='Rightsizer API host. By default, current r8s API host '
                   'will be used. Example: 5dm5otw4o7.execute-api.'
                   'eu-central-1.amazonaws.com')
@click.option('--port', '-p', type=int, default=443, required=False,
              help='Rightsizer API port.')
@click.option('--protocol', '-pr', type=click.Choice(ALLOWED_PROTOCOLS),
              default=PROTOCOL_HTTPS, required=False,
              help='Protocol name')
@cli_response()
def add(customer_id, description, input_storage, output_storage,
        username, password, host, port, protocol):
    """
    Creates Maestro RIGHTSIZER Application
    """
    from r8scli.service.initializer import init_configuration

    return init_configuration().application_post(
        customer=customer_id,
        description=description,
        input_storage=input_storage,
        output_storage=output_storage,
        host=host,
        port=port,
        protocol=protocol,
        username=username,
        password=password
    )


@application.command(cls=ViewCommand, name='update')
@click.option('--application_id', '-aid', type=str, required=True,
              help='Maestro Application id to update.')
@click.option('--description', '-d', type=str,
              help='Application description.')
@click.option('--input_storage', '-is', type=str,
              help='Name of Storage that will be used as metric source.')
@click.option('--output_storage', '-os', type=str,
              help='Name of Storage that will be used as '
                   'recommendation destination.')
@click.option('--username', '-u', type=str,
              help='R8s user username.')
@click.option('--password', '-pwd', type=str,
              hide_input=True, help='R8s user password.')
@click.option('--host', '-h', type=str,
              help='Rightsizer API host. Example: 5dm5otw4o7.execute-'
                   'api.eu-central-1.amazonaws.com')
@click.option('--port', '-p', type=int,
              help='Rightsizer API port')
@click.option('--protocol', '-pr', type=click.Choice(ALLOWED_PROTOCOLS),
              help='Protocol name')
@cli_response()
def update(application_id, description, input_storage, output_storage,
           username, password, host, port, protocol):
    """
    Updates Maestro RIGHTSIZER Application
    """
    from r8scli.service.initializer import init_configuration

    return init_configuration().application_patch(
        application_id=application_id,
        description=description,
        input_storage=input_storage,
        output_storage=output_storage,
        host=host,
        port=port,
        protocol=protocol,
        username=username,
        password=password
    )


@application.command(cls=ViewCommand, name='delete')
@click.option('--application_id', '-aid', type=str, required=True,
              help='Id of the application to delete.')
@click.option('--force', '-f', is_flag=True,
              help='To completely delete Application from db.')
@cli_response()
def delete(application_id, force):
    """
    Deletes RIGHTSIZER Application.
    """
    from r8scli.service.initializer import init_configuration
    if force:
        click.confirm(
            f'Do you really want to completely '
            f'delete application {application_id}?',
            abort=True
        )
    return init_configuration().application_delete(
        application_id=application_id)


application.add_command(licenses)
application.add_command(policies)
application.add_command(dojo)
