from abc import abstractmethod

from modular_sdk.modular import Modular

from commons import build_response, ApplicationException, \
    RESPONSE_INTERNAL_SERVER_ERROR, RESPONSE_FORBIDDEN_CODE, secure_event
from commons import validate_params
from commons.constants import MCP_USER_CONTEXT_HEADER, MCP_JWT_KEY_SSM_NAME, \
    PARAM_USER_TENANT_ACCESS
from commons.log_helper import get_logger
from services import SERVICE_PROVIDER
from services.rbac.endpoint_to_permission_mapping import \
    ENDPOINT_PERMISSION_MAPPING

PARAM_USER_ID = 'user_id'
PARAM_REQUEST_PATH = 'request_path'
PARAM_HTTP_METHOD = 'http_method'
PARAM_CUSTOMER = 'customer'
PARAM_USER_CUSTOMER = 'user_customer'
REQUEST_CONTEXT = None

_LOG = get_logger('abstract-api-handler-lambda')

# Module-level cache for (key, algorithm) to avoid repeated SSM/Settings calls
_mcp_jwt_key_algorithm_cache: dict = {}
_MCP_JWT_CACHE_KEY = 'mcp_jwt_auth'


def _load_mcp_jwt_key_and_algorithm() -> tuple[str | None, str]:
    settings = SERVICE_PROVIDER.settings_service()
    configuration = settings.get_mcp_jwt_auth_configuration(value=True)
    if not isinstance(configuration, dict) or not configuration:
        _LOG.warning('MCP JWT auth setting is not configured')
        return None, 'RS256'
    algorithm = configuration.get('algorithm') or 'RS256'
    key = SERVICE_PROVIDER.ssm_service().get_secret_value(MCP_JWT_KEY_SSM_NAME)
    if isinstance(key, dict):
        key = key.get('value')
    if not isinstance(key, str):
        key = None
    if key:
        key = _normalize_pem(key)
    return key, algorithm


def _normalize_pem(key: str) -> str:
    """Reconstruct proper PEM formatting if newlines were replaced with spaces."""
    if '\n' in key:
        return key
    if '-----BEGIN' not in key:
        return key
    key = key.strip()
    begin_end = '-----BEGIN PUBLIC KEY-----'
    end_end = '-----END PUBLIC KEY-----'
    if not key.startswith(begin_end) or not key.endswith(end_end):
        return key
    body = key[len(begin_end):key.rfind(end_end)].strip()
    body = body.replace(' ', '')
    body_lines = [body[i:i + 64] for i in range(0, len(body), 64)]
    return begin_end + '\n' + '\n'.join(body_lines) + '\n' + end_end


def _resolve_mcp_jwt_key_and_algorithm() -> tuple[str | None, str]:
    cached = _mcp_jwt_key_algorithm_cache.get(_MCP_JWT_CACHE_KEY)
    if cached is not None:
        return cached
    resolved = _load_mcp_jwt_key_and_algorithm()
    if resolved[0]:
        _mcp_jwt_key_algorithm_cache[_MCP_JWT_CACHE_KEY] = resolved
    return resolved


def _validate_mcp_context_token(token: str) -> dict | None:
    """
    Validates the MCP JWT token. Returns decoded claims on success.
    Returns None and logs a warning if the key is not configured.
    Raises ApplicationException(403) on invalid/expired token.
    """
    key, algorithm = _resolve_mcp_jwt_key_and_algorithm()
    if not key:
        _LOG.warning(
            'MCP JWT key is not configured — cannot validate MCP context token'
        )
        raise ApplicationException(
            code=RESPONSE_FORBIDDEN_CODE,
            content='MCP user context token is invalid',
        )
    is_asymmetric = algorithm.upper().startswith(('RS', 'ES', 'PS'))
    service = Modular().jwt_token_service(
        secret_key=key,
        algorithm=algorithm,
        public_key=key if is_asymmetric else None,
    )
    try:
        claims: dict = service.decode(token, verify_exp=True)
    except service.jwt.ExpiredSignatureError:
        _LOG.warning('MCP user context token has expired')
        raise ApplicationException(
            code=RESPONSE_FORBIDDEN_CODE,
            content='MCP user context token is invalid',
        )
    except (service.jwt.DecodeError, service.jwt.InvalidTokenError) as e:
        _LOG.warning(f'MCP user context token is invalid: {e}')
        raise ApplicationException(
            code=RESPONSE_FORBIDDEN_CODE,
            content='MCP user context token is invalid',
        )
    if not claims.get('customer_id'):
        _LOG.warning('MCP user context token does not contain customer_id')
        raise ApplicationException(
            code=RESPONSE_FORBIDDEN_CODE,
            content='MCP user context token is invalid',
        )
    return claims


def _resolve_local_mcp_user(claims: dict) -> str | None:
    """
    Returns the local r8s username (email) if a user with the claims email
    exists locally and belongs to the same customer as the JWT claims.
    Returns None if no matching local user is found.
    """
    email = claims.get('email')
    if not email:
        return None
    user_service = SERVICE_PROVIDER.user_service()
    if not user_service.is_user_exists(username=email):
        return None
    customer_id = claims.get('customer_id')
    if customer_id:
        user_customer = user_service.get_user_customer(email)
        if user_customer and user_customer != customer_id:
            _LOG.warning(
                f'Local user {email!r} belongs to customer '
                f'{user_customer!r} which differs from MCP token customer '
                f'{customer_id!r}. Ignoring local user'
            )
            return None
    return email


class AbstractApiHandlerLambda:

    @abstractmethod
    def validate_request(self, event) -> dict:
        """
        Validates event attributes
        :param event: lambda incoming event
        :return: dict with attribute_name in key and error_message in value
        """
        pass

    @abstractmethod
    def handle_request(self, event, context):
        """
        Inherited lambda function code
        :param event: lambda event
        :param context: lambda context
        :return:
        """
        pass

    def lambda_handler(self, event, context):
        try:
            _LOG.debug(f'Request: {secure_event(event=event)}')

            _LOG.debug('Checking user permissions')
            validate_params(event=event,
                            required_params_list=[PARAM_REQUEST_PATH,
                                                  PARAM_HTTP_METHOD])
            target_permission = self.__get_target_permission(event=event)
            if not target_permission:  # required to access signup/signin
                _LOG.debug(f'No permissions provided for the given endpoint: '
                           f'{event.get(PARAM_REQUEST_PATH)} and method: '
                           f'{event.get(PARAM_HTTP_METHOD)}')
            else:
                validate_params(event=event,
                                required_params_list=[PARAM_USER_ID])
                headers = event.get('headers') or {}
                mcp_context_header = next(
                    (v for k, v in headers.items()
                     if k.lower() == MCP_USER_CONTEXT_HEADER.lower()),
                    None
                )

                # Step 1: validate MCP JWT if present; 403 on bad token
                claims = None
                local_mcp_user = None
                if mcp_context_header:
                    claims = _validate_mcp_context_token(mcp_context_header)
                    local_mcp_user = _resolve_local_mcp_user(claims)
                    if local_mcp_user:
                        _LOG.info(
                            f'Local MCP user {local_mcp_user!r} found, '
                            f'switching identity'
                        )
                        event[PARAM_USER_ID] = local_mcp_user

                # Step 2: native permission check (under original or switched
                # identity if a local MCP user was found)
                ac_service = SERVICE_PROVIDER.access_control_service()
                if not ac_service.is_allowed_to_access(
                        event=event,
                        target_permission=target_permission
                ):
                    _LOG.debug(
                        f'User {event.get(PARAM_USER_ID)!r} is not allowed '
                        f'to access the resource: '
                        f'{event.get(PARAM_REQUEST_PATH)}'
                    )
                    return build_response(
                        code=RESPONSE_FORBIDDEN_CODE,
                        content=f'You are not allowed to access the resource '
                                f'{target_permission}')

                # Step 3: if JWT was valid but no local user found, expand
                # tenant access with live positions from Maestro
                if claims and not local_mcp_user:
                    customer = claims.get('customer_id')
                    if customer:
                        positions = SERVICE_PROVIDER.rabbitmq_service()\
                            .get_user_positions(customer=customer,
                                                claims=claims)
                        if positions:
                            tap = event.get(PARAM_USER_TENANT_ACCESS)
                            if tap:
                                tenant_names = {
                                    p['tenant'] for p in positions
                                    if p.get('tenant')
                                }
                                _LOG.debug(
                                    f'Expanding tenant access with Maestro '
                                    f'positions: {tenant_names}'
                                )
                                tap.allow_tenants(tenant_names)

                _LOG.debug(
                    f'Resolved tenant access payload: '
                    f'{event.get(PARAM_USER_TENANT_ACCESS)}'
                )
            errors = self.validate_request(event=event)
            if errors:
                return build_response(code=400,
                                      content=errors)
            execution_result = self.handle_request(event=event,
                                                   context=context)
            _LOG.debug(f'Response: {secure_event(execution_result)}')
            return execution_result
        except ApplicationException as e:
            _LOG.error(f'Error occurred; Event: {secure_event(event)}; '
                       f'Error: {e}')
            return build_response(code=e.code,
                                  content=e.content)
        except Exception as e:
            _LOG.error(
                f'Unexpected error occurred; Event: {secure_event(event)}; '
                f'Error: {e}')
            return build_response(code=RESPONSE_INTERNAL_SERVER_ERROR,
                                  content='Internal server error')

    def skip_auth(self, event, context):
        errors = self.validate_request(event=event)
        if errors:
            return build_response(code=400,
                                  content=errors)
        try:
            execution_result = self.handle_request(event=event,
                                                   context=context)
            _LOG.debug(f'Response: {execution_result}')
            return execution_result
        except ApplicationException as e:
            _LOG.error(f'Error occurred; Event: {event}; Error: {e}')
            return build_response(code=e.code,
                                  content=e.content)
        except Exception as e:
            _LOG.error(
                f'Unexpected error occurred; Event: {event}; Error: {e}')
            return build_response(code=RESPONSE_INTERNAL_SERVER_ERROR,
                                  content='Internal server error')

    @staticmethod
    def __get_target_permission(event):
        request_path = event.get(PARAM_REQUEST_PATH)
        http_method = event.get(PARAM_HTTP_METHOD)

        path_items = request_path.split('/')
        path_items = [item.strip() for item in path_items if item.strip()]
        del path_items[0]  # remove deploy stage
        request_path = '/' + '/'.join(path_items) + '/'
        target_permission = ENDPOINT_PERMISSION_MAPPING.get(
            request_path, {}).get(http_method, False)
        return target_permission
