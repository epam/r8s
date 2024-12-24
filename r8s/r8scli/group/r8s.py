from importlib.metadata import version as lib_version

import click
from r8scli.group import cli_response, ViewCommand, cast_to_list
from r8scli.group.algorithm import algorithm
from r8scli.group.application import application
from r8scli.group.job import job
from r8scli.group.license import license
from r8scli.group.parent import parent
from r8scli.group.policy import policy
from r8scli.group.recommendation import recommendation
from r8scli.group.report import report
from r8scli.group.role import role
from r8scli.group.setting import setting
from r8scli.group.shape import shape
from r8scli.group.storage import storage
from r8scli.group.user import user
from r8scli.service.config import create_configuration, clean_up_configuration, \
    save_token
from r8scli.service.constants import AVAILABLE_CHECK_TYPES
from r8scli.version import __version__


@click.group()
@click.version_option(__version__)
def r8s():
    """The main click's group to accumulates all the CLI commands"""


@r8s.command(cls=ViewCommand, name='configure')
@click.option('--api_link', '-api', type=str,
              required=True,
              help='Link to the R8s host.')
@cli_response()
def configure(api_link):
    """
    Configures r8s tool to work with r8s API.
    """
    context = click.get_current_context()
    return create_configuration(api_link=api_link, context=context)


@r8s.command(cls=ViewCommand, name='login')
@click.option('--username', '-u', type=str,
              required=True,
              help='R8s user username.')
@click.option('--password', '-p', type=str,
              required=True, hide_input=True, prompt=True,
              help='R8s user password.')
@cli_response(secured_params=['password'])
def login(username: str, password: str):
    """
    Authenticates user to work with R8s.
    """
    from r8scli.service.initializer import init_configuration

    response = init_configuration().login(
        username=username, password=password)
    if isinstance(response, tuple):
        access_token = response[0]
        refresh_token = response[1]
        return save_token(access_token=access_token,
                          refresh_token=refresh_token)
    return response


@r8s.command(cls=ViewCommand, name='refresh')
@cli_response()
def refresh():
    """
    Refreshe r8s access token using stored refresh token.
    """
    from r8scli.service.initializer import init_configuration

    response = init_configuration().refresh()
    if isinstance(response, dict):
        access_token = response.get('id_token')
        refresh_token = response.get('refresh_token')
        return save_token(access_token=access_token,
                          refresh_token=refresh_token)
    return response


@r8s.command(cls=ViewCommand, name='register')
@click.option('--username', '-u', type=str,
              required=True,
              help='R8s user username.')
@click.option('--password', '-p', type=str,
              required=True, hide_input=True, prompt=True,
              help='R8s user password.')
@click.option('--customer_id', '-cid', type=str,
              required=True,
              help='R8s user customer.')
@click.option('--role_name', '-rn', type=str,
              required=True,
              help='R8s user role name.')
@cli_response(secured_params=['password'])
def register(username: str, password: str, customer_id, role_name):
    """
    Creates user to work with R8s.
    """

    from r8scli.service.initializer import init_configuration
    response = init_configuration().register(
        username=username, password=password,
        customer=customer_id, role_name=role_name)
    return response


@r8s.command(cls=ViewCommand, name='cleanup')
@cli_response()
def cleanup():
    """
    Removes all the configuration data related to the tool.
    """
    return clean_up_configuration()


@r8s.command(cls=ViewCommand, name='health-check')
@click.option('--check_type', '-t', multiple=True, required=False,
              type=click.Choice(AVAILABLE_CHECK_TYPES),
              help='List of check types to execute.')
@cli_response()
def health_check(check_type):
    """
    Describes a R8s health check status.
    """
    from r8scli.service.initializer import init_configuration

    check_types = cast_to_list(check_type)
    return init_configuration().health_check_post(check_types=check_types)


r8s.add_command(policy)
r8s.add_command(role)
r8s.add_command(algorithm)
r8s.add_command(storage)
r8s.add_command(job)
r8s.add_command(report)
r8s.add_command(user)
r8s.add_command(application)
r8s.add_command(parent)
r8s.add_command(shape)
r8s.add_command(recommendation)
r8s.add_command(setting)
r8s.add_command(license)
