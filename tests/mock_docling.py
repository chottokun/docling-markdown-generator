import sys
from types import ModuleType


def mock_docling():
    if "docling" in sys.modules:
        return

    # Mock docling and other missing dependencies
    def create_mock_module(name):
        m = ModuleType(name)
        sys.modules[name] = m
        return m

    docling = create_mock_module("docling")
    docling.datamodel = create_mock_module("docling.datamodel")
    docling_base = create_mock_module("docling.datamodel.base_models")
    docling_base.InputFormat = type(
        "InputFormat", (), {"PDF": "pdf", "DOCX": "docx", "PPTX": "pptx"}
    )
    create_mock_module("docling.datamodel.pipeline_options")
    sys.modules["docling.datamodel.pipeline_options"].PdfPipelineOptions = type(
        "PdfPipelineOptions", (), {}
    )
    create_mock_module("docling.datamodel.document")
    sys.modules["docling.datamodel.document"].ConversionResult = type(
        "ConversionResult", (), {}
    )
    docling_conv = create_mock_module("docling.document_converter")
    docling_conv.DocumentConverter = type("DocumentConverter", (), {})
    docling_conv.PdfFormatOption = type("PdfFormatOption", (), {})
    docling_conv.PowerpointFormatOption = type("PowerpointFormatOption", (), {})
    docling_conv.WordFormatOption = type("WordFormatOption", (), {})

    create_mock_module("docling_core")
    create_mock_module("docling_core.transforms")
    create_mock_module("docling_core.transforms.serializer")
    docling_ser = create_mock_module("docling_core.transforms.serializer.markdown")
    docling_ser.MarkdownDocSerializer = type(
        "MarkdownDocSerializer", (), {"model_fields": {}}
    )
    docling_ser.MarkdownParams = type("MarkdownParams", (), {})
    docling_ser.MarkdownTableSerializer = type("MarkdownTableSerializer", (), {})
    docling_ser.SerializationResult = type("SerializationResult", (), {})
    docling_ser.create_ser_result = lambda **kwargs: None

    create_mock_module("docling_core.types")
    docling_types = create_mock_module("docling_core.types.doc")
    docling_types.DoclingDocument = type("DoclingDocument", (), {})
    docling_types.ImageRefMode = type("ImageRefMode", (), {"REFERENCED": "referenced"})
    docling_types.TableItem = type("TableItem", (), {})
