from pathlib import Path

import pytest

from wechat_ai_publisher.cli import _load_publish_assets
from wechat_ai_publisher.config import load_config
from wechat_ai_publisher.domain.models import (
    Article,
    ArticleAssets,
    AssetMetadata,
    JobManifest,
)
from wechat_ai_publisher.rendering.formatter import WechatFormatter
from wechat_ai_publisher.wechat.publisher import DraftPublisher


ROOT = Path(__file__).resolve().parents[1]


class FakeWechatClient:
    def __init__(self):
        self.inline_images: list[Path] = []
        self.covers: list[Path] = []
        self.drafts: list[dict[str, str]] = []

    def upload_inline_image(self, path: Path) -> str:
        self.inline_images.append(path)
        return f"https://example.com/{path.name}"

    def upload_cover(self, path: Path) -> str:
        self.covers.append(path)
        return "thumb-media-id"

    def add_draft(self, **payload: str) -> str:
        self.drafts.append(payload)
        return "draft-media-id"


def article() -> Article:
    return Article(
        topic_id="publish-test",
        title="发布视觉终稿",
        digest="验证发布时会保留正文视觉内容。",
        markdown="# 发布视觉终稿\n\n## 验证流程\n\n这里是正文。",
        author="智效进化论",
    )


def assets(tmp_path: Path) -> ArticleAssets:
    cover = tmp_path / "cover.png"
    inline = tmp_path / "inline.png"
    cover.write_bytes(b"cover")
    inline.write_bytes(b"inline")
    return ArticleAssets(
        theme_id="test",
        cover=AssetMetadata(
            id="cover",
            kind="cover",
            path=str(cover),
            purpose="测试封面",
            provider="test",
        ),
        images=[
            AssetMetadata(
                id="inline",
                kind="concept_image",
                path=str(inline),
                purpose="测试正文图",
                provider="test",
            )
        ],
        html_blocks={
            "验证流程": f'<img src="{inline}" alt="流程图">',
        },
    )


def test_publish_uploads_visual_assets_and_is_idempotent(tmp_path):
    client = FakeWechatClient()
    publisher = DraftPublisher(
        WechatFormatter(ROOT / "templates" / "article.html"),
        client,
    )
    visual_assets = assets(tmp_path)

    first = publisher.publish(
        article(),
        output_dir=tmp_path / "job",
        dry_run=False,
        approved=True,
        require_approval=True,
        assets=visual_assets,
    )
    second = publisher.publish(
        article(),
        output_dir=tmp_path / "job",
        dry_run=False,
        approved=True,
        require_approval=True,
        assets=visual_assets,
    )

    assert first == second
    assert first["media_id"] == "draft-media-id"
    assert client.inline_images == [tmp_path / "inline.png"]
    assert client.covers == [tmp_path / "cover.png"]
    assert len(client.drafts) == 1
    assert 'src="https://example.com/inline.png"' in client.drafts[0]["content"]


def test_publish_requires_approval_before_upload(tmp_path):
    with pytest.raises(PermissionError, match="人工审核"):
        DraftPublisher(
            WechatFormatter(ROOT / "templates" / "article.html"),
            FakeWechatClient(),
        ).publish(
            article(),
            output_dir=tmp_path / "job",
            dry_run=False,
            approved=False,
            require_approval=True,
            assets=assets(tmp_path),
        )


def test_publish_assets_are_rebased_after_artifact_download(tmp_path):
    project = tmp_path / "checkout"
    draft_dir = project / "articles" / "drafts"
    asset_dir = draft_dir / "assets" / "bundle"
    asset_dir.mkdir(parents=True)
    (asset_dir / "cover.png").write_bytes(b"cover")
    manifest_path = draft_dir / "bundle.visual-manifest.json"
    manifest_path.write_text(
        ArticleAssets(
            theme_id="test",
            cover=AssetMetadata(
                id="cover",
                kind="cover",
                path="assets/bundle/cover.png",
                purpose="测试封面",
                provider="test",
            ),
            html_blocks={
                "验证流程": '<img src="assets/bundle/cover.png" alt="流程图">'
            },
        ).model_dump_json(),
        encoding="utf-8",
    )
    config = load_config(ROOT / "config" / "account.ci.yaml")
    config.content.topic_file = project / "topics" / "topic-pool.yaml"
    config.content.output_dir = project / "runtime"
    job_dir = config.content.output_dir / "agent-test"
    job_dir.mkdir(parents=True)
    manifest = JobManifest(
        job_id="agent-test",
        topic_id="test",
        model="test",
        status="ready_to_publish",
        outputs={
            "visual_manifest": "articles/drafts/bundle.visual-manifest.json",
        },
    )

    loaded = _load_publish_assets(
        config,
        job_dir,
        manifest,
        WechatFormatter(ROOT / "templates" / "article.html"),
    )

    assert loaded is not None
    expected_cover = asset_dir / "cover.png"
    assert Path(loaded.cover.path) == expected_cover
    assert f'src="{expected_cover}"' in loaded.html_blocks["验证流程"]
