from dataclasses import dataclass


@dataclass
class ActiveSchedulePeriod:
    instance_id: str
    weekday: str
    time_from: str
    time_to: str
    probability: float
    action: str
