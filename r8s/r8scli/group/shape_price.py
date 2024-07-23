import click

from r8scli.group import ViewCommand, cli_response
from r8scli.service.constants import AVAILABLE_CLOUDS, AVAILABLE_OS


@click.group(name='price')
def price():
    """Manages Shape Price Entity"""


@price.command(cls=ViewCommand, name='describe')
@click.option('--name', '-n', type=str, help='Describe shape by name.')
@click.option('--cloud', '-c',
              type=click.Choice(AVAILABLE_CLOUDS),
              help='Describe shape prices in cloud.')
@click.option('--region', '-r', type=str,
              help='Describe shape prices in region.')
@click.option('--os', '-os',
              type=click.Choice(AVAILABLE_OS),
              help='Describe shape prices by operating system.')
@click.option('--customer_id', '-cid', type=str,
              help='Shape price customer to '
                   'describe [for admin users only].')
@cli_response()
def describe(name, cloud, region, os, customer_id):
    """
    Describes a R8s Shape Price.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().shape_price_get(
        customer=customer_id,
        cloud=cloud,
        name=name,
        region=region,
        os=os
    )


@price.command(cls=ViewCommand, name='add')
@click.option('--name', '-n', type=str, required=True,
              help='Shape name.')
@click.option('--cloud', '-c', required=True,
              type=click.Choice(AVAILABLE_CLOUDS),
              help='Price cloud.')
@click.option('--region', '-r', type=str, required=True,
              help='Shape region.')
@click.option('--os', '-os', required=True,
              type=click.Choice(AVAILABLE_OS),
              help='Shape os.')
@click.option('--on_demand_price', '-p', type=float, required=True,
              help='Shape on demand hour price in USD.')
@click.option('--customer_id', '-cid', type=str,
              help='Shape price customer [for admin users only].')
@cli_response()
def add(name, cloud, region, os, on_demand_price, customer_id):
    """
    Creates a R8s Shape Price.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().shape_price_post(
        customer=customer_id,
        cloud=cloud,
        name=name,
        region=region,
        os=os,
        on_demand=on_demand_price
    )


@price.command(cls=ViewCommand, name='update')

@click.option('--name', '-n', type=str, required=True,
              help='Shape name.')
@click.option('--cloud', '-c', required=True,
              type=click.Choice(AVAILABLE_CLOUDS),
              help='Shape cloud.')
@click.option('--region', '-r', type=str, required=True,
              help='Shape region.')
@click.option('--os', '-os', required=True,
              type=click.Choice(AVAILABLE_OS),
              help='Shape os.')
@click.option('--on_demand_price', '-p', type=float, required=True,
              help='Shape on demand hour price in USD.')
@click.option('--customer_id', '-cid', type=str,
              help='Shape price customer [for admin users only].')
@cli_response()
def update(name, cloud, region, os, on_demand_price, customer_id):
    """
    Updates a R8s Shape Price.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().shape_price_patch(
        customer=customer_id,
        cloud=cloud,
        name=name,
        region=region,
        os=os,
        on_demand=on_demand_price
    )


@price.command(cls=ViewCommand, name='delete')
@click.option('--name', '-n', type=str, required=True, help='Shape name.')
@click.option('--cloud', '-c', required=True,
              type=click.Choice(AVAILABLE_CLOUDS),
              help='Shape cloud.')
@click.option('--region', '-r', type=str, required=True,
              help='Shape region.')
@click.option('--os', '-os', required=True,
              type=click.Choice(AVAILABLE_OS),
              help='Shape cloud.')
@click.option('--customer_id', '-cid', type=str, required=False,
              help='Shape price customer to '
                   'delete [for admin users only].')
@cli_response()
def delete(name, cloud, region, os, customer_id):
    """
    Deletes a R8s Shape Price.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().shape_price_delete(
        customer=customer_id,
        cloud=cloud,
        name=name,
        region=region,
        os=os
    )
