import click

from r8scli.group import ViewCommand, cli_response
from r8scli.group.shape_price import price
from r8scli.service.constants import AVAILABLE_CLOUDS


@click.group(name='shape')
def shape():
    """Manages Shape Entity"""


@shape.command(cls=ViewCommand, name='describe')
@click.option('--name', '-n', type=str, help='Shape name to describe.')
@click.option('--cloud', '-c',
              type=click.Choice(AVAILABLE_CLOUDS),
              required=False, help='To describe all shape in cloud.')
@cli_response()
def describe(name=None, cloud=None):
    """
    Describes a R8s Shape.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().shape_get(name=name, cloud=cloud)


@shape.command(cls=ViewCommand, name='add')
@click.option('--name', '-n', type=str, required=True,
              help='Shape name to create.')
@click.option('--cloud', '-c',
              type=click.Choice(AVAILABLE_CLOUDS),
              required=True, help='Shape cloud.')
@click.option('--cpu', '-cpu', type=float, required=True,
              help='Shape cpu.')
@click.option('--memory', '-m', type=float, required=True,
              help='Shape memory (in gb).')
@click.option('--network_throughtput', '-nt', type=float, required=True,
              help='Shape network throughtput in mbps.')
@click.option('--iops', '-iops', type=float, required=True,
              help='Shape iops.')
@click.option('--family_type', '-ft', type=str, required=True,
              help='Shape family type.')
@click.option('--physical_processor', '-pp', type=str, required=True,
              help='Shape physical processor.')
@click.option('--architecture', '-arch', type=str, required=True,
              help='Shape architecture.')
@cli_response()
def add(name, cloud, cpu, memory, network_throughtput, iops,
        family_type, physical_processor, architecture):
    """
    Creates a R8s Shape.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().shape_post(
        name=name, cloud=cloud, cpu=cpu, memory=memory,
        network_throughtput=network_throughtput, iops=iops,
        family_type=family_type, physical_processor=physical_processor,
        architecture=architecture)


@shape.command(cls=ViewCommand, name='update')
@click.option('--name', '-n', type=str, required=True,
              help='Shape name to update.')
@click.option('--cloud', '-c',
              type=click.Choice(AVAILABLE_CLOUDS),
              required=False, help='Shape cloud.')
@click.option('--cpu', '-cpu', type=float, required=False,
              help='Shape cpu.')
@click.option('--memory', '-m', type=float, required=False,
              help='Shape memory (in gb).')
@click.option('--network_throughtput', '-nt', type=float, required=False,
              help='Shape network throughtput in mbps.')
@click.option('--iops', '-iops', type=float, required=False,
              help='Shape iops.')
@click.option('--family_type', '-ft', type=str, required=False,
              help='Shape family type.')
@click.option('--physical_processor', '-pp', type=str, required=False,
              help='Shape physical processor.')
@click.option('--architecture', '-arch', type=str, required=False,
              help='Shape architecture.')
@cli_response()
def update(name, cloud, cpu, memory, network_throughtput, iops,
           family_type, physical_processor, architecture):
    """
    Updates a R8s Shape.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().shape_patch(
        name=name, cloud=cloud, cpu=cpu, memory=memory,
        network_throughtput=network_throughtput, iops=iops,
        family_type=family_type, physical_processor=physical_processor,
        architecture=architecture)


@shape.command(cls=ViewCommand, name='delete')
@click.option('--name', '-n', type=str, required=True,
              help='Shape name to delete.')
@cli_response()
def delete(name):
    """
    Deletes a R8s Shape.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().shape_delete(name=name)


shape.add_command(price)
