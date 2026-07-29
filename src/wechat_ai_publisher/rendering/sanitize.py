from __future__ import annotations

import re

FORBIDDEN_BLOCKS = re.compile(
    r"<(?:script|style|svg|iframe)\b[^>]*>.*?</(?:script|style|svg|iframe)>",
    re.IGNORECASE | re.DOTALL,
)
FORBIDDEN_TAGS = re.compile(r"</?(?:script|style|svg|iframe)\b[^>]*>", re.IGNORECASE)
CLASS_OR_ID = re.compile(r"\s(?:class|id)=(?:\"[^\"]*\"|'[^']*')", re.IGNORECASE)
LOCAL_IMAGE = re.compile(r'<img\b[^>]*\bsrc="(?!https?://|data:)([^"]+)"', re.IGNORECASE)


def sanitize_wechat_html(content: str) -> str:
    content = FORBIDDEN_BLOCKS.sub("", content)
    content = FORBIDDEN_TAGS.sub("", content)
    return CLASS_OR_ID.sub("", content)


def validate_wechat_html(content: str, *, allow_local_images: bool = True) -> list[str]:
    issues: list[str] = []
    if FORBIDDEN_TAGS.search(content):
        issues.append("包含微信不兼容标签：script/style/svg/iframe")
    if re.search(r"<link\b|<meta\b[^>]*http-equiv", content, re.IGNORECASE):
        issues.append("包含外部样式或页面级元数据")
    if re.search(r"\sclass=", content, re.IGNORECASE):
        issues.append("包含依赖 class 的样式")
    if not allow_local_images and LOCAL_IMAGE.search(content):
        issues.append("包含尚未上传到微信服务器的本地图片")
    return issues

