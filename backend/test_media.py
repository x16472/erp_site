from __future__ import annotations

import json
import unittest
from unittest import mock
from urllib.error import HTTPError

from backend import media
from backend import input as user_input


SAMPLES = {
    "bilibili": "https://www.bilibili.com/video/BV1VRpw69E6V",
    "niconico": "https://www.nicovideo.jp/watch/sm46963007",
    "douyin": "https://www.douyin.com/video/7695310200543262714",
    "tiktok": "https://www.tiktok.com/@knieperreevers489/video/7670724706814774548",
}


class MediaMetadataTests(unittest.TestCase):
    def item(self, platform):
        return user_input.validate_media({"platform": platform, "url": SAMPLES[platform]})

    def test_real_titles_from_provider_fields(self):
        cases = [
            ("bilibili", {"code": 0, "data": {"title": "【我在现代当幽差】：赶着去投胎啊！！！！【UP动画】"}}),
            ("douyin", {"err_no": 0, "data": {"video_title": "跨境运输运费一趟有几万#斯堪尼亚 #绿通"}}),
        ]
        for platform, payload in cases:
            with self.subTest(platform=platform), mock.patch.object(
                media, "_fetch", return_value=json.dumps(payload).encode()
            ) as fetch:
                result = media.video_metadata(self.item(platform))
                expected = payload["data"].get("title", payload["data"].get("video_title"))
                self.assertEqual(result["title"], expected)
                self.assertNotEqual(result["title"], result["video_id"])
                self.assertEqual(result["title_status"], "available")
                self.assertTrue(fetch.call_args.args[0].startswith("https://"))

    def test_niconico_reads_xml_title_and_entities(self):
        xml = '<nicovideo_thumb_response status="ok"><thumb><title>銀河迷子 &amp; 実況</title></thumb></nicovideo_thumb_response>'
        with mock.patch.object(media, "_fetch", return_value=xml.encode()):
            self.assertEqual(media.video_metadata(self.item("niconico"))["title"], "銀河迷子 & 実況")

    def tiktok_page(self, video_id, caption):
        payload = {"source": {"data": {f"/embed/v2/{video_id}": {
            "videoData": {"itemInfos": {"id": video_id, "text": caption}},
        }}}}
        return ('<script id="__FRONTITY_CONNECT_STATE__" type="application/json">'
                + json.dumps(payload) + "</script>").encode()

    def test_tiktok_caption_belongs_to_requested_video(self):
        page = self.tiktok_page("7670724706814774548", "影片說明 &amp; 測試")
        with mock.patch.object(media, "_fetch", return_value=page) as fetch:
            result = media.video_metadata(self.item("tiktok"))
            self.assertEqual(result["title"], "影片說明 & 測試")
            self.assertEqual(result["title_status"], "available")
            fetch.assert_called_once()

    def test_tiktok_empty_caption_is_not_a_fetch_failure_or_video_id(self):
        page = self.tiktok_page("7670724706814774548", "")
        with mock.patch.object(media, "_fetch", return_value=page):
            result = media.video_metadata(self.item("tiktok"))
            self.assertEqual(result["title"], "此影片未提供標題")
            self.assertEqual(result["title_status"], "empty")

    def test_tiktok_ignores_another_video_and_generic_page_title(self):
        page = self.tiktok_page("6718335390845095173", "其他影片的標題")
        with mock.patch.object(media, "_fetch", side_effect=[page, b'{"provider_name":"TikTok"}']):
            with self.assertRaises(media.MetadataUnavailable):
                media.video_metadata(self.item("tiktok"))

    def test_tiktok_oembed_title_is_used_when_embed_metadata_is_missing(self):
        with mock.patch.object(media, "_fetch", side_effect=[
            b"<html><title>TikTok Embed</title></html>", b'{"title":"Real video caption"}',
        ]):
            self.assertEqual(media.video_metadata(self.item("tiktok"))["title"], "Real video caption")

    def test_provider_errors_never_become_titles(self):
        for platform, content in [
            ("bilibili", b'{"code":-404,"data":null}'),
            ("douyin", b'{"err_no":28003004,"data":{}}'),
            ("niconico", b'<nicovideo_thumb_response status="fail"/>'),
            ("bilibili", b"<html><title>Access denied</title></html>"),
        ]:
            with self.subTest(platform=platform), mock.patch.object(media, "_fetch", return_value=content):
                with self.assertRaises(media.MetadataUnavailable):
                    media.video_metadata(self.item(platform))

    def test_missing_title_is_a_failure_not_an_empty_caption(self):
        with mock.patch.object(media, "_fetch", return_value=b'{"code":0,"data":{}}'):
            with self.assertRaises(media.MetadataUnavailable):
                media.video_metadata(self.item("bilibili"))

    def test_fixed_endpoint_does_not_forward_user_query(self):
        item = user_input.validate_media({
            "platform": "bilibili",
            "url": SAMPLES["bilibili"] + "?p=2&url=http://127.0.0.1/admin",
        })
        with mock.patch.object(media, "_fetch", return_value=b'{"code":0,"data":{"title":"Title"}}') as fetch:
            result = media.video_metadata(item)
        self.assertEqual(fetch.call_args.args[0], "https://api.bilibili.com/x/web-interface/view?bvid=BV1VRpw69E6V")
        self.assertIn("p=2", result["embed_url"])

    def test_invalid_hosts_protocols_credentials_and_ports_are_rejected(self):
        urls = [
            "http://127.0.0.1/video/BV1VRpw69E6V",
            "https://www.bilibili.com.evil.test/video/BV1VRpw69E6V",
            "file:///video/BV1VRpw69E6V",
            "https://user:password@www.bilibili.com/video/BV1VRpw69E6V",
            "https://www.bilibili.com:8443/video/BV1VRpw69E6V",
            SAMPLES["bilibili"] + "?p=-1",
        ]
        for url in urls:
            with self.subTest(url=url), self.assertRaises(user_input.InputError):
                user_input.validate_media({"platform": "bilibili", "url": url})

    def test_embedded_and_shared_urls_still_resolve(self):
        for platform, url in [
            ("bilibili", "https://player.bilibili.com/player.html?bvid=BV1VRpw69E6V&p=2"),
            ("bilibili", "https://m.bilibili.com/video/av170001"),
            ("niconico", "https://nico.ms/sm46963007"),
            ("douyin", "https://open.douyin.com/player/video?vid=7695310200543262714"),
            ("tiktok", "https://www.tiktok.com/player/v1/7670724706814774548"),
        ]:
            with self.subTest(url=url):
                item = user_input.validate_media({"platform": platform, "url": url})
                self.assertTrue(item["video_id"])
                self.assertTrue(item["embed_url"].startswith("https:"))

    def test_original_only_links_never_present_ids_as_titles(self):
        for platform, url in [
            ("bilibili", "https://b23.tv/abc123"),
            ("niconico", "https://live.nicovideo.jp/watch/lv123"),
            ("douyin", "https://v.douyin.com/abc123"),
            ("tiktok", "https://www.tiktok.com/@user/live"),
        ]:
            with self.subTest(platform=platform), mock.patch.object(media, "_fetch") as fetch:
                result = media.video_metadata(user_input.validate_media({"platform": platform, "url": url}))
                self.assertEqual(result["title_status"], "unavailable")
                self.assertFalse(result["embed_url"])
                fetch.assert_not_called()

    def test_network_timeout_and_oversize_response_are_reported(self):
        opener = mock.MagicMock()
        opener.open.side_effect = TimeoutError()
        with mock.patch.object(media, "build_opener", return_value=opener):
            with self.assertRaises(media.MetadataUnavailable):
                media._fetch("https://ext.nicovideo.jp/api/getthumbinfo/sm9", media.time.monotonic() + 10)
        opener.open.side_effect = None
        opener.open.return_value.__enter__.return_value.read.return_value = b"x" * (media.MAX_RESPONSE_BYTES + 1)
        with mock.patch.object(media, "build_opener", return_value=opener):
            with self.assertRaises(media.MetadataUnavailable):
                media._fetch("https://ext.nicovideo.jp/api/getthumbinfo/sm9", media.time.monotonic() + 10)

    def test_redirects_are_not_followed(self):
        self.assertIsNone(media._NoRedirect().redirect_request(None, None, 302, "", {}, "http://127.0.0.1/"))

    def test_xml_entities_are_rejected(self):
        with mock.patch.object(media, "_fetch", return_value=b'<!DOCTYPE foo><nicovideo_thumb_response status="ok"/>'):
            with self.assertRaises(media.MetadataUnavailable):
                media.video_metadata(self.item("niconico"))


if __name__ == "__main__":
    unittest.main()

