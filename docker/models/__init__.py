import mongoengine
import os
from commons.exception import ExecutorException
from commons.constants import JOB_STEP_INITIALIZATION
from commons.log_helper import get_logger
from services.environment_service import EnvironmentService

_LOG = get_logger('r8s-mongo-initializer')

try:
    mongoengine.get_connection()
except mongoengine.ConnectionFailure:
    from services.clients.ssm import SSMClient, VaultSSMClient
    from services.ssm_service import SSMService
    environment_service = EnvironmentService()

    if environment_service.is_docker():
        ssm_client = VaultSSMClient(environment_service=environment_service)
    else:
        ssm_client = SSMClient(environment_service=environment_service)

    ssm_service = SSMService(client=ssm_client)
    from commons.constants import MONGODB_CONNECTION_URI_PARAMETER

    _LOG.debug(f'Initializing mongoDB connection.')
    _LOG.debug(f'Describing connection uri from ssm '
               f'\'{MONGODB_CONNECTION_URI_PARAMETER}\'')

    connection_uri = os.environ.get(
        MONGODB_CONNECTION_URI_PARAMETER)
    if not connection_uri:
        connection_uri = ssm_service.get_secret_value(
            secret_name=MONGODB_CONNECTION_URI_PARAMETER)
    if not connection_uri:
        _LOG.error(f'Mongodb connection uri must be specified either in env '
                   f'variable or Parameter Store.')
        raise ExecutorException(
            step_name=JOB_STEP_INITIALIZATION,
            reason="Improperly Configured. Please contact the support team"
        )
    mongoengine.connect(host=connection_uri)
