from unittest.mock import MagicMock, patch

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

from docling_lib.converter import (
    CustomMarkdownPictureSerializer,
    DocumentConversionOptions,
    PDFConverter,
    ThreadSafeModelPool,
)


def test_pdfconverter_get_format_options():
    converter = PDFConverter()
    pipeline_opts = PdfPipelineOptions()
    opts = converter._get_format_options(pipeline_opts)
    assert InputFormat.PDF in opts
    assert InputFormat.DOCX in opts
    assert InputFormat.XLSX in opts

def test_custom_picture_serializer_template_fallback():
    serializer = CustomMarkdownPictureSerializer(
        image_tag_template="![{image_name}]({slug}/{image_name})",
        slug="test-slug",
    )
    doc_mock = MagicMock()
    pic_mock = MagicMock()
    pic_mock.self_ref = "ref_1"
    doc_mock.pictures = [pic_mock]

    item_mock = MagicMock()
    item_mock.self_ref = "ref_1"
    item_mock.image = None

    with patch("docling_core.transforms.serializer.markdown.MarkdownPictureSerializer.serialize") as mock_super:
        res_mock = MagicMock()
        res_mock.text = ""
        mock_super.return_value = res_mock
        res = serializer.serialize(
            item=item_mock,
            doc_serializer=MagicMock(),
            doc=doc_mock
        )
        assert res.text == "![picture_1.png](test-slug/picture_1.png)"

def test_thread_safe_model_pool_lru_eviction():
    pool = ThreadSafeModelPool(max_size=2)
    opt1 = DocumentConversionOptions(num_threads=1)
    opt2 = DocumentConversionOptions(num_threads=2)
    opt3 = DocumentConversionOptions(num_threads=3)

    c1 = pool.get_converter(opt1)
    c2 = pool.get_converter(opt2)
    assert len(pool._pool) == 2

    c3 = pool.get_converter(opt3)
    assert len(pool._pool) == 2
    key1 = (
        opt1.image_scale,
        opt1.do_formula,
        opt1.do_ocr,
        opt1.do_chart,
        opt1.do_code,
        opt1.table_format,
        opt1.num_threads,
        opt1.cuda_use_flash_attention,
    )
    assert key1 not in pool._pool
