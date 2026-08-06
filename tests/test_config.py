from pathlib import Path
import os

from wechat_ai_publisher.config import load_config, load_sources_config


ROOT = Path(__file__).resolve().parents[1]


def test_load_config_resolves_project_paths(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    config = load_config(ROOT / "config" / "account.example.yaml")

    assert config.account.name == "智效进化论"
    assert "普通人的工作、钱包、安全、健康与家庭" in config.account.default_digest
    assert config.model.model == "qwen3.7-max-2026-05-17"
    assert config.model.resolved_model == "qwen3.7-max-2026-05-17"
    monkeypatch.setenv("OPENAI_MODEL", "configured-model")
    assert config.model.resolved_model == "configured-model"
    assert config.model.base_url == (
        "https://llm-q5islkwwval2g1sf.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
    )
    assert config.content.topic_file == ROOT / "topics" / "topic-pool.yaml"
    assert config.render.image.provider == "dashscope_native"
    assert config.render.image.model == "qwen-image-2.0-pro-2026-06-22"
    assert config.render.image.resolved_endpoint.endswith(
        "/api/v1/services/aigc/multimodal-generation/generation"
    )
    assert config.publish.mode == "draft_only"
    assert config.publish.auto_publish_after_approval is False
    sources = load_sources_config(config.discovery.sources_file)
    assert {"OpenAI News", "Google AI", "Google Workspace Updates"} <= {
        source.name for source in sources.rss
    }


def test_dotenv_fills_empty_process_environment(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (tmp_path / ".env").write_text("GITHUB_TOKEN=file-token\n", encoding="utf-8")
    config_path = config_dir / "account.yaml"
    config_path.write_text(
        """
account:
  name: 测试
  author: 测试
  default_digest: 测试
model:
  model: demo
content:
  topic_file: topics.yaml
  style_guide: style.md
  prompt_dir: prompts
  output_dir: runtime
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_TOKEN", "")

    load_config(config_path)

    assert os.getenv("GITHUB_TOKEN") == "file-token"

