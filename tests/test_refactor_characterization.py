import io
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import defusedxml.ElementTree as ET

from src.docling_lib.config import DOCLING_ARTIFACTS_PATH
from src.docling_lib.converter import DocumentConversionOptions, PDFConverter
from src.docling_lib.utils import (
    _extract_anchors_from_drawing,
    _parse_drawing_relationships,
    _parse_sheet_relationships,
    _parse_workbook_relationships,
    extract_excel_images,
    generate_doc_slug,
    generate_image_filename,
    get_picture_page_no,
)


def test_characterization_extract_excel_images_invalid_inputs():
    """Verify extract_excel_images handling of invalid files or non-zip bytes."""
    assert extract_excel_images(b"invalid_bytes_content") == []
    assert extract_excel_images(Path("non_existent_file_path.xlsx")) == []


def test_characterization_extract_excel_images_empty_zip():
    """Verify extract_excel_images handling of zip archives lacking OpenXML structure."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("dummy.txt", "content")
    assert extract_excel_images(buf.getvalue()) == []


def test_characterization_slug_and_filename_generation():
    """Verify boundary cases for slug and image filename generation."""
    assert generate_doc_slug(None) == "document"
    assert generate_doc_slug("") == "document"
    assert generate_doc_slug("  ") == "document"
    assert generate_doc_slug("My/Doc:Name*.pdf") == "Doc-Name"
    assert generate_doc_slug("Doc Name.pdf") == "Doc-Name"

    assert generate_image_filename("slug", 1, 1) == "slug_p1_1.png"
    # Negative/zero values bounded to 1
    assert generate_image_filename("slug", -5, 0) == "slug_p1_1.png"


def test_characterization_get_picture_page_no():
    """Verify page number extraction from picture item provenance."""
    pic = MagicMock()
    pic.prov = []
    assert get_picture_page_no(pic) == 1

    prov_item = MagicMock()
    prov_item.page_no = 3
    pic.prov = [prov_item]
    assert get_picture_page_no(pic) == 3


def test_characterization_pdf_converter_format_options():
    """Verify PDFConverter initializes format options properly."""
    options = DocumentConversionOptions()
    converter = PDFConverter(options)
    assert converter.options.image_dir_name == "images"
    assert converter.doc_converter is not None


def test_characterization_config_artifacts_path():
    """Verify DOCLING_ARTIFACTS_PATH configuration exists and is properly typed."""
    assert DOCLING_ARTIFACTS_PATH is None or isinstance(DOCLING_ARTIFACTS_PATH, Path)


# --- 批判的テスト（Adversarial & Boundary Tests） ---


def test_adversarial_parse_workbook_relationships():
    """XMLツリーの欠落・異常値・パス解決の耐性を検証。"""
    ns_rel = "http://schemas.openxmlformats.org/package/2006/relationships"

    # 空のツリー
    empty_tree = ET.fromstring("<Relationships />")
    assert _parse_workbook_relationships(empty_tree, ns_rel) == {}

    # Id欠落、Target欠落、xl/プレフィックス有無、先頭スラッシュ
    xml = f"""
    <Relationships xmlns="{ns_rel}">
        <Relationship Id="rId1" Target="worksheets/sheet1.xml" />
        <Relationship Id="rId2" Target="/xl/worksheets/sheet2.xml" />
        <Relationship Id="rId3" Target="xl/worksheets/sheet3.xml" />
        <Relationship Id="rId4" Target="" />
        <Relationship Target="worksheets/sheet5.xml" />
    </Relationships>
    """
    tree = ET.fromstring(xml)
    parsed = _parse_workbook_relationships(tree, ns_rel)
    assert parsed["rId1"] == "xl/worksheets/sheet1.xml"
    assert parsed["rId2"] == "xl/worksheets/sheet2.xml"
    assert parsed["rId3"] == "xl/worksheets/sheet3.xml"
    assert "rId4" not in parsed
    assert len(parsed) == 3


def test_adversarial_parse_sheet_relationships():
    """シートリレーションシップの相対パス解決と異常値の耐性を検証。"""
    ns_rel = "http://schemas.openxmlformats.org/package/2006/relationships"

    xml = f"""
    <Relationships xmlns="{ns_rel}">
        <Relationship Id="rId1" Target="../drawings/drawing1.xml" />
        <Relationship Id="rId2" Target="drawings/drawing2.xml" />
        <Relationship Id="rId3" Target="/xl/drawings/drawing3.xml" />
        <Relationship Id="rId4" Target="" />
    </Relationships>
    """
    tree = ET.fromstring(xml)
    parsed = _parse_sheet_relationships(tree, sheet_dir="xl/worksheets", ns_rel=ns_rel)
    assert parsed["rId1"] == "xl/drawings/drawing1.xml"
    assert parsed["rId2"] == "xl/worksheets/drawings/drawing2.xml"
    assert parsed["rId3"] == "xl/drawings/drawing3.xml"
    assert "rId4" not in parsed


def test_adversarial_parse_drawing_relationships():
    """ドローイングリレーションシップのメディアパス正規化を検証。"""
    ns_rel = "http://schemas.openxmlformats.org/package/2006/relationships"

    xml = f"""
    <Relationships xmlns="{ns_rel}">
        <Relationship Id="rId1" Target="../media/image1.png" />
        <Relationship Id="rId2" Target="media/image2.jpeg" />
        <Relationship Id="rId3" Target="/xl/media/image3.png" />
        <Relationship Id="rId4" Target="custom/dir/other.png" />
    </Relationships>
    """
    tree = ET.fromstring(xml)
    parsed = _parse_drawing_relationships(tree, drawing_dir="xl/drawings", ns_rel=ns_rel)
    assert parsed["rId1"] == "xl/media/image1.png"
    assert parsed["rId2"] == "xl/media/image2.jpeg"
    assert parsed["rId3"] == "xl/media/image3.png"
    assert parsed["rId4"] == "xl/drawings/custom/dir/other.png"


def test_adversarial_extract_anchors_corrupt_data():
    """壊れたXML要素、不正な座標、壊れた画像バイナリへの耐性を検証。"""
    ns_xdr = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
    ns_a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    rel_embed_attr = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"

    drawing_xml = f"""
    <wsDr xmlns:xdr="{ns_xdr}" xmlns:a="{ns_a}">
        <!-- 座標が文字列・空のアンカー -->
        <xdr:twoCellAnchor>
            <xdr:from>
                <xdr:col>invalid_col</xdr:col>
                <xdr:row></xdr:row>
            </xdr:from>
            <xdr:pic>
                <xdr:blipFill>
                    <a:blip r:embed="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>
                </xdr:blipFill>
            </xdr:pic>
        </xdr:twoCellAnchor>
        <!-- blipが存在しないアンカー -->
        <xdr:oneCellAnchor>
            <xdr:from>
                <xdr:col>1</xdr:col>
                <xdr:row>2</xdr:row>
            </xdr:from>
        </xdr:oneCellAnchor>
        <!-- namelistにない画像を参照するアンカー -->
        <xdr:twoCellAnchor>
            <xdr:from>
                <xdr:col>3</xdr:col>
                <xdr:row>4</xdr:row>
            </xdr:from>
            <xdr:pic>
                <xdr:blipFill>
                    <a:blip r:embed="rIdMissing" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>
                </xdr:blipFill>
            </xdr:pic>
        </xdr:twoCellAnchor>
    </wsDr>
    """
    drawing_tree = ET.fromstring(drawing_xml)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # 壊れた画像（無効なPNGバイナリ）
        zf.writestr("xl/media/corrupt.png", b"not_a_valid_image_binary")

    with zipfile.ZipFile(io.BytesIO(buf.getvalue()), "r") as zf:
        drawing_rels = {
            "rId1": "xl/media/corrupt.png",
            "rIdMissing": "xl/media/not_exist.png",
        }
        anchors = _extract_anchors_from_drawing(
            zf=zf,
            drawing_tree=drawing_tree,
            drawing_rels=drawing_rels,
            sheet_name="TestSheet",
            sheet_idx=1,
            namelist=zf.namelist(),
            ns_xdr=ns_xdr,
            ns_a=ns_a,
            rel_embed_attr=rel_embed_attr,
        )

        # 破損画像でも例外を吐かずに抽出され、pil_imageはNoneとしてハンドリングされること
        assert len(anchors) == 1
        assert anchors[0]["sheet_name"] == "TestSheet"
        assert anchors[0]["row"] == 0  # 空文字はデフォルト0
        assert anchors[0]["col"] == 0  # int変換失敗時はデフォルト0
        assert anchors[0]["pil_image"] is None
        assert anchors[0]["image_bytes"] == b"not_a_valid_image_binary"
        assert len(anchors[0]["sha256"]) == 64


def test_adversarial_pdf_converter_helpers(tmp_path: Path):
    """PDFConverter の分離メソッド（_hash_existing_pictures, _process_and_save_single_image）の耐性を検証。"""
    converter = PDFConverter(DocumentConversionOptions())

    # 1. _hash_existing_pictures の異常系耐性
    mock_doc = MagicMock()
    mock_pic_broken = MagicMock()
    mock_pic_broken.image.pil_image.save.side_effect = RuntimeError("Save failure")
    mock_doc.pictures = [mock_pic_broken]

    # 例外がスルーされクラッシュしないこと
    hashes = converter._hash_existing_pictures(mock_doc)
    assert isinstance(hashes, set)
    assert len(hashes) == 0

    # 2. _process_and_save_single_image の異常系耐性
    mock_element = MagicMock()
    mock_element.prov = []
    mock_element.image.pil_image.save.side_effect = PermissionError("Cannot write")

    # 例外が内部でハンドリングされ、呼び出し元に波及しないこと
    converter._process_and_save_single_image(
        i=0,
        element=mock_element,
        images_dir=tmp_path,
        doc_slug="test_doc",
    )

