from typing import Optional

from services.saving.abstract_saving import AbstractSaving


class Saving(AbstractSaving):
    action: str
    saving_percent: float
    saving_month_usd: float
    monthly_price_usd: float
    target_instance_type: Optional[str] = None

    def __init__(self, action, old_month_price, new_month_price,
                 target_instance_type=None):
        self.action = action

        saving_usd = round(old_month_price - new_month_price, 2)
        saving_percent = int(round(saving_usd / old_month_price, 2) * 100)

        self.saving_month_usd = saving_usd
        self.saving_percent = saving_percent
        self.monthly_price_usd = new_month_price
        if target_instance_type:
            self.target_instance_type = target_instance_type

    def __str__(self):
        return f'{self.action} saving: ${self.saving_month_usd} per month'

    def as_dict(self):
        item = {
            'action': self.action,
            'monthly_price_usd': self.monthly_price_usd,
            'saving_percent': self.saving_percent,
            'saving_month_usd': self.saving_month_usd,
        }
        if self.target_instance_type:
            item['target_instance_type'] = self.target_instance_type
        return item
