from dataclasses import dataclass
from typing import List

from commons.constants import ACTION_SPLIT
from services.saving.abstract_saving import AbstractSaving


@dataclass
class SplitInstance:
    instance_type: str
    monthly_price_usd: float
    probability: float


class SplitSaving(AbstractSaving):
    action = ACTION_SPLIT
    saving_percent: float
    saving_month_usd: float
    monthly_price_usd: float
    target_instances: List[SplitInstance]

    def __init__(self, old_month_price, new_month_price,
                 split_instances: List[SplitInstance]):
        saving_usd = round(old_month_price - new_month_price, 2)
        saving_percent = int(round(saving_usd / old_month_price, 2) * 100)
        self.saving_month_usd = saving_usd
        self.saving_percent = saving_percent
        self.monthly_price_usd = new_month_price
        self.target_instances = split_instances

    def as_dict(self):
        target_instances = [item.__dict__ for item in self.target_instances]
        item = {
            'action': self.action,
            'monthly_price_usd': self.monthly_price_usd,
            'saving_percent': self.saving_percent,
            'saving_month_usd': self.saving_month_usd,
            'target_instances': target_instances
        }
        return item
