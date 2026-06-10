from mcp.types import Content, TextContent

from r8s_mcp.commons.formatters import format_result
from r8s_mcp.commons.utils import (
    demo_tenant_notice, extract_tenant_names_from_jobs,
)
from r8s_mcp.services.r8s_client import R8SClient
from r8s_mcp.commons.log_helper import get_logger

_LOG = get_logger(__name__)


async def get_jobs(
        job_id: str | None = None,
        job_name: str | None = None,
        limit: int | None = None,
) -> list[Content]:
    """
    Retrieve jobs from the Syndicate RightSizer
    """
    async with R8SClient() as client:
        result = await client.get_jobs(
            job_id=job_id,
            job_name=job_name,
            limit=limit,
        )
        _LOG.info(result)
        tenant_names = extract_tenant_names_from_jobs(result)
        demo_notice = demo_tenant_notice(tenant_names)

        formatted_text = format_result(
            data=result,
            title="Jobs",
            demo_notice=demo_notice,
        )

        return [TextContent(type='text', text=formatted_text)]


async def submit_job(
        application_id: str | None = None,
        parent_id: str | None = None,
        scan_tenants: list[str] | None = None,
        scan_from_date: str | None = None,
        scan_to_date: str | None = None,
        force_rescan: bool = True,
) -> list[Content]:
    """
    Submit a new job to the Syndicate RightSizer
    """
    async with R8SClient() as client:
        result = await client.submit_job(
            application_id=application_id,
            parent_id=parent_id,
            scan_tenants=scan_tenants,
            scan_from_date=scan_from_date,
            scan_to_date=scan_to_date,
            force_rescan=force_rescan,
        )
        _LOG.info(result)
        tenant_names = extract_tenant_names_from_jobs(result)
        demo_notice = demo_tenant_notice(tenant_names)

        formatted_text = format_result(
            data=result,
            title="Jobs",
            demo_notice=demo_notice,
        )

        return [TextContent(type='text', text=formatted_text)]
