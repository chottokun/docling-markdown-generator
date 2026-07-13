import pytest
from fastapi import HTTPException

import docling_lib.server
from docling_lib.config import MAX_UPLOAD_SIZE
from unittest.mock import MagicMock, patch
from fastapi import Request
from docling_lib.server import (
    _create_output_dir,
    _validate_and_format_response,
    _validate_content_length,
    _validate_extension,
    _is_valid_file,
    _get_safe_path,
    _get_client_ip,
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
        (" test.pdf", ".pdf"),  # Leading space is preserved by Path.suffix but it finds the extension
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
    assert len(request_id) == 16  # 8 bytes hex
    assert request_output_dir == tmp_path / request_id
    assert request_output_dir.exists()
    assert request_output_dir.is_dir()


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
        assert ip == "203.0.113.195"


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
