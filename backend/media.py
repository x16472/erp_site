"""取得各影音平台的公開影片標題，不接受外部任意查詢端點。"""

from __future__ import annotations

import html
import json
import time
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from xml.etree import ElementTree

MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class MetadataUnavailable(RuntimeError):
    """來源未提供可驗證的影片資訊。"""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 查詢端點由伺服器固定產生；禁止重新導向至未驗證的目的地。
        return None


class _TikTokScripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts: dict[str, str] = {}
        self.current = ""

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            script_id = dict(attrs).get("id", "")
            self.current = script_id if script_id in {
                "__FRONTITY_CONNECT_STATE__", "__UNIVERSAL_DATA_FOR_REHYDRATION__", "SIGI_STATE",
            } else ""
            if self.current:
                self.scripts[self.current] = ""

    def handle_data(self, data):
        if self.current:
            self.scripts[self.current] += data

    def handle_endtag(self, tag):
        if tag == "script":
            self.current = ""


def _fetch(url: str, deadline: float) -> bytes:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise MetadataUnavailable("影片標題讀取逾時，請稍後重試")
    user_agent = "SilverShieldOperations/1.0"
    if url.startswith("https://www.tiktok.com/"):
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    request = Request(url, headers={
        "User-Agent": user_agent,
        "Accept": "*/*",
    })
    try:
        with build_opener(_NoRedirect()).open(request, timeout=min(6, remaining)) as response:
            content = response.read(MAX_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise MetadataUnavailable("影音來源暫時無法提供影片標題，請稍後重試或由原站觀看") from exc
    if len(content) > MAX_RESPONSE_BYTES:
        raise MetadataUnavailable("影音來源回應過大，無法取得影片標題")
    return content


def _read_json(content: bytes) -> dict:
    try:
        payload = json.loads(content)
    except (ValueError, UnicodeError) as exc:
        raise MetadataUnavailable("影音來源未回傳有效的影片資訊") from exc
    if not isinstance(payload, dict):
        raise MetadataUnavailable("影音來源未回傳有效的影片資訊")
    return payload


def _tiktok_caption(content: bytes, video_id: str) -> str | None:
    parser = _TikTokScripts()
    parser.feed(content.decode("utf-8"))
    for script_id, value in parser.scripts.items():
        payload = _read_json(value.encode("utf-8"))
        if script_id == "__FRONTITY_CONNECT_STATE__":
            source = payload.get("source", {}).get("data", {})
            page = source.get(f"/embed/v2/{video_id}", source.get(f"/embed/v2/{video_id}/", {}))
            item = page.get("videoData", {}).get("itemInfos", {})
            caption_key = "text"
        elif script_id == "__UNIVERSAL_DATA_FOR_REHYDRATION__":
            detail = payload.get("__DEFAULT_SCOPE__", {}).get("webapp.video-detail", {})
            item = detail.get("itemInfo", {}).get("itemStruct", {})
            caption_key = "desc"
        else:
            item = payload.get("ItemModule", {}).get(video_id, {})
            caption_key = "desc"
        # 只採用目前影片的說明，避免誤取音樂名稱、作者或推薦影片標題。
        if str(item.get("id", "")) == video_id and isinstance(item.get(caption_key), str):
            return item[caption_key]
    return None


def video_metadata(item: dict[str, str]) -> dict[str, str]:
    platform, video_id = item["platform"], item["video_id"]
    if not video_id:
        return {**item, "title": "尚未取得影片標題", "title_status": "unavailable"}
    deadline = time.monotonic() + 10
    title = None
    try:
        if platform == "bilibili":
            params = {"bvid": video_id} if video_id.startswith("BV") else {"aid": video_id[2:]}
            payload = _read_json(_fetch("https://api.bilibili.com/x/web-interface/view?" + urlencode(params), deadline))
            if payload.get("code") != 0:
                raise MetadataUnavailable("BiliBili 無法提供這部影片的標題，影片可能不公開或來源限制存取")
            title = payload.get("data", {}).get("title")
        elif platform == "niconico":
            content = _fetch(f"https://ext.nicovideo.jp/api/getthumbinfo/{video_id}", deadline)
            if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
                raise MetadataUnavailable("ニコニコ回傳的影片資訊格式不正確")
            root = ElementTree.fromstring(content)
            if root.get("status") != "ok":
                raise MetadataUnavailable("ニコニコ找不到這部影片，或影片未公開")
            title = root.findtext("./thumb/title")
        elif platform == "douyin":
            endpoint = "https://open.douyin.com/api/douyin/v1/video/get_iframe_by_video?"
            payload = _read_json(_fetch(endpoint + urlencode({"video_id": video_id}), deadline))
            if payload.get("err_no") != 0:
                raise MetadataUnavailable("Douyin 無法提供這部影片的標題，影片可能未公開或已移除")
            title = payload.get("data", {}).get("video_title")
        elif platform == "tiktok":
            content = _fetch(f"https://www.tiktok.com/embed/v2/{video_id}", deadline)
            title = _tiktok_caption(content, video_id)
            if title is None:
                endpoint = "https://www.tiktok.com/oembed?" + urlencode({"url": item["watch_url"]})
                payload = _read_json(_fetch(endpoint, deadline))
                title = payload.get("title")
        else:
            raise MetadataUnavailable("不支援的影音平台")
    except (ValueError, UnicodeError, TypeError, AttributeError, ElementTree.ParseError) as exc:
        raise MetadataUnavailable("影音來源回傳的影片資訊格式不正確，請稍後重試") from exc
    if not isinstance(title, str):
        raise MetadataUnavailable("影音來源未回傳影片標題，請稍後重試或由原站觀看")
    title = html.unescape(title).strip()
    return {
        **item,
        "title": title or "此影片未提供標題",
        "title_status": "available" if title else "empty",
    }

