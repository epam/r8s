import click

from r8s_group import cli_response, ViewCommand, cast_to_list
from r8s_service.constants import AVAILABLE_CLOUDS, ALLOWED_PROTOCOLS, \
    PROTOCOL_HTTPS, AVAILABLE_PARENT_SCOPES, PARENT_SCOPE_SPECIFIC_TENANT
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
@click.option('--clouds', '-c', type=click.Choice(AVAILABLE_CLOUDS),
              multiple=True, required=True, help='Parent clouds')
@click.option('--scope', '-s', required=True,
              type=click.Choice(AVAILABLE_PARENT_SCOPES),
              help='Parent scope. If intended to use for all Tenants, '
                   'use \'ALL_TENANTS\'.')
@click.option('--tenant_name', '-tn', required=False, type=str,
              help=f'Tenant name to be linked to Parent. '
                   f'Only for {PARENT_SCOPE_SPECIFIC_TENANT} scope.')
@cli_response()
def add(application_id, description, clouds, scope, tenant_name):
    """
    Creates Maestro RIGHTSIZER Parent
    """
    from r8s_service.initializer import init_configuration
    clouds = cast_to_list(clouds)
    return init_configuration().parent_post(
        application_id=application_id,
        description=description,
        clouds=clouds,
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


@parent.command(cls=ViewCommand, name='describe_tenant_links')
@click.option('--parent_id', '-pid', type=str, required=True,
              help='Maestro Parent id to describe linked tenants.')
@cli_response()
def describe_tenant_links(parent_id):
    """
    Describes Maestro tenant names linked to Parent with the given id
    """
    from r8s_service.initializer import init_configuration

    return init_configuration().parent_tenant_link_get(
        parent_id=parent_id
    )


@parent.command(cls=ViewCommand, name='link_tenant')
@click.option('--parent_id', '-pid', type=str, required=True,
              help='Maestro Parent id to link to tenant.')
@click.option('--tenant_name', '-tn', type=str, required=True,
              help='Maestro tenant name.')
@cli_response()
def link_tenant(parent_id, tenant_name):
    """
    Links Maestro tenant to RIGHTSIZER parent
    """
    from r8s_service.initializer import init_configuration

    return init_configuration().parent_tenant_link_post(
        parent_id=parent_id,
        tenant_name=tenant_name
    )


@parent.command(cls=ViewCommand, name='unlink_tenant')
@click.option('--tenant_name', '-tn', type=str, required=True,
              help='Maestro tenant name to unlink RIGHTSIZER parent.')
@cli_response()
def unlink_tenant(tenant_name):
    """
    Unlinks RIGHTSIZER parent from tenant
    """
    from r8s_service.initializer import init_configuration

    return init_configuration().parent_tenant_link_delete(
        tenant_name=tenant_name
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
# parent.add_command(shape_rule)