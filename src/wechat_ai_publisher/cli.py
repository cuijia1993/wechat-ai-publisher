from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from wechat_ai_publisher.agent.runner import ContentOperationsAgent
from wechat_ai_publisher.config import AppConfig, load_config, load_sources_config
from wechat_ai_publisher.discovery.client import DiscoveryClient
from wechat_ai_publisher.domain.models import (
    Article,
    ArticleAssets,
    AssetMetadata,
    DiscoveryBatch,
    GateResult,
    JobManifest,
    SourceSignal,
    VisualPlan,
)
from wechat_ai_publisher.export.draft_writer import DraftWriter
from wechat_ai_publisher.pipeline.orchestrator import ContentPipeline, load_topics, select_topic
from wechat_ai_publisher.providers.demo import DemoProvider
from wechat_ai_publisher.providers.image import DisabledImageProvider, build_image_provider
from wechat_ai_publisher.providers.llm import OpenAICompatibleProvider
from wechat_ai_publisher.quality.gates import QualityGate
from wechat_ai_publisher.rendering.components import render_visual_blocks
from wechat_ai_publisher.rendering.formatter import WechatFormatter
from wechat_ai_publisher.rendering.template_images import TemplateImageRenderer
from wechat_ai_publisher.rendering.theme import load_theme
from wechat_ai_publisher.wechat.analytics import (
    ArticleAnalytics,
    ArticleAnalyticsStore,
    parse_publish_date,
    recent_publish_dates,
)
from wechat_ai_publisher.wechat.client import WechatAPIError, WechatClient
from wechat_ai_publisher.wechat.publisher import DraftPublisher

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "account.yaml"
EXAMPLE_CONFIG = ROOT / "config" / "account.example.yaml"


def _config(path: str | None) -> AppConfig:
    return load_config(Path(path) if path else (DEFAULT_CONFIG if DEFAULT_CONFIG.exists() else EXAMPLE_CONFIG))


def _formatter(config: AppConfig) -> WechatFormatter:
    return WechatFormatter(
        ROOT / "templates" / "article.html",
        load_theme(config.render.theme_file),
    )


def _article_from_markdown(path: Path, config: AppConfig, topic_id: str) -> Article:
    markdown = path.read_text(encoding="utf-8")
    title_match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
    if not title_match:
        raise ValueError("Markdown 缺少一级标题")
    paragraphs = [
        line.strip()
        for line in markdown.splitlines()
        if line.strip() and not line.startswith(("#", "```", "-", "*", ">"))
    ]
    digest = paragraphs[0][:120] if paragraphs else config.account.default_digest
    return Article(
        topic_id=topic_id,
        title=title_match.group(1).strip(),
        digest=digest,
        markdown=markdown,
        author=config.account.author,
    )


def _extract_action_checklist(markdown: str) -> tuple[str, list[str]] | None:
    groups: list[tuple[str, list[str]]] = []
    heading = ""
    group_anchor = ""
    group_items: list[str] = []

    def flush() -> None:
        nonlocal group_anchor, group_items
        if len(group_items) >= 3 and group_anchor:
            groups.append((group_anchor, group_items))
        group_anchor = ""
        group_items = []

    for line in markdown.splitlines():
        heading_match = re.match(r"^#{2,3}\s+(.+)$", line)
        if heading_match:
            flush()
            heading = heading_match.group(1).strip()
            continue

        item_match = re.match(r"^\s*\d+\.\s+(.+)$", line)
        if item_match:
            if not group_items:
                group_anchor = heading
            item = item_match.group(1).strip()
            item = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", item)
            item = item.replace("**", "").replace("__", "")
            group_items.append(item)
        elif line.strip():
            flush()

    flush()
    return max(groups, key=lambda group: len(group[1]), default=None)


def _job(config: AppConfig, job_id: str) -> tuple[Path, JobManifest]:
    directory = config.content.output_dir / job_id
    path = directory / "manifest.json"
    if not path.exists():
        raise ValueError(f"找不到任务：{job_id}")
    return directory, JobManifest.model_validate_json(path.read_text(encoding="utf-8"))


def _resolve_job_path(config: AppConfig, directory: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    project_root = config.content.topic_file.parent.parent
    candidates = (project_root / path, directory / path)
    return next((candidate for candidate in candidates if candidate.exists()), candidates[0])


def _load_publish_assets(
    config: AppConfig,
    directory: Path,
    manifest: JobManifest,
    formatter: WechatFormatter,
) -> ArticleAssets | None:
    value = manifest.outputs.get("visual_manifest")
    if not value:
        return None
    path = _resolve_job_path(config, directory, value)
    if not path.is_file():
        raise ValueError("任务视觉清单不存在")
    assets = ArticleAssets.model_validate_json(path.read_text(encoding="utf-8"))
    project_root = config.content.topic_file.parent.parent

    def resolve_local(value: str) -> Path:
        local = Path(value)
        if local.is_absolute():
            return local
        candidates = (path.parent / local, project_root / local)
        return next((candidate for candidate in candidates if candidate.exists()), candidates[0])

    for anchor, block in list(assets.html_blocks.items()):
        for image in formatter.local_images(block):
            block = formatter.replace_image(block, str(image), str(resolve_local(str(image))))
        assets.html_blocks[anchor] = block
    for metadata in ([assets.cover] if assets.cover else []) + assets.images:
        if metadata is not None:
            metadata.path = str(resolve_local(metadata.path))
    return assets


def cmd_generate(args: argparse.Namespace) -> int:
    config = _config(args.config)
    topic = select_topic(load_topics(config.content.topic_file), args.topic)
    provider = DemoProvider() if args.demo else OpenAICompatibleProvider(config.model)
    manifest = ContentPipeline(config, provider).run(topic)
    print(manifest.model_dump_json(indent=2))
    return 0 if manifest.status == "ready_to_render" else 2


def cmd_check(args: argparse.Namespace) -> int:
    config = _config(args.config)
    topic = select_topic(load_topics(config.content.topic_file), args.topic)
    article = _article_from_markdown(Path(args.article), config, topic.id)
    result = QualityGate(config.quality).check(article, topic)
    print(result.model_dump_json(indent=2))
    return 0 if result.passed else 2


def cmd_render(args: argparse.Namespace) -> int:
    config = _config(args.config)
    directory, manifest = _job(config, args.job)
    article_path = Path(manifest.outputs.get("edited", manifest.outputs.get("draft", "")))
    if not article_path.is_file():
        raise ValueError("任务没有可渲染文章")
    article = Article.model_validate_json(article_path.read_text(encoding="utf-8"))
    formatter = _formatter(config)
    output = Path(args.output) if args.output else directory / "preview.html"
    output.write_text(formatter.render_preview(article.title, article.markdown), encoding="utf-8")
    print(json.dumps({"preview": str(output)}, ensure_ascii=False))
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    config = _config(args.config)
    directory, manifest = _job(config, args.job)
    gate_path = _resolve_job_path(config, directory, manifest.outputs.get("quality_gate", ""))
    if not gate_path.is_file():
        raise ValueError("任务尚未执行质量门禁")
    gate = GateResult.model_validate_json(gate_path.read_text(encoding="utf-8"))
    if not gate.passed:
        raise ValueError("质量门禁未通过，禁止创建草稿")
    article_path = _resolve_job_path(config, directory, manifest.outputs["edited"])
    article = Article.model_validate_json(article_path.read_text(encoding="utf-8"))
    formatter = _formatter(config)
    assets = _load_publish_assets(config, directory, manifest, formatter)

    dry_run = True if args.dry_run else config.publish.dry_run
    client = None
    if not dry_run:
        client = WechatClient(config.publish.app_id or "", config.publish.app_secret or "")
    result = DraftPublisher(
        formatter,
        client,
    ).publish(
        article,
        output_dir=directory,
        dry_run=dry_run,
        approved=args.approved,
        require_approval=config.publish.require_human_approval,
        cover=Path(args.cover) if args.cover else None,
        asset_root=config.content.topic_file.parent.parent,
        assets=assets,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _analytics_store(config: AppConfig) -> ArticleAnalyticsStore:
    return ArticleAnalyticsStore(config.content.output_dir / "analytics")


def cmd_analytics_fetch(args: argparse.Namespace) -> int:
    config = _config(args.config)
    if not config.publish.app_id or not config.publish.app_secret:
        raise ValueError("请配置 WECHAT_APP_ID 和 WECHAT_APP_SECRET")
    publish_dates = (
        [parse_publish_date(args.date)]
        if args.date
        else recent_publish_dates(args.days or 1)
    )
    analytics = ArticleAnalytics(
        WechatClient(config.publish.app_id, config.publish.app_secret),
        _analytics_store(config),
    )
    print(json.dumps(analytics.fetch(publish_dates), ensure_ascii=False, indent=2))
    return 0


def cmd_analytics_report(args: argparse.Namespace) -> int:
    config = _config(args.config)
    report = ArticleAnalytics(None, _analytics_store(config)).report(args.days)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cmd_rerender(args: argparse.Namespace) -> int:
    config = _config(args.config)
    source = Path(args.article).resolve()
    article = _article_from_markdown(source, config, args.topic_id)
    visual_plan = VisualPlan(
        cover_subtitle=f"{args.category}｜关键结论与可执行清单",
        blocks=[],
    )
    generated_dir = config.render.generated_assets_dir / f"rerender-{datetime.now():%Y%m%d-%H%M%S}"
    renderer = TemplateImageRenderer(_formatter(config).theme)
    cover = renderer.render_cover(
        title=article.title,
        subtitle=visual_plan.cover_subtitle,
        category=args.category,
        output=generated_dir / "cover.png",
        brand=config.account.name,
    )
    blocks = render_visual_blocks(visual_plan, _formatter(config).theme)
    assets = ArticleAssets(
        theme_id=visual_plan.theme_id,
        cover=AssetMetadata(
            id="cover",
            kind="cover",
            path=str(cover),
            purpose="微信公众号封面",
            provider="pillow-template",
        ),
        images=[],
        html_blocks=blocks,
    )
    output_dir = Path(args.output_dir).resolve() if args.output_dir else source.parent
    outputs = DraftWriter(output_dir, _formatter(config)).export(
        article,
        run_id=f"visual-{datetime.now():%Y%m%d-%H%M%S}",
        assets=assets,
    )
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return 0


def _demo_signals() -> list[SourceSignal]:
    return [
        SourceSignal(
            id="manual-agent-demo",
            source_name="Agent Demo",
            source_type="manual",
            title="Spring AI Agent 工作流演示",
            url="https://example.com/agent-demo",
            summary="用于离线验证自动发现、选题、写作、审查、质量门禁和本地草稿导出。",
            published_at=datetime.now(UTC),
            score=100,
            tags=["java", "spring", "ai", "agent"],
        )
    ]


def _agent(config: AppConfig, *, demo: bool) -> ContentOperationsAgent:
    sources = load_sources_config(config.discovery.sources_file)
    discovery = DiscoveryClient(sources)
    provider = (
        DemoProvider()
        if demo
        else OpenAICompatibleProvider(config.model, timeout_seconds=config.agent.stage_timeout_seconds)
    )
    writer = DraftWriter(
        ROOT / "articles" / "drafts",
        _formatter(config),
    )
    return ContentOperationsAgent(
        config,
        provider,
        discovery,
        writer,
        signals_override=_demo_signals() if demo else None,
        image_provider=(
            DisabledImageProvider()
            if demo
            else build_image_provider(config.render.image)
        ),
        check_historical_titles=not demo,
    )


def cmd_agent_discover(args: argparse.Namespace) -> int:
    config = _config(args.config)
    batch_id = f"{datetime.now():%Y%m%d-%H%M%S}"
    if args.demo:
        batch = DiscoveryBatch(batch_id=batch_id, signals=_demo_signals())
    else:
        batch = DiscoveryClient(load_sources_config(config.discovery.sources_file)).discover(batch_id)
    directory = config.content.output_dir / f"discovery-{batch_id}"
    directory.mkdir(parents=True, exist_ok=False)
    path = directory / "signals.json"
    path.write_text(batch.model_dump_json(indent=2), encoding="utf-8")
    print(batch.model_dump_json(indent=2))
    return 0 if batch.signals else 2


def cmd_agent_run(args: argparse.Namespace) -> int:
    config = _config(args.config)
    state = _agent(config, demo=args.demo).run()
    print(state.model_dump_json(indent=2))
    return 0 if state.status == "completed" else 2


def cmd_agent_resume(args: argparse.Namespace) -> int:
    config = _config(args.config)
    state = _agent(config, demo=args.demo).resume(args.run_id)
    print(state.model_dump_json(indent=2))
    return 0 if state.status == "completed" else 2


def cmd_agent_status(args: argparse.Namespace) -> int:
    config = _config(args.config)
    state = _agent(config, demo=True).load(args.run_id)
    print(state.model_dump_json(indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="智效进化论微信公众号 AI 发布流水线")
    parser.add_argument("--config", help="配置文件路径")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="执行多阶段文章生成")
    generate.add_argument("--topic", help="选题 ID；默认选择 selected 中得分最高项")
    generate.add_argument("--demo", action="store_true", help="使用本地演示模型，不访问网络")
    generate.set_defaults(func=cmd_generate)

    check = subparsers.add_parser("check", help="对 Markdown 文章执行质量门禁")
    check.add_argument("article")
    check.add_argument("--topic", required=True, help="选题 ID")
    check.set_defaults(func=cmd_check)

    render = subparsers.add_parser("render", help="生成公众号样式 HTML 预览")
    render.add_argument("--job", required=True, help="任务 ID")
    render.add_argument("--output", help="预览文件路径")
    render.set_defaults(func=cmd_render)

    publish = subparsers.add_parser("publish", help="预览或写入微信公众号草稿箱")
    publish.add_argument("--job", required=True, help="任务 ID")
    publish.add_argument("--dry-run", action="store_true", help="强制只生成本地预览")
    publish.add_argument("--approved", action="store_true", help="确认已经人工审核通过")
    publish.add_argument("--cover", help="真实上传使用的封面图片")
    publish.set_defaults(func=cmd_publish)

    analytics = subparsers.add_parser("analytics", help="拉取和汇总公众号发表数据")
    analytics_commands = analytics.add_subparsers(dest="analytics_command", required=True)

    analytics_fetch = analytics_commands.add_parser("fetch", help="拉取微信图文详细数据")
    analytics_fetch_dates = analytics_fetch.add_mutually_exclusive_group()
    analytics_fetch_dates.add_argument("--date", help="发表日期，格式 YYYY-MM-DD；默认昨天")
    analytics_fetch_dates.add_argument("--days", type=int, help="拉取最近 N 个发表日期")
    analytics_fetch.set_defaults(func=cmd_analytics_fetch)

    analytics_report = analytics_commands.add_parser("report", help="汇总已拉取的本地数据")
    analytics_report.add_argument("--days", type=int, default=30, help="统计最近 N 天，默认 30")
    analytics_report.set_defaults(func=cmd_analytics_report)

    rerender = subparsers.add_parser("rerender", help="用视觉主题重渲染单篇 Markdown")
    rerender.add_argument("article", help="Markdown 文件路径")
    rerender.add_argument("--topic-id", default="manual-rerender")
    rerender.add_argument("--category", default="技术实践")
    rerender.add_argument("--output-dir", help="输出目录，默认与原文相同")
    rerender.set_defaults(func=cmd_rerender)

    agent = subparsers.add_parser("agent", help="运行有界内容运营 Agent")
    agent_commands = agent.add_subparsers(dest="agent_command", required=True)

    discover = agent_commands.add_parser("discover", help="抓取官方 RSS 与 GitHub Release")
    discover.add_argument("--demo", action="store_true", help="使用离线发现信号")
    discover.set_defaults(func=cmd_agent_discover)

    agent_run = agent_commands.add_parser("run", help="自动选题并生成本地草稿")
    agent_run.add_argument("--draft-only", action="store_true", help="明确仅导出本地草稿")
    agent_run.add_argument("--demo", action="store_true", help="使用离线模型和发现信号")
    agent_run.set_defaults(func=cmd_agent_run)

    resume = agent_commands.add_parser("resume", help="从失败或中断步骤恢复")
    resume.add_argument("--run-id", required=True)
    resume.add_argument("--demo", action="store_true", help="使用离线模型和发现信号")
    resume.set_defaults(func=cmd_agent_resume)

    status = agent_commands.add_parser("status", help="查看 Agent 状态")
    status.add_argument("--run-id", required=True)
    status.set_defaults(func=cmd_agent_status)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except (ValueError, PermissionError, WechatAPIError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

