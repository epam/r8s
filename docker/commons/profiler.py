import time
from threading import Lock

from commons.constants import PROFILE_LOG_PATH
from commons.log_helper import get_logger


_LOG = get_logger('profiler')

lock = Lock()


def profiler(execution_step):
    def decorator(f):
        def wrapper(*args, **kwargs):
            start = time.time()
            response = f(*args, **kwargs)
            exec_time = round(time.time() - start, 3)
            _LOG.debug(f'Step {execution_step} took {exec_time} seconds')
            with lock:
                with open(PROFILE_LOG_PATH, 'a') as file:
                    file.write(f'{execution_step}:{exec_time}\n')
            return response
        return wrapper
    return decorator
