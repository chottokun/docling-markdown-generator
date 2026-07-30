import time
from unittest.mock import MagicMock, patch
import pytest
from PIL import Image

from docling_core.types.doc import DoclingDocument, TableItem, TableData, TableCell
from docling_lib.vlm import _get_cached_sync_client
from docling_lib.converter import (
    ThreadSafeModelPool,
    DocumentConversionOptions,
    PDFConverter,
    HTMLTableMarkdownSerializer,
)
from docling_lib.server import (
    _parse_trusted_proxies,
    _is_trusted_proxy,
    _rate_limit_data,
    rate_limiter,
)


def test_lock_free_sync_client_cache_hit():
    """Verify lock-free client cache is working and returning the cached client."""
    client1 = _get_cached_sync_client()
    client2 = _get_cached_sync_client()
    assert client1 is client2
    assert not client1.is_closed


def test_thread_safe_model_pool_caching_and_eviction():
    """Verify ThreadSafeModelPool caches converters and performs LRU eviction."""
    pool = ThreadSafeModelPool(max_size=2)

    opt1 = DocumentConversionOptions(do_ocr=True, image_scale=2.0)
    opt2 = DocumentConversionOptions(do_ocr=False, image_scale=2.0)
    opt3 = DocumentConversionOptions(do_ocr=True, image_scale=1.0)

    conv1 = pool.get_converter(opt1)
    conv2 = pool.get_converter(opt2)

    # Cache hits
    assert pool.get_converter(opt1) is conv1
    assert pool.get_converter(opt2) is conv2

    # Eviction: adding opt3 (pool size is 2, so LRU key 'opt1' should be evicted because opt2 was accessed most recently)
    conv3 = pool.get_converter(opt3)
    assert pool.get_converter(opt2) is conv2  # opt2 is still cached
    assert pool.get_converter(opt1) is not conv1  # conv1 was evicted and re-created


def test_single_image_avoidance_save_images():
    """Verify sequential execution is used for single-image documents and ThreadPool for multi-image."""
    converter = PDFConverter()
    doc = MagicMock(spec=DoclingDocument)
    mock_pic1 = MagicMock()
    mock_pic1.image = MagicMock()
    mock_pic1.image.pil_image = MagicMock(spec=Image.Image)
    mock_pic2 = MagicMock()
    mock_pic2.image = MagicMock()
    mock_pic2.image.pil_image = MagicMock(spec=Image.Image)

    # 1. Single image
    doc.pictures = [mock_pic1]
    with patch("docling_lib.converter.ThreadPoolExecutor") as mock_executor:
        converter._save_images(doc, MagicMock())
        mock_executor.assert_not_called()
        mock_pic1.image.pil_image.save.assert_called_once()

    # 2. Multi-image
    doc.pictures = [mock_pic1, mock_pic2]
    mock_pic1.image.pil_image.save.reset_mock()
    with patch("docling_lib.converter.ThreadPoolExecutor") as mock_executor:
        converter._save_images(doc, MagicMock())
        mock_executor.assert_called_once()


def test_adaptive_table_serializer():
    """Verify table serializer falls back to GFM when no merged cells exist."""
    serializer = HTMLTableMarkdownSerializer()

    # Case 1: No merged cells (all spans are 1)
    cell1 = MagicMock(spec=TableCell, row_span=1, col_span=1)
    cell2 = MagicMock(spec=TableCell, row_span=1, col_span=1)
    mock_data = MagicMock(spec=TableData, table_cells=[cell1, cell2])
    mock_item = MagicMock(spec=TableItem, data=mock_data)

    mock_doc = MagicMock(spec=DoclingDocument)
    mock_doc_serializer = MagicMock()

    with patch("docling_core.transforms.serializer.markdown.MarkdownTableSerializer.serialize") as mock_super_serialize:
        serializer.serialize(item=mock_item, doc_serializer=mock_doc_serializer, doc=mock_doc)
        mock_super_serialize.assert_called_once()

    # Case 2: Has merged cells (col_span > 1)
    cell_merged = MagicMock(spec=TableCell, row_span=1, col_span=2)
    mock_data_merged = MagicMock(spec=TableData, table_cells=[cell1, cell_merged])
    mock_item_merged = MagicMock(spec=TableItem, data=mock_data_merged)
    mock_item_merged.self_ref = "#/tables/1"
    mock_item_merged.export_to_html.return_value = "<table>HTML</table>"

    mock_caption_res = MagicMock()
    mock_caption_res.text = ""
    mock_caption_res.spans = []
    mock_doc_serializer.serialize_captions.return_value = mock_caption_res

    result = serializer.serialize(item=mock_item_merged, doc_serializer=mock_doc_serializer, doc=mock_doc)
    assert "<table>HTML</table>" in result.text


@pytest.mark.asyncio
async def test_rate_limiter_periodic_cleanup():
    """Verify rate limiter periodically cleans up stale client deques to prevent leaks."""
    from docling_lib import server
    server._rate_limit_data.clear()
    server._last_rate_limit_cleanup = 0.0

    # Add dummy entries
    server._rate_limit_data["stale-client1"].append(time.time() - 1000)
    server._rate_limit_data["stale-client2"].append(time.time() - 50)  # active-ish

    # Emulate request context
    mock_request = MagicMock()
    mock_request.client.host = "127.0.0.1"
    mock_request.headers = {}

    with patch("time.time", return_value=time.time()):
        await rate_limiter(mock_request)

    # Stale-client1 has expired timestamp, and since deque becomes empty, key should be removed.
    assert "stale-client1" not in server._rate_limit_data
    # stale-client2 timestamp is within window, so it remains.
    assert "stale-client2" in server._rate_limit_data


def test_trusted_proxies_caching():
    """Verify trusted proxies parsing caching and correct behavior."""
    from docling_lib import server

    with patch("docling_lib.server.TRUSTED_PROXIES", ["10.0.0.0/24", "192.168.1.1", "*"]):
        _parse_trusted_proxies.cache_clear()
        assert _is_trusted_proxy("192.168.1.1") is True
        assert _is_trusted_proxy("10.0.0.5") is True
        assert _is_trusted_proxy("8.8.8.8") is True  # due to wildcard '*'

        # Verify caching is populated
        cache_info = _parse_trusted_proxies.cache_info()
        assert cache_info.hits > 0


def test_thread_safe_model_pool_concurrent_access():
    """Critical Test: Verify ThreadSafeModelPool is thread-safe under concurrent requests."""
    import concurrent.futures

    pool = ThreadSafeModelPool(max_size=4)
    opts = DocumentConversionOptions(do_ocr=True, image_scale=2.0)

    results = []
    def fetch():
        return pool.get_converter(opts)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch) for _ in range(20)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # All returned instances for identical options must be identical (cache hit)
    first_instance = results[0]
    assert all(inst is first_instance for inst in results)


def test_adaptive_table_serializer_corrupt_data():
    """Critical Test: Verify table serializer safely handles None or missing table_cells."""
    serializer = HTMLTableMarkdownSerializer()

    # Case: table_cells is None or empty list
    mock_data = MagicMock(spec=TableData, table_cells=None)
    mock_item = MagicMock(spec=TableItem, data=mock_data)
    # Ensure _mock_name is not set so it doesn't trigger mock override
    del mock_item._mock_name

    mock_doc = MagicMock(spec=DoclingDocument)
    mock_doc_serializer = MagicMock()

    with patch("docling_core.transforms.serializer.markdown.MarkdownTableSerializer.serialize") as mock_super_serialize:
        serializer.serialize(item=mock_item, doc_serializer=mock_doc_serializer, doc=mock_doc)
        mock_super_serialize.assert_called_once()

