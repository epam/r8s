
class ConnectionError(Exception):
    """Exception raised for errors in the connection."""

    def __init__(self, message='Connection error occurred'):
        self.message = message
        super().__init__(self.message)
