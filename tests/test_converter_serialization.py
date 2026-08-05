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
            vlm_provider="ollama",
            vlm_api_key="",
            vlm_model="qwen2-vl:2b",
            vlm_endpoint="http://localhost:11434",
            vlm_prompt=(
                "この画像の概要を1〜2文程度で簡潔に日本語で説明してください。"
                "なお、グラフや図表の場合は主要な数値や傾向（増減・ピークなど）を含めて説明してください。"
            ),
            vlm_max_concurrent=5,
            vlm_captions={},
            image_dir_name="images",
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
            vlm_provider="ollama",
            vlm_api_key="",
            vlm_model="qwen2-vl:2b",
            vlm_endpoint="http://localhost:11434",
            vlm_prompt=(
                "この画像の概要を1〜2文程度で簡潔に日本語で説明してください。"
                "なお、グラフや図表の場合は主要な数値や傾向（増減・ピークなど）を含めて説明してください。"
            ),
            vlm_max_concurrent=5,
            vlm_captions={},
            image_dir_name="images",
            params=mock_params_cls.return_value,
        )
        assert result == "Another Mocked Content"


def test_custom_picture_serializer_caching_and_lookup():
    """Test that CustomMarkdownPictureSerializer caches index lookups and invalidates cache when doc changes."""
    from unittest.mock import MagicMock

    from docling_core.types.doc import DoclingDocument, PictureItem

    from docling_lib.converter import CustomMarkdownPictureSerializer

    class MockPicture:
        def __init__(self, self_ref):
            self.self_ref = self_ref
            self.image = None

    serializer = CustomMarkdownPictureSerializer(vlm_enabled=False)

    # Prepare doc1
    doc1 = MagicMock(spec=DoclingDocument)
    pic1 = MockPicture("#/pictures/1")
    pic2 = MockPicture("#/pictures/2")
    doc1.pictures = [pic1, pic2]

    # First serialize item on doc1 (populates cache)
    item1 = PictureItem(self_ref="#/pictures/1")
    with patch(
        "docling_core.transforms.serializer.markdown.MarkdownPictureSerializer.serialize"
    ) as mock_super_serialize:
        mock_super_serialize.return_value = MagicMock()
        serializer.serialize(item=item1, doc_serializer=MagicMock(), doc=doc1)

    assert serializer._cached_doc is doc1
    assert serializer._pic_ref_to_idx == {"#/pictures/1": 0, "#/pictures/2": 1}

    # Second serialize item on doc1 (uses cache, doesn't re-loop doc1.pictures)
    item2 = PictureItem(self_ref="#/pictures/2")
    with patch(
        "docling_core.transforms.serializer.markdown.MarkdownPictureSerializer.serialize"
    ) as mock_super_serialize:
        mock_super_serialize.return_value = MagicMock()
        # We delete doc1.pictures to prove it does not attempt to traverse or access it
        del doc1.pictures
        serializer.serialize(item=item2, doc_serializer=MagicMock(), doc=doc1)

    # Cache hit should return correct index
    # We can check that the index of f"picture_{idx + 1}.png" is reflected in the result or path logic
    # Let's verify by checking id changes or cache presence
    assert serializer._cached_doc is doc1

    # Prepare doc2 (cache invalidation check)
    doc2 = MagicMock(spec=DoclingDocument)
    pic3 = MockPicture("#/pictures/3")
    doc2.pictures = [pic3]

    item3 = PictureItem(self_ref="#/pictures/3")
    with patch(
        "docling_core.transforms.serializer.markdown.MarkdownPictureSerializer.serialize"
    ) as mock_super_serialize:
        mock_super_serialize.return_value = MagicMock()
        serializer.serialize(item=item3, doc_serializer=MagicMock(), doc=doc2)

    assert serializer._cached_doc is doc2
    assert serializer._pic_ref_to_idx == {"#/pictures/3": 0}
