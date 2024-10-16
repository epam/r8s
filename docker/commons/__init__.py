from datetime import datetime, timezone

from commons.constants import (PASSWORD_ATTR, ID_TOKEN_ATTR,
                               REFRESH_TOKEN_ATTR, AUTHORIZATION_PARAM)


def get_iso_timestamp():
    return datetime.now().isoformat()


def dateparse(time_in_secs):
    if len(str(time_in_secs)) > 10:  # if timestamp in milliseconds
        time_in_secs = time_in_secs[0:-3]
    dt = datetime.utcfromtimestamp(float(time_in_secs))
    dt = dt.replace(tzinfo=timezone.utc)
    return dt


def secure_event(event: dict,
                 secured_keys=(PASSWORD_ATTR, ID_TOKEN_ATTR,
                               REFRESH_TOKEN_ATTR, AUTHORIZATION_PARAM)):
    result_event = {}
    if not isinstance(event, dict):
        return event
    for key, value in event.items():
        if isinstance(value, dict):
            result_event[key] = secure_event(
                event=value,
                secured_keys=secured_keys)
        if isinstance(value, list):
            result_event[key] = []
            for item in value:
                result_event[key].append(secure_event(item))
        elif key in secured_keys:
            result_event[key] = '*****'
        else:
            result_event[key] = secure_event(value)

    return result_event
