import time

from commons.log_helper import get_logger

LOG_FILE_PATH = '/tmp/execution_log.txt'

_LOG = get_logger('profiler')


def profiler(execution_step):
    def decorator(f):
        def wrapper(*args, **kwargs):
            start = time.time()
            response = f(*args, **kwargs)
            exec_time = round(time.time() - start, 3)
            _LOG.debug(f'Step {execution_step} took {exec_time} seconds')
            with open(LOG_FILE_PATH, 'a') as file:
                file.write(f'{execution_step}:{exec_time}\n')
            return response
        return wrapper
    return decorator
