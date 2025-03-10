import click

from r8scli.group import cli_response, ViewCommand, cast_to_list
from r8scli.service.constants import AVAILABLE_CLOUDS


@click.group(name='job')
def job():
    """Manages job Entity"""


@job.command(cls=ViewCommand, name='describe')
@click.option('--job_id', '-id', type=str,
              help='Id of the job to describe.')
@click.option('--job_name', '-name', type=str,
              help='Name of the job to describe.')
@click.option('--limit', '-l', type=int,
              help='Limit maximum amount of jobs in the response.')
@cli_response(reversed=True)
def describe(job_id=None, job_name=None, limit=None):
    """
    Describes a R8s job.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().job_get(
        job_id=job_id, job_name=job_name, limit=limit)


@job.command(cls=ViewCommand, name='submit')
@click.option('--application_id', '-aid', type=str, required=False,
              help='Maestro RIGHTSIZER_LICENSES application id.')
@click.option('--parent_id', '-pid', type=str, required=False,
              help='Maestro RIGHTSIZER_LICENSES parent id. If not specified, '
                   'all available linked parents will be used')
@click.option('--scan_tenants', '-t', multiple=True, required=False,
              help='List of tenants to scan.')
@click.option('--scan_from_date', '-sfd', type=str, required=False,
              help='Processing start date. Format: "%Y-%m-%d" '
                   'Example: 2023-06-20. If not set, '
                   'all available metrics will be used.')
@click.option('--scan_to_date', '-std', type=str, required=False,
              help='Processing end date. Format: "%Y-%m-%d" '
                   'Example: 2023-06-20. If not set, scan will be '
                   'limitated by tomorrow\'s date.')
@cli_response()
def submit(application_id, parent_id, scan_tenants,
           scan_from_date, scan_to_date):
    """
    Submits a R8s job.
    """
    from r8scli.service.initializer import init_configuration

    scan_tenants = cast_to_list(scan_tenants)

    return init_configuration().job_post(
        application_id=application_id,
        parent_id=parent_id,
        scan_tenants=scan_tenants,
        scan_from_date=scan_from_date,
        scan_to_date=scan_to_date)


@job.command(cls=ViewCommand, name='terminate')
@click.option('--job_id', '-id', type=str, required=True,
              help='Job id.')
@cli_response()
def terminate(job_id):
    """
    Terminates a R8s batch job.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().job_delete(job_id=job_id)
