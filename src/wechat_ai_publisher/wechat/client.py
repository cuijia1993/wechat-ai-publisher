from __future__ import annotations

import mimetypes
import time
from pathlib import Path
from typing import Any

import httpx


class WechatAPIError(RuntimeError):
    pass


class WechatClient:
    BASE_URL = "https://api.weixin.qq.com/cgi-bin"
    DATACUBE_URL = "https://api.weixin.qq.com/datacube"

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        *,
        http: httpx.Client | None = None,
    ):
        if not app_id or not app_secret:
            raise ValueError("真实上传需要 WECHAT_APP_ID 和 WECHAT_APP_SECRET")
        self.app_id = app_id
        self.app_secret = app_secret
        self.http = http or httpx.Client(timeout=30)
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    @staticmethod
    def _ensure_success(payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("errcode", 0) != 0:
            raise WechatAPIError(f"微信接口失败：{payload.get('errcode')} {payload.get('errmsg', '')}")
        return payload

    def access_token(self) -> str:
        if self._access_token and time.monotonic() < self._token_expires_at:
            return self._access_token
        response = self.http.get(
            f"{self.BASE_URL}/token",
            params={"grant_type": "client_credential", "appid": self.app_id, "secret": self.app_secret},
        )
        response.raise_for_status()
        payload = self._ensure_success(response.json())
        token = payload.get("access_token")
        if not token:
            raise WechatAPIError("微信 Token 响应缺少 access_token")
        self._access_token = token
        self._token_expires_at = time.monotonic() + max(int(payload.get("expires_in", 7200)) - 300, 60)
        return token

    def upload_inline_image(self, path: Path) -> str:
        with path.open("rb") as handle:
            response = self.http.post(
                f"{self.BASE_URL}/media/uploadimg",
                params={"access_token": self.access_token()},
                files={"media": (path.name, handle, mimetypes.guess_type(path.name)[0] or "application/octet-stream")},
            )
        response.raise_for_status()
        payload = self._ensure_success(response.json())
        if not payload.get("url"):
            raise WechatAPIError("正文图片上传响应缺少 url")
        return str(payload["url"])

    def upload_cover(self, path: Path) -> str:
        with path.open("rb") as handle:
            response = self.http.post(
                f"{self.BASE_URL}/material/add_material",
                params={"access_token": self.access_token(), "type": "image"},
                files={"media": (path.name, handle, mimetypes.guess_type(path.name)[0] or "image/jpeg")},
            )
        response.raise_for_status()
        payload = self._ensure_success(response.json())
        if not payload.get("media_id"):
            raise WechatAPIError("封面上传响应缺少 media_id")
        return str(payload["media_id"])

    def add_draft(
        self,
        *,
        title: str,
        author: str,
        digest: str,
        content: str,
        thumb_media_id: str,
    ) -> str:
        response = self.http.post(
            f"{self.BASE_URL}/draft/add",
            params={"access_token": self.access_token()},
            json={
                "articles": [
                    {
                        "title": title,
                        "author": author,
                        "digest": digest,
                        "content": content,
                        "thumb_media_id": thumb_media_id,
                        "need_open_comment": 0,
                        "only_fans_can_comment": 0,
                    }
                ]
            },
        )
        response.raise_for_status()
        payload = self._ensure_success(response.json())
        if not payload.get("media_id"):
            raise WechatAPIError("创建草稿响应缺少 media_id")
        return str(payload["media_id"])

    def get_article_total_detail(self, publish_date: str) -> dict[str, Any]:
        response = self.http.post(
            f"{self.DATACUBE_URL}/getarticletotaldetail",
            params={"access_token": self.access_token()},
            json={"begin_date": publish_date, "end_date": publish_date},
        )
        response.raise_for_status()
        payload = self._ensure_success(response.json())
        articles = payload.get("list")
        if not isinstance(articles, list):
            raise WechatAPIError("图文统计响应缺少 list")
        return payload

