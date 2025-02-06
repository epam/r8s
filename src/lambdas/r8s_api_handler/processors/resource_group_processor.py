from typing import Union, List, Dict, Callable

from modular_sdk.commons.constants import (RIGHTSIZER_LICENSES_TYPE,
                                           ApplicationType)
from modular_sdk.models.application import Application
from modular_sdk.models.parent import Parent

from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_OK_CODE, \
    validate_params
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import GET_METHOD, PATCH_METHOD, \
    PARENT_ID_ATTR, \
    ERROR_NO_APPLICATION_FOUND, ADD_TAGS_ATTR, \
    ADD_RESOURCE_GROUPS_ATTR, REMOVE_TAGS_ATTR, REMOVE_RESOURCE_GROUPS_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService

_LOG = get_logger('r8s-resource-group-processor')

DEFAULT_RESOURCE_GROUP_CONFIG = {
    'allowed_resource_groups': [],
    'allowed_tags': []
}


class ResourceGroupProcessor(AbstractCommandProcessor):
    def __init__(self, application_service: RightSizerApplicationService,
                 parent_service: RightSizerParentService):
        self.application_service = application_service
        self.parent_service = parent_service

        self.method_to_handler: Dict[str, Callable] = {
            GET_METHOD: self.get,
            PATCH_METHOD: self.patch,
        }

    def get(self, event: dict):
        _LOG.info(f'Describe parent resource group config: {event}')
        validate_params(event, (PARENT_ID_ATTR,))

        _LOG.debug('Resolving applications')
        applications = self._revolve_application(event=event)

        parent_id = event[PARENT_ID_ATTR]
        app_ids = [app.application_id for app in applications]

        _LOG.debug(f'Describing parent \'{parent_id}\'')
        parent = self.get_parent(parent_id=parent_id,
                                 application_ids=app_ids)
        if not parent:
            _LOG.error('No parents found matching given query')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='No parents found matching given query'
            )
        _LOG.debug(f'Validating parent {parent.parent_id}')
        self._validate_parent(parent=parent)

        parent_meta = self.parent_service.get_parent_meta(parent=parent)

        if not parent_meta.resource_groups:
            _LOG.debug(f'No parent meta found, will be initialized.')
            parent_meta.resource_groups = DEFAULT_RESOURCE_GROUP_CONFIG
            parent.meta = parent_meta
            self.parent_service.save(parent)

        response = parent_meta.as_dict().get('resource_groups', {})
        _LOG.debug(f'Response: {response}')

        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )

    def patch(self, event: dict):
        _LOG.info(f'Update resource group config event: {event}')

        validate_params(event, (PARENT_ID_ATTR,))

        parent_id = event.get(PARENT_ID_ATTR)

        add_tags = event.get(ADD_TAGS_ATTR, [])
        remove_tags = event.get(REMOVE_TAGS_ATTR, [])
        add_resource_groups = event.get(ADD_RESOURCE_GROUPS_ATTR, [])
        remove_resource_groups = event.get(REMOVE_RESOURCE_GROUPS_ATTR, [])

        _LOG.debug(f'Searching for parent: {parent_id}')
        parent = self.parent_service.get_parent_by_id(
            parent_id=parent_id
        )
        _LOG.debug(f'Validating parent: {parent.parent_id}')
        self._validate_parent(parent=parent)

        _LOG.debug(f'Resolving available user applications')
        self._revolve_application(event=event, linked_parent=parent)

        parent_meta = self.parent_service.get_parent_meta(
            parent=parent
        )

        if not parent_meta.resource_groups:
            _LOG.debug(f'No parent meta found, will be initialized.')
            parent_meta.resource_groups = DEFAULT_RESOURCE_GROUP_CONFIG
            parent.meta = parent_meta
            self.parent_service.save(parent)

        resource_group_config = parent.meta.as_dict().get('resource_groups',
                                                          {})
        _LOG.debug(f'Initial resource group config: {resource_group_config}')

        if remove_tags:
            _LOG.debug(f'Removing tags: {add_tags}')
            resource_group_config['allowed_tags'] = self._remove_from_list(
                resource_group_config['allowed_tags'],
                *remove_tags
            )
        if remove_resource_groups:
            _LOG.debug(f'Removing groups: {remove_resource_groups}')
            resource_group_config['allowed_resource_groups'] = (
                self._remove_from_list(
                    resource_group_config['allowed_resource_groups'],
                    *remove_resource_groups
                ))
        if add_tags:
            _LOG.debug(f'Adding tags: {add_tags}')
            resource_group_config['allowed_tags'] = self._add_unique_to_list(
                resource_group_config['allowed_tags'],
                *add_tags
            )
        if add_resource_groups:
            _LOG.debug(f'Adding resource groups: {add_resource_groups}')

            resource_group_config['allowed_resource_groups'] = (
                self._add_unique_to_list(
                    resource_group_config['allowed_resource_groups'],
                    *add_resource_groups
                ))
        _LOG.debug(f'Resulted resource group config: {remove_resource_groups}')
        parent_meta.resource_groups = resource_group_config
        parent.meta = parent_meta
        _LOG.debug(f'Saving updated parent {parent.parent_id}')
        parent.save()

        _LOG.debug(f'Describing parent dto')
        response = parent.get_json()
        _LOG.info(f'Response: {response}')
        return build_response(
            code=200,
            content=response
        )

    @staticmethod
    def _add_unique_to_list(lst: list, *args) -> list:
        result = lst.copy()
        for arg in args:
            if arg not in result:
                result.append(arg)
        return result

    @staticmethod
    def _remove_from_list(lst: list, *args) -> list:
        result = lst.copy()
        for arg in args:
            if arg in result:
                result.remove(arg)
        return result

    def get_parent(self, parent_id, application_ids: List[str]):
        parent = self.parent_service.get_parent_by_id(
            parent_id=parent_id
        )
        if not parent or parent.is_deleted or \
                parent.application_id not in application_ids:
            _LOG.error(f'Parent \'{parent_id}\' does not exist.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Parent \'{parent_id}\' does not exist.'
            )
        return parent

    @staticmethod
    def _validate_parent(parent: Parent = None):
        if not parent:
            _LOG.error('No parent found matching given query.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='No parent found matching given query.'
            )
        if parent.type != RIGHTSIZER_LICENSES_TYPE:
            _LOG.error(f'Parent of \'{RIGHTSIZER_LICENSES_TYPE}\' '
                       f'type required.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Parent of \'{RIGHTSIZER_LICENSES_TYPE}\' '
                        f'type required.'
            )

    def _revolve_application(
            self, event, linked_parent: Parent = None
    ) -> Union[List[Application], Application]:
        applications = self.application_service.resolve_application(
            event=event, type_=ApplicationType.RIGHTSIZER_LICENSES)

        if not applications:
            _LOG.warning(ERROR_NO_APPLICATION_FOUND)
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=ERROR_NO_APPLICATION_FOUND
            )

        if linked_parent:
            target_application = None
            for application in applications:
                if application.application_id == linked_parent.application_id:
                    target_application = application
            if not target_application:
                _LOG.warning(ERROR_NO_APPLICATION_FOUND)
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=ERROR_NO_APPLICATION_FOUND
                )
            return target_application
        return applications
