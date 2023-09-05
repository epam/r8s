from datetime import datetime, timezone


def get_iso_timestamp():
    return datetime.now().isoformat()


def dateparse(time_in_secs):
    if len(str(time_in_secs)) > 10:  # if timestamp in milliseconds
        time_in_secs = time_in_secs[0:-3]
    dt = datetime.utcfromtimestamp(float(time_in_secs))
    dt = dt.replace(tzinfo=timezone.utc)
    return dt
