# 分散環境（Kubernetes / Celery）対応 アーキテクチャ設計仕様書

本ドキュメントは、Docling Markdown Conversion Serverを単一ノード構成から **Kubernetes (K8s) および分散メッセージキュー (Celery / ARQ / Redis)** を用いたエンタープライズ対応の分散システムへ拡張するための設計仕様および移行計画を定義します。

---

## 1. 背景と目的

現在のアーキテクチャは、単一ノード内での `ProcessPoolExecutor` (`spawn` コンテキスト) と `psutil` に基づく動的セマフォ制御により、高い安定性とパフォーマンスを実現しています。

しかし、以下のエンタープライズ要件に対応するためには、**APIサーバー（受信用ポッド）と変換ワーカー（処理用ポッド）の完全な分離（ステートレス化）** が不可欠となります。

- **無制限の水平スケール (Horizontal Auto-Scaling)**: 多数の並行リクエスト発生時、ワーカーポッドを即座に自動増設。
- **障害隔離 (Fault Isolation)**: 重厚なドキュメント処理（OOM等）がAPIサーバーの応答性（HTTP 200/500）に影響を与えない設計。
- **インフラコストの最適化**: 受信ポッドは軽量なCPUインスタンス、変換ワーカーポッドはGPU（NVIDIA A10G/T4等）または高メモリインスタンスへ分離配備。

---

## 2. 全体アーキテクチャ図

```
[ Client ]
    │
    ▼ (HTTP POST /convert/async)
[ K8s Ingress / Load Balancer ]
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ K8s API Pods (Stateless Ingress Layer)                   │
│ - 認証 (API Key / OAuth2)                              │
│ - 入力バリデーション & DoS防御 (Content-Size Middleware)  │
│ - 入力ファイルを StorageBackend へ保存                     │
│ - 変換タスクを ConversionQueue へ投入 (202 Accepted)     │
└──────────────┬──────────────────────────────┬───────────┘
               │                              │
               ▼ (Enqueue Task)               ▼ (Upload File)
┌──────────────────────────────┐  ┌──────────────────────────────┐
│ Task Queue / Broker          │  │ Shared Storage Backend       │
│ - Redis / RabbitMQ / Celery  │  │ - Amazon S3 / MinIO / EFS    │
│ - タスク状態（Pending/Done）   │  │ - 入力PDF / 出力Markdown/画像│
└──────────────┬───────────────┘  └──────────────┬───────────────┘
               │                              │
               ▼ (Fetch Task)                 ▼ (Read / Write)
┌─────────────────────────────────────────────────────────┐
│ K8s Worker Pods (GPU / CPU Processing Layer)             │
│ - HPA (Horizontal Pod Autoscaler): Queue長ベースでスケール  │
│ - Docling 変換パイプライン実行                             │
│ - VLM キャプション生成 / GPU 加速                          │
│ - 結果ファイルを StorageBackend へ書き込み               │
└─────────────────────────────────────────────────────────┘
```

---

## 3. コア抽象化インターフェース設計

非破壊的かつ段階的に移行できるよう、現行の直接的なローカルディスク/マルチプロセス呼び出しを抽象インターフェース経由にリファクタリングします。

### 3.1 タスクキュー抽象化 (`ConversionQueueInterface`)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class JobStatus:
    job_id: str
    status: str  # "queued", "processing", "completed", "failed"
    result_path: Optional[str] = None
    error_message: Optional[str] = None
    progress_percentage: float = 0.0

class ConversionQueueInterface(ABC):
    """タスクキュー（ローカルマルチプロセス / Redis / Celery / ARQ）の抽象インターフェース"""

    @abstractmethod
    async def enqueue_job(self, input_file_key: str, options: Dict[str, Any]) -> str:
        """タスクをキューに登録し、ユニークな job_id を返す"""
        pass

    @abstractmethod
    async def get_job_status(self, job_id: str) -> JobStatus:
        """指定された job_id の進行ステータスを取得する"""
        pass

    @abstractmethod
    async def cancel_job(self, job_id: str) -> bool:
        """処理中または待機中のタスクをキャンセルする"""
        pass
```

#### 実装クラス
1. `LocalProcessPoolQueue` (現行デフォルト): 単一ノード内の `ProcessPoolExecutor` を使用。
2. `CeleryQueue` / `ARQRedisQueue` (分散環境用): Redis/RabbitMQを経由して外部ワーカーポッドへタスクを分散。

---

### 3.2 ストレージ抽象化 (`StorageBackendInterface`)

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Optional

class StorageBackendInterface(ABC):
    """ストレージ（ローカルディスク / S3 / MinIO / EFS）の抽象インターフェース"""

    @abstractmethod
    async def save_file(self, file_obj: BinaryIO, destination_key: str) -> str:
        """ファイルをストレージに保存し、識別キーを返す"""
        pass

    @abstractmethod
    async def fetch_file(self, storage_key: str, local_destination: Path) -> Path:
        """ストレージからファイルをローカル一時パスへ取得する"""
        pass

    @abstractmethod
    async def generate_download_url(self, storage_key: str, expires_in_sec: int = 3600) -> str:
        """署名付きダウンロードURL（S3 Presigned URL等）またはローカルダウンロードパスを生成する"""
        pass

    @abstractmethod
    async def delete_file(self, storage_key: str) -> bool:
        """指定されたファイルを削除する"""
        pass
```

---

## 4. Kubernetes 運用仕様 (Operations & Lifecycle)

### 4.1 ヘルスチェックプローブ (Health Probes)

K8sポッドのライフサイクル管理のため、専用のヘルスチェックエンドポイントを実装します。

```python
@router.get("/healthz")
async def liveness_probe():
    """Liveness Probe: ポッドが生存しているか確認（デッドロック時に再起動）"""
    return {"status": "alive"}

@router.get("/readyz")
async def readiness_probe(
    queue: ConversionQueueInterface = Depends(get_queue),
    storage: StorageBackendInterface = Depends(get_storage),
):
    """Readiness Probe: ポッドがトラフィックを受信可能か確認（Redis/S3接続チェック）"""
    is_queue_ok = await queue.ping()
    is_storage_ok = await storage.ping()

    if is_queue_ok and is_storage_ok:
        return {"status": "ready"}
    raise HTTPException(status_code=503, detail="Service Unhealthy")
```

### 4.2 シグナルハンドリング & グレースフルシャットダウン (Graceful Shutdown)

K8sによるスケールダウンやノード再編成（SIGTERM受信時）において、実行中のタスクを安全に保護します。

- **API Pod**: 新規リクエストの受け付けを停止 (`/readyz` が 503 を返す) し、処理中のHTTPレスポンス完了を待機。
- **Worker Pod**: 現在処理中のドキュメントページ変換が完了するかタイムアウト（例: 30秒）に達するまで待機。未完了のタスクは Broker へ Re-queue (ACKを返さない) して別ワーカーへ引き継ぎ。

### 4.3 K8s マニフェスト構成要件

```yaml
# K8s Deployment Example for Worker Pod (GPU Accelerated)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: docling-worker-gpu
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: docling-worker
        image: docling-lib:v0.1.0
        command: ["celery", "-A", "docling_lib.tasks", "worker", "--loglevel=info"]
        resources:
          limits:
            nvidia.com/gpu: 1
            memory: 8Gi
            cpu: "4"
          requests:
            memory: 4Gi
            cpu: "2"
        env:
        - name: DOCLING_STORAGE_BACKEND
          value: "s3"
        - name: DOCLING_S3_BUCKET
          value: "docling-artifacts"
```

---

## 5. 段階的移行ロードマップ

既存の機能およびCLI/FastAPIの動作を100%維持しながら、段階的に拡張します。

- **Phase 1: インターフェース抽象化の導入（非破壊的）**
  - `ConversionQueueInterface` と `StorageBackendInterface` を定義。
  - デフォルト実装として `LocalProcessPoolQueue` と `LocalStorageBackend` を設定（既存動作と完全互換）。
- **Phase 2: K8sヘルスチェックと非同期ジョブステータスAPI**
  - エンドポイント `/healthz`, `/readyz` の追加。
  - 非同期タスク発行 (`POST /convert/async`) とステータス確認 (`GET /tasks/{job_id}`) の追加。
- **Phase 3: S3 / MinIO および Redis / Celery プラグインの実装**
  - `S3StorageBackend` および `CeleryTaskQueue` の実装。
  - HelmチャートおよびK8sマニフェストテンプレートの提供。

---
*本仕様書は、将来のKubernetesスケールアウト時に破壊的変更を起こさずにスムーズに移行するための設計ガイドラインです。*
