import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, Request

import docling_lib.server
from docling_lib.server import rate_limiter


@pytest.fixture(autouse=True)
def reset_rate_limit_data():
    """Reset the in-memory rate limit data before each test."""
    docling_lib.server._rate_limit_data.clear()


@pytest.mark.asyncio
async def test_rate_limiter_success():
    """Test that multiple requests within the limit succeed."""
    mock_request = MagicMock(spec=Request)
    mock_request.client.host = "1.2.3.4"

    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", 5):
        for _ in range(5):
            # Should not raise
            await rate_limiter(mock_request)


@pytest.mark.asyncio
async def test_rate_limiter_exceeded():
    """Test that an HTTPException with status code 429 is raised when the limit is exceeded."""
    mock_request = MagicMock(spec=Request)
    mock_request.client.host = "1.2.3.4"

    limit = 3
    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", limit):
        for _ in range(limit):
            await rate_limiter(mock_request)

        with pytest.raises(HTTPException) as exc_info:
            await rate_limiter(mock_request)

        assert exc_info.value.status_code == 429
        assert "Too Many Requests" in exc_info.value.detail


@pytest.mark.asyncio
async def test_rate_limiter_window_expiration():
    """Test that the rate limit bucket resets after the window expires."""
    mock_request = MagicMock(spec=Request)
    mock_request.client.host = "1.2.3.4"

    limit = 2
    window = 60

    start_time = 1000.0

    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", limit):
        with patch("docling_lib.server.RATE_LIMIT_WINDOW", window):
            with patch("time.time", return_value=start_time):
                # Fill the limit
                for _ in range(limit):
                    await rate_limiter(mock_request)

                # Verify it's blocked
                with pytest.raises(HTTPException) as exc_info:
                    await rate_limiter(mock_request)
                assert exc_info.value.status_code == 429

            # Simulate time passage beyond the window
            with patch("time.time", return_value=start_time + window + 1):
                # Should succeed now
                await rate_limiter(mock_request)


@pytest.mark.asyncio
async def test_rate_limiter_multiple_clients():
    """Test that different IPs have independent rate limits."""
    mock_request_1 = MagicMock(spec=Request)
    mock_request_1.client.host = "1.1.1.1"

    mock_request_2 = MagicMock(spec=Request)
    mock_request_2.client.host = "2.2.2.2"

    limit = 2
    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", limit):
        # Exceed limit for client 1
        for _ in range(limit):
            await rate_limiter(mock_request_1)

        with pytest.raises(HTTPException):
            await rate_limiter(mock_request_1)

        # Client 2 should still be able to make requests
        await rate_limiter(mock_request_2)


@pytest.mark.asyncio
async def test_rate_limiter_missing_client():
    """Test that the rate limiter handles requests where request.client is None."""
    mock_request = MagicMock(spec=Request)
    # Ensure header checks return None to trigger connection IP / client fallback
    mock_request.headers.get.return_value = None
    mock_request.client = None

    limit = 2
    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", limit):
        await rate_limiter(mock_request)
        await rate_limiter(mock_request)

        # Should be blocked now under "unknown" IP
        with pytest.raises(HTTPException) as exc_info:
            await rate_limiter(mock_request)
        assert exc_info.value.status_code == 429
        # Check if the log message (if we could capture it) or state uses "unknown"
        assert "unknown" in docling_lib.server._rate_limit_data
