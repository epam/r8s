import click

from r8s_group import cli_response, ViewCommand, cast_to_list
from r8s_service.constants import (AVAILABLE_CLOUDS, ALLOWED_PROTOCOLS, \
    PROTOCOL_HTTPS, AVAILABLE_PARENT_SCOPES, PARENT_SCOPE_ALL,
                                   PARENT_SCOPE_SPECIFIC, PARENT_SCOPE_DISABLED)
from r8s_group.parent_licenses import licenses
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
    Describes a RIGHTSIZER Parent.
    """
    from r8s_service.initializer import init_configuration
    return init_configuration().parent_get(
        application_id=application_id,
        parent_id=parent_id)


@parent.command(cls=ViewCommand, name='add')
@click.option('--application_id', '-aid', type=str, required=True,
              help='Maestro application id to create Parent for.')
@click.option('--description', '-d', type=str, required=True,
              help='Parent description.')
@click.option('--cloud', '-c', type=click.Choice(AVAILABLE_CLOUDS),
              required=False, help='Parent cloud. Only applied to ALL scope')
@click.option('--scope', '-s', required=True,
              type=click.Choice(AVAILABLE_PARENT_SCOPES),
              help=f'Parent scope. {PARENT_SCOPE_ALL} to enable all '
                   f'tenants/all tenants of specific cloud. '
                   f'{PARENT_SCOPE_SPECIFIC}/{PARENT_SCOPE_DISABLED} '
                   f'to enable/disable specific tenant')
@click.option('--tenant_name', '-tn', required=False, type=str,
              help=f'Tenant name to be linked to Parent. '
                   f'Only for {PARENT_SCOPE_DISABLED}/{PARENT_SCOPE_SPECIFIC} '
                   f'scopes.')
@cli_response()
def add(application_id, description, cloud, scope, tenant_name):
    """
    Creates Maestro RIGHTSIZER Parent
    """
    from r8s_service.initializer import init_configuration
    return init_configuration().parent_post(
        application_id=application_id,
        description=description,
        cloud=cloud,
        scope=scope,
        tenant_name=tenant_name
    )


@parent.command(cls=ViewCommand, name='delete')
@click.option('--parent_id', '-pid', type=str, required=True,
              help='Maestro Parent id to delete.')
@cli_response()
def delete(parent_id):
    """
    Updates Maestro RIGHTSIZER Parent
    """
    from r8s_service.initializer import init_configuration

    return init_configuration().parent_delete(
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

parent.add_command(licenses)
parent.add_command(shape_rule)