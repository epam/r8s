import click

from r8scli.group.integrations_mcp import mcp


@click.group(name='integrations')
def integrations():
    """Manages Integrations"""


integrations.add_command(mcp)
