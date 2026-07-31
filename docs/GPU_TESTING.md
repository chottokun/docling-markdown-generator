# GPU Testing and Acceleration Guide

本ドキュメントでは、NVIDIA GPU（CUDA）環境における本ライブラリの動作仕様、パフォーマンス最適化、VRAM管理、自動フォールバック機構、および GPU 環境を想定したテスト実行手順について解説します。

---

## 🏎 1. GPU アクセラレーションの設計と動作仕様

Docling ドキュメント変換パイプライン（PyTorch, RapidOCR, Layout Model, CodeFormula VLM）は、CUDA が有効な環境において GPU 加速を最大限活用できるように設計されています。

### 1.1 CUDA 互換性チェックと自動フォールバック (`is_cuda_compatible`)

ライブラリ起動時、`src/docling_lib/converter.py` 内の `is_cuda_compatible()` 関数により、システムの GPU 環境が厳格に検証されます。

1. **環境変数チェック**: `DOCLING_USE_GPU=False` の場合、直ちに CPU モードで動作します。
2. **CUDA 可用性確認**: `torch.cuda.is_available()` をチェックします。
3. **Compute Capability (算術性能) 検証**:
   - 現代の PyTorch ビルドでは、原則として **Compute Capability (CC) >= 7.5**（Turing世代以降: RTX 20シリーズ, GTX 1660, Tesla T4, A100, H100 等）が必須とされています。
   - CC < 7.5 の古い GPU（例: GTX 1060 / sm_61 等）が検出された場合、クラッシュやフリーズを防ぐため、安全に警告ログを出力して **CPU モードへ自動フォールバック** します。
4. **ダミーテンソル動作テスト**: 実際の GPU メモリ確保および同期テストを実行し、問題がない場合のみ GPU モード（`AcceleratorDevice.AUTO`）が選定されます。

---

## ⚡ 2. GPU 環境における最適化設定

環境変数を通じて、GPU 性能を最大化するための調整が可能です。

```bash
# GPU の有効化（デフォルト: True）
DOCLING_USE_GPU=True

# FlashAttention-2 の有効化（サポート対象 GPU のみ）
DOCLING_CUDA_FLASH_ATTENTION=True

# マルチプロセス並列ワーカー数（GPU VRAM 容量に応じた調整が必要）
DOCLING_MAX_WORKERS=2
```

### 2.1 マルチプロセス環境における GPU VRAM 管理

本ライブラリは `ProcessPoolExecutor` によるマルチプロセス並列化を採用しています。ワーカープロセスごとに独立した PyTorch / CUDA コンテキストが生成されるため、以下の点に留意してください。

- **VRAM 消費の計算目安**:
  - 1 ワーカープロセスあたり **約 2 GB 〜 4 GB** の VRAM を消費します。
  - 例: 8 GB VRAM の GPU の場合、`DOCLING_MAX_WORKERS=2` が推奨値となります。
  - 超過した場合は OOM (Out of Memory) が発生する可能性があるため、`server.py` 内の動的セマフォ制御 (`get_dynamic_semaphore_limit()`) がメモリ空き状況に応じて同時実行数を安全に制御します。

---

## 🧪 3. GPU 環境を想定したテスト実行手順

### 3.1 単体・統合テストの実行 (GPU有効)

GPU が利用可能なマシンで全テストスイートを実行するには、以下のコマンドを使用します：

```bash
# GPU を有効化して全テストを実行
DOCLING_USE_GPU=True uv run pytest
```

### 3.2 デバイス検証テストの実行

デバイス判定およびフォールバック処理のテストを個別実行します：

```bash
uv run pytest tests/test_device_verification.py tests/test_gpu_fallback.py -v
```

### 3.3 GPU 高負荷・並行変換ストレステスト

複数リクエストが同時にポスティングされた際の GPU / CPU 並行制御およびセマフォ動作を確認します：

```bash
# 高負荷テストスクリプトの実行
uv run python -c "
import asyncio, time
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from docling_lib.server import create_app

async def main():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test', timeout=180.0) as client:
        test_pdf = Path('tests/data/real_world/sample1_simple.pdf')
        tasks = [
            client.post('/convert/', files={'file': (f'test_{i}.pdf', open(test_pdf, 'rb'), 'application/pdf')})
            for i in range(4)
        ]
        results = await asyncio.gather(*tasks)
        print([r.status_code for r in results])

asyncio.run(main())
"
```

---

## 🔍 4. トラブルシューティング

- **`UserWarning: NVIDIA GeForce GTX 1060 ... is not compatible` が表示される場合**:
  - PyTorch のバージョンが該当 GPU アーキテクチャをサポートしていません。ライブラリは自動的に CPU にフォールバックするため、処理は正常に完了します。
- **CUDA Out of Memory (OOM) が発生する場合**:
  - `DOCLING_MAX_WORKERS` の値を減らす（例: `DOCLING_MAX_WORKERS=1`）か、`DOCLING_USE_GPU=False` に設定して CPU モードで運用してください。
