"""
Script for migrating r8s s3 metric format structure from timestamp-oriented,
where each timestamp folder represent several days/weeks of metrics,
into a structure where metrics are equally divided by days

Usage:
    python3 s3_patch_metric_format.py
    --access_key $ACCESS_KEY
    --secret_key $SECRET_KEY
    --session_token $SESSION_TOKEN
    --region $REGION
    --metric_bucket_name $BUCKET_NAME
    --prefix $PREFIX
"""

import argparse
import os
import pathlib
from datetime import datetime, timezone

import boto3
import pandas as pd

DATE_FORMAT = '%Y_%m_%d'


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-ak', '--access_key', help='AWS Access Key',
                        required=True)
    parser.add_argument('-sk', '--secret_key', help='AWS Secret Access Key',
                        required=True)
    parser.add_argument('-t', '--session_token', help='AWS Session Token',
                        required=True)
    parser.add_argument('-r', '--region', help='AWS Region', required=True)
    parser.add_argument('-mbn', '--metric_bucket_name',
                        help='S3 Bucket name with r8s metrics', required=True)
    parser.add_argument('-p', '--prefix', default='',
                        help='Metrics s3 prefix')
    return vars(parser.parse_args())


def export_args(access_key, secret_key, session_token,
                region, *args, **kwargs):
    os.environ['AWS_ACCESS_KEY_ID'] = access_key
    os.environ['AWS_SECRET_ACCESS_KEY'] = secret_key
    os.environ['AWS_SESSION_TOKEN'] = session_token
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

    for file in files:
        key = str(file).replace(folder_file_path, '').strip('/')
        with open(file, 'rb') as f:
            client.put_object(
                Body=f.read(),
                Bucket=bucket_name,
                Key=key
            )


def delete_s3_keys(client, bucket, keys: list):
    for key in keys:
        client.delete_object(
            Bucket=bucket,
            Key=str(key),
        )


def main():
    print("Parsing arguments")
    args = parse_args()

    local_folder = os.path.join(pathlib.Path(__file__).parent,
                                'temp-pre-patched')
    patched = os.path.join(pathlib.Path(__file__).parent, 'temp-patched')
    pathlib.Path(local_folder).mkdir(exist_ok=True)

    print('Exporting env variables')
    export_args(**args)

    print('Downloading metrics from S3')
    client = boto3.client('s3')
    bucket_name = args['metric_bucket_name']
    prefix = args['prefix']
    s3_keys = download_dir(
        local=local_folder,
        bucket=bucket_name,
        prefix=prefix,
        client=client
    )
    keys_to_delete = list_files(files=[pathlib.Path(key) for key in s3_keys])

    print('Patching metric files')
    files = list(pathlib.Path(local_folder).rglob("*.csv"))
    file_paths = list_files(files=files)

    for file_path in file_paths:
        process_file(
            file_path=file_path,
            output_folder_path=patched,
            folder_prefix=prefix
        )

    print('Uploading patched metrics')
    upload_dir(
        folder_file_path=patched,
        bucket_name=bucket_name,
        client=client
    )
    print('Removing old metric files from s3')
    delete_s3_keys(
        client=client,
        bucket=bucket_name,
        keys=keys_to_delete
    )


if __name__ == '__main__':
    main()
