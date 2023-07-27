import click

from r8s_group import cli_response, ViewCommand, cast_to_list
from r8s_service.constants import AVAILABLE_CLOUDS


@click.group(name='job')
def job():
    """Manages job Entity"""


@job.command(cls=ViewCommand, name='describe')
@click.option('--job_id', '-id', type=str,
              help='Id of the job to describe.')
@click.option('--job_name', '-name', type=str,
              help='Name of the job to describe.')
@cli_response()
def describe(job_id=None, job_name=None):
    """
    Describes a R8s job.
    """
    from r8s_service.initializer import init_configuration
    return init_configuration().job_get(job_id=job_id, job_name=job_name)


@job.command(cls=ViewCommand, name='submit')
@click.option('--parent_id', '-pid', type=str, required=True,
              help='Maestro RightSizer Parent id.')
@click.option('--customer_id', '-cid', type=str, required=False,
              help='Customer to scan.')
@click.option('--scan_tenants', '-t', multiple=True, required=False,
              help='List of tenants to scan.')
@click.option('--scan_date_from', '-sdf', type=str, required=False,
              help='Processing start date. Format: "%Y-%m-%d" '
                   'Example: 2023-06-20. If not set, '
                   'all available metrics will be used.')
@click.option('--scan_date_to', '-sdt', type=str, required=False,
              help='Processing end date. Format: "%Y-%m-%d" '
                   'Example: 2023-06-20. If not set, scan will be '
                   'limitated by tomorrow\'s date.')
@cli_response()
def submit(parent_id, customer_id, scan_tenants,
           scan_date_from, scan_date_to):
    """
    Submits a R8s job.
    """
    from r8s_service.initializer import init_configuration

    scan_tenants = cast_to_list(scan_tenants)

    return init_configuration().job_post(parent_id=parent_id,
                                         scan_customer=customer_id,
                                         scan_tenants=scan_tenants,
                                         scan_date_from=scan_date_from,
                                         scan_date_to=scan_date_to)


@job.command(cls=ViewCommand, name='terminate')
@click.option('--job_id', '-id', type=str, required=True,
              help='Job id.')
@cli_response()
def terminate(job_id):
    """
    Terminates a R8s batch job.
    """
    from r8s_service.initializer import init_configuration
    return init_configuration().job_delete(job_id=job_id)
