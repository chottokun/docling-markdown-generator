from unittest.mock import MagicMock, patch

from docling_core.types.doc import ImageRefMode

from docling_lib.converter import PDFConverter


def test_serialize_to_markdown():
    """Test that _serialize_to_markdown correctly configures and calls the enhanced serializer."""
    # Setup
    converter = PDFConverter()
    mock_doc = MagicMock()
    table_format = "html"

    # We patch where they are imported and used
    with (
        patch(
            "docling_lib.converter.EnhancedMarkdownSerializer"
        ) as mock_serializer_cls,
        patch("docling_lib.converter.MarkdownParams") as mock_params_cls,
    ):
        # Configure mocks
        mock_serializer_inst = mock_serializer_cls.return_value
        mock_ser_res = MagicMock()
        mock_ser_res.text = "Mocked Markdown Content"
        mock_serializer_inst.serialize.return_value = mock_ser_res

        mock_params_inst = mock_params_cls.return_value

        # Act
        result = converter._serialize_to_markdown(mock_doc, table_format)

        # Assert
        # Verify MarkdownParams instantiation
        mock_params_cls.assert_called_once_with(
            image_mode=ImageRefMode.REFERENCED,
            image_placeholder="<!-- image -->",
            page_break_placeholder=None,
        )

        # Verify EnhancedMarkdownSerializer instantiation
        mock_serializer_cls.assert_called_once_with(
            doc=mock_doc,
            table_format=table_format,
            vlm_enabled=False,
            vlm_model="qwen2-vl:2b",
            vlm_endpoint="http://localhost:11434",
            vlm_prompt="この画像の詳細な説明文を日本語で作成してください。",
            vlm_captions={},
            params=mock_params_inst,
        )

        # Verify serialize call
        mock_serializer_inst.serialize.assert_called_once()

        # Verify return value
        assert result == "Mocked Markdown Content"


def test_serialize_to_markdown_different_format():
    """Test that _serialize_to_markdown handles different table formats."""
    # Setup
    converter = PDFConverter()
    mock_doc = MagicMock()
    table_format = "markdown"

    with (
        patch(
            "docling_lib.converter.EnhancedMarkdownSerializer"
        ) as mock_serializer_cls,
        patch("docling_lib.converter.MarkdownParams") as mock_params_cls,
    ):
        # Configure mocks
        mock_serializer_inst = mock_serializer_cls.return_value
        mock_ser_res = MagicMock()
        mock_ser_res.text = "Another Mocked Content"
        mock_serializer_inst.serialize.return_value = mock_ser_res

        # Act
        result = converter._serialize_to_markdown(mock_doc, table_format)

        # Assert
        mock_serializer_cls.assert_called_once_with(
            doc=mock_doc,
            table_format=table_format,
            vlm_enabled=False,
            vlm_model="qwen2-vl:2b",
            vlm_endpoint="http://localhost:11434",
            vlm_prompt="この画像の詳細な説明文を日本語で作成してください。",
            vlm_captions={},
            params=mock_params_cls.return_value,
        )
        assert result == "Another Mocked Content"
