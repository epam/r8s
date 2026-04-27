from pathlib import Path

from fastmcp import FastMCP
from fastmcp.resources.types import FileResource
from pydantic import AnyUrl

from r8s_mcp.commons.log_helper import get_logger

_LOG = get_logger(__name__)

_DOC_URI_PREFIX = 'resource://'


class ResourceManager:
    """Loads bundled markdown files and registers them as FastMCP file resources."""

    def __init__(self,
                 resource_path: str | Path = './resources',
                 ) -> None:

        self.resource_path = Path(resource_path).expanduser().resolve()
        self._resources: list[FileResource] = []

        for f in sorted(self.resource_path.glob('*.md')):
            abs_path = f.resolve()
            uri = f'{_DOC_URI_PREFIX}/{f.name}'
            self._resources.append(
                FileResource(
                    uri=AnyUrl(uri),
                    name=f.name,
                    path=abs_path,
                    mime_type='text/markdown',
                ),
            )

        _LOG.info(
            f'Prepared {len(self._resources)} FastMCP resources from {self.resource_path}',
        )

    def register_resources(self, mcp: FastMCP) -> None:
        for resource in self._resources:
            mcp.add_resource(resource)
