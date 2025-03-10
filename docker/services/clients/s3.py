import json
import os

import boto3
from botocore.config import Config

from commons.constants import ENV_SERVICE_MODE_S3, DOCKER_SERVICE_MODE, \
    ENV_MINIO_HOST, ENV_MINIO_PORT, ENV_MINIO_ACCESS_KEY, \
    ENV_MINIO_SECRET_ACCESS_KEY, ENV_MINIO_ROOT_USER, \
    ENV_MINIO_ROOT_PASSWORD, ENV_MINIO_ENDPOINT, ENV_SERVICE_MODE
from commons.log_helper import get_logger

UTF_8_ENCODING = 'utf-8'

_LOG = get_logger('s3client')


class S3Client:
    IS_DOCKER = os.getenv(
        ENV_SERVICE_MODE_S3, os.getenv(ENV_SERVICE_MODE)
    ) == DOCKER_SERVICE_MODE

    def __init__(self, region):
        self.region = region
        self._client = None
        self._resource = None

    def build_config(self) -> Config:
        config = Config(retries={
            'max_attempts': 10,
            'mode': 'standard'
        })
        if self.IS_DOCKER:
            config = config.merge(Config(s3={
                'signature_version': 's3v4',
                'addressing_style': 'path'
            }))
        return config

    def _init_clients(self):
        config = self.build_config()
        if self.IS_DOCKER:
            host, port = os.getenv(ENV_MINIO_HOST), os.getenv(ENV_MINIO_PORT)
            endpoint = os.getenv(ENV_MINIO_ENDPOINT)
            url = None
            if endpoint:
                url = endpoint
            elif host and port:
                url = f'http://{host}:{port}'
            access_key = os.getenv(ENV_MINIO_ACCESS_KEY,
                                   os.getenv(ENV_MINIO_ROOT_USER))
            secret_access_key = os.getenv(ENV_MINIO_SECRET_ACCESS_KEY,
                                          os.getenv(ENV_MINIO_ROOT_PASSWORD))
            assert url, (f"\'{ENV_MINIO_ENDPOINT}\' or \'{ENV_MINIO_HOST}\' "
                         f"and \'{ENV_MINIO_PORT}\' envs must be specified "
                         f"for on-prem")
            assert (access_key and secret_access_key), \
                f"\'{ENV_MINIO_ACCESS_KEY}\', " \
                f"\'{ENV_MINIO_SECRET_ACCESS_KEY}\' envs must be specified " \
                f"for on-prem"
            session = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_access_key
            )
            self._client = session.client('s3', endpoint_url=url,
                                          config=config)
            self._resource = session.resource('s3', endpoint_url=url,
                                              config=config)
            _LOG.info('Minio connection was successfully initialized')
        else:  # saas
            self._client = boto3.client('s3', self.region, config=config)
            self._resource = boto3.resource('s3', self.region, config=config)
            _LOG.info('S3 connection was successfully initialized')

    @property
    def client(self):
        if not self._client:
            self._init_clients()
        return self._client

    @property
    def resource(self):
        if not self._resource:
            self._init_clients()
        return self._resource

    def file_exists(self, bucket_name, key):
        """
        Checks if object with the given key exists in bucket.
        :return: True if exists, else False
        """
        existing_objects = self.list_objects(bucket_name=bucket_name)
        existing_keys = [obj['Key'] for obj in existing_objects]
        _LOG.debug('Available s3 keys: {0}'.format(existing_keys))
        return key in existing_keys

    def put_object(self, bucket_name, object_name, body):
        s3_object = self.resource.Object(bucket_name, object_name)
        return s3_object.put(Body=body, ContentEncoding='utf-8')

    def is_bucket_exists(self, bucket_name):
        """
        Check if specified bucket exists.
        :param bucket_name: name of the bucket to check;
        :return: True is exists, otherwise - False
        """
        existing_buckets = self._list_buckets()
        return bucket_name in existing_buckets

    def _list_buckets(self):
        response = self.client.list_buckets()
        return [bucket['Name'] for bucket in response.get("Buckets")]

    def get_json_file_content(self, bucket_name, full_file_name):
        """
        Returns content of the object.
        :param bucket_name: name of the bucket.
        :param full_file_name: name of the file including its folders.
            Example: /folder1/folder2/file_name.json
        :return: content of the file
        """
        response = self.client.get_object(
            Bucket=bucket_name,
            Key=full_file_name
        )
        streaming_body = response.get('Body')
        if streaming_body:
            return json.loads(streaming_body.read())

    def get_json_lines_file_content(self, bucket_name, full_file_name):
        response = self.client.get_object(
            Bucket=bucket_name,
            Key=full_file_name
        )
        streaming_body = response.get('Body')
        body = streaming_body.read()
        lines = body.decode().split('\n')
        return [json.loads(line) for line in lines if line.strip()]

    def get_file_content(self, bucket_name, full_file_name,
                         decode=False):
        """
        Returns content of the object.
        :param bucket_name: name of the bucket.
        :param full_file_name: name of the file including its folders.
            Example: /folder1/folder2/file_name.json
        :param decode: flag
        :return: content of the file
        """
        response = self.client.get_object(
            Bucket=bucket_name,
            Key=full_file_name
        )
        streaming_body = response.get('Body')
        if decode:
            return streaming_body.read().decode(UTF_8_ENCODING)
        return streaming_body.read()

    def put_object_encrypted(self, bucket_name, object_name, body):
        return self.client.put_object(
            Body=body,
            Bucket=bucket_name,
            Key=object_name,
            ServerSideEncryption='AES256')

    def list_objects(self, bucket_name, prefix=None):
        result_keys = []
        params = dict(Bucket=bucket_name)
        if prefix:
            params['Prefix'] = prefix
        response = self.client.list_objects_v2(**params)
        if not response.get('Contents'):
            return None
        result_keys.extend(item for item in response['Contents'])
        while response['IsTruncated'] is True:
            token = response['NextContinuationToken']
            params['ContinuationToken'] = token
            response = self.client.list_objects_v2(**params)
            result_keys.extend(item for item in response['Contents'])
        return result_keys

    def list_objects_gen(self, bucket_name, prefix=None, only_keys=False):
        params = dict(Bucket=bucket_name)
        if prefix:
            params['Prefix'] = prefix
        response = self.client.list_objects_v2(**params)
        if not response.get('Contents'):
            return
        for item in response['Contents']:
            yield item['Key'] if only_keys else item

        while response['IsTruncated'] is True:
            token = response['NextContinuationToken']
            params['ContinuationToken'] = token
            response = self.client.list_objects_v2(**params)
            for item in response['Contents']:
                yield item['Key'] if only_keys else item

    def delete_file(self, bucket_name, file_key):
        self.resource.Object(bucket_name, file_key).delete()

    def generate_presigned_url(self, bucket_name, full_file_name,
                               client_method='get_object',
                               http_method='GET',
                               expires_in_sec=300):
        return self.client.generate_presigned_url(
            ClientMethod=client_method,
            Params={
                'Bucket': bucket_name,
                'Key': full_file_name,
            },
            ExpiresIn=expires_in_sec,
            HttpMethod=http_method
        )

    def generate_presigned_post_url(self, bucket_name, object_name,
                                    fields=None, conditions=None,
                                    expiration=300):
        response = self.client.generate_presigned_post(bucket_name,
                                                       object_name,
                                                       Fields=fields,
                                                       Conditions=conditions,
                                                       ExpiresIn=expiration)
        return response

    def list_dir(self, bucket_name, key):
        objects = self.list_objects(bucket_name, key)
        if objects:
            return [obj['Key'] for obj in objects]
        return []

    def download_file(self, bucket_name, full_file_name, output_folder_path):
        file_name = os.path.split(full_file_name)[-1]
        output_file_path = os.path.join(output_folder_path, file_name)

        with open(output_file_path, 'wb') as f:
            content = self.get_file_content(
                bucket_name=bucket_name,
                full_file_name=full_file_name
            )
            f.write(content)
        return output_file_path

    def create_bucket(self, bucket_name, region=None):
        region = region or self.region
        self.client.create_bucket(
            Bucket=bucket_name, CreateBucketConfiguration={
                'LocationConstraint': region
            }
        )
