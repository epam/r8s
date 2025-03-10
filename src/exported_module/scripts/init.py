from pathlib import Path
import os
import sys

dir_path = Path(
    os.path.dirname(os.path.realpath(__file__))).parent.parent.parent
src_path = os.path.join(dir_path, 'src')
sys.path.append(src_path)

from commons.log_helper import get_logger

_LOG = get_logger('init')

_LOG.debug(f'Executing initialization script')

try:
    from init_minio import init_minio
    _LOG.debug(f'Initializing minio')
    init_minio()
except Exception as e:
    _LOG.error(f'Minio initialization failed: {e}')

try:
    from init_mongo import init_mongo
    _LOG.debug(f'Initializing mongo')
    init_mongo()
except Exception as e:
    _LOG.error(f'Mongo initialization failed: {e}')

try:
    from init_vault import init_vault
    _LOG.debug(f'Initializing vault')
    init_vault()

    from init_system_user import init_system_user
    _LOG.debug(f'Initializing system user')
    init_system_user()
except Exception as e:
    _LOG.error(f'Initialization failed: {e}')

