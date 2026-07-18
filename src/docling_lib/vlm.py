import base64
import io
import logging

import httpx
from PIL import Image

from .utils import sanitize_log_message

logger = logging.getLogger(__name__)


async def generate_caption(
    image: Image.Image,
    model: str = "qwen2-vl:2b",
    endpoint: str = "http://localhost:11434",
    prompt: str = "この画像の詳細な説明文を日本語で作成してください。",
) -> str:
    """
    Asynchronously generates a description/caption for the given image
    using the Ollama /api/chat vision API.
    """
    try:
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    except Exception as e:
        logger.warning(
            f"Failed to encode image to base64 for VLM: {sanitize_log_message(e)}"
        )
        return ""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{endpoint.rstrip('/')}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                            "images": [img_base64],
                        }
                    ],
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content", "")
            return content.strip()
    except Exception as e:
        logger.warning(f"VLM caption generation failed: {sanitize_log_message(e)}")
        return ""


def generate_caption_sync(
    image: Image.Image,
    model: str = "qwen2-vl:2b",
    endpoint: str = "http://localhost:11434",
    prompt: str = "この画像の詳細な説明文を日本語で作成してください。",
) -> str:
    """
    Synchronously generates a description/caption for the given image
    using the Ollama /api/chat vision API.
    """
    try:
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    except Exception as e:
        logger.warning(
            f"Failed to encode image to base64 for VLM: {sanitize_log_message(e)}"
        )
        return ""

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{endpoint.rstrip('/')}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                            "images": [img_base64],
                        }
                    ],
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content", "")
            return content.strip()
    except Exception as e:
        logger.warning(f"VLM caption generation failed: {sanitize_log_message(e)}")
        return ""
