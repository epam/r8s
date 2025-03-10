import mongoengine
import os
from commons.exception import ExecutorException
from commons.constants import JOB_STEP_INITIALIZATION
from commons.log_helper import get_logger
from services.environment_service import EnvironmentService

_LOG = get_logger('r8s-mongo-initializer')


def get_from_ssm():
    from services.clients.ssm import SSMClient, VaultSSMClient
    from services.ssm_service import SSMService

    environment_service = EnvironmentService()

    if environment_service.is_docker():
        ssm_client = VaultSSMClient(
            environment_service=environment_service)
    else:
        ssm_client = SSMClient(environment_service=environment_service)

    ssm_service = SSMService(client=ssm_client)
    return ssm_service.get_secret_value(
        secret_name=MONGODB_CONNECTION_URI_PARAMETER)


def get_from_modular_sdk():
    from modular_sdk.commons.constants import (
        PARAM_MONGO_USER, PARAM_MONGO_DB_NAME,
        PARAM_MONGO_URL, PARAM_MONGO_PASSWORD
    )
    user = os.environ.get(PARAM_MONGO_USER)
    password = os.environ.get(PARAM_MONGO_PASSWORD)
    url = os.environ.get(PARAM_MONGO_URL)
    db = os.environ.get(PARAM_MONGO_DB_NAME)
    if all((user, password, url, db)):
        host, port = url.split(':')
        return {
            'host': host,
            'port': int(port),
            'username': user,
            'password': password,
            'db': db
        }


try:
    mongoengine.get_connection()
except mongoengine.ConnectionFailure:
    from commons.constants import MONGODB_CONNECTION_URI_PARAMETER

    _LOG.debug(f'Initializing mongoDB connection.')

    connection_uri = os.environ.get(MONGODB_CONNECTION_URI_PARAMETER)
    connection_kwargs = None
    if not connection_uri:
        _LOG.debug(f'Describing connection from ssm modular_sdk envs')
        connection_kwargs = get_from_modular_sdk()
    if not connection_uri and not connection_kwargs:
        _LOG.debug(f'Describing connection uri from ssm '
                   f'\'{MONGODB_CONNECTION_URI_PARAMETER}\'')
        connection_uri = get_from_ssm()
    if not connection_uri and not connection_kwargs:
        _LOG.error(f'Mongodb connection uri must be specified either in env '
                   f'variable or Parameter Store.')
        raise ExecutorException(
            step_name=JOB_STEP_INITIALIZATION,
            reason="Improperly Configured. Please contact the support team"
        )
    if connection_uri:
        mongoengine.connect(host=connection_uri)
    if connection_kwargs:
        mongoengine.connect(**connection_kwargs)
