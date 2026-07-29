from pathlib import Path

import pytest

from wechat_ai_publisher.config import load_config
from wechat_ai_publisher.domain.models import Article, Topic
from wechat_ai_publisher.pipeline.orchestrator import ContentPipeline
from wechat_ai_publisher.providers.demo import DemoProvider
from wechat_ai_publisher.rendering.formatter import WechatFormatter
from wechat_ai_publisher.wechat.publisher import DraftPublisher


ROOT = Path(__file__).resolve().parents[1]


def test_demo_pipeline_and_dry_run_end_to_end(tmp_path):
    config = load_config(ROOT / "config" / "account.example.yaml")
    config.content.output_dir = tmp_path
    topic = Topic(
        id="verified-demo",
        title="AI 辅助 Java 开发验证",
        primary_search_keyword="AI 工具",
        category="真实开发案例",
        target_reader="Java 工程师",
        reader_problem="生成结果缺少验证",
        core_conclusion="先验证，再采用",
        required_evidence=["本地检查记录"],
        verification_records=["测试夹具提供可复现检查记录"],
        status="selected",
    )

    manifest = ContentPipeline(config, DemoProvider()).run(topic)

    assert manifest.status == "ready_to_render"
    article = Article.model_validate_json(Path(manifest.outputs["edited"]).read_text(encoding="utf-8"))
    result = DraftPublisher(WechatFormatter(ROOT / "templates" / "article.html")).publish(
        article,
        output_dir=tmp_path / manifest.job_id,
        dry_run=True,
        approved=False,
        require_approval=True,
    )
    assert result["dry_run"] is True
    assert Path(str(result["preview"])).is_file()

    with pytest.raises(PermissionError, match="演示模型"):
        DraftPublisher(WechatFormatter(ROOT / "templates" / "article.html")).publish(
            article,
            output_dir=tmp_path / "real-publish",
            dry_run=False,
            approved=True,
            require_approval=False,
        )


def test_pipeline_stops_when_evidence_is_missing(tmp_path):
    config = load_config(ROOT / "config" / "account.example.yaml")
    config.content.output_dir = tmp_path
    topic = Topic(
        id="missing-evidence",
        title="缺少证据",
        category="案例",
        target_reader="Java 工程师",
        reader_problem="没有验证记录",
        core_conclusion="不能继续写作",
        required_evidence=["实际运行记录"],
    )

    manifest = ContentPipeline(config, DemoProvider()).run(topic)

    assert manifest.status == "evidence_required"
    assert "outline" not in manifest.outputs

