import boto3

from commons.log_helper import get_logger
from services.environment_service import EnvironmentService

_LOG = get_logger('batch_service')


class BatchClient:

    def __init__(self, environment_service: EnvironmentService):
        self._environment = environment_service
        self._client = None

    @property
    def client(self):
        if not self._client:
            self._client = boto3.client(
                'batch', self._environment.aws_region())
        return self._client

    def submit_job(self, job_name: str, job_queue: str, job_definition: str,
                   command: str, size: int = None, depends_on: list = None,
                   parameters=None, retry_strategy: int = None,
                   timeout: int = None, environment_variables: dict = None):

        params = {
            'jobName': job_name,
            'jobQueue': job_queue,
            'jobDefinition': job_definition,
            'containerOverrides': {
                'command': command.split(' ')
            }
        }
        if size:
            params['arrayProperties'] = {'size': size}
        if depends_on:
            params['dependsOn'] = depends_on
        if parameters:
            params['parameters'] = parameters
        if retry_strategy:
            params['retryStrategy'] = {'attempts': retry_strategy}
        if timeout:
            params['timeout'] = {'attemptDurationSeconds': timeout}
        if environment_variables:
            container_overrides = {
                'environment': [{'name': key, 'value': value}
                                for key, value in
                                environment_variables.items()]
            }
            params['containerOverrides'].update(container_overrides)
        response = self.client.submit_job(**params)
        return response

    def terminate_job(self, job_id: str, reason: str = 'Terminating job.'):
        params = {
            'jobId': job_id,
            'reason': reason
        }
        response = self.client.terminate_job(**params)
        return response

    def describe_jobs(self, jobs: list):
        response = self.client.describe_jobs(jobs=jobs)
        if response:
            return response.get('jobs', [])
        return []

    def get_job_definition_by_name(self, job_def_name):
        _LOG.debug(f'Retrieving last job definition with name {job_def_name}')
        return self.client.describe_job_definitions(
            jobDefinitionName=job_def_name, status='ACTIVE',
            maxResults=1)['jobDefinitions']

    def create_job_definition(self, job_def_name, image_url, command, platform,
                              job_role_arn=None, resource_requirements=None):
        return self.client.register_job_definition(
            jobDefinitionName=job_def_name, type='container',
            containerProperties={
                'image': image_url, 'command': command,
                'jobRoleArn': job_role_arn,
                'resourceRequirements': resource_requirements,
            },
            platformCapabilities=platform
        )

    def create_job_definition_from_existing_one(self, job_def, image_url):
        job_def_name = job_def['jobDefinitionName']
        properties = job_def['containerProperties']
        if not properties:
            _LOG.debug('No containerProperties field in the last job '
                       'definition - cannot specify command, jobRoleArn')
            return None
        command = properties['command']
        job_role_arn = properties['jobRoleArn']
        resource_requirements = properties['resourceRequirements']
        platform = job_def['platformCapabilities']
        return self.create_job_definition(
            job_def_name=job_def_name, image_url=image_url, command=command,
            platform=platform, job_role_arn=job_role_arn,
            resource_requirements=resource_requirements)
