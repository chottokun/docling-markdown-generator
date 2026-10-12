import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

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


def _parse_workbook_relationships(wb_rels_tree: Any, ns_rel: str) -> dict[str, str]:
    """Extracts target paths from workbook relationships XML."""
    wb_rels: dict[str, str] = {}
    for rel in wb_rels_tree.findall(f"{{{ns_rel}}}Relationship"):
        r_id = rel.attrib.get("Id")
        target = rel.attrib.get("Target", "")
        if r_id and target:
            target = target.lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            wb_rels[r_id] = target
    return wb_rels


def _parse_sheet_relationships(
    sheet_rels_tree: Any, sheet_dir: str, ns_rel: str
) -> dict[str, str]:
    """Extracts drawing target paths from sheet relationships XML."""
    sheet_rels: dict[str, str] = {}
    for rel in sheet_rels_tree.findall(f"{{{ns_rel}}}Relationship"):
        r_id_s = rel.attrib.get("Id")
        target_s = rel.attrib.get("Target", "")
        if r_id_s and target_s:
            target_s = target_s.lstrip("/")
            if not target_s.startswith("xl/") and not target_s.startswith("../"):
                target_s = f"{sheet_dir}/{target_s}"
            elif target_s.startswith("../"):
                target_s = "xl/" + target_s.split("../", 1)[1]
            sheet_rels[r_id_s] = target_s
    return sheet_rels


def _parse_drawing_relationships(
    drawing_rels_tree: Any, drawing_dir: str, ns_rel: str
) -> dict[str, str]:
    """Extracts media target paths from drawing relationships XML."""
    drawing_rels: dict[str, str] = {}
    for rel in drawing_rels_tree.findall(f"{{{ns_rel}}}Relationship"):
        r_id_d = rel.attrib.get("Id")
        target_d = rel.attrib.get("Target", "")
        if r_id_d and target_d:
            target_d = target_d.lstrip("/")
            if "media/" in target_d:
                target_d = "xl/media/" + target_d.rsplit("media/", 1)[1]
            elif not target_d.startswith("xl/"):
                target_d = f"{drawing_dir}/{target_d}"
            drawing_rels[r_id_d] = target_d
    return drawing_rels


def _extract_anchors_from_drawing(
    zf: Any,
    drawing_tree: Any,
    drawing_rels: dict[str, str],
    sheet_name: str,
    sheet_idx: int,
    namelist: list[str],
    ns_xdr: str,
    ns_a: str,
    rel_embed_attr: str,
) -> list[dict[str, Any]]:
    """Parses image anchors from a drawing XML tree and returns extracted media items."""
    import hashlib
    import io

    from PIL import Image as PILImage

    extracted: list[dict[str, Any]] = []
    anchors = drawing_tree.findall(
        f"{{{ns_xdr}}}twoCellAnchor"
    ) + drawing_tree.findall(f"{{{ns_xdr}}}oneCellAnchor")

    for anchor in anchors:
        from_node = anchor.find(f"{{{ns_xdr}}}from")
        row_idx = 0
        col_idx = 0
        if from_node is not None:
            col_elem = from_node.find(f"{{{ns_xdr}}}col")
            row_elem = from_node.find(f"{{{ns_xdr}}}row")
            if col_elem is not None and col_elem.text:
                col_idx = int(col_elem.text)
            if row_elem is not None and row_elem.text:
                row_idx = int(row_elem.text)

        blip = anchor.find(f".//{{{ns_a}}}blip")
        if blip is None:
            continue

        embed_id = blip.attrib.get(rel_embed_attr)
        if not embed_id:
            continue

        media_path = drawing_rels.get(embed_id)
        if not media_path or media_path not in namelist:
            continue

        img_bytes = zf.read(media_path)
        filename = media_path.rsplit("/", 1)[-1]
        pil_img = None
        try:
            pil_img = PILImage.open(io.BytesIO(img_bytes))
            pil_img.load()
        except Exception:
            pass

        sha256_hash = hashlib.sha256(img_bytes).hexdigest()
        extracted.append(
            {
                "sheet_name": sheet_name,
                "sheet_index": sheet_idx,
                "row": row_idx,
                "col": col_idx,
                "filename": filename,
                "image_bytes": img_bytes,
                "pil_image": pil_img,
                "media_path": media_path,
                "sha256": sha256_hash,
            }
        )

    return extracted


def extract_excel_images(file_path_or_bytes: Any) -> list[dict[str, Any]]:
    """
    Extracts embedded and pasted images from an Excel (.xlsx) file by traversing
    and parsing OpenXML relationships and drawing XML files (workbook.xml -> sheets -> drawing -> blip).

    Returns a list of dicts containing sheet_name, sheet_index (1-based), row, col,
    filename, image_bytes, pil_image, media_path, and sha256 hash.
    """
    import io
    import zipfile

    import defusedxml.ElementTree as ET

    ns_main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    ns_rel = "http://schemas.openxmlformats.org/package/2006/relationships"
    ns_xdr = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
    ns_a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    rel_embed_attr = (
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
    )
    rel_id_attr = (
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    )

    extracted: list[dict[str, Any]] = []

    try:
        if isinstance(file_path_or_bytes, bytes):
            zf = zipfile.ZipFile(io.BytesIO(file_path_or_bytes), "r")
        else:
            zf = zipfile.ZipFile(file_path_or_bytes, "r")
    except Exception as e:
        logger.warning(
            f"Could not open file as zip archive for image extraction: {sanitize_log_message(e)}"
        )
        return extracted

    with zf:
        namelist = zf.namelist()
        if (
            "xl/workbook.xml" not in namelist
            or "xl/_rels/workbook.xml.rels" not in namelist
        ):
            return extracted

        try:
            wb_tree = ET.fromstring(zf.read("xl/workbook.xml"))
            wb_rels_tree = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))

            wb_rels = _parse_workbook_relationships(wb_rels_tree, ns_rel)

            sheets = wb_tree.find(f"{{{ns_main}}}sheets")
            if sheets is None:
                return extracted

            for sheet_idx, sheet_node in enumerate(
                sheets.findall(f"{{{ns_main}}}sheet"), start=1
            ):
                sheet_name = sheet_node.attrib.get("name", f"Sheet{sheet_idx}")
                r_id = sheet_node.attrib.get(rel_id_attr)
                sheet_path = wb_rels.get(r_id or "")
                if not sheet_path or sheet_path not in namelist:
                    continue

                sheet_dir, sheet_file = sheet_path.rsplit("/", 1)
                sheet_rels_path = f"{sheet_dir}/_rels/{sheet_file}.rels"
                if sheet_rels_path not in namelist:
                    continue

                sheet_rels_tree = ET.fromstring(zf.read(sheet_rels_path))
                sheet_rels = _parse_sheet_relationships(sheet_rels_tree, sheet_dir, ns_rel)

                sheet_tree = ET.fromstring(zf.read(sheet_path))
                drawing_node = sheet_tree.find(f"{{{ns_main}}}drawing")
                if drawing_node is None:
                    continue

                d_r_id = drawing_node.attrib.get(rel_id_attr)
                drawing_path = sheet_rels.get(d_r_id or "")
                if not drawing_path or drawing_path not in namelist:
                    continue

                drawing_dir, drawing_file = drawing_path.rsplit("/", 1)
                drawing_rels_path = f"{drawing_dir}/_rels/{drawing_file}.rels"
                if drawing_rels_path not in namelist:
                    continue

                drawing_rels_tree = ET.fromstring(zf.read(drawing_rels_path))
                drawing_rels = _parse_drawing_relationships(
                    drawing_rels_tree, drawing_dir, ns_rel
                )

                drawing_tree = ET.fromstring(zf.read(drawing_path))
                drawing_anchors = _extract_anchors_from_drawing(
                    zf=zf,
                    drawing_tree=drawing_tree,
                    drawing_rels=drawing_rels,
                    sheet_name=sheet_name,
                    sheet_idx=sheet_idx,
                    namelist=namelist,
                    ns_xdr=ns_xdr,
                    ns_a=ns_a,
                    rel_embed_attr=rel_embed_attr,
                )
                extracted.extend(drawing_anchors)

        except Exception as exc:
            logger.warning(
                f"Error parsing OpenXML drawing relationships: {sanitize_log_message(exc)}"
            )

    return extracted


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


def generate_doc_slug(input_path_or_name: Any) -> str:
    """
    Generates a clean, filesystem-safe and URL-friendly slug from an input path, filename, or string.
    Normalizes whitespace and replaces unsafe characters with hyphens.
    """
    if not input_path_or_name:
        return "document"
    from pathlib import Path
    if isinstance(input_path_or_name, Path):
        name = input_path_or_name.stem
    elif isinstance(input_path_or_name, str):
        name = input_path_or_name.strip()
        if "/" in name or "\\" in name:
            name = Path(name).stem
        elif "." in name:
            name = name.rsplit(".", 1)[0]
    else:
        # Avoid stringifying mock objects into "MagicMock-name..."
        return "document"
    name = name.strip()
    # Replace whitespace and unsafe path characters with hyphens
    slug = re.sub(r"[\s/\\\:\*\?\"\<\>\|]+", "-", name).strip("-. ")
    return slug or "document"


def get_picture_page_no(picture_item: Any) -> int:
    """
    Extracts the 1-based page number from a PictureItem's provenance information.
    Defaults to 1 if not found or invalid.
    """
    if hasattr(picture_item, "prov") and picture_item.prov:
        for p in picture_item.prov:
            page_no = getattr(p, "page_no", None)
            if page_no is not None and isinstance(page_no, int) and page_no > 0:
                return page_no
    return 1


def generate_image_filename(slug: str, page_no: int, index: int) -> str:
    """
    Generates an image filename following the format: {doc_slug}_p{page}_{index}.png
    """
    safe_slug = slug or "document"
    safe_page = max(1, page_no)
    safe_index = max(1, index)
    return f"{safe_slug}_p{safe_page}_{safe_index}.png"
