"""
Script for migrating r8s s3 metric format structure from timestamp-oriented,
where each timestamp folder represent several days/weeks of metrics,
into a structure where metrics are equally divided by days

Usage:
    python3 s3_patch_metric_format.py
    --minio_host $MINIO_HOST
    --minio_port $MINIO_PORT
    --access_key $MINIO_ACCESS_KEY
    --secret_key $MINIO_SECRET_KEY
    --region $REGION
    --metric_bucket_name $BUCKET_NAME
    --prefix $PREFIX
    --action $ACTION

Depends on the action, different step of the patch will be executed:
- DOWNLOAD - download metrics from s3 to local from the given bucket and prefix
- PATCH - Convert metric files according to new daily metric format
- UPLOAD - Upload patched metrics to S3
- CLEANUP - Delete old metric files from S3
"""

import argparse
import os
import pathlib
from datetime import datetime, timezone

import boto3
import pandas as pd
from botocore.config import Config

DATE_FORMAT = '%Y-%m-%d'

ACTION_DOWNLOAD = 'DOWNLOAD'
ACTION_PATCH = 'PATCH'
ACTION_UPLOAD = 'UPLOAD'
ACTION_CLEANUP = 'CLEANUP'


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-host', '--minio_host', help='MinIO host',
                        required=True)
    parser.add_argument('-port', '--minio_port', help='MinIO port',
                        required=True)
    parser.add_argument('-ak', '--access_key', help='MinIO Access Key',
                        required=False)
    parser.add_argument('-sk', '--secret_key', help='MinIO Secret Access Key',
                        required=False)
    parser.add_argument('-r', '--region', help='AWS Region', required=True)
    parser.add_argument('-mbn', '--metric_bucket_name',
                        help='MinIO Bucket name with r8s metrics',
                        required=True)
    parser.add_argument('-p', '--prefix', default='',
                        help='Metrics s3 prefix')
    parser.add_argument('--action', choices=[ACTION_DOWNLOAD, ACTION_PATCH,
                                             ACTION_UPLOAD, ACTION_CLEANUP],
                        required=True, action='append',
                        help='Determines script action.')
    return vars(parser.parse_args())


def export_args(minio_host, minio_port, access_key, secret_key,
                region, *args, **kwargs):
    os.environ['MINIO_HOST'] = minio_host
    os.environ['MINIO_PORT'] = minio_port
    os.environ['MINIO_ACCESS_KEY'] = access_key
    os.environ['MINIO_SECRET_ACCESS_KEY'] = secret_key
    os.environ['AWS_DEFAULT_REGION'] = region
    os.environ['AWS_REGION'] = region


def dateparse(time_in_secs):
    if len(str(time_in_secs)) > 10:  # if timestamp in milliseconds
        time_in_secs = time_in_secs[0:-3]
    dt = datetime.utcfromtimestamp(float(time_in_secs))
    dt = dt.replace(tzinfo=timezone.utc)
    return dt


def list_files(files):
    filtered = []
    for file in files:
        try:
            timestamp = file.parts[-2]
            timestamp = int(timestamp) / 1000
            dt = datetime.fromtimestamp(timestamp)
            if dt.year > 2022:
                filtered.append(file)
        except:
            pass
    return filtered


def process_file(file_path, output_folder_path, folder_prefix):
    df = load_df(file_path=file_path)

    df_list = divide_by_days(
        df=df, skip_incomplete_corner_days=False,
        step_minutes=5)
    folders = parse_metric_folders(file_path=file_path)

    for df_ in df_list:
        save_df(
            df=df_,
            output_folder_path=output_folder_path,
            folder_prefix=folder_prefix,
            folders=folders)


def parse_metric_folders(file_path):
    customer = file_path.parts[-6]
    cloud = file_path.parts[-5]
    tenant = file_path.parts[-4]
    region = file_path.parts[-3]
    instance_id = file_path.parts[-1]

    return [customer, cloud, tenant, region, instance_id]


def load_df(file_path):
    df = pd.read_csv(file_path, parse_dates=True,
                     date_parser=dateparse,
                     index_col="timestamp"
                     )

    return df


def divide_by_days(df, skip_incomplete_corner_days: bool,
                   step_minutes: int):
    df_list = [group[1] for group in df.groupby(df.index.date)]
    if not df_list:
        return df_list

    if len(df_list) > 30 and skip_incomplete_corner_days:
        last_day_df = df_list[-1]
        if len(last_day_df) < 24 * 60 // step_minutes:
            df_list = df_list[:-1]
        first_day_df = df_list[0]
        if len(first_day_df) < 24 * 60 // step_minutes:
            df_list = df_list[1:]
    return df_list


def to_timestamp(timestamp):
    return int(timestamp.timestamp())


def save_df(df, output_folder_path, folders: list, folder_prefix):
    date_str = df.index.min().strftime(DATE_FORMAT)
    customer, cloud, tenant, region, instance_id = folders

    output_folder_path = os.path.join(
        output_folder_path, folder_prefix, customer, cloud, tenant, region,
        date_str
    )
    pathlib.Path(output_folder_path).mkdir(parents=True, exist_ok=True)

    output_file_path = os.path.join(output_folder_path, instance_id)
    df.reset_index(inplace=True)
    df['timestamp'] = df['timestamp'].apply(
        lambda timestamp: int(timestamp.timestamp()))

    columns_order = [
        'instance_id',
        'instance_type',
        'timestamp',
        'cpu_load',
        'memory_load',
        'net_output_load',
        'avg_disk_iops',
        'max_disk_iops',
    ]

    df = df[columns_order]
    df.to_csv(output_file_path, index=False)


def download_dir(prefix, local, bucket, client):
    """
    params:
    - prefix: pattern to match in s3
    - local: local path to folder in which to place files
    - bucket: s3 bucket with target contents
    - client: initialized s3 client object
    """
    keys = []
    dirs = []
    next_token = ''
    base_kwargs = {
        'Bucket': bucket,
        'Prefix': prefix,
    }
    while next_token is not None:
        kwargs = base_kwargs.copy()
        if next_token != '':
            kwargs.update({'ContinuationToken': next_token})
        results = client.list_objects_v2(**kwargs)
        contents = results.get('Contents')
        for i in contents:
            k = i.get('Key')
            if k[-1] != '/':
                keys.append(k)
            else:
                dirs.append(k)
        next_token = results.get('NextContinuationToken')
    for d in dirs:
        dest_pathname = os.path.join(local, d)
        if not os.path.exists(os.path.dirname(dest_pathname)):
            os.makedirs(os.path.dirname(dest_pathname))
    for k in keys:
        dest_pathname = os.path.join(local, k)
        if not os.path.exists(os.path.dirname(dest_pathname)):
            os.makedirs(os.path.dirname(dest_pathname))
        client.download_file(bucket, k, dest_pathname)
    return keys


def upload_dir(folder_file_path, bucket_name, client):
    files = list(pathlib.Path(folder_file_path).rglob("*.csv"))
    folder_file_path = folder_file_path.strip('./')
    for file in files:
        key = str(file).replace(folder_file_path, '').strip('/')
        with open(file, 'rb') as f:
            client.put_object(
                Body=f.read(),
                Bucket=bucket_name,
                Key=key
            )


def delete_s3_keys(client, bucket, folder_path: str):
    keys_to_delete = []
    folder_path = folder_path.strip('./')
    for type_ in ('.csv', '.json'):
        files = list(pathlib.Path(folder_path).rglob(f"*{type_}"))
        for file in files:
            key = str(file).replace(folder_path, '').strip('/')
            keys_to_delete.append(key)

    for key in keys_to_delete:
        try:
            client.delete_object(
                Bucket=bucket,
                Key=str(key),
            )
        except:
            pass


def main():
    print("Parsing arguments")
    args = parse_args()

    local_folder = os.path.join(pathlib.Path(__file__).parent,
                                'temp-pre-patched')
    patched = os.path.join(pathlib.Path(__file__).parent, 'temp-patched')
    pathlib.Path(local_folder).mkdir(exist_ok=True)

    print('Exporting env variables')
    export_args(**args)

    print('Initializing MinIO client')
    config = Config(retries={
        'max_attempts': 10,
        'mode': 'standard'
    })
    config = config.merge(Config(s3={
        'signature_version': 's3v4',
        'addressing_style': 'path'
    }))
    session = boto3.Session(
        aws_access_key_id=args.get('access_key'),
        aws_secret_access_key=args.get('secret_key')
    )
    url = f'http://{args.get("minio_host")}:{args.get("minio_port")}'
    client = session.client('s3', endpoint_url=url, config=config)

    bucket_name = args['metric_bucket_name']
    prefix = args['prefix']

    allowed_actions = args.get('action')

    if ACTION_DOWNLOAD in allowed_actions:
        print('Downloading metrics from S3')
        download_dir(
            local=local_folder,
            bucket=bucket_name,
            prefix=prefix,
            client=client
        )
        print(f'S3 files were downloaded to {local_folder}')

    if ACTION_PATCH in allowed_actions:
        print('Patching metric files')
        files = list(pathlib.Path(local_folder).rglob("*.csv"))
        file_paths = list_files(files=files)

        for file_path in file_paths:
            process_file(
                file_path=file_path,
                output_folder_path=patched,
                folder_prefix=prefix
            )
        print(f'Patched metrics were saved to {patched}')
    if ACTION_UPLOAD in allowed_actions:
        print('Uploading patched metrics')
        upload_dir(
            folder_file_path=patched,
            bucket_name=bucket_name,
            client=client
        )
        print('Patched metrics have been uploaded')

    if ACTION_CLEANUP in allowed_actions:
        print('Removing old metric files from s3')
        delete_s3_keys(
            client=client,
            bucket=bucket_name,
            folder_path=local_folder
        )
        print('Old metrics have been removed from s3')


if __name__ == '__main__':
    main()
