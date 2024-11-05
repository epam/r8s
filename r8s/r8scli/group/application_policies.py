import click

from r8scli.group import cli_response, ViewCommand
from r8scli.service.constants import ALLOWED_PROTOCOLS, \
    PROTOCOL_HTTPS, AVAILABLE_CLOUDS, PARAM_TAG, PARAM_COOLDOWN, \
    PARAM_SCALE_STEP, SCAPE_STEP_AUTO_DETECT, PARAM_THRESHOLDS, PARAM_DESIRED, \
    PARAM_MIN, PARAM_MAX, PARAM_TYPE, GROUP_POLICY_AUTO_SCALING, PARAM_ID
from r8scli.service.local_response_processor import LocalCommandResponse


@click.group(name='policies')
def policies():
    """Manages RIGHTSIZER Application Group Policies"""


@policies.command(cls=ViewCommand, name='describe')
@click.option('--application_id', '-aid', type=str, required=True,
              help='Id of the application to describe.')
@click.option('--group_id', '-gid', type=str, required=False,
              help='Group policy id to describe.')
@cli_response()
def describe(application_id=None, group_id=None):
    """
    Describes a RIGHTSIZER Application group policy.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().application_policies_get(
        application_id=application_id,
        group_id=group_id
    )


@policies.command(cls=ViewCommand, name='add_autoscaling')
@click.option('--application_id', '-aid', type=str, required=True,
              help='Id of the application to add policy.')
@click.option('--tag', '-tg', type=str, required=True,
              help='Group policy tag name.')
@click.option('--cooldown_days', '-cd', type=int, default=7,
              help='Minimum amount of days between scaling events.')
@click.option('--scale_step', '-ss', type=int, required=False,
              help='Amount of instances to spin up/terminate during scaling '
                   'event. If not specified, AUTO_DETECT will be used.')
@click.option('--threshold_min', '-tmin', type=int,
              help='Threshold value for triggering scale in event')
@click.option('--threshold_desired', '-tdes', type=int,
              help='Desired instance load.')
@click.option('--threshold_max', '-tmax', type=int,
              help='Threshold value for triggering scale out event')
@cli_response()
def add_autoscaling(application_id: str, tag: str, cooldown_days: int,
                    scale_step: int = None, threshold_min=None,
                    threshold_desired=None, threshold_max=None):
    """
    Adds AUTO_SCALING group policy to a RIGHTSIZER Application.
    """
    group_policy = {
        PARAM_TYPE: GROUP_POLICY_AUTO_SCALING,
        PARAM_TAG: tag,
        PARAM_COOLDOWN: cooldown_days,
    }

    if scale_step:
        group_policy[PARAM_SCALE_STEP] = scale_step

    thresholds = (threshold_min, threshold_desired, threshold_max)
    if any(thresholds):
        if not all(thresholds):
            return LocalCommandResponse(
                body={'message': 'Both min, max and desired threshold '
                                 'values should be specified'})
        group_policy[PARAM_THRESHOLDS] = {
            PARAM_MIN: threshold_min,
            PARAM_DESIRED: threshold_desired,
            PARAM_MAX: threshold_max
        }

    from r8scli.service.initializer import init_configuration
    return init_configuration().application_policies_post(
        application_id=application_id,
        group_policy=group_policy
    )


@policies.command(cls=ViewCommand, name='update_autoscaling')
@click.option('--application_id', '-aid', type=str, required=True,
              help='Id of the application to update policy.')
@click.option('--group_id', '-gid', type=str, required=True,
              help='Id of the group to update.')
@click.option('--tag', '-tg', type=str,
              help='Group policy tag name.')
@click.option('--cooldown_days', '-cd', type=int,
              help='Minimum amount of days between scaling events.')
@click.option('--scale_step', '-ss', type=int,
              help='Amount of instances to spin up/terminate during scaling '
                   'event. If set to 0, AUTO_DETECT will be used.')
@click.option('--threshold_min', '-tmin', type=int,
              help='Threshold value for triggering scale in event')
@click.option('--threshold_desired', '-tdes', type=int,
              help='Desired instance load.')
@click.option('--threshold_max', '-tmax', type=int,
              help='Threshold value for triggering scale out event')
@cli_response()
def update_autoscaling(application_id: str, group_id: str, tag=None,
                       cooldown_days=None,
                       scale_step=None, threshold_min=None,
                       threshold_desired=None, threshold_max=None):
    """
    Updates AUTO_SCALING group policy in RIGHTSIZER Application.
    """
    group_policy = {
        PARAM_ID: group_id,
        PARAM_TYPE: GROUP_POLICY_AUTO_SCALING,
    }

    if scale_step is not None:
        if scale_step == 0:
            group_policy[PARAM_SCALE_STEP] = SCAPE_STEP_AUTO_DETECT
        else:
            group_policy[PARAM_SCALE_STEP] = scale_step
    if tag:
        group_policy[PARAM_TAG] = tag
    if cooldown_days:
        group_policy[PARAM_COOLDOWN] = cooldown_days

    thresholds = (threshold_min, threshold_desired, threshold_max)
    if any(thresholds):
        if not all(thresholds):
            return LocalCommandResponse(
                body={'message': 'Both min, max and desired threshold '
                                 'values should be specified'})
        group_policy[PARAM_THRESHOLDS] = {
            PARAM_MIN: threshold_min,
            PARAM_DESIRED: threshold_desired,
            PARAM_MAX: threshold_max
        }
    from r8scli.service.initializer import init_configuration
    return init_configuration().application_policies_patch(
        application_id=application_id,
        group_policy=group_policy
    )


@policies.command(cls=ViewCommand, name='delete')
@click.option('--application_id', '-aid', type=str, required=True,
              help='Id of the RIGHTSIZER application.')
@click.option('--group_id', '-gid', type=str, required=True,
              help='Group policy id to delete.')
@cli_response()
def delete(application_id=None, group_id=None):
    """
    Deletes a RIGHTSIZER Application group policy.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().application_policies_delete(
        application_id=application_id,
        group_id=group_id
    )
