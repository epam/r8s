from abc import abstractmethod, ABC
from typing import Optional, Union, List

from services.health_checks import HealthCheckStatus
from services.health_checks.check_result import CheckResult


class AbstractHealthCheck(ABC):

    @abstractmethod
    def identifier(self) -> str:
        """
        Returns the identifier of a certain check
        :return: str
        """

    @abstractmethod
    def remediation(self) -> Optional[str]:
        """
        Actions in case the check is failed
        :return:
        """

    @abstractmethod
    def impact(self) -> Optional[str]:
        """
        Harm in case the check is failed
        :return:
        """

    def ok_result(self, details: Optional[dict] = None) -> CheckResult:
        return CheckResult(
            id=self.identifier(),
            status=HealthCheckStatus.HC_STATUS_OK.value,
            details=details,
        )

    def not_ok_result(self, details: Optional[dict] = None) -> CheckResult:
        return CheckResult(
            id=self.identifier(),
            status=HealthCheckStatus.HC_STATUS_NOT_OK.value,
            details=details,
            remediation=self.remediation(),
            impact=self.impact()
        )

    def unknown_result(self, details: Optional[dict] = None) -> CheckResult:
        return CheckResult(
            id=self.identifier(),
            status=HealthCheckStatus.HC_STATUS_UNKNOWN.value,
            details=details
        )

    @abstractmethod
    def check(self, *args, **kwargs) -> Union[List[CheckResult], CheckResult]:
        """
        Must check a certain aspect of the service
        :return: CheckResult
        """