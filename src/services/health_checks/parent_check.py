from typing import Optional, Union, List

from modular_sdk.models.parent import Parent
from modular_sdk.services.tenant_service import TenantService

from commons.constants import PARENT_SCOPE_ALL, ALLOWED_RULE_ACTIONS, \
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


class AlgorithmExistCheck(AbstractHealthCheck):

    def __init__(self, algorithm_service: AlgorithmService,
                 parent_service: RightSizerParentService):
        self.algorithm_service = algorithm_service
        self.parent_service = parent_service

    def identifier(self) -> str:
        return CHECK_ID_ALGORITHM_CHECK

    def remediation(self) -> Optional[str]:
        return f'Update your parent meta with valid r8s Algorithm'

    def impact(self) -> Optional[str]:
        return f'You won\'t be able to submit scans through this parent'

    def check(self, parent: Parent) -> Union[List[CheckResult], CheckResult]:
        parent_meta = self.parent_service.get_parent_meta(parent=parent)
        algorithm_name = getattr(parent_meta, 'algorithm', None)
        if not algorithm_name:
            return self.not_ok_result(
                {'error': "\'algorithm\' does not exist"}
            )

        if not self.algorithm_service.get_by_name(name=algorithm_name):
            _LOG.warning(f'Algorithm \'{algorithm_name}\' does not exist')
            return self.not_ok_result(
                details={'error': f'Algorithm \'{algorithm_name}\' '
                                  f'does not exist.'}
            )

        return self.ok_result()


class ParentScopeCheck(AbstractHealthCheck):

    def __init__(self, tenant_service: TenantService,
                 parent_service: RightSizerParentService):
        self.tenant_service = tenant_service
        self.parent_service = parent_service

    def identifier(self) -> str:
        return CHECK_ID_TENANT_SCOPE_CHECK

    def remediation(self) -> Optional[str]:
        return f'Set your parent \'scope\' with \'ALL_TENANTS\' or ' \
               f'link some tenants to parent'

    def impact(self) -> Optional[str]:
        return f'You won\'t be able to submit scans through this parent'

    def check(self, parent: Parent) -> Union[List[CheckResult], CheckResult]:
        parent_meta = self.parent_service.get_parent_meta(parent=parent)
        scope = getattr(parent_meta, 'scope', None)
        if not scope:
            return self.not_ok_result(
                {'error': "\'scope\' attribute does not exist"}
            )

        if scope == PARENT_SCOPE_ALL:
            return self.ok_result(
                details={'message': 'activated for all customer tenants'})
        _LOG.debug(f'Listing activated tenants for parent '
                   f'\'{parent.parent_id}\'')
        linked_tenants = self.parent_service.list_activated_tenants(
            parent=parent
        )
        if not linked_tenants:
            return self.not_ok_result(
                details={'message': 'No linked tenants found'}
            )
        linked_tenant_names = [tenant.name for tenant in linked_tenants]
        return self.ok_result(
            details={'message': f'Linked to tenants: '
                                f'{", ".join(linked_tenant_names)}'})


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
            AlgorithmExistCheck(algorithm_service=self.algorithm_service,
                                parent_service=self.parent_service),
            ParentScopeCheck(tenant_service=self.tenant_service,
                             parent_service=self.parent_service),
            ParentShapeRuleCheck(parent_service=self.parent_service)
        ]

    def check(self):
        _LOG.debug(f'Listing parents')
        parents = self.parent_service.list_rightsizer_parents()
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
