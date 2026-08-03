from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values, load_dotenv
from pydantic import BaseModel, Field


class AccountConfig(BaseModel):
    name: str
    author: str
    default_digest: str


class ModelConfig(BaseModel):
    model: str
    base_url: str | None = None
    base_url_env: str = "OPENAI_BASE_URL"
    api_key_env: str = "OPENAI_API_KEY"
    supports_vision: bool = False
    temperature: float = 0.3
    max_retries: int = 3

    @property
    def resolved_base_url(self) -> str | None:
        return os.getenv(self.base_url_env) or self.base_url

    @property
    def api_key(self) -> str | None:
        return os.getenv(self.api_key_env)


class ContentConfig(BaseModel):
    topic_file: Path
    style_guide: Path
    prompt_dir: Path
    output_dir: Path


class DiscoveryConfig(BaseModel):
    sources_file: Path = Path("config/sources.yaml")


class AgentConfig(BaseModel):
    max_steps: int = 24
    max_revisions: int = 2
    stage_timeout_seconds: float = 180
    draft_only: bool = True


class ImageProviderConfig(BaseModel):
    provider: str = "disabled"
    model: str | None = None
    endpoint: str | None = None
    endpoint_env: str = "IMAGE_API_BASE_URL"
    api_key_env: str = "IMAGE_API_KEY"
    timeout_seconds: float = 90

    @property
    def resolved_endpoint(self) -> str | None:
        return os.getenv(self.endpoint_env) or self.endpoint

    @property
    def api_key(self) -> str | None:
        return os.getenv(self.api_key_env)


class RenderConfig(BaseModel):
    theme_file: Path = Path("config/themes/professional-minimal.yaml")
    generated_assets_dir: Path = Path("assets/generated")
    image: ImageProviderConfig = Field(default_factory=ImageProviderConfig)


class QualityConfig(BaseModel):
    require_sources: bool = True
    require_verification_for_claims: bool = True
    editorial_min_score: float = Field(default=8.0, ge=0, le=10)
    visual_min_score: float = Field(default=8.0, ge=0, le=10)
    forbidden_terms: list[str] = Field(default_factory=list)
    internal_patterns: list[str] = Field(default_factory=list)


class PublishConfig(BaseModel):
    mode: str = "draft_only"
    dry_run: bool = True
    require_human_approval: bool = True
    auto_publish_after_approval: bool = False
    app_id_env: str = "WECHAT_APP_ID"
    app_secret_env: str = "WECHAT_APP_SECRET"

    @property
    def app_id(self) -> str | None:
        return os.getenv(self.app_id_env)

    @property
    def app_secret(self) -> str | None:
        return os.getenv(self.app_secret_env)


class AppConfig(BaseModel):
    account: AccountConfig
    model: ModelConfig
    content: ContentConfig
    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    render: RenderConfig = Field(default_factory=RenderConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    publish: PublishConfig = Field(default_factory=PublishConfig)


class RSSSourceConfig(BaseModel):
    name: str
    url: str
    enabled: bool = True


class GitHubSourceConfig(BaseModel):
    name: str
    repo: str
    enabled: bool = True


class SourcesConfig(BaseModel):
    max_items_per_source: int = 8
    lookback_days: int = 45
    timeout_seconds: float = 20
    github_token_env: str = "GITHUB_TOKEN"
    include_keywords: list[str] = Field(default_factory=list)
    rss: list[RSSSourceConfig] = Field(default_factory=list)
    github: list[GitHubSourceConfig] = Field(default_factory=list)

    @property
    def github_token(self) -> str | None:
        return os.getenv(self.github_token_env)


def _resolve_paths(data: dict[str, Any], root: Path) -> dict[str, Any]:
    content = data.get("content", {})
    for key in ("topic_file", "style_guide", "prompt_dir", "output_dir"):
        value = content.get(key)
        if value and not Path(value).is_absolute():
            content[key] = root / value
    discovery = data.get("discovery", {})
    sources_file = discovery.get("sources_file")
    if sources_file and not Path(sources_file).is_absolute():
        discovery["sources_file"] = root / sources_file
    render = data.setdefault("render", {})
    render.setdefault("theme_file", root / "config/themes/professional-minimal.yaml")
    render.setdefault("generated_assets_dir", root / "assets/generated")
    for key in ("theme_file", "generated_assets_dir"):
        value = render.get(key)
        if value and not Path(value).is_absolute():
            render[key] = root / value
    return data


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path).resolve()
    env_path = config_path.parent.parent / ".env"
    load_dotenv(env_path, override=False)
    for key, value in dotenv_values(env_path).items():
        if value and not os.getenv(key):
            os.environ[key] = value
    with config_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return AppConfig.model_validate(_resolve_paths(data, config_path.parent.parent))


def load_sources_config(path: str | Path) -> SourcesConfig:
    with Path(path).open(encoding="utf-8") as handle:
        return SourcesConfig.model_validate(yaml.safe_load(handle) or {})

