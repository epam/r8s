from enum import Enum


class HealthCheckStatus(Enum):
    HC_STATUS_OK = "OK"
    HC_STATUS_UNKNOWN = 'UNKNOWN'
    HC_STATUS_NOT_OK = 'NOT_OK'
