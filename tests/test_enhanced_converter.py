from unittest.mock import MagicMock, patch

from docling_core.types.doc import DoclingDocument, PictureItem

from docling_lib.converter import DocumentConversionOptions, EnhancedDoclingConverter


def test_enhanced_docling_converter_init():
    """Verify initialization with default and custom PDFConverter."""
    conv = EnhancedDoclingConverter()
    assert conv.docling_converter is not None

    custom_pdf_converter = MagicMock()
    conv2 = EnhancedDoclingConverter(docling_converter=custom_pdf_converter)
    assert conv2.docling_converter == custom_pdf_converter


@patch("docling_lib.converter.PDFConverter")
def test_convert_to_markdown_slug_generation(MockPDFConverter, tmp_path):
    """Verify slug generation replaces non-alphanumeric chars and handles empty cases."""
    mock_pdf_conv = MockPDFConverter.return_value
    mock_doc = MagicMock(spec=DoclingDocument)
    mock_doc.name = "Test Doc"
    mock_doc.pictures = []

    mock_result = MagicMock()
    mock_result.document = mock_doc
    mock_pdf_conv.doc_converter.convert.return_value = mock_result

    # We will verify that _serialize_to_markdown is called with the generated slug.
    mock_pdf_conv._serialize_to_markdown.return_value = "Content"
    mock_pdf_conv.options = DocumentConversionOptions()
    mock_pdf_conv._apply_metadata_frontmatter.return_value = "Frontmatter + Content"

    # 1. Standard file with spaces & uppercase
    conv = EnhancedDoclingConverter(docling_converter=mock_pdf_conv)
    input_path = tmp_path / "My Awesome Document! 123.pdf"
    conv.convert_to_markdown(input_path)

    # Assert _serialize_to_markdown called with 'my-awesome-document-123' slug
    mock_pdf_conv._serialize_to_markdown.assert_called_with(
        doc=mock_doc,
        table_format="html",
        options=mock_pdf_conv.options,
        image_tag_template="![[assets/{slug}/{image_name}]]",
        slug="my-awesome-document-123",
    )

    # 2. File with only special characters (fallback to 'document')
    input_path_special = tmp_path / "!!!.pdf"
    conv.convert_to_markdown(input_path_special)

    mock_pdf_conv._serialize_to_markdown.assert_called_with(
        doc=mock_doc,
        table_format="html",
        options=mock_pdf_conv.options,
        image_tag_template="![[assets/{slug}/{image_name}]]",
        slug="document",
    )


@patch("docling_lib.converter.PDFConverter")
def test_convert_to_markdown_saves_images_when_assets_dir_provided(MockPDFConverter, tmp_path):
    """Verify that images are saved to assets_dir when provided."""
    mock_pdf_conv = MockPDFConverter.return_value
    mock_doc = MagicMock(spec=DoclingDocument)
    mock_doc.name = "Doc with Pictures"
    mock_doc.pictures = [MagicMock(spec=PictureItem)]

    mock_result = MagicMock()
    mock_result.document = mock_doc
    mock_pdf_conv.doc_converter.convert.return_value = mock_result

    mock_pdf_conv._serialize_to_markdown.return_value = "Content"
    mock_pdf_conv.options = DocumentConversionOptions()
    mock_pdf_conv._apply_metadata_frontmatter.return_value = "Frontmatter + Content"

    conv = EnhancedDoclingConverter(docling_converter=mock_pdf_conv)
    assets_dir = tmp_path / "custom-assets"

    conv.convert_to_markdown(tmp_path / "test.pdf", assets_dir=assets_dir)

    # Assert directory is created and _save_images is called
    assert assets_dir.exists()
    mock_pdf_conv._save_images.assert_called_once_with(mock_doc, assets_dir)


def test_custom_picture_serializer_template_interpolation():
    """Verify custom template is correctly interpolated when serializing picture item."""
    from docling_core.transforms.serializer.markdown import SerializationResult
    from docling_core.types.doc import PictureItem

    from docling_lib.converter import CustomMarkdownPictureSerializer

    # We mock serialize behavior
    doc = MagicMock(spec=DoclingDocument)
    pic = MagicMock(spec=PictureItem)
    pic.self_ref = "pictures.0"
    doc.pictures = [pic]

    serializer = CustomMarkdownPictureSerializer(
        image_tag_template="![[assets/{slug}/{image_name}]]",
        slug="my-cool-doc",
    )

    with patch("docling_core.transforms.serializer.markdown.MarkdownPictureSerializer.serialize") as mock_super_serialize:
        mock_super_serialize.return_value = SerializationResult(text="super_text")

        res = serializer.serialize(
            item=pic,
            doc_serializer=MagicMock(),
            doc=doc,
        )

        assert res.text == "![[assets/my-cool-doc/picture_1.png]]"
