from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from wechat_ai_publisher.config import SourcesConfig
from wechat_ai_publisher.domain.models import SourceDocument, SourceSignal

BLOCKED_PAGE_MARKERS = (
    "enable javascript and cookies to continue",
    "verification successful. waiting",
    "just a moment",
    "cf-chl-",
)
TEXT_CONTENT_TYPES = (
    "text/html",
    "text/plain",
    "text/markdown",
    "application/xhtml+xml",
)


class _ArticleTextParser(HTMLParser):
    SKIP_TAGS = {"script", "style", "svg", "form", "noscript", "template"}
    PREFERRED_TAGS = {"article", "main"}
    BREAK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "header",
        "li",
        "main",
        "nav",
        "p",
        "section",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._preferred_depth = 0
        self._all: list[str] = []
        self._preferred: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.casefold()
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in self.PREFERRED_TAGS:
            self._preferred_depth += 1
        if tag in self.BREAK_TAGS:
            self._append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in self.SKIP_TAGS:
            self._skip_depth = max(self._skip_depth - 1, 0)
            return
        if self._skip_depth:
            return
        if tag in self.BREAK_TAGS:
            self._append("\n")
        if tag in self.PREFERRED_TAGS:
            self._preferred_depth = max(self._preferred_depth - 1, 0)

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._append(data)

    def _append(self, value: str) -> None:
        self._all.append(value)
        if self._preferred_depth:
            self._preferred.append(value)

    @property
    def text(self) -> str:
        preferred = _clean_text("".join(self._preferred))
        return preferred if len(preferred) >= 80 else _clean_text("".join(self._all))


def _clean_text(value: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


class SourceFetcher:
    def __init__(
        self,
        config: SourcesConfig,
        *,
        http: httpx.Client | None = None,
        resolve_hosts: bool = True,
    ) -> None:
        self.config = config
        self.http = http or httpx.Client(
            timeout=config.timeout_seconds,
            follow_redirects=False,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; WeChatAIPublisher/1.0; "
                    "+https://github.com)"
                )
            },
        )
        self.resolve_hosts = resolve_hosts

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("来源正文只允许抓取公开 HTTP/HTTPS URL")
        try:
            literal = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            literal = None
        if literal and not literal.is_global:
            raise ValueError("来源正文禁止访问私有或本地网络地址")
        if not self.resolve_hosts or literal:
            return
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
        if any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError("来源域名解析到了私有或本地网络地址")

    def _download(self, url: str) -> tuple[bytes, str, str]:
        current = url
        for _ in range(6):
            self._validate_url(current)
            with self.http.stream("GET", current) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise RuntimeError("来源页面返回了无目标地址的重定向")
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").casefold()
                if not any(value in content_type for value in TEXT_CONTENT_TYPES):
                    raise RuntimeError(f"来源页面内容类型不受支持：{content_type}")
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > self.config.max_document_bytes:
                        raise RuntimeError("来源页面超过允许的最大体积")
                    chunks.append(chunk)
                return b"".join(chunks), content_type, str(response.url)
        raise RuntimeError("来源页面重定向次数过多")

    def fetch(self, signal: SourceSignal) -> SourceDocument:
        try:
            payload, content_type, final_url = self._download(signal.url)
            raw = payload.decode("utf-8", errors="replace")
            lowered = raw.casefold()
            if any(marker in lowered for marker in BLOCKED_PAGE_MARKERS):
                raise RuntimeError("来源页面返回了人机验证，未获得官方正文")
            if "html" in content_type or "xhtml" in content_type:
                parser = _ArticleTextParser()
                parser.feed(raw)
                content = parser.text
                method = "html"
            else:
                content = _clean_text(raw)
                method = "text"
            content = content[: self.config.max_document_chars]
            if len(content) < self.config.min_document_chars:
                raise RuntimeError(
                    f"来源正文过短：{len(content)} 字符，"
                    f"至少需要 {self.config.min_document_chars} 字符"
                )
            return SourceDocument(
                signal_id=signal.id,
                title=signal.title,
                url=final_url,
                content=content,
                content_type=content_type,
                extraction_method=method,
                content_hash=hashlib.sha256(content.encode()).hexdigest(),
                usable=True,
            )
        except Exception as exc:
            summary = _clean_text(signal.summary)
            if len(summary) >= self.config.min_document_chars:
                return SourceDocument(
                    signal_id=signal.id,
                    title=signal.title,
                    url=signal.url,
                    content=summary[: self.config.max_document_chars],
                    content_type="text/plain",
                    extraction_method="signal_summary",
                    content_hash=hashlib.sha256(summary.encode()).hexdigest(),
                    usable=True,
                    error=f"全文抓取失败，已使用来源摘要：{exc}",
                )
            return SourceDocument(
                signal_id=signal.id,
                title=signal.title,
                url=signal.url,
                usable=False,
                error=str(exc),
            )
