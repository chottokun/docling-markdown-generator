import io
import logging
from unittest.mock import MagicMock

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

    # We expect an exception or some result, but we're looking at logs
    try:
        await convert_file(mock_file)
    except Exception:
        pass

    found_log = False
    for record in caplog.records:
        if "Processing file:" in record.message and "[INJECTED]" in record.message:
            found_log = True
            assert "\n" not in record.message, "Vulnerability still present: newline found in log message"
            assert "malicious [INJECTED] forged log entry.pdf" in record.message, "Filename not correctly sanitized"
            print(f"Verified! Log message is sanitized:\n{record.message}")
            break

    assert found_log, "Target log message not found"

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__]))
