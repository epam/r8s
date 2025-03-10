import click

from r8scli.group import cli_response, cast_to_list, ViewCommand


@click.group(name='policy')
def policy():
    """Manages Policy Entity"""


@policy.command(cls=ViewCommand, name='describe')
@click.option('--policy_name', '-name', type=str,
              help='Policy name to describe.')
@cli_response()
def describe(policy_name=None):
    """
    Describes a R8s policies.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().policy_get(policy_name=policy_name)


@policy.command(cls=ViewCommand, name='add')
@click.option('--policy_name', '-name', type=str, required=True,
              help='Policy name to create')
@click.option('--permission', '-p', multiple=True,
              required=False,
              help='List of permissions to attach to the policy')
@click.option('--permissions_admin', '-padm', is_flag=True, required=False,
              help='Adds all admin permissions')
@click.option('--path_to_permissions', '-path', required=False,
              help='Path to .json file that contains list of permissions to '
                   'attach to the policy')
@cli_response()
def add(policy_name, permission, permissions_admin,
        path_to_permissions):
    """
    Creates a R8s policy.
    """
    from r8scli.service.initializer import init_configuration
    permissions = cast_to_list(permission)
    return init_configuration().policy_post(policy_name=policy_name,
                                            permissions=permissions,
                                            permissions_admin=permissions_admin,
                                            path_to_permissions=path_to_permissions)


@policy.command(cls=ViewCommand, name='update')
@click.option('--policy_name', '-name', type=str, required=True)
@click.option('--attach_permission', '-a', multiple=True,
              required=False,
              help='Names of permissions to attach to the policy')
@click.option('--detach_permission', '-d', multiple=True,
              required=False,
              help='Names of permissions to detach from the policy')
@cli_response()
def update(policy_name, attach_permission,
           detach_permission):
    """
    Updates list of permissions attached to the policy.
    """
    from r8scli.service.initializer import init_configuration

    if not attach_permission and not detach_permission:
        return {'message': 'At least one of the following arguments must be '
                           'provided: attach_permission, detach_permission'}

    attach_permissions = cast_to_list(attach_permission)
    detach_permissions = cast_to_list(detach_permission)
    return init_configuration().policy_patch(
        policy_name=policy_name,
        attach_permissions=attach_permissions,
        detach_permissions=detach_permissions)


@policy.command(cls=ViewCommand, name='delete')
@click.option('--policy_name', '-name', type=str, required=True,
              help='Policy name to delete')
@cli_response()
def delete(policy_name):
    """
    Deletes r8s policy.
    """
    from r8scli.service.initializer import init_configuration
    if policy_name:
        policy_name = policy_name.lower()
    return init_configuration().policy_delete(policy_name=policy_name.lower())
