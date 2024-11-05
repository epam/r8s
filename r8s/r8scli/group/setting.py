import click
from r8scli.group.setting_client import client
from r8scli.group.setting_config import config

@click.group(name='setting')
def setting():
    """Manages Setting Entity"""

setting.add_command(client)
setting.add_command(config)
