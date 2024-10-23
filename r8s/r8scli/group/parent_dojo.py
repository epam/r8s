import click

from r8scli.group import cli_response, ViewCommand
from r8scli.service.constants import (AVAILABLE_PARENT_SCOPES)


@click.group(name='dojo')
def dojo():
    """Manages RIGHTSIZER_SIEM_DEFECT_DOJO Parent Entity"""


@dojo.command(cls=ViewCommand, name='describe')
@click.option('--application_id', '-aid', type=str, required=False,
              help='Id of the application to describe parents.')
@click.option('--parent_id', '-pid', type=str, required=False,
              help='Parent id to describe.')
@cli_response()
def describe(application_id=None, parent_id=None):
    """
    Describes a RIGHTSIZER_SIEM_DEFECT_DOJO Parent.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().parent_dojo_get(
        application_id=application_id,
        parent_id=parent_id
    )


@dojo.command(cls=ViewCommand, name='add')
@click.option('--application_id', '-aid', type=str, required=True,
              help='DEFECT_DOJO application id create Parent for.')
@click.option('--description', '-d', type=str, required=True,
              help='Parent description.')
@click.option('--tenant', '-t', type=str, required=False,
              help='Tenant to activate Dojo for.')
@click.option('--scope', '-s', type=click.Choice(AVAILABLE_PARENT_SCOPES),
              required=True, help='Parent scope')
@cli_response()
def add(application_id, description, tenant, scope):
    """
    Creates RIGHTSIZER_SIEM_DEFECT_DOJO parent
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().parent_dojo_post(
        application_id=application_id,
        description=description,
        tenant=tenant,
        scope=scope
    )


@dojo.command(cls=ViewCommand, name='delete')
@click.option('--parent_id', '-pid', type=str, required=True,
              help='Maestro Parent id to delete.')
@click.option('--force', '-f', is_flag=True,
              help='To completely delete Parent from db.')
@cli_response()
def delete(parent_id, force):
    """
    Deletes RIGHTSIZER_SIEM_DEFECT_DOJO Parent
    """
    from r8scli.service.initializer import init_configuration
    if force:
        click.confirm(
            f'Do you really want to completely '
            f'delete parent {parent_id}?',
            abort=True
        )
    return init_configuration().parent_dojo_delete(
        parent_id=parent_id,
        force=force
    )
