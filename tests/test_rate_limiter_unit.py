import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, Request

import docling_lib.server
from docling_lib.server import rate_limiter


@pytest.fixture(autouse=True)
def clear_rate_limit_data():
    """Ensure rate limit data is cleared before each test."""
    docling_lib.server._rate_limit_data.clear()


@pytest.mark.asyncio
async def test_rate_limiter_success():
    """Test that requests within the limit succeed."""
    request = MagicMock(spec=Request)
    request.client.host = "127.0.0.1"

    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", 2):
        with patch("docling_lib.server.RATE_LIMIT_WINDOW", 60):
            # First request
            await rate_limiter(request)
            # Second request
            await rate_limiter(request)
            # Should not raise any exception


@pytest.mark.asyncio
async def test_rate_limiter_exceeded():
    """Test that requests exceeding the limit raise 429."""
    request = MagicMock(spec=Request)
    request.client.host = "127.0.0.1"

    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", 1):
        with patch("docling_lib.server.RATE_LIMIT_WINDOW", 60):
            # First request
            await rate_limiter(request)

            # Second request -> Exceeded
            with pytest.raises(HTTPException) as exc_info:
                await rate_limiter(request)

            assert exc_info.value.status_code == 429
            assert "Too Many Requests" in exc_info.value.detail


@pytest.mark.asyncio
async def test_rate_limiter_window_expiration():
    """Test that old timestamps are purged and allow new requests."""
    request = MagicMock(spec=Request)
    request.client.host = "127.0.0.1"

    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", 1):
        with patch("docling_lib.server.RATE_LIMIT_WINDOW", 10):
            with patch("time.time") as mock_time:
                mock_time.return_value = 100
                # First request at t=100
                await rate_limiter(request)

                # Second request at t=105 -> Still within window, should fail
                mock_time.return_value = 105
                with pytest.raises(HTTPException):
                    await rate_limiter(request)

                # Third request at t=111 -> Window expired (111-100 > 10), should succeed
                mock_time.return_value = 111
                await rate_limiter(request)


@pytest.mark.asyncio
async def test_rate_limiter_unknown_client():
    """Test that rate limiter handles requests with no client info."""
    request = MagicMock(spec=Request)
    request.client = None

    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", 1):
        # First request
        await rate_limiter(request)

        # Second request -> Exceeded for "unknown"
        with pytest.raises(HTTPException) as exc_info:
            await rate_limiter(request)
        assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_rate_limiter_multiple_clients():
    """Test that rate limits are tracked independently for different IPs."""
    request1 = MagicMock(spec=Request)
    request1.client.host = "1.1.1.1"

    request2 = MagicMock(spec=Request)
    request2.client.host = "2.2.2.2"

    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", 1):
        # request1 succeeds
        await rate_limiter(request1)

        # request2 succeeds (different IP)
        await rate_limiter(request2)

        # request1 fails
        with pytest.raises(HTTPException):
            await rate_limiter(request1)

        # request2 fails
        with pytest.raises(HTTPException):
            await rate_limiter(request2)
