import click

from r8scli.group import cli_response, ViewCommand


@click.group(name='auth')
def auth():
    """Manages MCP JWT auth configuration"""


@auth.command(cls=ViewCommand, name='describe')
@cli_response()
def describe():
    """
    Describes current MCP JWT auth configuration
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().mcp_auth_get()


@auth.command(cls=ViewCommand, name='add')
@click.option('--jwt', '-j', type=str, required=True,
              hide_input=True, prompt=True,
              help='JWT verification key (public key). '
                   'If not provided, will be prompted securely')
@click.option('--algorithm', '-alg', type=str, default='RS256',
              show_default=True,
              help='JWT signing algorithm')
@cli_response()
def add(jwt: str, algorithm: str):
    """
    Adds MCP JWT auth configuration. Only one configuration is allowed.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().mcp_auth_post(jwt=jwt, algorithm=algorithm)


@auth.command(cls=ViewCommand, name='update')
@click.option('--jwt', '-j', type=str, required=False,
              help='JWT verification key. Use --prompt_jwt to enter securely')
@click.option('--prompt_jwt', '-pj', is_flag=True, default=False,
              help='Prompt for the JWT verification key securely '
                   '(input hidden) instead of passing via --jwt')
@click.option('--algorithm', '-alg', type=str, required=False,
              help='JWT signing algorithm')
@cli_response()
def update(jwt: str | None, prompt_jwt: bool, algorithm: str | None):
    """
    Updates existing MCP JWT auth configuration
    """
    from r8scli.service.initializer import init_configuration
    if jwt and prompt_jwt:
        raise click.ClickException(
            'Provide either --jwt or --prompt_jwt, not both'
        )
    if prompt_jwt:
        jwt = click.prompt('JWT verification key', hide_input=True)
    if jwt is None and algorithm is None:
        raise click.ClickException(
            'Provide at least one of --jwt or --algorithm'
        )
    return init_configuration().mcp_auth_patch(jwt=jwt, algorithm=algorithm)


@auth.command(cls=ViewCommand, name='delete')
@cli_response()
def delete():
    """
    Removes current MCP JWT auth configuration
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().mcp_auth_delete()


auth.add_command(describe)
auth.add_command(add)
auth.add_command(update)
auth.add_command(delete)
