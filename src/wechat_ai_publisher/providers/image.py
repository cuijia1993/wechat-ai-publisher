from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Callable, Protocol
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageOps

from wechat_ai_publisher.config import ImageProviderConfig


class ImageProvider(Protocol):
    name: str
    model: str | None
    last_source_url: str | None

    def generate(
        self,
        *,
        prompt: str,
        output: Path,
        width: int,
        height: int,
    ) -> Path | None: ...


class DisabledImageProvider:
    name = "disabled"
    model = None
    last_source_url = None

    def generate(
        self,
        *,
        prompt: str,
        output: Path,
        width: int,
        height: int,
    ) -> Path | None:
        return None


class CallableImageProvider:
    """用于插件适配和测试；生产环境可用同一协议包装任意静态生图服务。"""

    def __init__(
        self,
        callback: Callable[[str, Path, int, int], Path | None],
        *,
        name: str,
        model: str | None = None,
    ):
        self.callback = callback
        self.name = name
        self.model = model
        self.last_source_url: str | None = None

    def generate(
        self,
        *,
        prompt: str,
        output: Path,
        width: int,
        height: int,
    ) -> Path | None:
        return self.callback(prompt, output, width, height)


class DashScopeImageProvider:
    name = "dashscope_native"

    def __init__(
        self,
        config: ImageProviderConfig,
        *,
        client: httpx.Client | None = None,
    ):
        if not config.model:
            raise ValueError("DashScope 文生图缺少 model 配置")
        if not config.resolved_endpoint:
            raise ValueError("DashScope 文生图缺少 endpoint 配置")
        if not config.api_key:
            raise ValueError(f"DashScope 文生图缺少密钥环境变量：{config.api_key_env}")
        self.model = config.model
        self.endpoint = config.resolved_endpoint
        self.api_key = config.api_key
        self.client = client or httpx.Client(
            timeout=config.timeout_seconds,
            follow_redirects=True,
        )
        self.last_source_url: str | None = None

    @staticmethod
    def _validate_download_url(url: str) -> None:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not (
            hostname == "aliyuncs.com" or hostname.endswith(".aliyuncs.com")
        ):
            raise ValueError("文生图响应包含非阿里云 HTTPS 资源地址")

    def generate(
        self,
        *,
        prompt: str,
        output: Path,
        width: int,
        height: int,
    ) -> Path | None:
        response = self.client.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": [{"text": prompt}],
                        }
                    ]
                },
                "parameters": {
                    "size": f"{width}*{height}",
                    "n": 1,
                    "prompt_extend": True,
                    "watermark": False,
                    "negative_prompt": "人物肖像，品牌商标，水印，模糊文字，低清晰度，复杂装饰",
                },
            },
        )
        response.raise_for_status()
        payload = response.json()
        try:
            image_url = payload["output"]["choices"][0]["message"]["content"][0]["image"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("DashScope 文生图响应缺少图片地址") from exc
        self._validate_download_url(image_url)

        image_response = self.client.get(image_url)
        image_response.raise_for_status()
        with Image.open(BytesIO(image_response.content)) as generated:
            generated.load()
            normalized = generated.convert("RGB")
            if normalized.size != (width, height):
                normalized = ImageOps.fit(
                    normalized,
                    (width, height),
                    method=Image.Resampling.LANCZOS,
                )
            output.parent.mkdir(parents=True, exist_ok=True)
            temporary = output.with_suffix(output.suffix + ".tmp")
            normalized.save(temporary, format="PNG", optimize=True)
            temporary.replace(output)
        self.last_source_url = image_url
        return output


def build_image_provider(config: ImageProviderConfig) -> ImageProvider:
    if config.provider == "disabled":
        return DisabledImageProvider()
    if config.provider == "dashscope_native":
        if not config.api_key or not config.resolved_endpoint or not config.model:
            return DisabledImageProvider()
        return DashScopeImageProvider(config)
    raise ValueError(f"不支持的静态生图 Provider：{config.provider}")

