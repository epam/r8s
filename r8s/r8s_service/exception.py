from abc import ABC


class R8sBaseException(ABC, Exception):
    """
    Base R8s_admin exception
    """


class R8sBadRequestException(R8sBaseException):
    """
    Incoming request to R8s_admin is invalid due to parameters invalidity.
    """
    code = 400


class R8sUnauthorizedException(R8sBaseException):
    """
    Provided credentials are invalid
    """
    code = 401


class R8sForbiddenException(R8sBaseException):
    """
    Permission policy denies a command execution for requestor
    """
    code = 403


class R8sNotFoundException(R8sBaseException):
    """
    The requested resource has not been found
    """
    code = 404


class R8sTimeoutException(R8sBaseException):
    """
    Failed to respond in expected time range
    """
    code = 408


class R8sConflictException(R8sBaseException):
    """
    Incoming request processing failed due to environment state is incompatible
    with requested command
    """
    code = 409


class R8sInternalException(R8sBaseException):
    """
    R8s_admin failed to process incoming requests due to an error in the code.
    It’s a developer’s mistake.
    """
    code = 500


class R8sBadGatewayException(R8sBaseException):
    """
    R8s_admin obtained the Error message from 3rd party application it is
    integrated with to satisfy the user's command.
    """
    code = 502


class R8sConfigurationException(R8sBaseException):
    """
    Internal service is not configured: General configuration mismatch
    """
    code = 503


HTTP_CODE_EXCEPTION_MAPPING = {
    400: R8sBadRequestException,
    401: R8sUnauthorizedException,
    403: R8sForbiddenException,
    404: R8sNotFoundException,
    408: R8sTimeoutException,
    409: R8sConflictException,
    500: R8sInternalException,
    502: R8sBadGatewayException,
    503: R8sConfigurationException
}
