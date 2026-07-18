from unittest.mock import patch

import torch

import docling_lib.config as config
from docling_lib.converter import is_cuda_compatible


def test_is_cuda_compatible_disabled(monkeypatch):
    """If USE_GPU is False, is_cuda_compatible should return False immediately."""
    monkeypatch.setattr(config, "USE_GPU", False)
    assert is_cuda_compatible() is False


def test_is_cuda_compatible_no_cuda(monkeypatch):
    """If torch.cuda.is_available() is False, is_cuda_compatible should return False."""
    monkeypatch.setattr(config, "USE_GPU", True)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    assert is_cuda_compatible() is False


@patch("docling_lib.converter.torch.zeros")
def test_is_cuda_compatible_successful(mock_zeros, monkeypatch):
    """If CUDA is available and tensor operation succeeds, is_cuda_compatible returns True."""
    monkeypatch.setattr(config, "USE_GPU", True)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "get_device_capability", lambda dev: (8, 6))
    monkeypatch.setattr(torch.cuda, "synchronize", lambda: None)

    assert is_cuda_compatible() is True
    mock_zeros.assert_called_once_with(1, device=torch.device("cuda"))


@patch("docling_lib.converter.torch.zeros")
def test_is_cuda_compatible_incompatible_gpu(mock_zeros, monkeypatch):
    """If tensor operation raises a CUDA error, is_cuda_compatible should return False."""
    monkeypatch.setattr(config, "USE_GPU", True)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "get_device_capability", lambda dev: (8, 6))
    mock_zeros.side_effect = RuntimeError(
        "CUDA error: no kernel image is available for execution"
    )

    assert is_cuda_compatible() is False


def test_is_cuda_compatible_low_capability(monkeypatch):
    """If GPU compute capability is less than 7.5, is_cuda_compatible should return False."""
    monkeypatch.setattr(config, "USE_GPU", True)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    # Mock get_device_capability to return (6, 1) (like GTX 1060)
    monkeypatch.setattr(torch.cuda, "get_device_capability", lambda dev: (6, 1))

    assert is_cuda_compatible() is False
