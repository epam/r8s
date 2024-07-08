"""
On-prem entering point. All the imports are inside functions to make the
helps fast and be safe from importing not existing packages
"""
import logging
import logging.config
import multiprocessing
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

from bottle import Bottle

load_dotenv()

from services import SERVICE_PROVIDER

SRC = Path(__file__).parent.resolve()
ROOT = SRC.parent.resolve()

DEPLOYMENT_RESOURCES_FILENAME = 'deployment_resources.json'

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 8000
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


if __name__ == '__main__':
    Run()(gunicorn=True)
