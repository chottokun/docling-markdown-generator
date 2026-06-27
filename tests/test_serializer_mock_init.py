from unittest.mock import MagicMock
from docling_lib.converter import EnhancedMarkdownSerializer, HTMLTableMarkdownSerializer
from docling_core.transforms.serializer.markdown import MarkdownParams

def test_enhanced_markdown_serializer_with_mock_doc():
    """
    Verify that EnhancedMarkdownSerializer can be initialized with a MagicMock document,
    bypassing Pydantic validation as intended by the refactored code.
    """
    mock_doc = MagicMock()
    # Now it should work with table_format="html" as well
    serializer = EnhancedMarkdownSerializer(doc=mock_doc, table_format="html")

    assert serializer.doc == mock_doc
    # Check if params was initialized
    assert isinstance(serializer.params, MarkdownParams)

    # Verify that table_serializer is set correctly even with mock
    assert isinstance(serializer.table_serializer, HTMLTableMarkdownSerializer)

    # Verify that other fields in model_fields are initialized
    for field in serializer.model_fields:
        # Pydantic instances should have these fields
        assert hasattr(serializer, field)
