# R8S MCP server

Python [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that exposes Syndicate RightSizer (R8S) HTTP APIs to MCP clients (for example Cursor). It is built on [FastMCP](https://github.com/jlowin/fastmcp) and the official `mcp` Python SDK.

## Requirements

- Python **3.11+** (uses `typing.Literal` unpacking for tool enums)
- Network access to your R8S API base URL
- Credentials the API accepts (username / password used for sign-in)

## Install

From the `r8s_mcp_server` directory (the folder that contains this `README.md`):

```bash
pip install .
```

Editable install while developing:

```bash
pip install -e ".[dev]"
```

This installs the `r8s-mcp` console script and the importable package `r8s_mcp`.

## Configuration

### Required (API)

| Variable | Description |
| --- | --- |
| `R8S_API_URL` | Base URL of the R8S API (no trailing slash required; it is normalized). |
| `R8S_USERNAME` | API username. |
| `R8S_PASSWORD` | API password. |

You can override these with CLI flags `--r8s-api-base-url`, `--username`, and `--password`.

### Optional

| Variable                      | Default    | Description                                                                                                                                                 |
|-------------------------------|------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `R8S_API_TIMEOUT`             | `30.0`     | HTTP client timeout (seconds).                                                                                                                              |
| `R8S_API_MAX_RETRIES`         | `3`        | Retries for failed requests.                                                                                                                                |
| `R8S_MCP_MODE`                | `stdio`    | Transport: `stdio`, `sse`, or `streamable-http`.                                                                                                            |
| `R8S_MCP_HOST`                | `0.0.0.0`  | Bind host for HTTP transports.                                                                                                                              |
| `R8S_MCP_PORT`                | `8080`     | Port for HTTP transports.                                                                                                                                   |
| `R8S_OUTPUT_FORMAT`           | `markdown` | Default tool output format when the `X-R8S-Output-Format` header is absent (`markdown`, `json`, `yaml`).                                                    |
| `LOG_LEVEL`                   | `DEBUG`    | Logging level.                                                                                                                                              |
| `R8S_MCP_SECRET_API_KEY_HASH` | unset      | If set, SHA-256 hex digest of the shared secret; HTTP requests must send `X-R8S-MCP-SECRET-API-KEY` matching that secret. If unset, this check is disabled. |
| `R8S_DEMO_TENAT_NAMES`        | unset      | A comma-separated list of tenant names marked as demo projects.                                                                                             |

### Resources path

Bundled Markdown under `r8s_mcp/resources/` is resolved from the **installed package location** (not the process cwd), so tools like modular-mcp still find docs when the parent server runs from another directory. Override with **`R8S_MCP_RESOURCE_PATH`** if you keep docs elsewhere.

## Run

**Stdio** (typical for local MCP clients):

```bash
r8s-mcp
# or
python -m r8s_mcp
```

**HTTP** (example):

```bash
r8s-mcp --mode streamable-http --host 127.0.0.1 --port 8080
```

Load environment from a file before parsing other options:

```bash
r8s-mcp --env-file /path/to/.env
```

For HTTP transports, optional `--allowed-hosts` configures MCP transport security (allowed Host / Origin patterns).

## Cursor / MCP client

Point your client at the server:

- **Stdio**: command `r8s-mcp` or `python -m r8s_mcp`, cwd set to the project or any directory where env vars are visible.
- **HTTP**: base URL of the streamable HTTP or SSE app your server exposes, plus any required headers (output format, optional secret API key, optional `X-R8S-MCP-USER-NAME`).

## Version

The package version is read from `r8s_mcp/commons/__version__.py` at build time (`hatchling`).

## License

Proprietary unless your organization specifies otherwise.
