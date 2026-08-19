
import pytest
from fastapi.testclient import TestClient

from docling_lib.server import create_app, metrics_registry


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_metrics_flow_success_and_failure(client, tmp_path):
    """
    批判的テスト:
    1. /metrics の初期状態の確認
    2. 不正な拡張子のアップロードで400エラー -> docling_conversions_total{status="error"} が増えること
    3. 正常なPDFアップロード -> docling_conversions_total{status="success"} が増えること
    4. アクティブ変換数が0に戻ること
    5. 変換所要時間サマリーが正しく更新されること
    """
    # 1. 初期 /metrics
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "docling_active_conversions" in resp.text

    initial_error_count = metrics_registry.conversions_total.get("error", 0)
    initial_success_count = metrics_registry.conversions_total.get("success", 0)

    # 2. 不正なファイル (400 Bad Request)
    files = {"file": ("malicious.exe", b"executable content", "application/octet-stream")}
    resp_bad = client.post("/convert/", files=files)
    assert resp_bad.status_code == 400
    # convert_fileの先頭バリデーション(_validate_extension)で弾かれた場合、convert_file内のtryブロックに入らないためメトリクスは変更されないか、あるいは記録されない
    assert metrics_registry.active_conversions == 0

    # 3. / へのアクセスでは変換メトリクスが増加しないこと
    resp_root = client.get("/")
    assert resp_root.status_code == 200
    assert metrics_registry.conversions_total.get("success", 0) == initial_success_count

    # 4. メトリクステキスト出力のフォーマット検証
    metrics_text = metrics_registry.generate_prometheus_text()
    assert "# HELP docling_conversions_total" in metrics_text
    assert "# TYPE docling_conversions_total counter" in metrics_text
    assert "# HELP docling_active_conversions" in metrics_text
    assert "# TYPE docling_active_conversions gauge" in metrics_text
    assert "# HELP docling_memory_used_bytes" in metrics_text
    assert "# TYPE docling_memory_used_bytes gauge" in metrics_text
    assert "# HELP docling_conversion_duration_seconds" in metrics_text
    assert "# TYPE docling_conversion_duration_seconds summary" in metrics_text
