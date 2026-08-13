from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, Request

import docling_lib.server
from docling_lib.config import MAX_UPLOAD_SIZE
from docling_lib.server import (
    _create_output_dir,
    _get_client_ip,
    _get_safe_path,
    _is_valid_file,
    _validate_and_format_response,
    _validate_content_length,
    _validate_extension,
)


@pytest.mark.parametrize(
    "content_length",
    [
        None,
        0,
        1024,
        MAX_UPLOAD_SIZE,
    ],
)
def test_validate_content_length_valid(content_length):
    # Should not raise any exception
    _validate_content_length(content_length)


@pytest.mark.parametrize(
    "content_length",
    [
        MAX_UPLOAD_SIZE + 1,
        MAX_UPLOAD_SIZE + 1024,
    ],
)
def test_validate_content_length_invalid(content_length):
    with pytest.raises(HTTPException) as exc_info:
        _validate_content_length(content_length)
    assert exc_info.value.status_code == 413
    assert "Payload Too Large" in exc_info.value.detail


@pytest.mark.parametrize(
    "filename, expected_ext",
    [
        ("test.pdf", ".pdf"),
        ("document.docx", ".docx"),
        ("presentation.pptx", ".pptx"),
        ("spreadsheet.xlsx", ".xlsx"),
        ("TEST.PDF", ".pdf"),
        ("Document.Docx", ".docx"),
        ("multi.dot.file.pdf", ".pdf"),
        ("path/to/file.xlsx", ".xlsx"),
        ("image.png", ".png"),
        ("photo.jpg", ".jpg"),
        ("page.html", ".html"),
        ("document.epub", ".epub"),
        (
            " test.pdf",
            ".pdf",
        ),  # Leading space is preserved by Path.suffix but it finds the extension
        ("report.tex", ".tex"),
        ("subtitle.vtt", ".vtt"),
        ("data.xbrl", ".xbrl"),
        ("email.eml", ".eml"),
        ("message.msg", ".msg"),
        ("image.tiff", ".tiff"),
        ("image.jpeg", ".jpeg"),
        ("page.htm", ".htm"),
        ("README.md", ".md"),
    ],
)
def test_validate_extension_valid(filename, expected_ext):
    assert _validate_extension(filename) == expected_ext


@pytest.mark.parametrize(
    "filename",
    [
        ("test.txt"),
        ("archive.zip"),
        ("README"),
        (""),
        ("no_extension."),
        (".pdf"),  # This is tricky, Path(".pdf").suffix is ""
        ("file."),
        ("test.pdf "),  # Trailing space
        ("test.pdf\n"),  # Newline
        ("test.exe.pdf.txt"),  # Double extension where last is invalid
    ],
)
def test_validate_extension_invalid(filename):
    with pytest.raises(HTTPException) as exc_info:
        _validate_extension(filename)
    assert exc_info.value.status_code == 400
    assert "Unsupported file format" in exc_info.value.detail


@pytest.mark.asyncio
async def test_create_output_dir(tmp_path, monkeypatch):
    """Test that _create_output_dir creates a unique directory and returns its ID and path."""
    # Setup: Redirect OUTPUT_DIR to a temporary directory
    monkeypatch.setattr(docling_lib.server, "OUTPUT_DIR", tmp_path)

    # Act
    request_id, request_output_dir = await _create_output_dir()

    # Assert
    assert isinstance(request_id, str)
    assert len(request_id) == 32  # 16 bytes hex
    assert request_output_dir == tmp_path / request_id
    assert request_output_dir.exists()
    assert request_output_dir.is_dir()


@pytest.mark.asyncio
async def test_create_output_dir_entropy_and_uniqueness(tmp_path, monkeypatch):
    """Test that generated request IDs have sufficient entropy and are unique across multiple calls."""
    monkeypatch.setattr(docling_lib.server, "OUTPUT_DIR", tmp_path)

    ids = set()
    for _ in range(100):
        req_id, _ = await _create_output_dir()
        # Verify length and format (should be hex characters)
        assert len(req_id) == 32
        assert all(c in "0123456789abcdef" for c in req_id)
        ids.add(req_id)

    # All generated IDs must be unique
    assert len(ids) == 100


@pytest.mark.asyncio
async def test_create_output_dir_file_exists_error(tmp_path, monkeypatch):
    """Test that _create_output_dir propagates FileExistsError when a regular file exists at the path."""
    monkeypatch.setattr(docling_lib.server, "OUTPUT_DIR", tmp_path)

    import os
    original_urandom = os.urandom

    def mock_urandom(size):
        if size == 16:
            return b"1234567890123456"
        return original_urandom(size)

    monkeypatch.setattr(os, "urandom", mock_urandom)

    file_path_urandom = tmp_path / b"1234567890123456".hex()
    file_path_urandom.write_text("not a directory")

    with pytest.raises(FileExistsError):
        await _create_output_dir()


@pytest.mark.asyncio
async def test_create_output_dir_permission_error(tmp_path, monkeypatch):
    """Test that _create_output_dir propagates PermissionError when folder creation is not permitted."""
    monkeypatch.setattr(docling_lib.server, "OUTPUT_DIR", tmp_path)

    async def mock_run(func, *args, **kwargs):
        raise PermissionError("Permission denied")

    monkeypatch.setattr(docling_lib.server, "run_in_threadpool", mock_run)

    with pytest.raises(PermissionError):
        await _create_output_dir()


@pytest.mark.asyncio
async def test_create_output_dir_os_error(tmp_path, monkeypatch):
    """Test that _create_output_dir propagates OSError when an unexpected OS error occurs."""
    monkeypatch.setattr(docling_lib.server, "OUTPUT_DIR", tmp_path)

    async def mock_run(func, *args, **kwargs):
        raise OSError("Unexpected filesystem failure")

    monkeypatch.setattr(docling_lib.server, "run_in_threadpool", mock_run)

    with pytest.raises(OSError, match="Unexpected filesystem failure"):
        await _create_output_dir()


@pytest.mark.asyncio
async def test_validate_and_format_response_none():
    """Test that _validate_and_format_response raises 500 when result_path is None."""
    with pytest.raises(HTTPException) as exc_info:
        await _validate_and_format_response(None, "test_id")
    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Conversion failed."


@pytest.mark.asyncio
async def test_validate_and_format_response_not_exists(tmp_path):
    """Test that _validate_and_format_response raises 500 when result_path does not exist."""
    result_path = tmp_path / "non_existent.md"
    with pytest.raises(HTTPException) as exc_info:
        await _validate_and_format_response(result_path, "test_id")
    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Conversion failed."


@pytest.mark.asyncio
async def test_validate_and_format_response_success(tmp_path):
    """Test that _validate_and_format_response returns the correct success response."""
    result_path = tmp_path / "success.md"
    result_path.write_text("content")
    request_id = "test_id_123"

    response = await _validate_and_format_response(result_path, request_id)

    assert response["message"] == "Conversion successful"
    assert response["markdown_file"] == "success.md"
    assert response["output_id"] == request_id
    assert response["download_url"] == f"/download/{request_id}/success.md"


def test_is_valid_file(tmp_path):
    """Test that _is_valid_file correctly validates path existence and file status."""
    # 1. Existing file should return True
    valid_file = tmp_path / "test.txt"
    valid_file.write_text("hello")
    assert _is_valid_file(valid_file) is True

    # 2. Non-existent file should return False
    non_existent_file = tmp_path / "non_existent.txt"
    assert _is_valid_file(non_existent_file) is False

    # 3. Existing directory should return False
    directory_path = tmp_path / "test_dir"
    directory_path.mkdir()
    assert _is_valid_file(directory_path) is False


@pytest.mark.parametrize(
    "request_id, filename",
    [
        ("abc123XYZ", "report.md"),
        ("abc-123_xyz", "output.txt"),
        ("12345", "test.pdf"),
    ],
)
def test_get_safe_path_valid(request_id, filename, tmp_path, monkeypatch):
    """Test that _get_safe_path succeeds and resolves paths correctly with valid parameters."""
    monkeypatch.setattr("docling_lib.server.OUTPUT_DIR", tmp_path)

    resolved_output_dir, safe_dir, file_path = _get_safe_path(request_id, filename)

    assert resolved_output_dir == tmp_path.resolve()
    assert safe_dir == (tmp_path / request_id).resolve()
    assert file_path == (tmp_path / request_id / filename).resolve()


@pytest.mark.parametrize(
    "request_id",
    [
        "abc/def",
        "abc..def",
        "abc.def",
        "abc def",
        "abc#def",
        "abc\\def",
        "abc?",
    ],
)
def test_get_safe_path_invalid_request_id(request_id):
    """Test that _get_safe_path raises ValueError for invalid request_id patterns."""
    with pytest.raises(ValueError, match="Invalid request_id"):
        _get_safe_path(request_id, "test.md")


@pytest.mark.parametrize(
    "filename",
    [
        "sub/file.txt",
        "../file.txt",
        "./file.txt",
        "/absolute/path",
        "file/",
        ".",
    ],
)
def test_get_safe_path_invalid_filename(filename):
    """Test that _get_safe_path raises ValueError for invalid filename patterns."""
    with pytest.raises(ValueError, match="Invalid filename"):
        _get_safe_path("valid_id", filename)


def test_get_client_ip_x_forwarded_for_single():
    """Test _get_client_ip when X-Forwarded-For header contains a single IP and connection is trusted."""
    mock_request = MagicMock(spec=Request)
    mock_headers = {"x-forwarded-for": "203.0.113.195"}
    mock_request.headers.get = lambda k, d=None: mock_headers.get(k.lower(), d)
    mock_request.client.host = "127.0.0.1"

    with patch("docling_lib.server.TRUSTED_PROXIES", ["127.0.0.1"]):
        ip = _get_client_ip(mock_request)
        assert ip == "203.0.113.195"


def test_get_client_ip_x_forwarded_for_multiple():
    """Test _get_client_ip when X-Forwarded-For header contains multiple comma-separated IPs and connection is trusted."""
    mock_request = MagicMock(spec=Request)
    mock_headers = {"x-forwarded-for": "203.0.113.195, 70.41.3.18, 150.172.238.178"}
    mock_request.headers.get = lambda k, d=None: mock_headers.get(k.lower(), d)
    mock_request.client.host = "127.0.0.1"

    with patch("docling_lib.server.TRUSTED_PROXIES", ["127.0.0.1"]):
        ip = _get_client_ip(mock_request)
        # Security logic traverses right-to-left. 150.172.238.178 is untrusted, so it's resolved as the real client IP.
        assert ip == "150.172.238.178"


def test_get_client_ip_x_real_ip():
    """Test _get_client_ip when X-Forwarded-For is missing but X-Real-IP is present and connection is trusted."""
    mock_request = MagicMock(spec=Request)
    mock_headers = {"x-real-ip": "198.51.100.1"}
    mock_request.headers.get = lambda k, d=None: mock_headers.get(k.lower(), d)
    mock_request.client.host = "127.0.0.1"

    with patch("docling_lib.server.TRUSTED_PROXIES", ["127.0.0.1"]):
        ip = _get_client_ip(mock_request)
        assert ip == "198.51.100.1"


def test_get_client_ip_fallback_to_client_host():
    """Test _get_client_ip when proxy headers are missing, falling back to connection host."""
    mock_request = MagicMock(spec=Request)
    mock_request.headers.get = lambda k, d=None: d
    mock_request.client.host = "192.0.2.1"

    with patch("docling_lib.server.TRUSTED_PROXIES", ["127.0.0.1"]):
        ip = _get_client_ip(mock_request)
        assert ip == "192.0.2.1"


def test_build_conversion_options():
    """Test that _build_conversion_options correctly populates options."""
    from docling_lib.server import _build_conversion_options, DocumentConversionRequest
    req_options = DocumentConversionRequest(
        table_format="html",
        include_page_breaks=True,
        include_kv_extraction=False,
        vlm_enabled=True,
        vlm_provider="ollama",
        vlm_api_key="secret",
        vlm_model="llama3",
        vlm_endpoint="http://localhost:11434",
        vlm_prompt="describe",
        vlm_max_concurrent=5,
        num_threads=4,
        cuda_use_flash_attention=True,
    )
    options = _build_conversion_options(req_options)
    assert options.table_format == "html"
    assert options.include_page_breaks is True
    assert options.include_kv_extraction is False
    assert options.vlm_enabled is True
    assert options.vlm_provider == "ollama"
    assert options.vlm_api_key == "secret"
    assert options.vlm_model == "llama3"
    assert options.vlm_endpoint == "http://localhost:11434"
    assert options.vlm_prompt == "describe"
    assert options.vlm_max_concurrent == 5
    assert options.num_threads == 4
    assert options.cuda_use_flash_attention is True


def test_build_options_dict():
    """Test that _build_options_dict correctly converts options to dict."""
    from docling_lib.server import _build_options_dict
    from docling_lib.converter import DocumentConversionOptions
    options = DocumentConversionOptions(
        table_format="html",
        include_page_breaks=True,
        include_kv_extraction=False,
        vlm_enabled=True,
        vlm_provider="ollama",
        vlm_api_key="secret",
        vlm_model="llama3",
        vlm_endpoint="http://localhost:11434",
        vlm_prompt="describe",
        vlm_max_concurrent=5,
        num_threads=4,
        cuda_use_flash_attention=True,
    )
    opt_dict = _build_options_dict(options)
    assert opt_dict["table_format"] == "html"
    assert opt_dict["include_page_breaks"] is True
    assert opt_dict["include_kv_extraction"] is False
    assert opt_dict["vlm_enabled"] is True
    assert opt_dict["vlm_provider"] == "ollama"
    assert opt_dict["vlm_api_key"] == "secret"
    assert opt_dict["vlm_model"] == "llama3"
    assert opt_dict["vlm_endpoint"] == "http://localhost:11434"
    assert opt_dict["vlm_prompt"] == "describe"
    assert opt_dict["vlm_max_concurrent"] == 5
    assert opt_dict["num_threads"] == 4
    assert opt_dict["cuda_use_flash_attention"] is True


@pytest.mark.asyncio
async def test_run_multiprocess_conversion(tmp_path):
    """Test that _run_multiprocess_conversion runs the multi process task worker and returns output path."""
    from docling_lib.server import _run_multiprocess_conversion
    from pathlib import Path

    dummy_result = tmp_path / "output.md"

    async def mock_run_in_executor(executor, func, *args):
        # Simply return a dummy path string as if the worker succeeded
        return str(dummy_result)

    with patch("asyncio.get_running_loop") as mock_loop_getter:
        mock_loop = MagicMock()
        mock_loop.run_in_executor = mock_run_in_executor
        mock_loop_getter.return_value = mock_loop

        res = await _run_multiprocess_conversion(tmp_path / "input.pdf", tmp_path, {})
        assert res == dummy_result


def test_get_client_ip_fallback_to_unknown():
    """Test _get_client_ip when proxy headers are missing and request.client is None."""
    mock_request = MagicMock(spec=Request)
    mock_request.headers.get = lambda k, d=None: d
    mock_request.client = None

    with patch("docling_lib.server.TRUSTED_PROXIES", ["127.0.0.1"]):
        ip = _get_client_ip(mock_request)
        assert ip == "unknown"


def test_get_client_ip_untrusted_proxy_ignores_headers():
    """Test _get_client_ip when connection is not trusted, proxy headers must be ignored."""
    mock_request = MagicMock(spec=Request)
    mock_headers = {"x-forwarded-for": "203.0.113.195", "x-real-ip": "198.51.100.1"}
    mock_request.headers.get = lambda k, d=None: mock_headers.get(k.lower(), d)
    mock_request.client.host = "192.0.2.1"

    with patch("docling_lib.server.TRUSTED_PROXIES", ["127.0.0.1"]):
        ip = _get_client_ip(mock_request)
        assert ip == "192.0.2.1"
