import argparse
import os
from typing import cast

from dotenv import load_dotenv

from r8s_mcp.server import main, TransportMode
from r8s_mcp.commons.context import OutputFormat


def main_sync():
    """Entry point for the R8S MCP server."""
    # Pre-parse to load .env file BEFORE other args use os.environ.get()
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument('--env-file', type=str)
    pre_args, _ = pre_parser.parse_known_args()

    if pre_args.env_file:
        load_dotenv(dotenv_path=pre_args.env_file, override=True)

    # Now parse all arguments (env vars from .env are loaded)
    parser = argparse.ArgumentParser(description='Run the R8S MCP server.')

    parser.add_argument(
        '--mode',
        type=str,
        choices=['stdio', 'sse', 'streamable-http'],
        default=os.environ.get('R8S_MCP_MODE', 'stdio'),
        help='Server transport mode (default: stdio)',
    )
    parser.add_argument(
        '--host',
        type=str,
        default=os.environ.get('R8S_MCP_HOST', '0.0.0.0'),
        help='Host for HTTP modes (default: 0.0.0.0)',
    )
    parser.add_argument(
        '--port',
        type=int,
        default=int(os.environ.get('R8S_MCP_PORT', '8080')),
        help='Port for HTTP modes (default: 8080)',
    )
    parser.add_argument(
        '--r8s-api-base-url',
        type=str,
        help='Base URL for the R8S API',
    )
    parser.add_argument(
        '--username',
        type=str,
        help='Username for authentication',
    )
    parser.add_argument(
        '--password',
        type=str,
        help='Password for authentication',
    )
    parser.add_argument(
        '--env-file',
        type=str,
        help='Path to the .env file',
    )
    parser.add_argument(
        '--allowed-hosts',
        type=str,
        nargs='+',
        help='Allowed host headers for HTTP mode',
    )
    parser.add_argument(
        '--default-output-format',
        type=str,
        choices=['markdown', 'json', 'yaml'],
        default=os.environ.get('R8S_OUTPUT_FORMAT', 'markdown'),
        help='Default output format when `X-R8s-Output-Format` header is not '
             'provided (default: markdown)',
    )

    args = parser.parse_args()

    main(
        api_base_url=args.r8s_api_base_url,
        username=args.username,
        password=args.password,
        transport=cast(TransportMode, args.mode),
        host=args.host,
        port=args.port,
        allowed_hosts=args.allowed_hosts,
        default_output_format=cast(OutputFormat, args.default_output_format),
    )


if __name__ == '__main__':
    main_sync()
