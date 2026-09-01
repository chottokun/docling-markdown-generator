# テストと品質保証ガイド (Testing & QA Guide)

本プロジェクトでは、コードの堅牢性と後方互換性を保証するため、TDD（テスト駆動開発）をベースとした多層的なテストスイートおよび検証スクリプトを運用しています。

---

## 📌 目次
1. [テスト構成の概要](#1-テスト構成の概要)
2. [単体・モジュールテスト（高速）](#2-単体モジュールテスト高速)
3. [カバレッジ計測と静的解析](#3-カバレッジ計測と静的解析)
4. [実データ E2E 検証](#4-実データ-e2e-検証)
5. [Docker コンテナ環境での E2E 検証](#5-docker-コンテナ環境での-e2e-検証)
6. [GPU / ハードウェア自動フォールバック検証](#6-gpu--ハードウェア自動フォールバック検証)
7. [セキュリティ・耐障害性回帰テスト](#7-セキュリティ耐障害性回帰テスト)

---

## 1. テスト構成の概要

| カテゴリ | 対象ファイル・コマンド | 目的 |
| :--- | :--- | :--- |
| **単体/結合テスト** | `uv run pytest` | API、シリアライザー、プール、設定、VLMリトライ等のモジュール検証（モック利用） |
| **静的解析・型検査** | `uv tool run ruff check src` / `uv tool run mypy --ignore-missing-imports src` | コード品質、フォーマット、型安全性の担保 |
| **実データ E2E** | `uv run python tests/e2e_real_api_check.py` | 実ファイル（Word/Excel等）によるFastAPIサーバーのEnd-to-End検証 |
| **Docker E2E** | `uv run python tests/e2e_docker_check.py` | 稼働中の Docker コンテナ（HTTP/8090）に対する実通信・ダウンロード検証 |
| **複雑表検証** | `docker compose run ... verify_excel.py` | 経済産業省技術マトリクス等の極めて複雑なセルの結合のHTML Table変換検証 |

---

## 2. 単体・モジュールテスト（高速）

日常の開発サイクルやCI/CDパイプラインで実行するテストです。外部API通信や重いAIモデルのダウンロードをモック化しているため、短時間で実行できます。

```bash
# 全テストの実行（360+件）
uv run pytest

# 特定のモジュールのみ実行
uv run pytest tests/test_converter.py
uv run pytest tests/test_server.py
uv run pytest tests/test_vlm_retry_critical.py
```

---

## 3. カバレッジ計測と静的解析

### 3.1 テストカバレッジの計測
```bash
uv run pytest --cov=src --cov-report=term-missing
```

### 3.2 リンター & フォーマッター
```bash
# コードチェック
uv tool run ruff check src tests

# コードフォーマットチェック
uv tool run ruff format --check src tests

# 自動フォーマット適用
uv tool run ruff format src tests
```

### 3.3 静的型チェック (Mypy)
```bash
uv tool run mypy --ignore-missing-imports src
```

---

## 4. 実データ E2E 検証

FastAPI サーバーを立ち上げ、実データ（Word / Excel / PDF）を実際にアップロード・変換・ダウンロードし、Prometheus メトリクスが正常にカウントアップされるかを一気通貫で検証します。

```bash
uv run python tests/e2e_real_api_check.py
```

---

## 5. Docker コンテナ環境での E2E 検証

Docker コンテナとしてデプロイされた API サーバー（`http://localhost:8090`）に対して外部からリクエストを送信し、本番コンテナ環境での完全稼働を確認します。

```bash
# 1. コンテナの起動
docker compose up -d --build

# 2. Docker E2E 検証スクリプトの実行
uv run python tests/e2e_docker_check.py
```

### 複雑な Excel マトリクス表の検証 (Docker経由)
経済産業省の技術マトリクスのような大規模・複雑なExcelファイルの結合セル変換精度を検証します：
```bash
docker compose run --user root --entrypoint "python scripts/verify_excel.py" docling-server
```
*変換結果は `./output/gijutsu_matrix/processed_document.md` に出力され、目視でHTML Tableの構造を確認できます。*

---

## 6. GPU / ハードウェア自動フォールバック検証

GPU が利用可能な環境において、CUDA Compute Capability の整合性を確認し、不整合時や非GPU環境で安全にCPUモードにフォールバックすることを確認します。

```bash
# GPU 強制有効化でのテスト実行
DOCLING_USE_GPU=True uv run pytest tests/test_device_verification.py tests/test_gpu_fallback.py
```

---

## 7. セキュリティ・耐障害性回帰テスト

脆弱性や不正入力に対する防御機能を網羅的にテストします：
```bash
# パストラバーサル防止テスト
uv run pytest tests/test_path_traversal.py tests/test_output_security.py

# 認証 & IPレートリミット（スプーフィング耐性）テスト
uv run pytest tests/test_security_auth_rate_limit.py tests/test_rate_limit_ip_source.py

# 大容量アップロード DoS 防御テスト
uv run pytest tests/test_dos_protection.py

# YAMLインジェクション / ログインジェクション防止テスト
uv run pytest tests/test_yaml_injection.py tests/test_utils.py
```
