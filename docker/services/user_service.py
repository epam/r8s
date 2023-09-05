from commons import ApplicationException, \
    build_response, RESPONSE_BAD_REQUEST_CODE
from commons.log_helper import get_logger
from services.clients.cognito import CognitoClient

_LOG = get_logger('cognito-client')


class CognitoUserService:

    def __init__(self, client: CognitoClient):
        self.client: CognitoClient = client

    def save(self, username, password, role):
        _LOG.debug(f'Validating password for user {username}')
        errors = self.__validate_password(password)
        if errors:
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='; '.join(errors))
        if self.client.is_user_exists(username):
            raise ApplicationException(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'The user with name {username} already exists.')

        _LOG.debug(f'Creating the user with username {username}')
        self.client.sign_up(username=username, password=password, role=role)
        _LOG.debug(f'Setting the password for the user {username}')
        self.client.set_password(username=username,
                                 password=password)

    def get_user(self, user_id):
        if isinstance(self.client, CognitoClient):
            return self.client.get_user(user_id)['Username']
        return self.client.get_user(user_id)

    def get_user_role_name(self, user):
        return self.client.get_user_role(user)

    @staticmethod
    def __validate_password(password):
        errors = []
        upper = any(char.isupper() for char in password)
        numeric = any(char.isdigit() for char in password)
        symbol = any(not char.isalnum() for char in password)
        if not upper:
            errors.append('Password must have uppercase characters')
        if not numeric:
            errors.append('Password must have numeric characters')
        if not symbol:
            errors.append('Password must have symbol characters')
        if len(password) < 8:
            errors.append(f'Invalid length. Valid min length: 8')

        if errors:
            return errors

    def initiate_auth(self, username, password):
        return self.client.admin_initiate_auth(username=username,
                                               password=password)

    def respond_to_auth_challenge(self, challenge_name):
        return self.client.respond_to_auth_challenge(
            challenge_name=challenge_name)

    def update_role(self, username, role):
        self.client.update_role(username=username, role=role)

    def is_user_exists(self, username):
        return self.client.is_user_exists(username)

    def delete_role(self, username):
        self.client.delete_role(username=username)

    def is_system_user_exists(self):
        return self.client.is_system_user_exists()

    def get_system_user(self):
        return self.client.get_system_user()
