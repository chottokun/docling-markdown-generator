import logging
from unittest.mock import MagicMock

import pytest

from docling_lib.converter import CustomMarkdownPictureSerializer
from docling_lib.utils import serialize_table_data_to_markdown
from docling_lib.vlm import _resolve_caption_defaults


def test_image_tag_template_format_error(caplog):
    """
    Verify that CustomMarkdownPictureSerializer handles malformed image tag templates gracefully
    by logging a warning and falling back to default image markdown link.
    """
    serializer = CustomMarkdownPictureSerializer(
        image_tag_template="![image]({invalid_key})",
        slug="test-slug",
        image_dir_name="custom_img_dir",
    )

    doc = MagicMock()
    pic_item = MagicMock()
    pic_item.self_ref = "#/pictures/0"
    pic_item.image = None

    # Set up doc.pictures so idx matches 0
    pic_mock = MagicMock()
    pic_mock.self_ref = "#/pictures/0"
    doc.pictures = [pic_mock]

    doc_serializer = MagicMock()
    doc_serializer.serialize_captions.return_value = MagicMock(text="")
    doc_serializer.get_excluded_refs.return_value = []
    doc_serializer.serialize_annotations.return_value = MagicMock(text="")

    with caplog.at_level(logging.WARNING):
        res = serializer.serialize(
            item=pic_item,
            doc_serializer=doc_serializer,
            doc=doc,
        )

        assert "Failed to format image_tag_template" in caplog.text
        assert res.text == "![image](custom_img_dir/picture_1.png)"


def test_resolve_caption_defaults_all_providers():
    """
    Verify parameter default resolution and automatic endpoint adjustment
    for all VLM providers.
    """
    # Ollama default endpoint
    p, m, e, pr = _resolve_caption_defaults("", "", "", "")
    assert p == "ollama"
    assert m == "qwen2-vl:2b"
    assert e == "http://localhost:11434"
    assert "概要" in pr

    # OpenAI endpoint adjustment
    p, m, e, pr = _resolve_caption_defaults("openai", "gpt-4o", "http://localhost:11434", "")
    assert p == "openai"
    assert e == "https://api.openai.com/v1"

    # Anthropic endpoint adjustment
    p, m, e, pr = _resolve_caption_defaults("anthropic", "claude-3-5-sonnet", "", "")
    assert p == "anthropic"
    assert e == "https://api.anthropic.com"

    # Google/Gemini endpoint adjustment
    p, m, e, pr = _resolve_caption_defaults("google", "gemini-1.5-pro", "", "")
    assert p == "google"
    assert e == "https://generativelanguage.googleapis.com"


def test_serialize_table_data_edge_cases():
    """
    Verify serialize_table_data_to_markdown handles None, empty table_cells,
    and missing dimensions correctly.
    """
    # 1. None table_data
    assert serialize_table_data_to_markdown(None) == ""

    # 2. table_data without table_cells
    td_no_cells = MagicMock()
    td_no_cells.table_cells = None
    assert serialize_table_data_to_markdown(td_no_cells) == ""

    # 3. Dynamic dimension calculation when num_rows and num_cols are 0
    td_dynamic = MagicMock()
    td_dynamic.num_rows = 0
    td_dynamic.num_cols = 0

    c1 = MagicMock()
    c1.start_row_offset_idx = 0
    c1.end_row_offset_idx = 1
    c1.start_col_offset_idx = 0
    c1.end_col_offset_idx = 1
    c1.text = "Header 1"

    c2 = MagicMock()
    c2.start_row_offset_idx = 0
    c2.end_row_offset_idx = 1
    c2.start_col_offset_idx = 1
    c2.end_col_offset_idx = 2
    c2.text = "Header 2"

    c3 = MagicMock()
    c3.start_row_offset_idx = 1
    c3.end_row_offset_idx = 2
    c3.start_col_offset_idx = 0
    c3.end_col_offset_idx = 1
    c3.text = "Cell 1|2"

    td_dynamic.table_cells = [c1, c2, c3]

    res = serialize_table_data_to_markdown(td_dynamic)
    assert "| Header 1 | Header 2 |" in res
    assert "| Cell 1\\|2 |  |" in res
