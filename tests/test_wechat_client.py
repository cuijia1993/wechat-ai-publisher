import json

import httpx

from wechat_ai_publisher.wechat.client import WechatAPIError, WechatClient


def test_token_is_cached_and_draft_is_created():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "token-1", "expires_in": 7200})
        if request.url.path.endswith("/draft/add"):
            payload = json.loads(request.content)
            assert payload["articles"][0]["thumb_media_id"] == "cover-1"
            return httpx.Response(200, json={"media_id": "draft-1"})
        return httpx.Response(404, json={"errcode": 404, "errmsg": "not found"})

    client = WechatClient("app", "secret", http=httpx.Client(transport=httpx.MockTransport(handler)))

    assert client.access_token() == "token-1"
    assert client.add_draft(
        title="标题",
        author="作者",
        digest="摘要",
        content="<p>正文</p>",
        thumb_media_id="cover-1",
    ) == "draft-1"
    assert calls.count("/cgi-bin/token") == 1


def test_wechat_error_is_not_silenced():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"errcode": 40013, "errmsg": "invalid appid"})
    )
    client = WechatClient("bad", "secret", http=httpx.Client(transport=transport))

    try:
        client.access_token()
    except WechatAPIError as exc:
        assert "40013" in str(exc)
    else:
        raise AssertionError("应抛出 WechatAPIError")


def test_article_total_detail_uses_datacube_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "token-1", "expires_in": 7200})
        if request.url.path == "/datacube/getarticletotaldetail":
            assert request.url.params["access_token"] == "token-1"
            assert json.loads(request.content) == {
                "begin_date": "2026-07-30",
                "end_date": "2026-07-30",
            }
            return httpx.Response(
                200,
                json={"list": [{"msgid": "123_1", "detail_list": []}], "is_delay": False},
            )
        return httpx.Response(404, json={"errcode": 404, "errmsg": "not found"})

    client = WechatClient("app", "secret", http=httpx.Client(transport=httpx.MockTransport(handler)))

    payload = client.get_article_total_detail("2026-07-30")

    assert payload["list"][0]["msgid"] == "123_1"

