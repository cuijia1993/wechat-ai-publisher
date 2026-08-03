from __future__ import annotations

import json
from pathlib import Path

from wechat_ai_publisher.domain.models import Article, ArticleAssets
from wechat_ai_publisher.rendering.formatter import WechatFormatter
from wechat_ai_publisher.rendering.sanitize import sanitize_wechat_html
from wechat_ai_publisher.wechat.client import WechatClient


class DraftPublisher:
    def __init__(self, formatter: WechatFormatter, client: WechatClient | None = None):
        self.formatter = formatter
        self.client = client

    def publish(
        self,
        article: Article,
        *,
        output_dir: Path,
        dry_run: bool,
        approved: bool,
        require_approval: bool,
        cover: Path | None = None,
        asset_root: Path | None = None,
        assets: ArticleAssets | None = None,
    ) -> dict[str, str | bool]:
        if not dry_run and require_approval and not approved:
            raise PermissionError("未提供人工审核通过标记，禁止创建微信草稿")
        if not dry_run and article.publication_status != "candidate":
            raise PermissionError("演示模型产物不能创建微信公众号草稿")

        output_dir.mkdir(parents=True, exist_ok=True)
        record_path = output_dir / "publish-result.json"
        if not dry_run and record_path.exists():
            existing = json.loads(record_path.read_text(encoding="utf-8"))
            if existing.get("media_id"):
                return existing

        visual_blocks = dict(assets.html_blocks) if assets else {}
        prelude = visual_blocks.pop("__prelude__", "")
        body = sanitize_wechat_html(prelude) + self.formatter.render_body(
            article.markdown,
            include_h1=False,
            visual_blocks=visual_blocks,
        )
        preview = self.formatter.render_preview(
            article.title,
            article.markdown,
            prelude_html=prelude,
            visual_blocks=visual_blocks,
        )
        preview_path = output_dir / "preview.html"
        preview_path.write_text(preview, encoding="utf-8")

        if dry_run:
            result: dict[str, str | bool] = {
                "dry_run": True,
                "preview": str(preview_path),
                "status": "not_uploaded",
            }
        else:
            if not self.client:
                raise ValueError("真实上传需要微信客户端")
            if cover is None and assets and assets.cover:
                cover = Path(assets.cover.path)
            if not cover or not cover.is_file():
                raise ValueError("真实上传必须提供存在的封面图片")
            for image in self.formatter.local_images(body):
                resolved = image if image.is_absolute() else (asset_root or Path.cwd()) / image
                uploaded_url = self.client.upload_inline_image(resolved)
                body = self.formatter.replace_image(body, str(image), uploaded_url)
            thumb_media_id = self.client.upload_cover(cover)
            media_id = self.client.add_draft(
                title=article.title,
                author=article.author,
                digest=article.digest,
                content=body,
                thumb_media_id=thumb_media_id,
            )
            result = {"dry_run": False, "status": "draft_created", "media_id": media_id}

        record_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

