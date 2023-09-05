from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List

from services.health_checks import HealthCheckStatus


@dataclass
class CheckResult:
    id: str
    remediation: Optional[str] = None
    impact: Optional[str] = None
    status: HealthCheckStatus = HealthCheckStatus.HC_STATUS_OK
    details: Optional[Dict] = field(default_factory=dict)

    def is_ok(self) -> bool:
        if isinstance(self.status, HealthCheckStatus):
            return self.status == HealthCheckStatus.HC_STATUS_OK
        return self.status == HealthCheckStatus.HC_STATUS_OK.value

    def as_dict(self):
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class CheckCollectionResult:
    id: str
    type: str
    details: Optional[List[CheckResult]]

    def as_dict(self):
        result = {k: v for k, v in asdict(self).items() if v is not None}
        if self.details:
            detail_dicts = [detail.as_dict() for detail in self.details]
            result['details'] = detail_dicts
        result['status'] = self.status.value
        return result

    @property
    def status(self):
        if not self.details:
            return HealthCheckStatus.HC_STATUS_NOT_OK
        if all([check.is_ok() for check in self.details]):
            return HealthCheckStatus.HC_STATUS_OK
        return HealthCheckStatus.HC_STATUS_NOT_OK
