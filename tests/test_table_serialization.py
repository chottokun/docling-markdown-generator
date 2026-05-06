from unittest.mock import MagicMock, patch
from docling_lib.converter import HTMLTableMarkdownSerializer
from docling_core.types.doc import TableItem, DoclingDocument
from docling_core.transforms.serializer.markdown import SerializationResult, MarkdownTableSerializer
from docling_core.transforms.serializer.base import Span

def test_html_table_serialization_success():
    """Test successful HTML table serialization."""
    serializer = HTMLTableMarkdownSerializer()

    # Setup mocks
    mock_item = MagicMock(spec=TableItem)
    # create_ser_result uses item.self_ref
    mock_item.self_ref = "#/tables/1"
    mock_item.export_to_html.return_value = "<table><tr><td>cell</td></tr></table>"

    mock_doc = MagicMock(spec=DoclingDocument)

    mock_doc_serializer = MagicMock()
    # Mock serialize_captions to return an empty result with empty spans
    mock_caption_res = MagicMock(spec=SerializationResult)
    mock_caption_res.text = ""
    mock_caption_res.spans = []
    mock_doc_serializer.serialize_captions.return_value = mock_caption_res

    # Act
    result = serializer.serialize(
        item=mock_item,
        doc_serializer=mock_doc_serializer,
        doc=mock_doc
    )

    # Assert
    assert "<table><tr><td>cell</td></tr></table>" in result.text
    mock_item.export_to_html.assert_called_once_with(doc=mock_doc)
    assert len(result.spans) == 1
    assert result.spans[0].item.self_ref == "#/tables/1"

def test_html_table_serialization_fallback(caplog):
    """Test fallback to standard markdown serialization when HTML export fails."""
    serializer = HTMLTableMarkdownSerializer()

    # Setup mocks
    mock_item = MagicMock(spec=TableItem)
    mock_item.export_to_html.side_effect = Exception("HTML Export Failed")

    mock_doc = MagicMock(spec=DoclingDocument)

    mock_doc_serializer = MagicMock()
    mock_caption_res = MagicMock(spec=SerializationResult)
    mock_caption_res.text = ""
    mock_caption_res.spans = []
    mock_doc_serializer.serialize_captions.return_value = mock_caption_res

    # We want to verify that super().serialize is called.
    fallback_result = MagicMock(spec=SerializationResult)
    fallback_result.text = "| col1 |\n| --- |\n| val1 |"

    with patch.object(MarkdownTableSerializer, 'serialize', return_value=fallback_result) as mock_super_serialize:
        # Act
        result = serializer.serialize(
            item=mock_item,
            doc_serializer=mock_doc_serializer,
            doc=mock_doc
        )

        # Assert
        assert result == fallback_result
        assert "Failed to export table as HTML, falling back: HTML Export Failed" in caplog.text
        mock_super_serialize.assert_called_once_with(
            item=mock_item, doc_serializer=mock_doc_serializer, doc=mock_doc
        )

def test_html_table_serialization_with_captions():
    """Test HTML table serialization includes captions."""
    serializer = HTMLTableMarkdownSerializer()

    # Setup mocks
    mock_item = MagicMock(spec=TableItem)
    mock_item.self_ref = "#/tables/1"
    mock_item.export_to_html.return_value = "<table>Table Content</table>"

    mock_doc = MagicMock(spec=DoclingDocument)

    mock_doc_serializer = MagicMock()
    # Mock serialize_captions to return a caption
    mock_caption_item = MagicMock()
    mock_caption_item.self_ref = "#/texts/2"

    mock_caption_span = MagicMock(spec=Span)
    mock_caption_span.item = mock_caption_item

    mock_caption_res = MagicMock(spec=SerializationResult)
    mock_caption_res.text = "Table 1: My Table"
    mock_caption_res.spans = [mock_caption_span]

    mock_doc_serializer.serialize_captions.return_value = mock_caption_res

    # Act
    result = serializer.serialize(
        item=mock_item,
        doc_serializer=mock_doc_serializer,
        doc=mock_doc
    )

    # Assert
    assert "Table 1: My Table" in result.text
    assert "<table>Table Content</table>" in result.text
    assert result.text == "Table 1: My Table\n\n<table>Table Content</table>"
    # Verify both caption and table spans are present
    assert len(result.spans) == 2
    assert any(span.item.self_ref == "#/texts/2" for span in result.spans)
    assert any(span.item.self_ref == "#/tables/1" for span in result.spans)
