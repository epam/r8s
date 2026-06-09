import click

from r8scli.group import cli_response, ViewCommand


@click.group(name='tenant')
def tenant():
    """Manages Tenant Entity"""


@tenant.command(cls=ViewCommand, name='describe')
@click.option('--tenant_name', '-tn', type=str, default=None,
              help='Tenant name to describe')
@cli_response()
def describe(tenant_name=None):
    """
    Describes a R8s tenant
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().tenant_get(tenant_name=tenant_name)
