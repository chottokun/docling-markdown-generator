import io
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile

from docling_lib.server import convert_file


@pytest.mark.asyncio
async def test_log_injection_fix_verification(caplog):
    caplog.set_level(logging.INFO)

    malicious_filename = "malicious\n[INJECTED] forged log entry.pdf"

    # Mock UploadFile
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = malicious_filename
    mock_file.file = io.BytesIO(b"%PDF-1.4 dummy")

    # We mock the internal calls to avoid actual file I/O and dependencies,
    # ensuring the test focuses on the logging behavior without silent failures.
    with (
        patch(
            "docling_lib.server._save_upload_temp",
            new_callable=AsyncMock,
            return_value=Path("tmp"),
        ),
        patch(
            "docling_lib.server._create_output_dir",
            new_callable=AsyncMock,
            return_value=("id", Path("out")),
        ),
        patch("docling_lib.server.run_in_threadpool", new_callable=AsyncMock),
        patch("docling_lib.server._validate_and_format_response", new_callable=AsyncMock),
        patch("docling_lib.server._cleanup_temp_file", new_callable=AsyncMock),
    ):
        await convert_file(mock_file, content_length=None)

    found_log = False
    for record in caplog.records:
        if "Processing file:" in record.message and "[INJECTED]" in record.message:
            found_log = True
            assert "\n" not in record.message, (
                "Vulnerability still present: newline found in log message"
            )
            assert "malicious [INJECTED] forged log entry.pdf" in record.message, (
                "Filename not correctly sanitized"
            )
            print(f"Verified! Log message is sanitized:\n{record.message}")
            break

    assert found_log, "Target log message not found"


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__]))
