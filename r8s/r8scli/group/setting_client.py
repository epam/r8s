import click
from r8scli.group import cli_response, ViewCommand

PARAM_PEM = 'PEM'


@click.group(name='client')
def client():
    """Manages License Manager Client data"""


@client.command(cls=ViewCommand, name='describe')
@click.option('--format', '-f', type=click.Choice([PARAM_PEM]),
              default=PARAM_PEM, show_default=PARAM_PEM,
              help='Format of the private-key.')
@cli_response()
def describe(format):
    """
    Describe current License Manager client-key data
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().lm_client_setting_get(format=format)


@client.command(cls=ViewCommand, name='add')
@click.option('--key_id', '-kid',
              type=str, required=True,
              help='Key-id granted by the License Manager.')
@click.option('--algorithm', '-alg', type=str,
              help='Algorithm granted by the License Manager.', required=True)
@click.option('--private_key', '-prk', type=str, required=True,
              help='Private-key granted by the License Manager.')
@click.option('--format', '-f', type=click.Choice([PARAM_PEM]),
              default=PARAM_PEM, show_default=PARAM_PEM,
              help='Format of the private-key.')
@click.option('--b64encoded', '-b64', is_flag=True, default=False,
              help='Specify whether the private is b64encoded.')
@cli_response(secured_params=['private_key', 'key_id'])
def add(key_id, algorithm, private_key, format, b64encoded):
    """
    Adds License Manager provided client-key data
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().lm_client_setting_post(
        key_id=key_id,
        algorithm=algorithm,
        private_key=private_key,
        format=format,
        b64encoded=b64encoded
    )


@client.command(cls=ViewCommand, name='delete')
@click.option('--key_id', '-kid',
              type=str, required=True,
              help='Key-id granted by the License Manager.')
@cli_response()
def delete(key_id: str):
    """
    Removes current License Manager client-key data
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().lm_client_setting_delete(
        key_id=key_id
    )


client.add_command(describe)
client.add_command(add)
client.add_command(delete)
