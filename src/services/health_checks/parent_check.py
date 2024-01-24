from typing import Optional, Union, List

from modular_sdk.models.parent import Parent
from modular_sdk.services.tenant_service import TenantService
from modular_sdk.commons.constants import ParentType, ApplicationType

from commons.constants import ALLOWED_RULE_ACTIONS, \
    ALLOWED_RULE_CONDITIONS, ALLOWED_SHAPE_FIELDS, CHECK_TYPE_PARENT
from commons.log_helper import get_logger
from models.parent_attributes import ShapeRule
from services.algorithm_service import AlgorithmService
from services.health_checks.abstract_health_check import AbstractHealthCheck
from services.health_checks.check_result import CheckResult, \
    CheckCollectionResult
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService

_LOG = get_logger('application-check')

ERROR_NO_PARENT_FOUND = 'NO_PARENT'

CHECK_ID_ALGORITHM_CHECK = 'ALGORITHM_CHECK'
CHECK_ID_TENANT_SCOPE_CHECK = 'TENANT_SCOPE_CHECK'
CHECK_ID_SHAPE_RULE_CHECK = 'SHAPE_RULE_CHECK'


class ParentShapeRuleCheck(AbstractHealthCheck):

    def __init__(self, parent_service: RightSizerParentService):
        self.parent_service = parent_service

    def identifier(self) -> str:
        return CHECK_ID_SHAPE_RULE_CHECK

    def remediation(self) -> Optional[str]:
        return f'Update your shape rules with valid values.'

    def impact(self) -> Optional[str]:
        return f'Shape rules won\'t be applied'

    def check(self, parent: Parent) -> Union[List[CheckResult], CheckResult]:
        parent_meta = self.parent_service.get_parent_meta(parent=parent)
        shape_rules = self.parent_service.list_shape_rules(
            parent_meta=parent_meta)

        if not shape_rules:
            return self.ok_result(
                details={'message': "No Shape Rules found."}
            )

        result = {}

        for shape_rule in shape_rules:
            shape_errors = self._validate_shape_rule(shape_rule=shape_rule)
            result[shape_rule.rule_id] = shape_errors

        contains_errors = any([value for value in result.values()])

        if contains_errors:
            return self.not_ok_result(
                details=result
            )

        rule_ids = [shape_rule.rule_id for shape_rule in shape_rules]
        return self.ok_result(
            details={'message': f'Rules {", ".join(rule_ids)} are valid'})

    @staticmethod
    def _validate_shape_rule(shape_rule: ShapeRule):
        errors = []

        if shape_rule.action not in ALLOWED_RULE_ACTIONS:
            errors.append(f'Invalid action: {shape_rule.action}.')

        if shape_rule.condition not in ALLOWED_RULE_CONDITIONS:
            errors.append(f'Invalid condition: {shape_rule.condition}.')

        if shape_rule.field not in ALLOWED_SHAPE_FIELDS:
            errors.append(f'Invalid field: {shape_rule.field}.')
        return errors


class ParentCheckHandler:
    def __init__(self, application_service: RightSizerApplicationService,
                 parent_service: RightSizerParentService,
                 tenant_service: TenantService,
                 algorithm_service: AlgorithmService):
        self.application_service = application_service
        self.parent_service = parent_service
        self.tenant_service = tenant_service
        self.algorithm_service = algorithm_service

        self.checks = [
            ParentShapeRuleCheck(parent_service=self.parent_service)
        ]

    def check(self):
        _LOG.debug(f'Listing parents')
        applications = self.application_service.list(
            _type=ApplicationType.RIGHTSIZER)
        parents = []
        for application in applications:
            application_parents = self.parent_service.list_application_parents(
                application_id=application.application_id,
                only_active=True
            )
            parents.extend(application_parents)
        if not parents:
            _LOG.warning(f'No active RIGHTSIZER parents found')
            result = CheckCollectionResult(
                id='NONE',
                type=CHECK_TYPE_PARENT,
                details=[]
            )
            return result.as_dict()

        result = []

        for parent in parents:
            parent_checks = []
            for check_instance in self.checks:
                check_result = check_instance.check(parent=parent)

                parent_checks.append(check_result)

            parent_result = CheckCollectionResult(
                id=parent.parent_id,
                type=CHECK_TYPE_PARENT,
                details=parent_checks
            )

            result.append(parent_result.as_dict())
        return result
