import copy
from datetime import datetime
from typing import List

from commons.constants import ACTION_SHUTDOWN
from commons.log_helper import get_logger
from services.saving.abstract_saving import AbstractSaving
from services.saving.saving import Saving
from services.saving.saving_result import SavingResult
from services.saving.split_saving import SplitSaving, SplitInstance
from services.shape_price_service import ShapePriceService

HOURS_IN_MONTH = 730.5
SECONDS_IN_DAY = 86400

_LOG = get_logger('r8s-saving_service')


class SavingService:
    def __init__(self, shape_price_service: ShapePriceService):
        self.shape_price_service = shape_price_service

        self.action_calculator_mapping = {
            'SCHEDULE': self._calculate_schedule_saving,
            'SCALE_DOWN': self._calculate_resize_saving,
            'SCALE_UP': self._calculate_resize_saving,
            'CHANGE_SHAPE': self._calculate_resize_saving,
            'SHUTDOWN': self._calculate_shutdown_saving,
            'SPLIT': self._calculate_split_saving
        }

    def calculate_savings(self, general_actions, current_shape: str,
                          recommended_shapes, schedule,
                          customer, region, os, price_type='on_demand'):
        saving_options: List[AbstractSaving] = []
        general_actions = copy.copy(general_actions)

        # as an alternative for shutdown
        if 'SHUTDOWN' in general_actions:
            general_actions.append('SCALE_DOWN')

        current_monthly_price = self._get_monthly_price(
            instance_type=current_shape, customer=customer,
            region=region, price_type=price_type, os=os)

        if not current_monthly_price:
            _LOG.warning(f'No shape price found for current shape '
                         f'\'{current_shape}\'')
            return {}

        for action in general_actions:
            calculator_func = self.action_calculator_mapping.get(action)
            if not calculator_func:
                continue
            kwargs = {
                'action': action,
                'current_instance_type': current_shape,
                'recommended_shapes': recommended_shapes,
                'schedule': schedule,
                'current_monthly_price': current_monthly_price,
                'customer': customer,
                'region': region,
                'price_type': price_type,
                'os': os
            }
            try:
                result = calculator_func(**kwargs)
                if not result:
                    continue
            except:
                _LOG.error(f'Exception occurred while calculating saving '
                           f'for action \'{action}\'')
                continue

            if isinstance(result, list):
                saving_options.extend(result)
            elif isinstance(result, AbstractSaving):
                saving_options.append(result)

        saving_options.sort(key=lambda k: k.saving_month_usd, reverse=True)

        saving_result = SavingResult(
            current_instance_type=current_shape,
            current_monthly_price_usd=current_monthly_price,
            saving_options=saving_options
        )
        return saving_result.as_dict()

    def _calculate_schedule_saving(self, action, schedule,
                                   current_monthly_price, **kwargs):

        total_coverage_percent = 0.0
        for schedule_item in schedule:
            coverage_percent = self._get_schedule_coverage_percent(
                schedule=schedule_item)

            # schedules do not intercept
            total_coverage_percent += coverage_percent

        new_monthly_price = round(current_monthly_price *
                                  total_coverage_percent, 2)

        saving = Saving(
            action=action,
            old_month_price=current_monthly_price,
            new_month_price=new_monthly_price
        )
        return saving

    def _calculate_resize_saving(self, action, recommended_shapes,
                                 current_monthly_price, customer, region,
                                 os, price_type, **kwargs):
        savings = []

        for shape_data in recommended_shapes:
            instance_type = shape_data.get('name')
            monthly_price = self._get_monthly_price(
                instance_type=instance_type,
                customer=customer,
                region=region,
                price_type=price_type,
                os=os)
            if monthly_price:
                saving = Saving(
                    action=action,
                    old_month_price=current_monthly_price,
                    new_month_price=monthly_price,
                    target_instance_type=instance_type
                )
                savings.append(saving)
        return savings

    @staticmethod
    def _calculate_shutdown_saving(current_monthly_price, **kwargs):
        return Saving(
            action=ACTION_SHUTDOWN,
            old_month_price=current_monthly_price,
            new_month_price=0
        )

    def _calculate_split_saving(self, current_instance_type,
                                recommended_shapes, current_monthly_price,
                                customer, region, os, price_type, **kwargs):
        split_instances = []
        total_monthly_price = 0.0

        for shape_data in recommended_shapes:
            probability = shape_data.get('probability')
            if not probability:
                continue
            instance_type = shape_data.get('name')
            monthly_price = self._get_monthly_price(
                instance_type=instance_type,
                customer=customer, region=region,
                price_type=price_type, os=os)
            monthly_price = round(monthly_price * probability, 2)
            total_monthly_price += monthly_price

            split_instance = SplitInstance(
                instance_type=instance_type,
                monthly_price_usd=monthly_price,
                probability=probability
            )
            split_instances.append(split_instance)
        return SplitSaving(
            old_month_price=current_monthly_price,
            new_month_price=round(total_monthly_price, 2),
            split_instances=split_instances
        )

    def _get_monthly_price(self, instance_type,
                           customer, region, os, price_type):
        shape_price = self.shape_price_service.get(
            customer=customer,
            name=instance_type,
            region=region,
            os=os
        )
        if not shape_price:
            return
        hour_price = getattr(shape_price, price_type, None)
        if not hour_price:
            return
        return round(hour_price * HOURS_IN_MONTH, 2)

    @staticmethod
    def _get_schedule_coverage_percent(schedule: dict):
        weekdays = schedule.get('weekdays')
        weekdays = list(set(weekdays))

        weekdays_coverage_percent = len(weekdays) / 7

        start_str = schedule.get('start')
        stop_str = schedule.get('stop')

        start_dt = datetime.strptime(start_str, '%H:%M')
        stop_dt = datetime.strptime(stop_str, '%H:%M')

        schedule_duration_seconds = int((stop_dt - start_dt).total_seconds())

        day_coverage_percent = schedule_duration_seconds / SECONDS_IN_DAY

        return round(weekdays_coverage_percent * day_coverage_percent, 2)
