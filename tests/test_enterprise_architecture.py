import threading
import time
from concurrent.futures import ThreadPoolExecutor as PyThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from PIL import Image

import docling_core.types.doc as d
import docling_core.types.doc.items.table.table_data as td
from docling_core.transforms.serializer.markdown import SerializationResult
from docling_lib.converter import (
    PDFConverter,
    DocumentConversionOptions,
    ThreadSafeModelPool,
    SafeYAMLSerializer,
    HTMLTableMarkdownSerializer,
)


# --- 1. ThreadSafeModelPool Tests ---

def test_thread_safe_model_pool_caching():
    """Verify caching, eviction and thread safety of ThreadSafeModelPool."""
    pool = ThreadSafeModelPool(max_instances=2)

    options1 = DocumentConversionOptions(image_scale=1.0)
    options2 = DocumentConversionOptions(image_scale=2.0)
    options3 = DocumentConversionOptions(image_scale=3.0)

    with patch("docling_lib.converter.PDFConverter") as mock_converter_cls:
        # Create different instances
        inst1 = MagicMock()
        inst2 = MagicMock()
        inst3 = MagicMock()
        mock_converter_cls.side_effect = [inst1, inst2, inst3]

        # 1. Cache hit test
        c1 = pool.get_converter(options1)
        c1_cached = pool.get_converter(options1)
        assert c1 is c1_cached
        assert mock_converter_cls.call_count == 1

        # 2. Add second instance
        c2 = pool.get_converter(options2)
        assert c2 is not c1

        # 3. Exceed max limit of 2 (should evict options1 / oldest)
        c3 = pool.get_converter(options3)
        assert mock_converter_cls.call_count == 3

        # 4. Try to fetch options1 again - should re-create
        inst4 = MagicMock()
        mock_converter_cls.side_effect = [inst4]
        c1_recreated = pool.get_converter(options1)
        assert c1_recreated is inst4


def test_thread_safe_model_pool_concurrent_access():
    """Verify that multiple threads requesting the same options get the exact same converter securely."""
    pool = ThreadSafeModelPool(max_instances=2)
    options = DocumentConversionOptions(image_scale=1.5)

    converters = []
    barrier = threading.Barrier(4)

    def thread_task():
        barrier.wait()
        conv = pool.get_converter(options)
        converters.append(conv)

    threads = [threading.Thread(target=thread_task) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All threads should get the exact same converter instance
    assert len(converters) == 4
    for c in converters:
        assert c is converters[0]


# --- 2. SafeYAMLSerializer Tests ---

def test_safe_yaml_serializer_prevent_injection():
    """Verify SafeYAMLSerializer serializes complex, malicious inputs safely as string values."""
    metadata = {
        "title": "My Title\n---\nauthor: Injected Author",
        "description": "Multi-line description\nwith nested block: value"
    }
    yaml_str = SafeYAMLSerializer.serialize(metadata)

    # Check structure is retained as safe string literals
    assert yaml_str.startswith("---\n")
    assert yaml_str.endswith("---\n")

    # Parse it back to verify that the malicious payload is securely parsed as strings
    parsed = yaml.safe_load(yaml_str.strip("---\n"))
    assert parsed["title"] == "My Title\n---\nauthor: Injected Author"
    assert parsed["description"] == "Multi-line description\nwith nested block: value"


# --- 3. Adaptive Table Renderer Tests ---

def test_adaptive_table_renderer_no_merged_cells():
    """Verify that a table without merged cells uses the standard GFM Markdown renderer."""
    serializer = HTMLTableMarkdownSerializer()

    # Construct standard non-merged cells (row_span=1, col_span=1)
    cell = td.TableCell(
        text="Standard Cell",
        start_row_offset_idx=0,
        end_row_offset_idx=1,
        start_col_offset_idx=0,
        end_col_offset_idx=1,
        row_span=1,
        col_span=1,
    )
    table_data = td.TableData(table_cells=[cell])
    table_item = d.TableItem(self_ref="#/tables/1", label="table", data=table_data)

    mock_doc = MagicMock()
    mock_doc_serializer = MagicMock()

    # Expected standard markdown serialization result
    expected_result = SerializationResult(text="| Standard Cell |\n| --- |", spans=[])

    with patch("docling_core.transforms.serializer.markdown.MarkdownTableSerializer.serialize", return_value=expected_result) as mock_super_serialize:
        result = serializer.serialize(item=table_item, doc_serializer=mock_doc_serializer, doc=mock_doc)
        assert result == expected_result
        mock_super_serialize.assert_called_once_with(
            item=table_item, doc_serializer=mock_doc_serializer, doc=mock_doc
        )


def test_adaptive_table_renderer_with_merged_cells():
    """Verify that a table with merged cells (row_span > 1) uses the high-fidelity HTML renderer."""
    serializer = HTMLTableMarkdownSerializer()

    # Construct merged cells (row_span=2)
    cell = td.TableCell(
        text="Merged Cell",
        start_row_offset_idx=0,
        end_row_offset_idx=2,
        start_col_offset_idx=0,
        end_col_offset_idx=1,
        row_span=2,
        col_span=1,
    )
    table_data = td.TableData(table_cells=[cell])
    table_item = d.TableItem(self_ref="#/tables/1", label="table", data=table_data)

    mock_doc = MagicMock()
    mock_doc_serializer = MagicMock()
    mock_caption_res = MagicMock(spec=SerializationResult)
    mock_caption_res.text = ""
    mock_caption_res.spans = []
    mock_doc_serializer.serialize_captions.return_value = mock_caption_res

    # Setup export_to_html mock using object.__setattr__ to bypass Pydantic restricted fields
    object.__setattr__(table_item, "export_to_html", MagicMock(return_value="<table>Merged Content</table>"))

    result = serializer.serialize(item=table_item, doc_serializer=mock_doc_serializer, doc=mock_doc)
    assert "<table>Merged Content</table>" in result.text


# --- 4. VLM Concurrency Bounds Tests ---

@patch("docling_lib.vlm.generate_caption_sync")
def test_vlm_prefetch_concurrency_bounds_single_image(mock_caption_sync):
    """Verify single-image documents bypass ThreadPoolExecutor and run sequentially."""
    mock_caption_sync.return_value = "Caption!"

    converter = PDFConverter()
    options = DocumentConversionOptions(
        vlm_enabled=True,
        vlm_max_concurrent=5,
    )

    # 1. Setup doc with exactly 1 image
    img_ref = d.ImageRef(
        mimetype="image/png",
        dpi=72,
        size=d.Size(width=50.0, height=50.0),
        uri="http://example.com/pic1.png",
    )
    object.__setattr__(img_ref, "_pil", Image.new("RGB", (50, 50)))
    pic_item = d.PictureItem(self_ref="#/body/0", image=img_ref)

    doc = MagicMock(spec=d.DoclingDocument)
    doc.pictures = [pic_item]

    # Patch ThreadPoolExecutor to verify it is NOT instantiated
    with patch("docling_lib.converter.ThreadPoolExecutor") as MockExecutor:
        captions = converter._prefetch_vlm_captions(doc, options)
        assert captions == {"#/body/0": "Caption!"}
        MockExecutor.assert_not_called()


@patch("docling_lib.vlm.generate_caption_sync")
def test_vlm_prefetch_concurrency_bounds_multi_image(mock_caption_sync):
    """Verify multi-image documents utilize ThreadPoolExecutor with bounded max_workers."""
    mock_caption_sync.return_value = "Caption!"

    converter = PDFConverter()
    options = DocumentConversionOptions(
        vlm_enabled=True,
        vlm_max_concurrent=3,
    )

    # 1. Setup doc with 2 images
    img_ref1 = d.ImageRef(mimetype="image/png", dpi=72, size=d.Size(width=50.0, height=50.0), uri="1")
    object.__setattr__(img_ref1, "_pil", Image.new("RGB", (50, 50)))
    pic_item1 = d.PictureItem(self_ref="#/body/0", image=img_ref1)

    img_ref2 = d.ImageRef(mimetype="image/png", dpi=72, size=d.Size(width=50.0, height=50.0), uri="2")
    object.__setattr__(img_ref2, "_pil", Image.new("RGB", (50, 50)))
    pic_item2 = d.PictureItem(self_ref="#/body/1", image=img_ref2)

    doc = MagicMock(spec=d.DoclingDocument)
    doc.pictures = [pic_item1, pic_item2]

    # Patch ThreadPoolExecutor to verify max_workers = min(32, vlm_max_concurrent) = 3
    with patch("docling_lib.converter.ThreadPoolExecutor", wraps=PyThreadPoolExecutor) as MockExecutor:
        captions = converter._prefetch_vlm_captions(doc, options)
        assert len(captions) == 2
        # Verify executor was initialized with max_workers=3
        MockExecutor.assert_called_once_with(max_workers=3)
