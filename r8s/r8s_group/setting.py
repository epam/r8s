import click
from r8s_group.setting_lm_client import client
from r8s_group.setting_lm_config import config

@click.group(name='setting')
def setting():
    """Manages Setting Entity"""

setting.add_command(client)
setting.add_command(config)
