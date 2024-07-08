from typing import Iterable

from services import SERVICE_PROVIDER

environment = SERVICE_PROVIDER.environment_service()
BUCKETS = [
    "r8s-metrics",
    "r8s-results"
]


def create_buckets(buckets: Iterable[str]) -> None:
    client = SERVICE_PROVIDER.s3()
    env = SERVICE_PROVIDER.environment_service()
    for buckets_name in buckets:
        if client.is_bucket_exists(bucket_name=buckets_name):
            print(f'Bucket with name \'{buckets_name}\' already exists. '
                  f'Skipping..')
            continue
        client.create_bucket(
            bucket_name=buckets_name,
            region=env.aws_region() or 'eu-central-1'
        )
        print(f'Bucket {buckets_name} created.')


def init_minio():
    create_buckets(BUCKETS)


if __name__ == '__main__':
    init_minio()
