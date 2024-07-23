import click
from r8scli.group import cli_response, ViewCommand
from r8scli.service.local_response_processor import LocalCommandResponse


@click.group(name='config')
def config():
    """Manages License Manager Config data"""


@config.command(cls=ViewCommand, name='describe')
@cli_response()
def describe():
    """
    Describes current License Manager access configuration data
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().lm_config_setting_get()


@config.command(cls=ViewCommand, name='add')
@click.option('--host', '-h',
              type=str, required=True,
              help='License Manager host. You can specify the full url here')
@click.option('--port', '-p', type=int,
              help='License Manager port.', required=False)
@click.option('--protocol', '-pr', type=click.Choice(['HTTP', 'HTTPS']),
              help='License manager protocol')
@click.option('--stage', '-st', type=str,
              help='Path prefix')
@cli_response()
def add(host, port, protocol, stage):
    """
    Adds License Manager access configuration data
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().lm_config_setting_post(
        host=host, port=port,
        protocol=protocol, stage=stage
    )


@config.command(cls=ViewCommand, name='delete')
@click.option('--confirm', is_flag=True, help='Confirms the action.')
@cli_response()
def delete(confirm: bool):
    """
    Removes current License Manager access configuration data
    """
    if not confirm:
        return LocalCommandResponse(
            body={'message': 'Please, specify `--confirm` flag'})

    from r8scli.service.initializer import init_configuration
    return init_configuration().lm_config_setting_delete()
