from abc import ABC, abstractmethod


class AbstractSaving(ABC):
    action: str
    saving_percent: float
    saving_month_usd: float
    monthly_price_usd: float

    @abstractmethod
    def __init__(self, action, old_month_price, new_month_price,
                 *args, **kwargs):
        pass

    @abstractmethod
    def as_dict(self):
        pass
