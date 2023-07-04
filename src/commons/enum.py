from enum import Enum


class ListEnum(Enum):
    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))
