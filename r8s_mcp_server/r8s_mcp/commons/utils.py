import json

from r8s_mcp.commons.context import get_mcp_config
from r8s_mcp.commons.log_helper import get_logger

_LOG = get_logger(__name__)

def resolve_demo_tenants():
    """Resolve the demo tenant names from the MCP configuration."""

    config = get_mcp_config()
    _LOG.debug(f"Resolved demo tenant names: {str(set(config.demo_tenant_names))}")
    return config.demo_tenant_names

def demo_tenant_notice(
    tenant_names_in_scope: set[str] | None = None,
) -> str:
    """
    Plain-text notice when any tenant in scope is configured as a demo tenant.
    """
    demos = resolve_demo_tenants()
    if not demos or not tenant_names_in_scope:
        return ''
    hit = set(t for t in tenant_names_in_scope if t in demos)
    if not hit:
        return ''
    if len(hit) == 1:
        only = next(iter(hit))
        name_json = json.dumps(only)
        return (
            f'Demo project: this request involves shared demo project(tenant) '
            f'{name_json}.'
        )
    names_json = ', '.join(json.dumps(t) for t in sorted(hit))
    return (
        f'Demo project: this result involves shared demo projects(tenants) '
        f'{names_json}.'
    )


def extract_tenant_names_from_recommendations(result: dict) -> set[str]:
    """
    Recommendation items have a flat `tenant` field.
    """
    tenant_names = set()
    for item in (result or {}).get('items', []):
        tenant = item.get('tenant')
        if tenant:
            tenant_names.add(tenant)
    return tenant_names


def extract_tenant_names_from_jobs(result: dict) -> set[str]:
    """
    Job items keep tenants as keys of `tenant_status_map`.
    """
    tenant_names = set()
    for item in (result or {}).get('items', []):
        status_map = item.get('tenant_status_map') or {}
        tenant_names.update(status_map.keys())
    return tenant_names
