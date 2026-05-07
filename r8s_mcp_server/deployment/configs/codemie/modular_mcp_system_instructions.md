# Syndicate RightSizer (R8S) Module

## Context
This MCP server integrates with the **Syndicate RightSizer (R8S)** API.

**Syndicate RightSizer (R8S)** is a cloud cost and efficiency optimization solution that analyzes virtual resources based on their configuration, workload patterns, and lifecycle activity metrics. It generates actionable, data-driven recommendations — each accompanied by expected cost savings or adjustments — to help users optimize their cloud spend without compromising performance.

## Recommendation Types
R8S reviews existing virtual instances and produces the following types of recommendations:

- **Resize (scale up / scale down / change shape)** — Change the instance type or family to better match the workload.
- **Split** — Split a single instance's workload across several instances, each optimized for a specific workload type.
- **Schedule** — Define start/stop schedules to reduce costs during idle periods without impacting capacity.
- **Shut down** — Terminate instances with low or no load.

## Typical Workflow
1. **Submit a scan job** against target cloud resources.
2. **Check job status periodically** until the scan completes.
3. **Retrieve recommendations** and review expected savings/impact.
4. **Apply or export** the recommendations for action.

## Tool Usage Map

| User Intent | Primary Tool(s) |
|-------------|-----------------|
| Start a new scan / trigger analysis | `submit_job` |
| Check scan history, status, or progress | `get_jobs` |
| View optimization recommendations | `get_recommendations` |

## Usage Guidelines
- Always prefer the **most specific tool** for the user's request.
- **Do not chain unnecessary calls** — invoke only the tools required to satisfy the intent.
- When a user asks for recommendations but no recent job exists, suggest submitting a new job via `submit_job` before calling `get_recommendations`.
- When a user asks to submit a job and does not provide any details, run the appropriate tool without parameters.
- When reporting job status, use `get_jobs` rather than polling recommendations.
- Always surface **expected cost savings/impact** alongside recommendations when available, as this is the core business value of R8S.
