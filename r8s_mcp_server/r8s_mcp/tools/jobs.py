from mcp.types import Content, TextContent

from r8s_mcp.commons.formatters import format_result
from r8s_mcp.services.r8s_client import R8SClient


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
        return [TextContent(type='text', text=format_result(result))]


async def submit_job(
        application_id: str | None = None,
        parent_id: str | None = None,
        scan_tenants: list[str] | None = None,
        scan_from_date: str | None = None,
        scan_to_date: str | None = None,
        force_rescan: bool | None = None,
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
        return [TextContent(type='text', text=format_result(result))]
