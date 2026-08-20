import json
import yaml
from typing import Any, Dict, List

from r8s_mcp.commons.context import get_output_format
from r8s_mcp.commons.log_helper import get_logger

_LOG = get_logger(__name__)


def format_result(
        data: Any,
        title: str | None = None,
        demo_notice: str | None = None,
) -> str:
    """
    Format result based on config output format.

    Args:
        data: The data to format
        title: Optional title for the formatted output
        demo_notice: Optional notice to include in the formatted output
            regarding demo tenants

    Returns:
        Formatted string based on configured output format
    """

    output_format = get_output_format()
    _LOG.debug(f'Formatting result with format: {output_format}')

    formatted = format_response(
        data=data,
        format_type=output_format,
        title=title,
    )

    if demo_notice:
        formatted = f'{demo_notice}\n\n{formatted}'

    return formatted

def format_response(
        data: Any,
        format_type: str = 'markdown',
        title: str = None,
) -> str:
    """
    Format response data based on the specified format type.

    Args:
        data: The data to format
        format_type: One of 'markdown', 'json', 'yaml'
        title: Optional title for markdown format

    Returns:
        Formatted string
    """
    if format_type == 'json':
        return format_as_json(data)
    elif format_type == 'yaml':
        return format_as_yaml(data)
    else:  # markdown (default)
        return format_as_markdown(data, title=title)


def format_as_json(data: Any) -> str:
    """Convert data to formatted JSON."""
    return json.dumps(data, indent=2, ensure_ascii=False)


def format_as_yaml(data: Any) -> str:
    """Convert data to YAML format."""
    return yaml.dump(data, default_flow_style=False, allow_unicode=True)


def format_as_markdown(data: Any, title: str = None) -> str:
    """Convert data to Markdown format."""
    lines = []

    if title:
        lines.append(f"# {title}\n")

    if isinstance(data, dict):
        lines.append(_dict_to_markdown(data))
    elif isinstance(data, list):
        lines.append(_list_to_markdown(data))
    else:
        lines.append(str(data))

    return "\n".join(lines)


def _dict_to_markdown(d: Dict, level: int = 2) -> str:
    """Convert dictionary to Markdown."""
    lines = []

    for key, value in d.items():
        # Format key as header
        header = "#" * min(level, 6)  # Max 6 levels in Markdown
        formatted_key = str(key).replace('_', ' ').title()
        lines.append(f"{header} {formatted_key}\n")

        if isinstance(value, dict):
            lines.append(_dict_to_markdown(value, level + 1))
        elif isinstance(value, list):
            lines.append(_list_to_markdown(value))
        elif isinstance(value, bool):
            lines.append(f"{'Yes' if value else 'No'}\n")
        elif value is None:
            lines.append("_Not set_\n")
        else:
            # Handle multi-line strings
            str_value = str(value)
            if '\n' in str_value:
                lines.append(f"```\n{str_value}\n```\n")
            else:
                lines.append(f"{str_value}\n")

    return "\n".join(lines)


def _list_to_markdown(lst: List) -> str:
    """Convert list to Markdown."""
    if not lst:
        return "_Empty list_\n"

    lines = []

    # Check if it's a list of dicts (table format)
    if all(isinstance(item, dict) for item in lst):
        lines.append(_list_of_dicts_to_table(lst))
    else:
        for item in lst:
            if isinstance(item, dict):
                lines.append("\n---\n")
                lines.append(_dict_to_markdown(item, level=3))
            else:
                lines.append(f"- {item}")

    return "\n".join(lines)


def _list_of_dicts_to_table(items: List[Dict]) -> str:
    """Convert list of dictionaries to Markdown table."""
    if not items:
        return ""

    # Get all unique keys from all items
    all_keys = set()
    for item in items:
        all_keys.update(item.keys())
    keys = sorted(all_keys)

    # Header
    header_names = [str(k).replace('_', ' ').title() for k in keys]
    lines = [
        "| " + " | ".join(header_names) + " |",
        "| " + " | ".join("---" for _ in keys) + " |",
    ]

    # Rows
    for item in items:
        row_values = []
        for k in keys:
            value = item.get(k, "")
            # Escape pipe characters and convert to string
            str_value = str(value).replace("|", "\\|").replace("\n", " ")
            # Truncate long values #
            # TODO: Investigate and handle long values.
            # if len(str_value) > 50:
            #     str_value = str_value[:47] + "..."
            row_values.append(str_value)
        lines.append("| " + " | ".join(row_values) + " |")

    return "\n".join(lines)
