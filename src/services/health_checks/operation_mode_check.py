from typing import Optional, Union, List

from modular_sdk.commons.constants import ParentType
from modular_sdk.models.application import Application
from modular_sdk.models.parent import Parent
from modular_sdk.services.tenant_service import TenantService

from commons.constants import MAESTRO_RIGHTSIZER_APPLICATION_TYPE, \
    INPUT_STORAGE_ATTR, OUTPUT_STORAGE_ATTR, CLOUD_ATTR, SCOPE_ATTR, \
    ALGORITHM_ATTR, CHECK_TYPE_OPERATION_MODE, PARENT_SCOPE_ALL, CLOUD_AWS, \
    CLOUD_GOOGLE, CLOUD_AZURE
from commons.log_helper import get_logger
from services.health_checks.abstract_health_check import AbstractHealthCheck
from services.health_checks.check_result import CheckCollectionResult, \
    CheckResult
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService

_LOG = get_logger(__name__)

CHECK_ID_OPERATION_MODE_CONFIGURATION = 'OPERATION_MODE_CONFIGURATION'
CHECK_ID_OPERATION_MODE_COMPATIBILITY = 'OPERATION_MODE_COMPATIBILITY'

CLOUD_ALL = 'ALL'

class OperationModeConfigurationCheck(AbstractHealthCheck):

    def __init__(self, application_service: RightSizerApplicationService,
                 parent_service: RightSizerParentService):
        self.application_service = application_service
        self.parent_service = parent_service

    def identifier(self) -> str:
        return CHECK_ID_OPERATION_MODE_CONFIGURATION

    def remediation(self) -> Optional[str]:
        return f'Update your parent/application meta with valid values'

    def impact(self) -> Optional[str]:
        return f'You won\'t be able to submit scans with this ' \
               f'parent/application pair'

    def check(self, application: Application, parent: Parent) -> \
            Union[List[CheckResult], CheckResult]:
        application_meta = self.application_service.get_application_meta(
            application=application
        )
        app_meta_dict = application_meta.as_dict()
        input_storage = app_meta_dict.get(INPUT_STORAGE_ATTR)
        output_storage = app_meta_dict.get(OUTPUT_STORAGE_ATTR)

        cloud = parent.cloud if parent.cloud else CLOUD_ALL
        result = {
            INPUT_STORAGE_ATTR: input_storage,
            OUTPUT_STORAGE_ATTR: output_storage,
            CLOUD_ATTR: cloud,
            SCOPE_ATTR: parent.scope
        }
        if any([value is None for value in result.values()]):
            return self.not_ok_result(
                details=result
            )

        return self.ok_result(details=result)


class OperationModeConfigurationCompatibilityCheck(AbstractHealthCheck):

    def __init__(self, application_service: RightSizerApplicationService,
                 parent_service: RightSizerParentService,
                 tenant_service: TenantService):
        self.application_service = application_service
        self.parent_service = parent_service
        self.tenant_service = tenant_service

    def identifier(self) -> str:
        return CHECK_ID_OPERATION_MODE_COMPATIBILITY

    def remediation(self) -> Optional[str]:
        return f'Update your parents/applications meta get rid of ' \
               f'overlapped tenant linkage'

    def impact(self) -> Optional[str]:
        return f'RIGHTSIZER may not work as expected due to ' \
               f'Application/Parent misconfiguration'

    def check(self, pairs: list) -> Union[List[CheckResult], CheckResult]:
        tenant_parent_mapping = {}
        errors = []
        for pair in pairs:
            application, parent = pair
            covered_tenants = self._get_covered_tenants(pair=pair)

            for tenant_name in covered_tenants:
                if tenant_name not in tenant_parent_mapping:
                    tenant_parent_mapping[tenant_name] = [parent.parent_id]
                else:
                    tenant_parent_mapping[tenant_name].append(parent.parent_id)

        if PARENT_SCOPE_ALL in tenant_parent_mapping \
                and len(tenant_parent_mapping) > 1:
            error = f'Misconfiguration: \'{PARENT_SCOPE_ALL}\' parent scope ' \
                    f'can\'t be used more that once per customer/cloud ' \
                    f'and/or alongside with directly linked tenants'
            _LOG.debug(error)
            errors.append(error)
        tenants_with_duplicated_links = []
        for tenant_name, activated_in_parents in tenant_parent_mapping.items():
            if tenant_name == PARENT_SCOPE_ALL:
                continue
            if len(activated_in_parents) > 1:
                tenants_with_duplicated_links.append(tenant_name)

        if tenants_with_duplicated_links:
            error = f'Misconfiguration: Tenant ca\'t be activated in ' \
                    f'several RIGHTSIZER parents: ' \
                    f'{", ".join(tenants_with_duplicated_links)}'
            _LOG.debug(error)
            errors.append(error)

        # Get cloud of first (any) parent
        cloud = pairs[0][1].cloud
        if not cloud:
            cloud = CLOUD_ALL

        details = {
            'tenant_parent_mapping': tenant_parent_mapping,
            'cloud': cloud
        }
        if not errors:
            return self.ok_result(details=details)

        details['errors'] = errors
        return self.not_ok_result(details=details)

    def _get_covered_tenants(self, pair) -> List[str]:
        application, parent = pair

        if not application or not parent:
            return []

        if parent.tenant_name:
            tenant = self.tenant_service.get(
                tenant_name=parent.tenant_name)
            if not tenant:
                return []
            return [tenant.name]
        else:
            return [PARENT_SCOPE_ALL]


class OperationModeCheckHandler:
    def __init__(self, application_service: RightSizerApplicationService,
                 parent_service: RightSizerParentService,
                 tenant_service: TenantService):
        self.application_service = application_service
        self.parent_service = parent_service
        self.tenant_service = tenant_service

        self.checks = [
            OperationModeConfigurationCheck(
                application_service=self.application_service,
                parent_service=self.parent_service)
        ]
        self.singe_checks = [
            OperationModeConfigurationCompatibilityCheck(
                application_service=self.application_service,
                parent_service=self.parent_service,
                tenant_service=self.tenant_service
            )
        ]

    def check(self):
        _LOG.debug(f'Listing applications')
        applications = list(self.application_service.list(
            _type=MAESTRO_RIGHTSIZER_APPLICATION_TYPE, deleted=False))
        _LOG.debug(f'Found applications: '
                   f'{[app.application_id for app in applications]}')
        parents = []
        for application in applications:
            _LOG.debug(f'Listing application {application.application_id} '
                       f'parents')
            application_parents = self.parent_service.list_application_parents(
                application_id=application.application_id,
                only_active=True
            )
            _LOG.debug(f'Found application {application.application_id} '
                       f'parents: '
                       f'{[parent.parent_id for parent in application_parents]}')
            parents.extend(application_parents)
            _LOG.debug(f'App Parents: '
                       f'{[parent.get_json() for parent in application_parents]}')
        if not applications or not parents:
            _LOG.warning(f'No active parents/applications found')
            result = CheckCollectionResult(
                id='NONE',
                type=CHECK_TYPE_OPERATION_MODE
            )
            return result.as_dict()
        pairs = {
            CLOUD_AWS: [],
            CLOUD_AZURE: [],
            CLOUD_GOOGLE: [],
            CLOUD_ALL: []
        }

        for parent in parents:
            if parent.cloud and  parent.cloud not in pairs:
                continue
            related_application = [app for app in applications
                                   if parent.application_id ==
                                   app.application_id]
            if related_application and len(related_application) == 1:
                related_application = related_application[0]
            else:
                related_application = None
            _LOG.debug(f'Found link: '
                       f'Application: {related_application.application_id}, '
                       f'Parent: {parent.parent_id}')
            if parent.cloud:
                pairs[parent.cloud].append((related_application, parent))
            else:
                pairs[CLOUD_ALL].append((related_application, parent))
        result = []

        for cloud, cloud_pairs in pairs.items():
            _LOG.debug(f'Processing cloud {cloud} pairs')
            for application, parent in cloud_pairs:
                _LOG.debug(f'Processing pair - '
                           f'Application: {application.application_id}, '
                           f'Parent: {parent.parent_id}')
                checks = []
                for check_instance in self.checks:
                    check_result = check_instance.check(application=application,
                                                        parent=parent)

                    checks.append(check_result)

                operation_mode_result = CheckCollectionResult(
                    id=parent.parent_id,
                    type=CHECK_TYPE_OPERATION_MODE,
                    details=checks
                )
                _LOG.debug(f'Pair result: {operation_mode_result.as_dict()}')
                result.append(operation_mode_result.as_dict())

        common_check_results = []
        _LOG.debug(f'Processing common check')
        for cloud, cloud_pairs in pairs.items():
            if not cloud_pairs:
                continue
            for check_instance in self.singe_checks:
                check_result = check_instance.check(pairs=cloud_pairs)
                common_check_results.append(check_result)

        common_check_result = CheckCollectionResult(
            id='COMMON',
            type=CHECK_TYPE_OPERATION_MODE,
            details=common_check_results
        )
        _LOG.debug(f'Common check result: {common_check_result.as_dict()}')
        result.append(common_check_result.as_dict())
        return result
