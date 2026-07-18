from unittest.mock import MagicMock, patch

from docling_core.transforms.serializer.base import Span
from docling_core.transforms.serializer.markdown import (
    MarkdownTableSerializer,
    SerializationResult,
)
from docling_core.types.doc import DoclingDocument, TableItem

from docling_lib.converter import HTMLTableMarkdownSerializer


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
        item=mock_item, doc_serializer=mock_doc_serializer, doc=mock_doc
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

    with patch.object(
        MarkdownTableSerializer, "serialize", return_value=fallback_result
    ) as mock_super_serialize:
        # Act
        result = serializer.serialize(
            item=mock_item, doc_serializer=mock_doc_serializer, doc=mock_doc
        )

        # Assert
        assert result == fallback_result
        assert (
            "Failed to export table as HTML, falling back: HTML Export Failed"
            in caplog.text
        )
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
        item=mock_item, doc_serializer=mock_doc_serializer, doc=mock_doc
    )

    # Assert
    assert "Table 1: My Table" in result.text
    assert "<table>Table Content</table>" in result.text
    assert result.text == "Table 1: My Table\n\n<table>Table Content</table>"
    # Verify both caption and table spans are present
    assert len(result.spans) == 2
    assert any(span.item.self_ref == "#/texts/2" for span in result.spans)
    assert any(span.item.self_ref == "#/tables/1" for span in result.spans)


def test_html_table_serialization_empty():
    """Test HTML table serialization when both captions and HTML export are empty."""
    serializer = HTMLTableMarkdownSerializer()

    # Setup mocks
    mock_item = MagicMock(spec=TableItem)
    mock_item.export_to_html.return_value = ""

    mock_doc = MagicMock(spec=DoclingDocument)

    mock_doc_serializer = MagicMock()
    mock_caption_res = MagicMock(spec=SerializationResult)
    mock_caption_res.text = ""
    mock_caption_res.spans = []
    mock_doc_serializer.serialize_captions.return_value = mock_caption_res

    # Act
    result = serializer.serialize(
        item=mock_item, doc_serializer=mock_doc_serializer, doc=mock_doc
    )

    # Assert
    assert result.text == ""
    assert result.spans == []


def test_html_table_serialization_fallback_kwargs():
    """Test that kwargs are propagated during fallback."""
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

    custom_kwargs = {"custom_arg": "value", "another_arg": 123}

    with patch.object(
        MarkdownTableSerializer, "serialize", return_value=MagicMock()
    ) as mock_super_serialize:
        # Act
        serializer.serialize(
            item=mock_item,
            doc_serializer=mock_doc_serializer,
            doc=mock_doc,
            **custom_kwargs,
        )

        # Assert
        mock_super_serialize.assert_called_once_with(
            item=mock_item,
            doc_serializer=mock_doc_serializer,
            doc=mock_doc,
            **custom_kwargs,
        )
        mock_doc_serializer.serialize_captions.assert_called_once_with(
            item=mock_item,
            **custom_kwargs,
        )


def test_html_table_serialization_no_html_content():
    """Test HTML table serialization when export_to_html returns None or empty."""
    serializer = HTMLTableMarkdownSerializer()

    # Case 1: export_to_html returns None
    mock_item = MagicMock(spec=TableItem)
    mock_item.export_to_html.return_value = None

    mock_doc = MagicMock(spec=DoclingDocument)
    mock_doc_serializer = MagicMock()
    mock_caption_res = MagicMock(spec=SerializationResult)
    mock_caption_res.text = "Caption"
    mock_caption_res.spans = []
    mock_doc_serializer.serialize_captions.return_value = mock_caption_res

    result = serializer.serialize(
        item=mock_item, doc_serializer=mock_doc_serializer, doc=mock_doc
    )
    # Should only contain caption
    assert result.text == "Caption"

    # Case 2: export_to_html returns empty string
    mock_item.export_to_html.return_value = ""
    result = serializer.serialize(
        item=mock_item, doc_serializer=mock_doc_serializer, doc=mock_doc
    )
    assert result.text == "Caption"


def test_serialize_table_to_html_export_failure(caplog):
    """
    Test specifically named for _serialize_table_to_html HTML export failure.
    Verifies that when item.export_to_html raises an Exception, the exception
    is handled gracefully, a warning is logged, and it falls back to the
    super-class serialize implementation.
    """
    serializer = HTMLTableMarkdownSerializer()

    # Setup mocks
    mock_item = MagicMock(spec=TableItem)
    mock_item.export_to_html.side_effect = Exception("HTML Export Failure Simulation")

    mock_doc = MagicMock(spec=DoclingDocument)

    mock_doc_serializer = MagicMock()
    mock_caption_res = MagicMock(spec=SerializationResult)
    mock_caption_res.text = ""
    mock_caption_res.spans = []
    mock_doc_serializer.serialize_captions.return_value = mock_caption_res

    # Expected fallback markdown result
    fallback_result = MagicMock(spec=SerializationResult)
    fallback_result.text = "| mock_col |\n| --- |\n| mock_val |"

    with patch.object(
        MarkdownTableSerializer, "serialize", return_value=fallback_result
    ) as mock_super_serialize:
        # Act
        result = serializer.serialize(
            item=mock_item, doc_serializer=mock_doc_serializer, doc=mock_doc
        )

        # Assert
        assert result == fallback_result
        assert (
            "Failed to export table as HTML, falling back: HTML Export Failure Simulation"
            in caplog.text
        )
        mock_super_serialize.assert_called_once_with(
            item=mock_item, doc_serializer=mock_doc_serializer, doc=mock_doc
        )
