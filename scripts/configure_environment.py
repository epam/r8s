import argparse
import json
import os
import secrets
import string
import sys
from datetime import datetime, timedelta
from pathlib import Path

SYSTEM_ADMIN_USER_NAME = 'SYSTEM_ADMIN'
DEFAULT_COGNITO_USER_POOL_NAME = 'r8s'
IAM_PERMISSIONS_FILE_NAME = 'iam_permissions.json'
ADMIN_POLICY_FILE_NAME = 'admin_policy.json'


def load_local_json_file(file_name):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(dir_path, file_name)

    if not os.path.exists(file_path):
        print(f"File \'{file_path}\' does not exist")
        sys.exit(1)

    with open(file_path, 'r') as f:
        return json.load(f)


def create_iam_permissions():
    from models.setting import Setting
    iam_permissions = load_local_json_file(IAM_PERMISSIONS_FILE_NAME)
    name = iam_permissions.get('name')
    value = iam_permissions.get('value')
    setting = Setting(name=name, value=value)
    setting.save()
    return setting


def create_admin_policy():
    from models.policy import Policy
    admin_policy = load_local_json_file(ADMIN_POLICY_FILE_NAME)
    permissions = admin_policy.get('permissions')
    policy_name = admin_policy.get('name')

    policy = Policy(name=policy_name, permissions=permissions)
    policy.save()
    return policy


def create_admin_role(role_name: str, admin_policy):
    from models.role import Role
    today = datetime.date(datetime.today())
    expiration = today + timedelta(days=180)

    role = Role(
        name=role_name,
        policies=[admin_policy.name],
        expiration=expiration
    )
    role.save()
    return role


def generate_password():
    alphabet = string.ascii_letters + string.digits + '&*<>-_'
    password = ''.join(secrets.choice(alphabet) for _ in range(20))
    return password


def create_admin(role, username=SYSTEM_ADMIN_USER_NAME):
    from services import SERVICE_PROVIDER

    user_service = SERVICE_PROVIDER.user_service()
    password = generate_password()
    user_service.save(username=username,
                      password=password,
                      role=role.name,
                      customer='admin')
    return username, password


def parse_args():
    parser = argparse.ArgumentParser(
        description='Script for initial r8s environment configuration')
    parser.add_argument('-ak', '--access_key', help='AWS Access Key',
                        required=True)
    parser.add_argument('-sk', '--secret_key', help='AWS Secret Access Key',
                        required=True)
    parser.add_argument('-t', '--session_token', help='AWS Session Token',
                        required=True)
    parser.add_argument('-r', '--region', help='AWS Region', required=True)
    parser.add_argument('-uri', '--r8s_mongodb_connection_uri',
                        help='MongoDB Connection string', required=True)
    parser.add_argument('-p', '--cognito_user_pool_name',
                        help=f'R8s Cognito user pool name. '
                             f'Default: "{DEFAULT_COGNITO_USER_POOL_NAME}"',
                        default=DEFAULT_COGNITO_USER_POOL_NAME)
    return vars(parser.parse_args())


def export_args(access_key, secret_key, session_token,
                region, r8s_mongodb_connection_uri, cognito_user_pool_name):
    os.environ['AWS_ACCESS_KEY_ID'] = access_key
    os.environ['AWS_SECRET_ACCESS_KEY'] = secret_key
    os.environ['AWS_SESSION_TOKEN'] = session_token
    os.environ['AWS_REGION'] = region
    os.environ['r8s_mongodb_connection_uri'] = r8s_mongodb_connection_uri
    os.environ['cognito_user_pool_name'] = cognito_user_pool_name


def export_src_path():
    dir_path = Path(os.path.dirname(os.path.realpath(__file__))).parent
    src_path = os.path.join(dir_path, 'src')
    sys.path.append(src_path)


def main():
    print("Parsing arguments")
    args = parse_args()

    print('Exporting path to src')
    export_src_path()

    print('Exporting env variables')
    export_args(**args)

    print('Creating IAM_PERMISSIONS settings')
    create_iam_permissions()

    print('Creating admin policy')
    admin_policy = create_admin_policy()

    print('Creating admin role')
    admin_role = create_admin_role(role_name=admin_policy.name,
                                   admin_policy=admin_policy)

    print('Creating admin user')
    username, password = create_admin(role=admin_role,
                                      username='SYSTEM_ADMIN')
    print(username, password)


if __name__ == '__main__':
    main()
