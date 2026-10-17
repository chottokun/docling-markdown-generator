from unittest.mock import MagicMock

from docling_core.transforms.serializer.markdown import create_ser_result
from docling_core.types.doc import DoclingDocument, PictureItem

from src.docling_lib.converter import DocumentConversionOptions
from src.docling_lib.serializers import CustomMarkdownPictureSerializer
from src.docling_lib.server import _MetricsRegistry
from src.docling_lib.vlm import (
    _prepare_rest_payload,
    _resolve_caption_defaults,
    _should_retry_status,
)


def test_document_conversion_options_defaults():
    options = DocumentConversionOptions()
    assert options.image_dir_name == "images"
    assert options.table_format == "html"
    assert options.do_ocr is True


def test_custom_markdown_picture_serializer_caching():
    serializer = CustomMarkdownPictureSerializer(
        image_dir_name="custom_img",
        image_tag_template="![{image_name}]({slug}/{image_name})",
        slug="test_slug",
    )

    doc = MagicMock(spec=DoclingDocument)
    doc.name = "sample_doc"
    pic1 = MagicMock(spec=PictureItem)
    pic1.self_ref = "#/pictures/0"
    pic1.prov = []
    pic1.meta = None
    pic1.captions = []
    pic1.annotations = []
    pic1.image = None

    pic2 = MagicMock(spec=PictureItem)
    pic2.self_ref = "#/pictures/1"
    pic2.prov = []
    pic2.meta = None
    pic2.captions = []
    pic2.annotations = []
    pic2.image = None

    doc.pictures = [pic1, pic2]
    doc_serializer = MagicMock()
    doc_serializer.serialize_captions.return_value = create_ser_result(text="")
    doc_serializer.serialize_annotations.return_value = create_ser_result(text="")
    doc_serializer.get_excluded_refs.return_value = []

    # Serialize pic1
    res1 = serializer.serialize(
        item=pic1,
        doc_serializer=doc_serializer,
        doc=doc,
    )
    assert "test_slug_p1_1.png" in res1.text
    assert serializer._cached_doc is doc
    assert serializer._pic_ref_to_idx["#/pictures/0"] == 0
    assert serializer._pic_ref_to_idx["#/pictures/1"] == 1

    # Serialize pic2 using cached doc
    res2 = serializer.serialize(
        item=pic2,
        doc_serializer=doc_serializer,
        doc=doc,
    )
    assert "test_slug_p1_2.png" in res2.text


def test_vlm_helpers_characterization():
    # Test _should_retry_status
    assert _should_retry_status(429) is True
    assert _should_retry_status(502) is True
    assert _should_retry_status(503) is True
    assert _should_retry_status(504) is True
    assert _should_retry_status(200) is False
    assert _should_retry_status(400) is False
    assert _should_retry_status(404) is False

    # Test _resolve_caption_defaults
    provider, model, endpoint, prompt = _resolve_caption_defaults(
        provider="", model="", endpoint="", prompt=""
    )
    assert provider == "ollama"
    assert model == "qwen2-vl:2b"
    assert endpoint == "http://localhost:11434"
    assert "概要" in prompt

    # Test _prepare_rest_payload for openai
    url, headers, json_body = _prepare_rest_payload(
        provider="openai",
        model="gpt-4o",
        prompt="Describe image",
        img_base64="ABC123Base64",
        text_content="Supplementary text",
        api_key="secret-key",
        endpoint="https://api.openai.com/v1",
    )
    assert url == "https://api.openai.com/v1/chat/completions"
    assert headers["Authorization"] == "Bearer secret-key"
    assert json_body["model"] == "gpt-4o"
    assert len(json_body["messages"][0]["content"]) == 2


def test_metrics_registry_characterization():
    registry = _MetricsRegistry()
    registry.active_conversions = 2
    registry.record_conversion("success", 1.23)
    registry.record_conversion("error", 0.45)

    text = registry.generate_prometheus_text()
    assert 'docling_conversions_total{status="success"} 1' in text
    assert 'docling_conversions_total{status="error"} 1' in text
    assert "docling_active_conversions 2" in text
    assert "docling_memory_used_bytes" in text
    assert "docling_conversion_duration_seconds_count 2" in text
