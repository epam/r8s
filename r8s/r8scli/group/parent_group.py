import click

from r8scli.group import cli_response, ViewCommand, cast_to_list


@click.group(name='group')
def group():
    """Manages RIGHTSIZER_LICENSES Parent group configuration
    Syndicate RightSizer considers resources within the same group as related.
    This includes resources that share the same tag value or belong to the
    same AWS resource group.

    Works only for tags/resource groups added to configuration.
    """


@group.command(cls=ViewCommand, name='describe')
@click.option('--parent_id', '-pid', type=str, required=True,
              help='Parent id to describe resource group config.')
@cli_response()
def describe(parent_id):
    """
    Describes a R8s parent resource group configuration.

    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().resource_group_get(parent_id=parent_id)


@group.command(cls=ViewCommand, name='add_allowed_tags')
@click.option('--parent_id', '-pid', type=str, required=True,
              help='Parent id to update resource group config.')
@click.option('--tag', '-t', multiple=True,
              required=True,
              help='List of tag keys to add')
@cli_response()
def add_allowed_tags(parent_id, tag):
    """
    Adds specified tags to resource group configuration.
    """
    from r8scli.service.initializer import init_configuration

    add_tags = cast_to_list(tag)
    return init_configuration().resource_group_patch(
        parent_id=parent_id, add_tags=add_tags)


@group.command(cls=ViewCommand, name='remove_tags')
@click.option('--parent_id', '-pid', type=str, required=True,
              help='Parent id to update resource group config.')
@click.option('--tag', '-t', multiple=True,
              required=True,
              help='List of tag keys to remove')
@cli_response()
def remove_tags(parent_id, tag):
    """
    Removes specified tags from resource group configuration.
    """
    from r8scli.service.initializer import init_configuration

    remove_tags = cast_to_list(tag)
    return init_configuration().resource_group_patch(
        parent_id=parent_id, remove_tags=remove_tags)


@group.command(cls=ViewCommand, name='add_resource_group')
@click.option('--parent_id', '-pid', type=str, required=True,
              help='Parent id to update resource group config.')
@click.option('--group', '-g', multiple=True,
              required=True,
              help='List of AWS Resource Group names to add')
@cli_response()
def add_resource_group(parent_id, group):
    """
    Adds specified resource groups to configuration.
    """
    from r8scli.service.initializer import init_configuration

    add_resource_groups = cast_to_list(group)
    return init_configuration().resource_group_patch(
        parent_id=parent_id, add_resource_groups=add_resource_groups)


@group.command(cls=ViewCommand, name='remove_resource_group')
@click.option('--parent_id', '-pid', type=str, required=True,
              help='Parent id to update resource group config.')
@click.option('--group', '-g', multiple=True,
              required=True,
              help='List of AWS Resource Group names to remove')
@cli_response()
def remove_resource_group(parent_id, group):
    """
    Removes specified resource groups from configuration.
    """
    from r8scli.service.initializer import init_configuration

    remove_resource_groups = cast_to_list(group)
    return init_configuration().resource_group_patch(
        parent_id=parent_id, remove_resource_groups=remove_resource_groups)
