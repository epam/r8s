import click

from r8scli.group import cli_response, ViewCommand, cast_to_list


@click.group(name='report')
def report():
    """Manages reports"""


@report.command(cls=ViewCommand, name='general')
@click.option('--job_id', '-id', type=str, required=True,
              help='Job id.')
@click.option('--customer_id', '-cid', type=str, required=False,
              help='Customer to filter result instances.')
@click.option('--cloud', '-c', type=str, required=False,
              help='Cloud to filter result instances.')
@click.option('--tenant', '-t', type=str, required=False,
              help='Tenant to filter result instances.')
@click.option('--region', '-r', type=str, required=False,
              help='Region to filter result instances.')
@click.option('--instance_id', '-iid', type=str, required=False,
              help='Get result for specific instance.')
@click.option('--detailed', '-d', is_flag=True,  required=False, default=False,
              help='Get full content of recommendations.')
@cli_response()
def general(job_id, customer_id, cloud, tenant, region, instance_id, detailed):
    """
    Describes a R8s general job report.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().report_describe_general(
        job_id=job_id, customer=customer_id, cloud=cloud, tenant=tenant,
        region=region, detailed=detailed, instance_id=instance_id)


@report.command(cls=ViewCommand, name='download')
@click.option('--job_id', '-id', type=str, required=True,
              help='Job id.')
@click.option('--customer_id', '-cid', type=str, required=False,
              help='Customer to filter result instances.')
@click.option('--tenant', '-t', type=str, required=False,
              help='Tenant to filter result instances.')
@click.option('--region', '-r', type=str, required=False,
              help='Region to filter result instances.')
@cli_response()
def download(job_id, customer_id, tenant, region):
    """
    Describe a R8s job report with presigned url.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().report_describe_download(
        job_id=job_id, customer=customer_id, tenant=tenant, region=region)


@report.command(cls=ViewCommand, name='initiate_tenant_mail_report')
@click.option('--customer_id', '-cid', type=str, required=True,
              help='Customer name to initiate report for.')
@click.option('--tenants', '-t', multiple=True,
              required=True, help='List of tenants to generate report.')
@cli_response()
def initiate_tenant_mail_report(customer_id, tenants):
    """
    Initiates tenant mail report.
    """
    from r8scli.service.initializer import init_configuration

    tenants = cast_to_list(tenants)
    return init_configuration().initiate_tenant_mail_report(
        customer=customer_id,
        tenants=tenants
    )
