import shutil
from pathlib import Path

from docling_lib.converter import process_pdf


def test_process_pdf_path_traversal(tmp_path, monkeypatch):
    """
    Test that process_pdf should not allow writing outside the current working directory.
    """
    monkeypatch.chdir(tmp_path)
    # Create a dummy PDF
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(
        b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<Root 1 0 R>>\n%%EOF"
    )

    # /tmp/outside_dir_test is outside tmp_path
    outside_dir = tmp_path.parent / "outside_dir_test"

    # Ensure it doesn't exist before
    if outside_dir.exists():
        shutil.rmtree(outside_dir)

    # Act
    result = process_pdf(pdf_path, outside_dir)

    # Assert
    assert result is None, (
        "process_pdf should return None when path traversal is detected"
    )
    assert not outside_dir.exists(), (
        f"Directory should not have been created: {outside_dir}"
    )


def test_process_pdf_relative_traversal(tmp_path, monkeypatch):
    """
    Test that process_pdf should not allow writing using relative path traversal.
    """
    monkeypatch.chdir(tmp_path)
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(
        b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<Root 1 0 R>>\n%%EOF"
    )

    # A path that tries to escape using ..
    outside_dir = Path("output/../../outside_relative")
    # This will resolve to tmp_path.parent / "outside_relative"
    resolved_outside = (tmp_path / outside_dir).resolve()

    if resolved_outside.exists():
        if resolved_outside.is_dir():
            shutil.rmtree(resolved_outside)
        else:
            resolved_outside.unlink()

    # Act
    result = process_pdf(pdf_path, outside_dir)

    # Assert
    assert result is None
    assert not resolved_outside.exists()
