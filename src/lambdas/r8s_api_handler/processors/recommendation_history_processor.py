from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params, ApplicationException
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import GET_METHOD, PATCH_METHOD, CUSTOMER_ATTR, \
    INSTANCE_ID_ATTR, RECOMMENDATION_TYPE_ATTR, \
    JOB_ID_ATTR, FEEDBACK_STATUS_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from models.recommendation_history import RecommendationTypeEnum, \
    FeedbackStatusEnum
from services.abstract_api_handler_lambda import PARAM_USER_CUSTOMER
from services.recommendation_history_service import \
    RecommendationHistoryService

_LOG = get_logger('r8s-recommendation-history-processor')


class RecommendationHistoryProcessor(AbstractCommandProcessor):
    def __init__(self,
                 recommendation_history_service: RecommendationHistoryService):
        self.recommendation_history_service = recommendation_history_service
        self.method_to_handler = {
            GET_METHOD: self.get,
            PATCH_METHOD: self.patch,
        }

    def process(self, event) -> dict:
        method = event.get(PARAM_HTTP_METHOD)
        command_handler = self.method_to_handler.get(method)
        if not command_handler:
            message = f'Unable to handle command {method} in ' \
                      f'algorithm processor'
            _LOG.error(f'status code: {RESPONSE_BAD_REQUEST_CODE}, '
                       f'process error: {message}')
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        return command_handler(event=event)

    def get(self, event):
        _LOG.debug(f'Describe recommendation event: {event}')

        customer = event.get(PARAM_USER_CUSTOMER)
        if customer == 'admin':
            customer = event.get(CUSTOMER_ATTR)
        instance_id = event.get(INSTANCE_ID_ATTR)
        recommendation_type = event.get(RECOMMENDATION_TYPE_ATTR)
        job_id = event.get(JOB_ID_ATTR)
        if recommendation_type:
            self._validate_recommendation_type(
                recommendation_type=recommendation_type)

        _LOG.debug(f'Searching for recommendations')
        recommendations = self.recommendation_history_service.list(
            customer=customer,
            resource_id=instance_id,
            recommendation_type=recommendation_type,
            job_id=job_id
        )

        if not recommendations:
            _LOG.warning(f'No recommendation found matching given query.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'No recommendation found matching given query.'
            )

        _LOG.debug(f'Describing recommendation dto')
        response = [recommendation.get_dto()
                    for recommendation in recommendations]

        _LOG.debug(f'Response: {response}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )

    def patch(self, event):
        _LOG.debug(f'Update recommendation event: {event}')
        validate_params(event, (INSTANCE_ID_ATTR, RECOMMENDATION_TYPE_ATTR,
                                FEEDBACK_STATUS_ATTR))

        customer = event.get(PARAM_USER_CUSTOMER)
        if customer == 'admin':
            customer = event.get(CUSTOMER_ATTR)

        if not customer:
            _LOG.warning(f'\'{CUSTOMER_ATTR}\' must be '
                         f'specified for admin users.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'\'{CUSTOMER_ATTR}\' must be specified '
                        f'for admin users.'
            )

        instance_id = event.get(INSTANCE_ID_ATTR)
        recommendation_type = event.get(RECOMMENDATION_TYPE_ATTR)
        feedback_status = event.get(FEEDBACK_STATUS_ATTR)

        self._validate_recommendation_type(
            recommendation_type=recommendation_type)
        self._validate_feedback_status(feedback_status=feedback_status,
                                       recommendation_type=recommendation_type)

        _LOG.debug(f'Searching for instance \'{instance_id}\' '
                   f'recommendation of type \'{recommendation_type}\'')
        recommendation = list(
            self.recommendation_history_service.get_recent_recommendation(
                resource_id=instance_id,
                recommendation_type=recommendation_type,
                customer=customer,
                limit=1
            ))
        if not recommendation:
            _LOG.error('No recommendations found matching given query.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content='No recommendations found matching given query.'
            )
        recommendation = recommendation[0]
        _LOG.debug('Updating recommendation')
        recommendation = self.recommendation_history_service.save_feedback(
            recommendation=recommendation,
            feedback_status=feedback_status
        )
        _LOG.debug('Describing recommendation dto')
        response = recommendation.get_dto()

        _LOG.debug(f'Response: {response}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )

    @staticmethod
    def _validate_recommendation_type(recommendation_type: str):
        if recommendation_type.upper() not in RecommendationTypeEnum.list():
            raise ApplicationException(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Invalid recommendation type specified '
                        f'\'{recommendation_type}\'. Options: '
                        f'\'{", ".join(RecommendationTypeEnum.list())}\''
            )

    @staticmethod
    def _validate_feedback_status(recommendation_type: str,
                                  feedback_status: str):
        if feedback_status.upper() not in FeedbackStatusEnum.list():
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Invalid feedback status specified '
                        f'\'{feedback_status}\'. Options: '
                        f'\'{", ".join(FeedbackStatusEnum.list())}\''
            )
        feedback_options = RecommendationTypeEnum.get_allowed_feedback_types(
            recommendation_type=recommendation_type
        )
        if feedback_status not in feedback_options:
            error = f'Specified feedback status \'{feedback_status}\' ' \
                    f'is not applicable for \'{recommendation_type}\' ' \
                    f'recommendation. ' \
                    f'Options: \'{", ".join(feedback_options)}\''
            _LOG.error(error)
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=error
            )
