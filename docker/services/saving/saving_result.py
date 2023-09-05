from dataclasses import dataclass
from typing import List

from services.saving.abstract_saving import AbstractSaving


@dataclass
class SavingResult:
    current_instance_type: str
    current_monthly_price_usd: float
    saving_options: List[AbstractSaving]

    def as_dict(self):
        saving_options = [option.as_dict() for option in self.saving_options]

        item = {
            'current_instance_type': self.current_instance_type,
            'current_monthly_price_usd': self.current_monthly_price_usd,
            'saving_options': saving_options
        }
        return item
