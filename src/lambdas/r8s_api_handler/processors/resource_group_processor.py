from typing import Union, List, Dict, Callable

from modular_sdk.commons.constants import (RIGHTSIZER_LICENSES_TYPE,
                                           ApplicationType)
from modular_sdk.models.application import Application
from modular_sdk.models.parent import Parent

from commons import RESPONSE_BAD_REQUEST_CODE, build_response, \
    RESPONSE_OK_CODE, \
    validate_params, RESPONSE_RESOURCE_NOT_FOUND_CODE, generate_id
from commons.constants import GET_METHOD, PATCH_METHOD, \
    PARENT_ID_ATTR, \
    ERROR_NO_APPLICATION_FOUND, ADD_TAGS_ATTR, \
    ADD_RESOURCE_GROUPS_ATTR, REMOVE_TAGS_ATTR, REMOVE_RESOURCE_GROUPS_ATTR, \
    ID_ATTR, TYPE_ATTR, SCALE_STEP_ATTR, COOLDOWN_DAYS_ATTR, \
    GROUP_POLICY_AUTO_SCALING, SCALE_STEP_AUTO_DETECT, MIN_ATTR, MAX_ATTR, \
    DESIRED_ATTR, ALLOWED_RESOURCE_GROUPS_ATTR, ALLOWED_TAGS_ATTR, POST_METHOD, \
    DELETE_METHOD
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService

_LOG = get_logger('r8s-resource-group-processor')

DEFAULT_COOLDOWN_DAYS = 7
THRESHOLD_KEYS = (MIN_ATTR, MAX_ATTR, DESIRED_ATTR)


class ResourceGroupProcessor(AbstractCommandProcessor):
    def __init__(self, application_service: RightSizerApplicationService,
                 parent_service: RightSizerParentService):
        self.application_service = application_service
        self.parent_service = parent_service

        self.method_to_handler: Dict[str, Callable] = {
            GET_METHOD: self.get,
            POST_METHOD: self.post,
            PATCH_METHOD: self.patch,
            DELETE_METHOD: self.delete
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

        group_id = event.get(ID_ATTR)
        groups = []
        if group_id:
            _LOG.debug(f'Describing group {group_id}')
            group = self.parent_service.get_resource_group(
                meta=parent_meta,
                group_id=group_id)
            if group:
                groups.append(group)
        else:
            _LOG.debug(f'Listing parent {parent.parent_id} groups')
            groups = self.parent_service.list_resource_groups(meta=parent_meta)

        if not groups:
            _LOG.debug('No resource groups found matching given query')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content='No resource groups found matching given query'
            )

        _LOG.debug(f'Response: {groups}')

        return build_response(
            code=RESPONSE_OK_CODE,
            content=groups
        )

    def post(self, event: dict):
        _LOG.debug(f'Create resource group event: {event}')
        validate_params(event,
                        (PARENT_ID_ATTR,))
        if ALLOWED_RESOURCE_GROUPS_ATTR not in event and ALLOWED_TAGS_ATTR not in event:
            _LOG.debug(f'Either \'{ALLOWED_RESOURCE_GROUPS_ATTR}\' or '
                       f'\'{ALLOWED_TAGS_ATTR}\' parameter must be specified')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Either \'{ALLOWED_RESOURCE_GROUPS_ATTR}\' or '
                        f'\'{ALLOWED_TAGS_ATTR}\' parameter must be specified'
            )
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

        _LOG.debug(f'Building resource group config')
        resource_group = self._build_resource_group(event=event)

        _LOG.debug(f'Resource group config: {resource_group}. Adding to '
                   f'parent {parent.parent_id} meta')

        self.parent_service.add_resource_group(
            meta=parent_meta,
            resource_group=resource_group
        )
        _LOG.debug(f'Saving updated parent {parent_id}')
        parent.meta = parent_meta
        self.parent_service.save(parent=parent)

        _LOG.debug(f'Response: {resource_group}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=resource_group
        )

    @staticmethod
    def _build_resource_group(event: dict):
        tag_based = event.get(ALLOWED_TAGS_ATTR)
        native = event.get(ALLOWED_RESOURCE_GROUPS_ATTR)

        if not tag_based:
            tag_based = []
        if not native:
            native = []

        resource_group = {
            ID_ATTR: generate_id(),
            ALLOWED_RESOURCE_GROUPS_ATTR: native,
            ALLOWED_TAGS_ATTR: tag_based,
            TYPE_ATTR: GROUP_POLICY_AUTO_SCALING,
            SCALE_STEP_ATTR: event.get(SCALE_STEP_ATTR,
                                       SCALE_STEP_AUTO_DETECT),
            COOLDOWN_DAYS_ATTR: event.get(COOLDOWN_DAYS_ATTR,
                                          DEFAULT_COOLDOWN_DAYS)
        }
        return resource_group

    def patch(self, event: dict):
        _LOG.info(f'Update resource group config event: {event}')

        validate_params(event, (PARENT_ID_ATTR, ID_ATTR))

        parent_id = event[PARENT_ID_ATTR]
        group_id = event[ID_ATTR]

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

        resource_group = self.parent_service.get_resource_group(
            meta=parent_meta,
            group_id=group_id
        )
        if not resource_group:
            _LOG.error('No resource group found mathing given query')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='No resource group found mathing given query'
            )

        if remove_tags:
            _LOG.debug(f'Removing tags: {add_tags}')
            resource_group[ALLOWED_TAGS_ATTR] = self._remove_from_list(
                resource_group[ALLOWED_TAGS_ATTR],
                *remove_tags
            )
        if remove_resource_groups:
            _LOG.debug(f'Removing native groups: {remove_resource_groups}')
            resource_group[ALLOWED_RESOURCE_GROUPS_ATTR] = (
                self._remove_from_list(
                    resource_group[ALLOWED_RESOURCE_GROUPS_ATTR],
                    *remove_resource_groups
                ))
        if add_tags:
            _LOG.debug(f'Adding tags: {add_tags}')
            resource_group[ALLOWED_TAGS_ATTR] = self._add_unique_to_list(
                resource_group[ALLOWED_TAGS_ATTR],
                *add_tags
            )
        if add_resource_groups:
            _LOG.debug(f'Adding native resource groups: {add_resource_groups}')

            resource_group[ALLOWED_RESOURCE_GROUPS_ATTR] = (
                self._add_unique_to_list(
                    resource_group[ALLOWED_RESOURCE_GROUPS_ATTR],
                    *add_resource_groups
                ))
        _LOG.debug(f'Resulted resource group config: {remove_resource_groups}')
        self.parent_service.update_resource_group(
            meta=parent_meta,
            resource_group=resource_group
        )
        parent.meta = parent_meta
        _LOG.debug(f'Saving updated parent {parent.parent_id}')
        parent.save()

        _LOG.info(f'Response: {resource_group}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=resource_group
        )

    def delete(self, event: dict):
        _LOG.debug(f'Delete resource group event: {event}')
        validate_params(event, (PARENT_ID_ATTR, ID_ATTR))

        _LOG.debug('Resolving applications')
        applications = self._revolve_application(event=event)

        parent_id = event[PARENT_ID_ATTR]
        group_id = event[ID_ATTR]
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

        resource_group = self.parent_service.get_resource_group(
            meta=parent_meta, group_id=group_id
        )
        if not resource_group:
            _LOG.error('No resource group found mathing given query')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='No resource group found mathing given query'
            )
        _LOG.debug(f'Removing group {group_id} from parent '
                   f'{parent.parent_id}')
        self.parent_service.remove_resource_group(
            meta=parent_meta,
            group_id=group_id
        )
        parent.meta = parent_meta

        _LOG.debug('Saving updated parent')
        self.parent_service.save(parent=parent)

        _LOG.debug(f'Resource group {group_id} has been removed from '
                   f'parent {parent.parent_id}.')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'Resource group {group_id} has been removed from '
                    f'parent {parent.parent_id}.'
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
