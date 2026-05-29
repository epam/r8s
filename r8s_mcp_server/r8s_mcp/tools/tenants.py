from mcp.types import Content, TextContent

from r8s_mcp.commons.formatters import format_result
from r8s_mcp.commons.utils import demo_tenant_notice
from r8s_mcp.services.r8s_client import R8SClient


async def get_tenants(
        name: str | None = None,
) -> list[Content]:
    """
    Retrieve tenants from the Syndicate RightSizer
    """
    async with R8SClient() as client:
        result = await client.get_tenants(
            name=name,
        )
        tenant_names = set()  # TODO get tenant names from result
        demo_notice = demo_tenant_notice(tenant_names)

        formatted_text = format_result(
            data=result,
            title="Jobs",
            demo_notice=demo_notice,
        )

        return [TextContent(type='text', text=formatted_text)]
