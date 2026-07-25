import asyncio
import atexit
import base64
import io
import logging
import threading
import weakref

import httpx
from PIL import Image

from .utils import sanitize_log_message

logger = logging.getLogger(__name__)

# Cache of threading semaphores based on (provider, endpoint, max_concurrent)
_semaphores_lock = threading.Lock()
_semaphores = {}

# Reusable HTTP clients to implement connection pooling and keep-alive.
# Store the original class references to detect when they are mocked during testing.
_ORIG_CLIENT_CLASS = httpx.Client
_ORIG_ASYNC_CLIENT_CLASS = httpx.AsyncClient

_sync_client_cache = None
_sync_client_lock = threading.Lock()

# Map running event loop to its cached AsyncClient
_async_client_cache = weakref.WeakKeyDictionary()
_async_client_lock = threading.Lock()

# Default API request timeout (seconds)
_DEFAULT_TIMEOUT = 300.0





def _cleanup_cached_clients():
    """アプリケーション終了時にキャッシュされたhttpxクライアントを安全に閉じる。"""
    global _sync_client_cache
    with _sync_client_lock:
        if _sync_client_cache is not None and not getattr(_sync_client_cache, "is_closed", True):
            _sync_client_cache.close()
            _sync_client_cache = None


atexit.register(_cleanup_cached_clients)



class _UnclosedClientContext:
    """
    Context wrapper for a shared synchronous Client that prevents context managers
    from closing the shared client instance, but forwards all other attributes.
    """
    def __init__(self, client: httpx.Client):
        self._client = client

    def __enter__(self) -> httpx.Client:
        return self._client

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Prevent the shared client from being closed on context exit
        pass

    def __getattr__(self, name):
        return getattr(self._client, name)


class _UnclosedAsyncClientContext:
    """
    Context wrapper for a shared asynchronous AsyncClient that prevents context managers
    from closing the shared client instance, but forwards all other attributes.
    """
    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    async def __aenter__(self) -> httpx.AsyncClient:
        return self._client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Prevent the shared client from being closed on context exit
        pass

    def __getattr__(self, name):
        return getattr(self._client, name)


def _get_cached_sync_client() -> httpx.Client:
    """
    Returns a cached, shared synchronous httpx.Client with connection pooling enabled.
    If httpx.Client is mocked in the current scope, caching is bypassed to respect the mock.
    """
    global _sync_client_cache
    if httpx.Client is not _ORIG_CLIENT_CLASS:
        # Bypassing cache since httpx.Client is mocked/patched
        return httpx.Client(timeout=_DEFAULT_TIMEOUT)

    # Optimistic lock-free read path
    client = _sync_client_cache
    if client is not None and not getattr(client, "is_closed", False):
        return client

    with _sync_client_lock:
        if _sync_client_cache is None or getattr(_sync_client_cache, "is_closed", False):
            _sync_client_cache = _ORIG_CLIENT_CLASS(timeout=_DEFAULT_TIMEOUT)
        return _sync_client_cache


def _get_cached_async_client() -> httpx.AsyncClient:
    """
    Returns a cached, shared asynchronous httpx.AsyncClient associated with the current running event loop.
    If httpx.AsyncClient is mocked in the current scope, caching is bypassed to respect the mock.
    """
    if httpx.AsyncClient is not _ORIG_ASYNC_CLIENT_CLASS:
        # Bypassing cache since httpx.AsyncClient is mocked/patched
        return httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Bypassing cache if no event loop is running (fallback to non-cached client)
        return _ORIG_ASYNC_CLIENT_CLASS(timeout=_DEFAULT_TIMEOUT)

    with _async_client_lock:
        client = _async_client_cache.get(loop)
        if client is None or getattr(client, "is_closed", False):
            client = _ORIG_ASYNC_CLIENT_CLASS(timeout=_DEFAULT_TIMEOUT)
            _async_client_cache[loop] = client
        return client


def get_semaphore(
    max_concurrent: int, provider: str = "ollama", endpoint: str = ""
) -> threading.Semaphore:
    """
    Retrieves or creates a thread-safe Semaphore to enforce VLM rate limiting,
    isolated per provider, endpoint, and concurrency limit.
    """
    with _semaphores_lock:
        key = (
            provider.strip().lower() if provider else "ollama",
            endpoint.strip().lower() if endpoint else "",
            max_concurrent,
        )
        if key not in _semaphores:
            _semaphores[key] = threading.Semaphore(max_concurrent)
        return _semaphores[key]


def _encode_image_to_base64(image: Image.Image) -> str:
    """
    Helper to encode a PIL image into a Base64-encoded PNG string.
    """
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def _prepare_rest_payload(
    provider: str,
    model: str,
    prompt: str,
    img_base64: str | None,
    text_content: str | None,
    api_key: str,
    endpoint: str,
) -> tuple[str, dict, dict]:
    """
    Prepares the request URL, headers, and JSON body for the chosen VLM/LLM provider.
    Returns: (url, headers, json_body)
    """
    provider_lower = provider.strip().lower()
    headers = {"Content-Type": "application/json"}
    full_prompt = prompt
    if text_content:
        full_prompt = f"{prompt}\n\n[Content]\n{text_content}"

    # 1. OpenAI / OpenAI-compatible (vLLM, llama.cpp, etc.)
    if provider_lower in ("openai", "vllm", "llama.cpp"):
        url = f"{endpoint.rstrip('/')}/chat/completions"
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        if img_base64:
            content_list = [
                {"type": "text", "text": full_prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img_base64}"},
                },
            ]
        else:
            content_list = [{"type": "text", "text": full_prompt}]

        json_body = {
            "model": model,
            "messages": [{"role": "user", "content": content_list}],
            "stream": False,
        }

    # 2. Anthropic Claude
    elif provider_lower == "anthropic":
        url = f"{endpoint.rstrip('/')}/v1/messages"
        headers.update(
            {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
        )

        if img_base64:
            content_list = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": img_base64,
                    },
                },
                {"type": "text", "text": full_prompt},
            ]
        else:
            content_list = [{"type": "text", "text": full_prompt}]

        json_body = {
            "model": model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": content_list}],
        }

    # 3. Google Gemini
    elif provider_lower in ("google", "gemini"):
        # Default endpoint for Google is usually https://generativelanguage.googleapis.com
        url = f"{endpoint.rstrip('/')}/v1beta/models/{model}:generateContent?key={api_key}"

        if img_base64:
            parts = [
                {"text": full_prompt},
                {
                    "inlineData": {
                        "mimeType": "image/png",
                        "data": img_base64,
                    }
                },
            ]
        else:
            parts = [{"text": full_prompt}]

        json_body = {"contents": [{"parts": parts}]}

    # 4. Default: Ollama (Existing)
    else:
        url = f"{endpoint.rstrip('/')}/api/chat"
        if img_base64:
            message_content = {
                "role": "user",
                "content": full_prompt,
                "images": [img_base64],
            }
        else:
            message_content = {
                "role": "user",
                "content": full_prompt,
            }

        json_body = {
            "model": model,
            "messages": [message_content],
            "stream": False,
        }

    return url, headers, json_body


def _extract_response_content(provider: str, data: dict) -> str:
    """
    Extracts the text content from the provider's standard JSON response.
    """
    provider_lower = provider.strip().lower()

    try:
        if provider_lower in ("openai", "vllm", "llama.cpp"):
            return data["choices"][0]["message"]["content"]
        elif provider_lower == "anthropic":
            return data["content"][0]["text"]
        elif provider_lower in ("google", "gemini"):
            return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            # Ollama
            return data.get("message", {}).get("content", "")
    except (KeyError, IndexError, TypeError) as e:
        logger.warning(
            f"Failed to parse response content from VLM provider {provider_lower}: "
            f"{sanitize_log_message(e)}"
        )
        return ""


async def generate_caption(
    image: Image.Image | None = None,
    provider: str = "ollama",
    api_key: str = "",
    model: str = "qwen2-vl:2b",
    endpoint: str = "http://localhost:11434",
    prompt: str = "この画像の詳細な説明文を日本語で作成してください。",
    text_content: str | None = None,
    vlm_max_concurrent: int = 5,
) -> str:
    """
    Asynchronously generates a description/caption/summary for an image or structured text
    using the selected VLM/LLM REST provider with dynamic rate-limiting control.
    """
    # Force defaults if parameters are None/empty to match backward-compatible tests
    if not provider:
        provider = "ollama"
    provider_lower = provider.strip().lower()

    if not model:
        model = "qwen2-vl:2b"

    # Automatically adjust default endpoints for other cloud providers
    if not endpoint or (endpoint == "http://localhost:11434" and provider_lower != "ollama"):
        if provider_lower == "ollama":
            endpoint = "http://localhost:11434"
        elif provider_lower in ("openai", "vllm", "llama.cpp"):
            endpoint = "https://api.openai.com/v1"
        elif provider_lower == "anthropic":
            endpoint = "https://api.anthropic.com"
        elif provider_lower in ("google", "gemini"):
            endpoint = "https://generativelanguage.googleapis.com"

    if not prompt:
        prompt = "この画像の詳細な説明文を日本語で作成してください。"

    # Encode image if provided
    img_base64 = None
    if image is not None:
        try:
            img_base64 = _encode_image_to_base64(image)
        except Exception as e:
            logger.warning(
                f"Failed to encode image to base64 for VLM: {sanitize_log_message(e)}"
            )
            return ""

    url, headers, json_body = _prepare_rest_payload(
        provider=provider,
        model=model,
        prompt=prompt,
        img_base64=img_base64,
        text_content=text_content,
        api_key=api_key,
        endpoint=endpoint,
    )

    # Use semaphore for rate limiting, isolated per provider & endpoint
    sem = get_semaphore(vlm_max_concurrent, provider=provider, endpoint=endpoint)
    acquired = False
    try:
        # Acquire semaphore asynchronously using to_thread to prevent event-loop blocking
        await asyncio.to_thread(sem.acquire)
        acquired = True

        # Use helper to get a cached client, or a fresh mocked client if patched.
        raw_client = _get_cached_async_client()
        # If it is the original unmocked client class, wrap it to avoid closing it on context block exit.
        if httpx.AsyncClient is _ORIG_ASYNC_CLIENT_CLASS:
            client_ctx = _UnclosedAsyncClientContext(raw_client)
        else:
            client_ctx = raw_client

        # Optimized: Using cached AsyncClient via connection pooling instead of instantiating on every call
        async with client_ctx as client:
            response = await client.post(url, headers=headers, json=json_body)
            response.raise_for_status()
            data = response.json()
            content = _extract_response_content(provider, data)
            return content.strip()
    except Exception as e:
        logger.warning(
            f"VLM/LLM caption generation failed for {provider}: {sanitize_log_message(e)}"
        )
        return ""
    finally:
        if acquired:
            sem.release()


def generate_caption_sync(
    image: Image.Image | None = None,
    provider: str = "ollama",
    api_key: str = "",
    model: str = "qwen2-vl:2b",
    endpoint: str = "http://localhost:11434",
    prompt: str = "この画像の詳細な説明文を日本語で作成してください。",
    text_content: str | None = None,
    vlm_max_concurrent: int = 5,
) -> str:
    """
    Synchronously generates a description/caption/summary for an image or structured text
    using the selected VLM/LLM REST provider with dynamic rate-limiting control.
    """
    # Force defaults if parameters are None/empty to match backward-compatible tests
    if not provider:
        provider = "ollama"
    provider_lower = provider.strip().lower()

    if not model:
        model = "qwen2-vl:2b"

    # Automatically adjust default endpoints for other cloud providers
    if not endpoint or (endpoint == "http://localhost:11434" and provider_lower != "ollama"):
        if provider_lower == "ollama":
            endpoint = "http://localhost:11434"
        elif provider_lower in ("openai", "vllm", "llama.cpp"):
            endpoint = "https://api.openai.com/v1"
        elif provider_lower == "anthropic":
            endpoint = "https://api.anthropic.com"
        elif provider_lower in ("google", "gemini"):
            endpoint = "https://generativelanguage.googleapis.com"

    if not prompt:
        prompt = "この画像の詳細な説明文を日本語で作成してください。"

    # Encode image if provided
    img_base64 = None
    if image is not None:
        try:
            img_base64 = _encode_image_to_base64(image)
        except Exception as e:
            logger.warning(
                f"Failed to encode image to base64 for VLM: {sanitize_log_message(e)}"
            )
            return ""

    url, headers, json_body = _prepare_rest_payload(
        provider=provider,
        model=model,
        prompt=prompt,
        img_base64=img_base64,
        text_content=text_content,
        api_key=api_key,
        endpoint=endpoint,
    )

    # Use semaphore for rate limiting, isolated per provider & endpoint
    sem = get_semaphore(vlm_max_concurrent, provider=provider, endpoint=endpoint)
    acquired = False
    try:
        sem.acquire()
        acquired = True

        # Use helper to get a cached client, or a fresh mocked client if patched.
        raw_client = _get_cached_sync_client()
        # If it is the original unmocked client class, wrap it to avoid closing it on context block exit.
        if httpx.Client is _ORIG_CLIENT_CLASS:
            client_ctx = _UnclosedClientContext(raw_client)
        else:
            client_ctx = raw_client

        # Optimized: Using cached Client via connection pooling instead of instantiating on every call
        with client_ctx as client:
            response = client.post(url, headers=headers, json=json_body)
            response.raise_for_status()
            data = response.json()
            content = _extract_response_content(provider, data)
            return content.strip()
    except Exception as e:
        logger.warning(
            f"VLM/LLM caption generation failed for {provider}: {sanitize_log_message(e)}"
        )
        return ""
    finally:
        if acquired:
            sem.release()
