class ExecutorException(Exception):

    def __init__(self, step_name, reason):
        self.step_name = step_name
        self.reason = reason

    def __str__(self):
        return f'Error occurred on \'{self.step_name}\' step: {self.reason}'


class ProcessingPostponedException(Exception):

    def __init__(self, postponed_till: str):
        self.postponed_till = postponed_till

    def __str__(self):
        return f'Processing is postponed till {self.postponed_till}'
