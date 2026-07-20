import os
import torch
import pytest

from docling_lib.converter import is_cuda_compatible
import docling_lib.config as config


def test_device_compatibility_verification():
    """
    実機（コンテナ内）のデバイス環境が、指定された TARGET_DEVICE の期待値と
    一致していることを検証するE2Eハードウェアチェックテスト。
    """
    target_device = os.getenv("TARGET_DEVICE", "").strip().lower()

    if target_device == "cpu":
        # CPUビルド（またはCPU強制環境）の場合の検証
        assert not torch.cuda.is_available(), (
            "ERROR: TARGET_DEVICE is set to 'cpu', but torch.cuda is available. "
            "CPU-only environment should not load CUDA binaries."
        )
        assert not is_cuda_compatible(), (
            "ERROR: is_cuda_compatible() returned True in CPU-only mode."
        )
        print("SUCCESS: Confirmed CPU-only execution path and no CUDA load.")

    elif target_device == "gpu":
        # GPUビルド（CUDA有効環境）の場合の検証
        # GPUが物理的に利用可能で、ドライバーがロードされている場合の挙動を確認
        if torch.cuda.is_available():
            # GPUがロードされている場合、is_cuda_compatible() の評価が実態（7.5以上等）と一致するか
            device = torch.device("cuda")
            major, minor = torch.cuda.get_device_capability(device)
            capability = major + minor / 10.0
            
            # 互換性チェックの判定ロジックと実判定結果の整合性確認
            compatible_expected = (capability >= 7.5) and (not config.USE_GPU is False)
            
            # get_device_capabilityの判定基準に沿っているか検証
            assert is_cuda_compatible() == compatible_expected, (
                f"ERROR: is_cuda_compatible() did not match physical hardware capability. "
                f"Hardware Capability: {capability}, Expected: {compatible_expected}"
            )
            print(f"SUCCESS: GPU Mode verified. Capability: {capability}, Compatible: {compatible_expected}")
        else:
            # 物理GPUがない、あるいはNVIDIA Container Toolkitが構成されていない場合はCPUフォールダウンが正常か確認
            assert not is_cuda_compatible(), (
                "ERROR: CUDA is not available, but is_cuda_compatible() returned True."
            )
            print("SUCCESS: GPU Mode fell back to CPU due to missing CUDA drivers/devices.")
    else:
        # 特になにも指定がない場合はパス（ローカルテスト環境など）
        print(f"INFO: No TARGET_DEVICE specified ({target_device}). Skipping strict hardware mapping test.")
