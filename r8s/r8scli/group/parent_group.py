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
@click.option('--group_id', '-gid', type=str, required=False,
              help='Resource group id to describe.')
@cli_response()
def describe(parent_id: str, group_id: str):
    """
    Describes a R8s parent resource group configuration.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().resource_group_get(parent_id=parent_id,
                                                   group_id=group_id)


@group.command(cls=ViewCommand, name='add')
@click.option('--parent_id', '-pid', type=str, required=True,
              help='Parent id to create resource group config in.')
@click.option('--allowed_tag', '-at', multiple=True,
              required=False,
              help='List of tag keys to add')
@click.option('--group_arn', '-arn', multiple=True,
              required=False,
              help='List of AWS native resource groups to add')
@click.option('--scale_step', '-ss', type=int, required=False,
              help='Amount of group resources rightsizing step. '
                   'If not specified, will be determined automatically.')
@click.option('--cooldown_days', '-cd', type=int, required=False,
              help='In days, minimum amount of time between '
                   'group recommendations. Defaults to 7')
@cli_response()
def describe(parent_id: str, allowed_tag, group_arn, scale_step,
             cooldown_days):
    """
    Describes a R8s parent resource group configuration.
    """
    from r8scli.service.initializer import init_configuration

    allowed_tags = cast_to_list(allowed_tag)
    allowed_resource_groups = cast_to_list(group_arn)

    return init_configuration().resource_group_post(
        parent_id=parent_id,
        allowed_tags=allowed_tags,
        allowed_resource_groups=allowed_resource_groups,
        scale_step=scale_step,
        cooldown_days=cooldown_days
    )


@group.command(cls=ViewCommand, name='add_allowed_tags')
@click.option('--parent_id', '-pid', type=str, required=True,
              help='Parent id to update resource group config.')
@click.option('--group_id', '-gid', type=str, required=True,
              help='Resource group id to update.')
@click.option('--tag', '-t', multiple=True,
              required=True,
              help='List of tag keys to add')
@cli_response()
def add_allowed_tags(parent_id, group_id, tag):
    """
    Adds specified tags to resource group configuration.
    """
    from r8scli.service.initializer import init_configuration

    add_tags = cast_to_list(tag)
    return init_configuration().resource_group_patch(
        parent_id=parent_id, group_id=group_id, add_tags=add_tags)


@group.command(cls=ViewCommand, name='remove_tags')
@click.option('--parent_id', '-pid', type=str, required=True,
              help='Parent id to update resource group config.')
@click.option('--group_id', '-gid', type=str, required=True,
              help='Resource group id to update.')
@click.option('--tag', '-t', multiple=True,
              required=True,
              help='List of tag keys to remove')
@cli_response()
def remove_tags(parent_id, group_id, tag):
    """
    Removes specified tags from resource group configuration.
    """
    from r8scli.service.initializer import init_configuration

    return init_configuration().resource_group_patch(
        parent_id=parent_id, group_id=group_id, remove_tags=cast_to_list(tag))


@group.command(cls=ViewCommand, name='add_resource_group')
@click.option('--parent_id', '-pid', type=str, required=True,
              help='Parent id to update resource group config.')
@click.option('--group_id', '-gid', type=str, required=True,
              help='Resource group id to update.')
@click.option('--group_arn', '-arn', multiple=True,
              required=True,
              help='List of AWS Resource group ARN to add')
@cli_response()
def add_resource_group(parent_id, group_id, group_arn):
    """
    Adds specified resource groups to configuration.
    """
    from r8scli.service.initializer import init_configuration

    add_resource_groups = cast_to_list(group_arn)
    return init_configuration().resource_group_patch(
        parent_id=parent_id, group_id=group_id,
        add_resource_groups=add_resource_groups)


@group.command(cls=ViewCommand, name='remove_resource_group')
@click.option('--parent_id', '-pid', type=str, required=True,
              help='Parent id to update resource group config.')
@click.option('--group_id', '-gid', type=str, required=True,
              help='Resource group id to update.')
@click.option('--group_arn', '-arn', multiple=True,
              required=True,
              help='List of AWS Resource group ARN to remove')
@cli_response()
def remove_resource_group(parent_id, group_id, group_arn):
    """
    Removes specified resource groups from configuration.
    """
    from r8scli.service.initializer import init_configuration

    remove_resource_groups = cast_to_list(group_arn)
    return init_configuration().resource_group_patch(
        parent_id=parent_id, group_id=group_id,
        remove_resource_groups=remove_resource_groups)


@group.command(cls=ViewCommand, name='delete')
@click.option('--parent_id', '-pid', type=str, required=True,
              help='Parent id to update resource group config.')
@click.option('--group_id', '-gid', type=str, required=True,
              help='Resource group id to update.')
@cli_response()
def delete(parent_id, group_id):
    """
    Removes specified resource groups from configuration.
    """
    from r8scli.service.initializer import init_configuration

    return init_configuration().resource_group_delete(
        parent_id=parent_id, group_id=group_id
    )
