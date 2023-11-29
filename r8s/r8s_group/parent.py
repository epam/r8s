import click

from r8s_group import cli_response, ViewCommand, cast_to_list
from r8s_service.constants import (AVAILABLE_CLOUDS, ALLOWED_PROTOCOLS, \
                                   PROTOCOL_HTTPS, AVAILABLE_PARENT_SCOPES,
                                   PARENT_SCOPE_ALL,
                                   PARENT_SCOPE_SPECIFIC,
                                   PARENT_SCOPE_DISABLED)
from r8s_group.parent_shaperule import shape_rule


@click.group(name='parent')
def parent():
    """Manages RIGHTSIZER Parent Entity"""


@parent.command(cls=ViewCommand, name='describe')
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


@parent.command(cls=ViewCommand, name='add')
@click.option('--application_id', '-aid', type=str, required=True,
              help='RIGHTSIZER_LICENSES application id create Parent for.')
@click.option('--description', '-d', type=str, required=True,
              help='Parent description.')
@click.option('--tenant', '-t', type=str, required=False,
              help='Tenant to activate license for.')
@click.option('--scope', '-s', type=click.Choice(AVAILABLE_PARENT_SCOPES),
              required=True, help='Parent scope')
@cli_response()
def add(application_id, description, tenant, scope):
    """
    Activates License for Tenants
    """
    from r8s_service.initializer import init_configuration
    return init_configuration().parent_licenses_post(
        application_id=application_id,
        description=description,
        tenant=tenant,
        scope=scope
    )


@parent.command(cls=ViewCommand, name='delete')
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


@parent.command(cls=ViewCommand, name='describe_resize_insights')
@click.option('--parent_id', '-pid', type=str, required=True,
              help='Parent id to describe.')
@click.option('--instance_type', '-it', type=str, required=True,
              help='Native instance type name to test.')
@cli_response()
def describe_resize_insights(parent_id, instance_type):
    """
    Describes r8s shape selection logic insights
    """
    from r8s_service.initializer import init_configuration

    return init_configuration().parent_insights_resize(
        parent_id=parent_id,
        instance_type=instance_type
    )


parent.add_command(shape_rule)
