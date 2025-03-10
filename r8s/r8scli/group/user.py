import click

from r8scli.group import cli_response, ViewCommand


@click.group(name='user')
def user():
    """Manages User Entity"""


@user.command(cls=ViewCommand, name='describe')
@click.option('--username', '-u', type=str, help='User name to describe.')
@cli_response()
def describe(username=None):
    """
    Describes a R8s user.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().user_get(username=username)


@user.command(cls=ViewCommand, name='update')
@click.option('--username', '-u', type=str, required=True,
              help='User name to update password.')
@click.option('--password', '-p', type=str, required=True, hide_input=True,
              prompt=True, help='User password to set.')
@cli_response()
def update(username, password):
    """
    Updates user password.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().user_patch(username=username,
                                           password=password)


@user.command(cls=ViewCommand, name='delete')
@click.option('--username', '-u', type=str, required=True,
              help='User name delete.')
@cli_response()
def delete(username):
    """
    Deletes user.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().user_delete(username=username)
