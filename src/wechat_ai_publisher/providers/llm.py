from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Protocol, TypeVar

from openai import OpenAI
from pydantic import BaseModel

from wechat_ai_publisher.config import ModelConfig

T = TypeVar("T", bound=BaseModel)


class LLMProvider(Protocol):
    def structured(self, *, system: str, user: str, response_model: type[T]) -> T: ...

    def structured_with_images(
        self,
        *,
        system: str,
        user: str,
        image_paths: list[Path],
        response_model: type[T],
    ) -> T: ...


def _extract_json(text: str) -> dict:
    value = text.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        value = "\n".join(lines[1:-1])
    return json.loads(value)


class OpenAICompatibleProvider:
    def __init__(self, config: ModelConfig, *, timeout_seconds: float | None = None):
        if not config.api_key:
            raise ValueError(f"缺少模型密钥环境变量：{config.api_key_env}")
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.resolved_base_url,
            max_retries=config.max_retries,
            timeout=timeout_seconds,
        )

    def structured(self, *, system: str, user: str, response_model: type[T]) -> T:
        schema = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
        completion = self.client.chat.completions.create(
            model=self.config.resolved_model,
            temperature=self.config.temperature,
            messages=[
                {
                    "role": "system",
                    "content": f"{system}\n只返回符合以下 JSON Schema 的 JSON：\n{schema}",
                },
                {"role": "user", "content": user},
            ],
        )
        content = completion.choices[0].message.content
        if not content:
            raise RuntimeError("模型返回了空内容")
        return response_model.model_validate(_extract_json(content))

    def structured_with_images(
        self,
        *,
        system: str,
        user: str,
        image_paths: list[Path],
        response_model: type[T],
    ) -> T:
        schema = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
        user_content: list[dict] = [{"type": "text", "text": user}]
        for path in image_paths:
            mime = mimetypes.guess_type(path.name)[0] or "image/png"
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime};base64,{encoded}",
                        "detail": "high",
                    },
                }
            )
        completion = self.client.chat.completions.create(
            model=self.config.resolved_model,
            temperature=self.config.temperature,
            messages=[
                {
                    "role": "system",
                    "content": f"{system}\n只返回符合以下 JSON Schema 的 JSON：\n{schema}",
                },
                {"role": "user", "content": user_content},
            ],
        )
        content = completion.choices[0].message.content
        if not content:
            raise RuntimeError("视觉审查模型返回了空内容")
        return response_model.model_validate(_extract_json(content))

