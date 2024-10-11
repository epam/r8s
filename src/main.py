"""
On-prem entering point. All the imports are inside functions to make the
helps fast and be safe from importing not existing packages
"""
import logging
import logging.config
from datetime import timedelta
import multiprocessing
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from scheduler import Scheduler
import time
from threading import Thread

from bottle import Bottle

from services import SERVICE_PROVIDER

SRC = Path(__file__).parent.resolve()
ROOT = SRC.parent.resolve()

DEPLOYMENT_RESOURCES_FILENAME = 'deployment_resources.json'

RUN_ACTION = 'run'
CREATE_INDEXES_ACTION = 'create_indexes'
CREATE_BUCKETS_ACTION = 'create_buckets'
INIT_VAULT_ACTION = 'init_vault'
ENV_ACTION = 'env'

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 8010
DEFAULT_NUMBER_OF_WORKERS = (multiprocessing.cpu_count() * 2) + 1


# DEFAULT_ON_PREM_API_LINK = f'http://{DEFAULT_HOST}:{str(DEFAULT_PORT)}/caas'
# DEFAULT_API_GATEWAY_NAME = 'r8s-api'

# API_GATEWAY_LINK = 'https://{id}.execute-api.{region}.amazonaws.com/{stage}'

# R8S_CONFIGURE_COMMAND = '$ r8s configure --api_link {api_link}'
# R8S_LOGIN_COMMAND = '$ r8s login --username {username} --password ' \
#                     '\'{password}\''


def get_logger():
    config = {
        'version': 1,
        'disable_existing_loggers': True
    }
    logging.config.dictConfig(config)
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


_LOG = get_logger()


class ActionHandler(ABC):

    @staticmethod
    def is_docker() -> bool:
        # such a kludge due to different envs that points to on-prem env in
        # LM and MCDM
        lm_docker = SERVICE_PROVIDER.environment_service().is_docker()
        mcdm_docker = SERVICE_PROVIDER.mcdm_client().environment_service(). \
            is_docker()
        return lm_docker or mcdm_docker

    @abstractmethod
    def __call__(self, **kwargs):
        pass


class Run(ActionHandler):
    @staticmethod
    def make_app() -> Bottle:
        """For gunicorn"""
        from exported_module.api.deployment_resources_parser import \
            DeploymentResourcesParser
        from exported_module.api.app import DynamicAPI
        api = DynamicAPI(dr_parser=DeploymentResourcesParser(
            SRC / DEPLOYMENT_RESOURCES_FILENAME
        ))
        return api.app

    def __call__(self, host: str = DEFAULT_HOST, port: str = DEFAULT_PORT,
                 gunicorn: bool = False, workers: Optional[int] = None):
        if not gunicorn and workers:
            print(
                '--workers is ignored because it you are not running Gunicorn')
        app = self.make_app()
        if gunicorn:
            workers = workers or DEFAULT_NUMBER_OF_WORKERS
            from exported_module.api.app_gunicorn import \
                R8sGunicornApplication
            options = {
                'bind': f'{host}:{port}',
                'workers': workers,
            }
            R8sGunicornApplication(app, options).run()
        else:
            app.run(host=host, port=port)


def license_manager_sync():
    _LOG.debug(f'Running scheduled license sync')
    license_service = SERVICE_PROVIDER.license_service()
    algorithm_service = SERVICE_PROVIDER.algorithm_service()
    license_manager_service = SERVICE_PROVIDER.license_manager_service()
    settings_service = SERVICE_PROVIDER.settings_service()

    licenses = license_service.list_licenses()
    if not licenses:
        _LOG.debug(f'No active licenses found, LM sync will be skipped.')
        return
    algorithms = algorithm_service.list()
    if not algorithms:
        _LOG.debug(f'No algorithms found, LM sync will be skipped.')
        return
    _LOG.debug(f'Licenses to update: {[l.license_key for l in licenses]}')
    try:
        for license_ in licenses:
            _LOG.info(f'Syncing license \'{license_.license_key}\'')
            customer = list(license_.customers.keys())[0]

            response = license_manager_service.synchronize_license(
                license_key=license_.license_key,
                customer=customer
            )
            if not response.status_code == 200:
                _LOG.error(f'Invalid LM response obtained: {response}.')
                raise ValueError(f'Invalid LM response obtained: {response}.')
            _LOG.debug(f'Reading license data from LM response')
            license_data = response.json()['items'][0]

            _LOG.debug(f'Updating license {license_.license_key} '
                       f'with data: {license_data}')
            license_ = license_service.update_license(
                license_obj=license_,
                license_data=license_data
            )
            _LOG.debug(f'Updating licensed algorithm')
            for customer in license_.customers.keys():
                algorithm_service.sync_licensed_algorithm(
                    license_data=license_data,
                    customer=customer
                )
    except Exception as e:
        _LOG.debug(f'License sync failed: {e}')
        settings_service.lm_grace_increment_failed()
    else:
        _LOG.debug(f'License(s) synced successfully')
        settings_service.lm_grace_reset()

    if not settings_service.lm_grace_is_job_allowed():
        _LOG.debug(f'License Manager grace period has ended.')
        for algorithm in algorithms:
            _LOG.debug(f'Deleting algorithm {algorithm.name}')
            algorithm.delete()


def run_scheduled_sync(grace_config: dict):
    schedule = Scheduler()
    schedule.cyclic(timedelta(seconds=grace_config['period_seconds']),
                    license_manager_sync)

    while True:
        schedule.exec_jobs()
        time.sleep(1)


def main():
    from exported_module.scripts.init_vault import init_vault
    from exported_module.scripts.init_minio import init_minio
    from exported_module.scripts.init_mongo import init_mongo

    init_vault()
    init_minio()

    grace_config = {
        'period_seconds': 60,
        'grace_period_count': 5,
        'failed_count': 0
    }
    init_mongo(grace_config)

    _LOG.debug(f'Creating scheduled license sync job')
    thread = Thread(target=run_scheduled_sync, args=(grace_config,))
    thread.start()

    _LOG.debug(f'Starting r8s application')
    Run()()


if __name__ == '__main__':
    main()
