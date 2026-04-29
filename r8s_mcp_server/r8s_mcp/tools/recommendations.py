from mcp.types import Content, TextContent

from r8s_mcp.commons.constants import RecommendationType
from r8s_mcp.commons.formatters import format_result
from r8s_mcp.services.r8s_client import R8SClient


async def get_recommendations(
        instance_id: str | None = None,
        recommendation_type: RecommendationType | None = None,
        job_id: str | None = None,
        customer_id: str | None = None,
) -> list[Content]:
    """
    Retrieve recommendation from the Syndicate RightSizer
    """
    async with R8SClient() as client:
        result = await client.get_recommendations(
            instance_id=instance_id,
            recommendation_type=recommendation_type,
            job_id=job_id,
            customer_id=customer_id,
        )
        return [TextContent(type='text', text=format_result(result))]