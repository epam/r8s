from datetime import datetime
from typing import Union

import boto3

from commons import ApplicationException, RESPONSE_INTERNAL_SERVER_ERROR, \
    RESPONSE_BAD_REQUEST_CODE, get_iso_timestamp
from commons.log_helper import get_logger
from connections.auth_extension.base_auth_client import BaseAuthClient

_LOG = get_logger('cognitoclient')
CUSTOM_ROLE_ATTR = 'custom:r8s_role'
CUSTOM_CUSTOMER_ATTR = 'custom:customer'
CUSTOM_LATEST_LOGIN_ATTR = 'custom:latest_login'
SUB_ATTR = 'sub'

PARAM_USER_POOLS = 'UserPools'


class CognitoClient(BaseAuthClient):
    def __init__(self, environment_service):
        region = environment_service.aws_region()
        self.client = boto3.client('cognito-idp', region)
        self.user_pool_name = environment_service.get_user_pool_name()

    def list_user_pools(self):
        list_user_pools = self.client.list_user_pools(MaxResults=10)
        pools = []
        while list_user_pools[PARAM_USER_POOLS]:
            pools.extend(list_user_pools[PARAM_USER_POOLS])
            next_token = list_user_pools.get('NextToken')
            if next_token:
                list_user_pools = self.client.list_user_pools(
                    MaxResults=10, NextToken=next_token)
            else:
                break
        return pools

    def list_users(self, attributes_to_get=None):
        params = dict(UserPoolId=self.__get_user_pool_id())
        if attributes_to_get:
            params['AttributesToGet'] = attributes_to_get
        users = self.client.list_users(**params)
        return self._format_users(users)

    def admin_initiate_auth(self, username, password):
        """
        Initiates the authentication flow. Returns AuthenticationResult if
        the caller does not need to pass another challenge. If the caller
        does need to pass another challenge before it gets tokens,
        ChallengeName, ChallengeParameters, and Session are returned.
        """
        user_pool_id = self.__get_user_pool_id()
        client_id = self.__get_client_id()
        auth_params = {
            'USERNAME': username,
            'PASSWORD': password
        }
        if self.is_user_exists(username):
            try:
                result = self.client.admin_initiate_auth(
                    UserPoolId=user_pool_id, ClientId=client_id,
                    AuthFlow='ADMIN_NO_SRP_AUTH', AuthParameters=auth_params)
                self.update_latest_login(username)
                return result
            except self.client.exceptions.NotAuthorizedException:
                return None

    def respond_to_auth_challenge(self, challenge_name):
        """
        Responds to an authentication challenge.
        """
        client_id = self.__get_client_id()
        self.client.respond_to_auth_challenge(ClientId=client_id,
                                              ChallengeName=challenge_name)

    def sign_up(self, username, password, customer, role, tenants=None):
        client_id = self.__get_client_id()
        custom_attr = [{
            'Name': 'name',
            'Value': username
        }, {
            'Name': CUSTOM_CUSTOMER_ATTR,
            'Value': customer
        }, {
            'Name': CUSTOM_ROLE_ATTR,
            'Value': role
        }]
        validation_data = [
            {
                'Name': 'name',
                'Value': username
            }
        ]
        return self.client.sign_up(ClientId=client_id,
                                   Username=username,
                                   Password=password,
                                   UserAttributes=custom_attr,
                                   ValidationData=validation_data)

    def set_password(self, username, password, permanent=True):
        user_pool_id = self.__get_user_pool_id()
        return self.client.admin_set_user_password(UserPoolId=user_pool_id,
                                                   Username=username,
                                                   Password=password,
                                                   Permanent=permanent)

    def __get_client_id(self):
        user_pool_id = self.__get_user_pool_id()
        client = self.client.list_user_pool_clients(
            UserPoolId=user_pool_id, MaxResults=1)['UserPoolClients']
        if not client:
            _LOG.error('Application Authentication Service is not configured '
                       'properly: no client applications found')
            raise ApplicationException(
                code=RESPONSE_INTERNAL_SERVER_ERROR,
                content='Application Authentication Service is not configured '
                        'properly.')
        return client[0]['ClientId']

    def get_user_pool(self, user_pool_name):
        for pool in self.list_user_pools():
            if pool.get('Name') == user_pool_name:
                return pool['Id']

    def get_user(self, username):
        users = self.is_user_exists(username=username)
        if users:
            return users[0]
        _LOG.error(f'No user with username {username} was found')
        raise ApplicationException(
            code=RESPONSE_BAD_REQUEST_CODE,
            content=f'No user with username {username} was found')

    def is_user_exists(self, username):
        user_pool_id = self.__get_user_pool_id()
        users = self.client.list_users(
            UserPoolId=user_pool_id,
            Filter=f'username = "{username}"')
        users = self._format_users(users)
        return users

    def _get_user_attr(self, user, attr_name, query_user=True):
        """user attribute can be either a 'username' or a user dict object
        already fetched from AWS Cognito"""
        if query_user:
            user = self.get_user(username=user)
        for attr in user['Attributes']:
            if attr['Name'] == attr_name:
                return attr['Value']

    def get_user_role(self, username):
        return self._get_user_attr(username, CUSTOM_ROLE_ATTR)

    def get_user_id(self, username):
        return self._get_user_attr(username, SUB_ATTR)

    def update_role(self, username, role):
        user_pool_id = self.__get_user_pool_id()
        role_attribute = [
            {
                'Name': CUSTOM_ROLE_ATTR,
                'Value': role
            }
        ]
        self.client.admin_update_user_attributes(UserPoolId=user_pool_id,
                                                 Username=username,
                                                 UserAttributes=role_attribute)

    def update_customer(self, username, customer):
        user_pool_id = self.__get_user_pool_id()
        customer_attribute = [
            {
                'Name': CUSTOM_CUSTOMER_ATTR,
                'Value': customer
            }
        ]
        self.client.admin_update_user_attributes(
            UserPoolId=user_pool_id, Username=username,
            UserAttributes=customer_attribute)

    def delete_customer(self, username):
        user_pool_id = self.__get_user_pool_id()
        self.client.admin_delete_user_attributes(
            UserPoolId=user_pool_id, Username=username,
            UserAttributes=[CUSTOM_CUSTOMER_ATTR])

    def get_user_latest_login(self, username):
        return self._get_user_attr(username, CUSTOM_LATEST_LOGIN_ATTR)

    def update_latest_login(self, username: str,
                            latest_login: Union[str, datetime, None] = None):
        latest_login = latest_login or get_iso_timestamp()
        user_pool_id = self.__get_user_pool_id()
        if isinstance(latest_login, datetime):
            latest_login = latest_login.isoformat()
        latest_login_attribute = [
            {
                'Name': CUSTOM_LATEST_LOGIN_ATTR,
                'Value': latest_login
            }
        ]
        self.client.admin_update_user_attributes(
            UserPoolId=user_pool_id, Username=username,
            UserAttributes=latest_login_attribute)

    def delete_role(self, username):
        user_pool_id = self.__get_user_pool_id()
        self.client.admin_delete_user_attributes(
            UserPoolId=user_pool_id, Username=username,
            UserAttributeNames=[CUSTOM_ROLE_ATTR])

    def __get_user_pool_id(self):
        user_pools = self.list_user_pools()
        user_pool = [pool for pool in user_pools
                     if pool['Name'] == self.user_pool_name]
        if not user_pool:
            _LOG.error(f'User pool {self.user_pool_name} does not exists')
            raise ApplicationException(
                code=RESPONSE_INTERNAL_SERVER_ERROR,
                content='Application Authentication Service is '
                        'not configured properly.')

        user_pool_id = user_pool[0].get('Id')
        _LOG.debug(f'Retrieving the user pool with id {user_pool_id}')
        return user_pool_id

    def is_system_user_exists(self):
        """Checks whether user with customer='SYSTEM' already exists"""
        raise NotImplementedError()

    def get_system_user(self):
        """Returns the user with customer='SYSTEM' if exists, else - None"""
        raise NotImplementedError()

    def get_user_customer(self, username):
        return self._get_user_attr(username, CUSTOM_CUSTOMER_ATTR)

    def delete_user(self, username):
        return self.client.admin_delete_user(
            UserPoolId=self.__get_user_pool_id(),
            Username=username
        )

    @staticmethod
    def _format_users(users):
        formatted_users = []
        for user in users:
            user_item = {'username': user.get('Username')}
            for attribute in user.get('Attributes', []):
                user_item[attribute['Name']] = attribute['Value']
            formatted_users.append(user_item)
        return formatted_users
