from typing import Annotated

from mcp.types import Content, TextContent
from pydantic import Field

from r8s_mcp.commons.constants import CheckHealthType
from r8s_mcp.commons.formatters import format_result
from r8s_mcp.services.r8s_client import R8SClient


async def health_check(
    types: Annotated[
        list[CheckHealthType] | None,
        Field(
            description=(
                'Which health check categories to run '
                '(subset of APPLICATION, PARENT, STORAGE, SHAPE, '
                'OPERATION_MODE, SHAPE_UPDATE_DATE). Omit for the full suite.'
            ),
        ),
    ] = None,
) -> list[Content]:
    """
    Check the health status of the Syndicate RightSizer
    """
    async with R8SClient() as client:
        result = await client.health_check(types=types)
        return [TextContent(type='text', text=format_result(result))]
