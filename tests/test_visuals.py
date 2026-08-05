import json
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

from wechat_ai_publisher.cli import _extract_action_checklist
from wechat_ai_publisher.config import ImageProviderConfig
from wechat_ai_publisher.domain.models import (
    Article,
    ArticleAssets,
    AssetMetadata,
    VisualBlock,
    VisualPlan,
)
from wechat_ai_publisher.export.draft_writer import DraftWriter
from wechat_ai_publisher.providers.image import (
    DashScopeImageProvider,
    DisabledImageProvider,
    build_image_provider,
)
from wechat_ai_publisher.rendering.components import render_visual_blocks
from wechat_ai_publisher.rendering.formatter import WechatFormatter
from wechat_ai_publisher.rendering.template_images import TemplateImageRenderer
from wechat_ai_publisher.rendering.theme import load_theme

ROOT = Path(__file__).resolve().parents[1]


def test_extract_action_checklist_uses_longest_numbered_group():
    markdown = """# 标题

## 数据设置

1. 关闭训练
2. 删除记录
3. 检查授权

## 使用前检查

1. **确认身份。** 看清服务对象
2. **限制权限。** 只开必需范围
3. **保留日志。** 记录关键操作
4. **准备退出。** 确保可以撤销
"""

    assert _extract_action_checklist(markdown) == (
        "使用前检查",
        [
            "确认身份。 看清服务对象",
            "限制权限。 只开必需范围",
            "保留日志。 记录关键操作",
            "准备退出。 确保可以撤销",
        ],
    )


def test_theme_and_components_use_wechat_compatible_inline_styles():
    theme = load_theme(ROOT / "config" / "themes" / "professional-minimal.yaml")
    plan = VisualPlan(
        cover_subtitle="验证升级边界",
        blocks=[
            VisualBlock(
                id="steps",
                kind="flowchart",
                anchor="验证步骤",
                title="四步验证",
                items=["读取变更", "建立样例", "运行检查", "人工确认"],
            )
        ],
    )

    html = render_visual_blocks(plan, theme)["验证步骤"]

    assert theme.colors.teal == "#0F9F91"
    assert 'style="' in html
    assert "background-color:#F4F8F8" in html
    assert "background-color:#0F9F91" in html
    assert "border:1px solid" not in html
    assert "class=" not in html
    assert "<svg" not in html
    assert "<script" not in html


def test_concept_image_does_not_also_render_duplicate_html_card():
    theme = load_theme(ROOT / "config" / "themes" / "professional-minimal.yaml")
    plan = VisualPlan(
        cover_subtitle="概念图",
        blocks=[
            VisualBlock(
                id="concept",
                kind="concept_image",
                anchor="对应章节",
                title="跨应用数据关联",
                description="日历与搜索工具的数据交汇",
                prompt="abstract calendar and search",
            )
        ],
    )

    assert render_visual_blocks(plan, theme) == {}


def test_template_images_have_expected_dimensions(tmp_path):
    from wechat_ai_publisher.rendering.template_images import resolve_cjk_font_path

    resolve_cjk_font_path(bold=True)
    resolve_cjk_font_path(bold=False)
    renderer = TemplateImageRenderer(
        load_theme(ROOT / "config" / "themes" / "professional-minimal.yaml")
    )
    cover = renderer.render_cover(
        title="Spring AI 升级前先验证这五项",
        subtitle="把发布说明转化为迁移清单",
        category="版本解读",
        output=tmp_path / "cover.png",
    )
    checklist = renderer.render_checklist(
        title="升级检查清单",
        items=["依赖版本", "API 变更", "数据兼容"],
        output=tmp_path / "checklist.png",
    )

    with Image.open(cover) as image:
        assert image.size == (900, 383)
    with Image.open(checklist) as image:
        assert image.size == (900, 348)


def test_disabled_image_provider_and_atomic_visual_export(tmp_path):
    provider = DisabledImageProvider()
    assert (
        provider.generate(
            prompt="静态概念插画",
            output=tmp_path / "disabled.png",
            width=900,
            height=560,
        )
        is None
    )

    theme = load_theme(ROOT / "config" / "themes" / "professional-minimal.yaml")
    image_path = TemplateImageRenderer(theme).render_checklist(
        title="检查清单",
        items=["先确认来源", "再执行验证"],
        output=tmp_path / "source.png",
    )
    assets = ArticleAssets(
        theme_id=theme.id,
        cover=AssetMetadata(
            id="cover",
            kind="cover",
            path=str(image_path),
            purpose="测试封面",
            provider="pillow-template",
        ),
        images=[
            AssetMetadata(
                id="checklist",
                kind="checklist",
                path=str(image_path),
                purpose="测试清单",
                provider="pillow-template",
            )
        ],
        html_blocks={
            "验证步骤": '<img src="{{asset:checklist}}" alt="检查清单">'
        },
    )
    article = Article(
        topic_id="visual-test",
        title="视觉导出测试",
        digest="验证主题 HTML、图片和清单原子导出。",
        markdown="# 视觉导出测试\n\n## 验证步骤\n\n检查导出结果。",
        author="智效进化论",
    )
    writer = DraftWriter(
        tmp_path / "drafts",
        WechatFormatter(ROOT / "templates" / "article.html", theme),
    )

    outputs = writer.export(article, run_id="run-1", assets=assets)
    html = Path(outputs["html"]).read_text(encoding="utf-8")
    manifest = json.loads(Path(outputs["visual_manifest"]).read_text(encoding="utf-8"))

    assert "assets/visual-test-run-1/checklist.png" in html
    assert Path(outputs["cover"]).is_file()
    assert manifest["images"][0]["provider"] == "pillow-template"
    assert manifest["cover"]["path"] == "assets/visual-test-run-1/cover.png"
    assert (
        'src="assets/visual-test-run-1/checklist.png"'
        in manifest["html_blocks"]["验证步骤"]
    )
    assert not list((tmp_path / "drafts").glob("*.tmp"))


def test_dashscope_qwen_image_provider_downloads_and_normalizes_png(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("TEST_IMAGE_API_KEY", "test-key")
    source = BytesIO()
    Image.new("RGB", (1024, 768), "#0B1F3A").save(source, format="PNG")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            captured.update(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "output": {
                        "choices": [
                            {
                                "message": {
                                    "content": [
                                        {
                                            "image": "https://mock.aliyuncs.com/generated.png"
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                },
            )
        return httpx.Response(200, content=source.getvalue(), headers={"content-type": "image/png"})

    config = ImageProviderConfig(
        provider="dashscope_native",
        model="qwen-image-2.0-pro-2026-06-22",
        endpoint="https://workspace.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
        endpoint_env="UNSET_IMAGE_ENDPOINT",
        api_key_env="TEST_IMAGE_API_KEY",
    )
    provider = DashScopeImageProvider(
        config,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    output = provider.generate(
        prompt="深蓝青绿色专业极简抽象技术流程，无文字",
        output=tmp_path / "qwen.png",
        width=900,
        height=560,
    )

    assert output == tmp_path / "qwen.png"
    assert captured["model"] == "qwen-image-2.0-pro-2026-06-22"
    assert captured["parameters"]["size"] == "900*560"
    assert provider.last_source_url == "https://mock.aliyuncs.com/generated.png"
    with Image.open(output) as image:
        assert image.size == (900, 560)


def test_image_provider_safely_disables_when_key_is_missing(monkeypatch):
    monkeypatch.delenv("MISSING_IMAGE_KEY", raising=False)
    provider = build_image_provider(
        ImageProviderConfig(
            provider="dashscope_native",
            model="qwen-image-2.0-pro-2026-06-22",
            endpoint="https://workspace.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
            endpoint_env="UNSET_IMAGE_ENDPOINT",
            api_key_env="MISSING_IMAGE_KEY",
        )
    )

    assert isinstance(provider, DisabledImageProvider)

