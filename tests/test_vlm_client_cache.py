import asyncio
import threading
from unittest.mock import MagicMock

import httpx
import pytest

import docling_lib.vlm as vlm
from docling_lib.vlm import (
    _cleanup_cached_clients,
    _get_cached_async_client,
    _get_cached_sync_client,
)


def test_sync_client_cached(monkeypatch):
    """
    検証：_get_cached_sync_client が同一の httpx.Client インスタンスを返し、
    タイムアウト値がデフォルト定数と一致すること。
    """
    # キャッシュをクリアした状態から開始
    monkeypatch.setattr(vlm, "_sync_client_cache", None)

    client1 = _get_cached_sync_client()
    client2 = _get_cached_sync_client()

    assert client1 is client2
    assert client1.timeout.connect == vlm._DEFAULT_TIMEOUT

    # クリーンアップ
    _cleanup_cached_clients()


def test_sync_client_recreated_if_closed(monkeypatch):
    """
    検証：キャッシュされているクライアントがクローズされた場合、
    次の呼び出しで新しいクライアントが再作成されること。
    """
    monkeypatch.setattr(vlm, "_sync_client_cache", None)

    client1 = _get_cached_sync_client()

    # 疑似的にクローズ
    client1.close()

    client2 = _get_cached_sync_client()

    assert client1 is not client2
    assert not client2.is_closed

    # クリーンアップ
    _cleanup_cached_clients()


@pytest.mark.asyncio
async def test_async_client_cached_per_loop(monkeypatch):
    """
    検証：イベントループごとに異なる httpx.AsyncClient がキャッシュされること。
    """
    # 既存のキャッシュを退避してクリア
    monkeypatch.setattr(vlm, "_async_client_cache", weakref_dict_mock := {})

    client1 = _get_cached_async_client()
    # monkeypatch の代わりに直接 dict 操作をするため、weakref.WeakKeyDictionary ではなく普通の dict に差し替える
    monkeypatch.setattr(vlm, "_async_client_cache", weakref_dict_mock)

    client2 = _get_cached_async_client()

    assert client1 is client2

    # 別のスレッドで別のイベントループを動かして検証
    other_client = None

    def run_in_other_loop():
        nonlocal other_client
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            other_client = loop.run_until_complete(
                asyncio.sleep(0.01, result=_get_cached_async_client())
            )
        finally:
            loop.close()

    t = threading.Thread(target=run_in_other_loop)
    t.start()
    t.join()

    assert other_client is not None
    assert client1 is not other_client


def test_client_cache_bypassed_when_mocked(monkeypatch):
    """
    検証：httpx.Client が patch 等でモック化されている場合、
    キャッシュをバイパスしてモックインスタンスを作成すること。
    """
    monkeypatch.setattr(vlm, "_sync_client_cache", None)

    # クラス全体をモック
    mock_client_class = MagicMock(spec=httpx.Client)
    monkeypatch.setattr(httpx, "Client", mock_client_class)

    client1 = _get_cached_sync_client()
    client2 = _get_cached_sync_client()

    # モックされているため、毎回新しくクラスが呼び出されるはず
    assert mock_client_class.call_count == 2
    assert vlm._sync_client_cache is None  # キャッシュには書き込まれない


def test_atexit_cleanup(monkeypatch):
    """
    検証：_cleanup_cached_clients を呼び出した際、
    キャッシュされたクライアントが close され、キャッシュが None に戻ること。
    """
    monkeypatch.setattr(vlm, "_sync_client_cache", None)

    client = _get_cached_sync_client()
    assert vlm._sync_client_cache is client
    assert not client.is_closed

    # クリーンアップ呼び出し
    _cleanup_cached_clients()

    assert vlm._sync_client_cache is None
    assert client.is_closed
