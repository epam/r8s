from r8s_mcp.tools.health import health_check
from r8s_mcp.tools.jobs import get_jobs, submit_job
from r8s_mcp.tools.recommendations import get_recommendations
from r8s_mcp.tools.tenants import get_tenants

tools_mapping = {
        "health_check": health_check,
        "get_jobs": get_jobs,
        "submit_job": submit_job,
        "get_recommendations": get_recommendations,
        "get_tenants": get_tenants,
    }
