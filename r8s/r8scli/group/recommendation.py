import click

from r8scli.group import cli_response, cast_to_list, ViewCommand
from r8scli.service.constants import AVAILABLE_RECOMMENDATION_TYPES, \
    AVAILABLE_FEEDBACK_STATUSES


@click.group(name='recommendation')
def recommendation():
    """Manages Recommendation Entity"""


@recommendation.command(cls=ViewCommand, name='describe')
@click.option('--instance_id', '-iid', type=str,
              help='Instance id to describe recommendations.')
@click.option('--recommendation_type', '-type',
              type=click.Choice(AVAILABLE_RECOMMENDATION_TYPES),
              help='Recommendation type to describe.')
@click.option('--job_id', '-jid', type=str,
              help='Describe recommendation by job id.')
@click.option('--customer_id', '-cid', type=str,
              help='Describe recommendation by customer (admin users only)')
@cli_response()
def describe(instance_id=None, recommendation_type=None, job_id=None,
             customer_id=None):
    """
    Describes a R8s recommendations.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().recommendation_get(
        instance_id=instance_id,
        recommendation_type=recommendation_type,
        customer=customer_id,
        job_id=job_id
    )


@recommendation.command(cls=ViewCommand, name='update')
@click.option('--instance_id', '-iid', type=str, required=True,
              help='Instance id to update recommendations.')
@click.option('--recommendation_type', '-type', required=True,
              type=click.Choice(AVAILABLE_RECOMMENDATION_TYPES),
              help='Recommendation type to update.')
@click.option('--feedback_status', '-fst', required=True,
              type=click.Choice(AVAILABLE_FEEDBACK_STATUSES),
              help='Feedback status to set.')
@click.option('--customer_id', '-cid', type=str,
              help='Update recommendation by customer (admin users only)')
@cli_response()
def update(instance_id, recommendation_type,feedback_status,
           customer_id):
    """
    Saves feedback for r8s recommendation
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().recommendation_patch(
        instance_id=instance_id,
        recommendation_type=recommendation_type,
        feedback_status=feedback_status,
        customer=customer_id,
    )
