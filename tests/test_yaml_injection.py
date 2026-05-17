from unittest.mock import MagicMock

from docling_lib.converter import PDFConverter


def test_yaml_frontmatter_injection_newline():
    # Setup
    converter = PDFConverter()
    doc = MagicMock()
    # Malicious name with injection
    doc.name = "Normal Title\nauthor: Injected Author"
    md_content = "Body content"

    # Act
    result = converter._apply_metadata_frontmatter(doc, md_content)

    # Assert
    # The title should contain the whole string on one line
    assert "title: Normal Title author: Injected Author" in result
    # There should NOT be a separate line starting with author:
    assert "\nauthor:" not in result


def test_yaml_frontmatter_injection_carriage_return():
    # Setup
    converter = PDFConverter()
    doc = MagicMock()
    # Malicious name with injection using carriage return
    doc.name = "Normal Title\rauthor: Injected Author"
    md_content = "Body content"

    # Act
    result = converter._apply_metadata_frontmatter(doc, md_content)

    # Assert
    assert "title: Normal Title author: Injected Author" in result
    assert "\rauthor:" not in result
    assert (
        "author:" not in result.splitlines()[2]
    )  # title is on line 2 (0-indexed) if count ---


def test_yaml_frontmatter_injection_breakout():
    # Setup
    converter = PDFConverter()
    doc = MagicMock()
    # Malicious name attempting to break out of frontmatter
    doc.name = "Title\n---\n\n# Injected Markdown"
    md_content = "Original Body"

    # Act
    result = converter._apply_metadata_frontmatter(doc, md_content)

    # Assert
    # Should be sanitized to one line
    assert "title: Title ---  # Injected Markdown" in result
    # Check that there are only two '---' separators (one start, one end) plus one in the title
    assert result.count("---") == 3
