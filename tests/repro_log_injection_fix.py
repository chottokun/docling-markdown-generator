import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from types import ModuleType

# Mock missing dependencies
def mock_module(name):
    m = ModuleType(name)
    sys.modules[name] = m
    return m

docling = mock_module('docling')
docling.datamodel = mock_module('docling.datamodel')
docling.datamodel.base_models = mock_module('docling.datamodel.base_models')
docling.datamodel.pipeline_options = mock_module('docling.datamodel.pipeline_options')
docling.document_converter = mock_module('docling.document_converter')

docling_core = mock_module('docling_core')
docling_core.transforms = mock_module('docling_core.transforms')
docling_core.transforms.serializer = mock_module('docling_core.transforms.serializer')
docling_core.transforms.serializer.markdown = mock_module('docling_core.transforms.serializer.markdown')
docling_core.types = mock_module('docling_core.types')
docling_core.types.doc = mock_module('docling_core.types.doc')

mock_module('fastapi')
mock_module('fastapi.middleware.cors')
mock_module('fastapi.responses')
mock_module('starlette.concurrency')

# Mock specific classes/functions needed for import
docling.datamodel.base_models.InputFormat = MagicMock()
docling.datamodel.pipeline_options.PdfPipelineOptions = MagicMock()
docling.document_converter.DocumentConverter = MagicMock()
docling.document_converter.PdfFormatOption = MagicMock()
docling.document_converter.PowerpointFormatOption = MagicMock()
docling.document_converter.WordFormatOption = MagicMock()

docling_core.transforms.serializer.markdown.MarkdownDocSerializer = MagicMock()
docling_core.transforms.serializer.markdown.MarkdownParams = MagicMock()
docling_core.transforms.serializer.markdown.MarkdownTableSerializer = MagicMock()
docling_core.transforms.serializer.markdown.SerializationResult = MagicMock()
docling_core.transforms.serializer.markdown.create_ser_result = MagicMock()

docling_core.types.doc.DoclingDocument = MagicMock()
docling_core.types.doc.ImageRefMode = MagicMock()
docling_core.types.doc.TableItem = MagicMock()

# Now import the code to test
from docling_lib.converter import process_pdf

def test_workflow_error_log_injection_v2():
    bad_message = "Multi-line\nerror\nmessage"

    # We'll use a simple list to capture log records
    log_records = []
    class RecordCapturer(logging.Handler):
        def emit(self, record):
            log_records.append(record)

    logger = logging.getLogger("docling_lib.converter")
    handler = RecordCapturer()
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)

    try:
        with patch("docling_lib.converter._validate_input_path", return_value=True), \
             patch("docling_lib.converter._validate_output_security", return_value=True), \
             patch("docling_lib.converter._get_or_create_converter", side_effect=Exception(bad_message)):

            process_pdf(Path("fake.pdf"), Path("fake_out"))

        found_log = False
        for record in log_records:
            msg = record.getMessage()
            if "Workflow Error:" in msg:
                found_log = True
                print(f"Captured log: {repr(msg)}")
                assert "\n" not in msg, f"Vulnerability present: newline found in log message: {repr(msg)}"
                assert "\r" not in msg
                assert "Multi-line error message" in msg

        assert found_log, "Target log message not found"
    finally:
        logger.removeHandler(handler)

if __name__ == "__main__":
    try:
        test_workflow_error_log_injection_v2()
        print("Test passed!")
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
