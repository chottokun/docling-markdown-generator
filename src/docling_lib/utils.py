import re
from typing import Any

# Regex to redact sensitive query parameters in strings/URLs (e.g., key=..., api_key=..., etc.)
_SENSITIVE_PARAM_RE = re.compile(
    r"((?:key|api_key|token|secret|credential|api-key)=(?:\w+))", re.IGNORECASE
)


def parse_math_block_newline(value: Any) -> str | bool:
    """
    Parses a string or boolean representation of math_block_newline option into
    either a boolean (True/False) or "auto".
    """
    if isinstance(value, str):
        v = value.strip().lower()
        if v == "true":
            return True
        elif v == "false":
            return False
        elif v == "auto":
            return "auto"
    elif isinstance(value, bool):
        return value
    return "auto"


def sanitize_log_message(message: Any) -> str:
    """
    Sanitizes a message for logging by replacing newline characters with spaces.
    This prevents log injection vulnerabilities.
    Also redacts potential API keys or sensitive query parameters to prevent leakage.
    """
    if not isinstance(message, str):
        message = str(message)
    sanitized = message.replace("\n", " ").replace("\r", " ")
    # Redact sensitive parameters
    sanitized = _SENSITIVE_PARAM_RE.sub(r"\1_REDACTED", sanitized)
    # Also handle specific key=... format where value is a mix of characters
    sanitized = re.sub(
        r"([?&](?:key|api_key|token|secret|credential|api[-_]key)=)[^&\s'\"]+",
        r"\1REDACTED",
        sanitized,
        flags=re.IGNORECASE,
    )
    return sanitized


def serialize_table_data_to_markdown(table_data) -> str:
    """
    Converts docling TableData into a clean, exact markdown table.
    """
    if (
        not table_data
        or not hasattr(table_data, "table_cells")
        or not table_data.table_cells
    ):
        return ""

    num_rows = getattr(table_data, "num_rows", 0)
    num_cols = getattr(table_data, "num_cols", 0)

    # If dimensions are not explicitly specified, calculate them dynamically from the cells
    if not num_rows or not num_cols:
        for cell in table_data.table_cells:
            num_rows = max(num_rows, cell.end_row_offset_idx)
            num_cols = max(num_cols, cell.end_col_offset_idx)

    if not num_rows or not num_cols:
        return ""

    grid = [["" for _ in range(num_cols)] for _ in range(num_rows)]

    for cell in table_data.table_cells:
        r_start = cell.start_row_offset_idx
        c_start = cell.start_col_offset_idx
        if 0 <= r_start < num_rows and 0 <= c_start < num_cols:
            grid[r_start][c_start] = (
                cell.text.replace("\n", " ").replace("|", "\\|").strip()
                if cell.text
                else ""
            )

    lines = []
    if num_rows > 0:
        lines.append("| " + " | ".join(grid[0]) + " |")
        lines.append("| " + " | ".join(["---"] * num_cols) + " |")
        for r in range(1, num_rows):
            lines.append("| " + " | ".join(grid[r]) + " |")

    return "\n".join(lines)
