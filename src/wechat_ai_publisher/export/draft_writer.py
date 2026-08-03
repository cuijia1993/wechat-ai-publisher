from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from wechat_ai_publisher.domain.models import Article, ArticleAssets, AssetMetadata
from wechat_ai_publisher.rendering.formatter import WechatFormatter


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value).strip("-").lower()
    return slug[:80] or "article"


class DraftWriter:
    def __init__(self, output_dir: Path, formatter: WechatFormatter):
        self.output_dir = output_dir
        self.formatter = formatter

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)

    @staticmethod
    def _copy_asset(
        metadata: AssetMetadata,
        *,
        asset_dir: Path,
        relative_dir: Path,
    ) -> tuple[AssetMetadata, str]:
        source = Path(metadata.path)
        if not source.is_file():
            raise FileNotFoundError(f"视觉资产不存在：{source}")
        filename = f"{slugify(metadata.id)}{source.suffix.lower() or '.png'}"
        destination = asset_dir / filename
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        shutil.copyfile(source, temporary)
        os.replace(temporary, destination)
        copied = metadata.model_copy(deep=True)
        copied.path = str(destination)
        return copied, (relative_dir / filename).as_posix()

    def export(
        self,
        article: Article,
        *,
        run_id: str,
        assets: ArticleAssets | None = None,
    ) -> dict[str, str]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        base = f"{slugify(article.topic_id)}-{run_id}"
        markdown_path = self.output_dir / f"{base}.md"
        html_path = self.output_dir / f"{base}.html"
        prelude = ""
        visual_blocks: dict[str, str] = {}
        result = {"markdown": str(markdown_path), "html": str(html_path)}

        if assets is not None:
            copied_assets = assets.model_copy(deep=True)
            relative_dir = Path("assets") / base
            asset_dir = self.output_dir / relative_dir
            asset_dir.mkdir(parents=True, exist_ok=True)
            asset_urls: dict[str, str] = {}
            if assets.cover:
                copied_assets.cover, asset_urls[assets.cover.id] = self._copy_asset(
                    assets.cover, asset_dir=asset_dir, relative_dir=relative_dir
                )
            copied_assets.images = []
            for metadata in assets.images:
                copied, relative_url = self._copy_asset(
                    metadata, asset_dir=asset_dir, relative_dir=relative_dir
                )
                copied_assets.images.append(copied)
                asset_urls[metadata.id] = relative_url
            blocks = dict(assets.html_blocks)
            for asset_id, relative_url in asset_urls.items():
                token = f"{{{{asset:{asset_id}}}}}"
                blocks = {anchor: value.replace(token, relative_url) for anchor, value in blocks.items()}
            copied_assets.html_blocks = blocks
            for metadata in ([copied_assets.cover] if copied_assets.cover else []) + copied_assets.images:
                if metadata is not None:
                    metadata.path = asset_urls[metadata.id]
            preview_blocks = dict(blocks)
            prelude = preview_blocks.pop("__prelude__", "")
            visual_blocks = preview_blocks
            manifest_path = self.output_dir / f"{base}.visual-manifest.json"
            self._atomic_write(
                manifest_path,
                copied_assets.model_dump_json(indent=2),
            )
            result["visual_manifest"] = str(manifest_path)
            result["cover"] = (
                str(self.output_dir / asset_urls[assets.cover.id])
                if assets.cover
                else ""
            )

        self._atomic_write(markdown_path, article.markdown)
        self._atomic_write(
            html_path,
            self.formatter.render_preview(
                article.title,
                article.markdown,
                prelude_html=prelude,
                visual_blocks=visual_blocks,
            ),
        )
        return result

