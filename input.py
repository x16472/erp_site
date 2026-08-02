"""前端輸入驗證層。

此模組只負責清理與驗證輸入；通過後由 app.py 交給 data.py 寫入
SQL Server，避免驗證、HTTP 與資料存取責任混在一起。
"""

from __future__ import annotations

import base64
import binascii
import re
from datetime import date
from typing import Any
from urllib.parse import parse_qs, urlparse

ALLOWED_CATEGORIES = {"出勤", "班級", "接送", "收費", "設備", "餐點", "其他"}
ALLOWED_THEMES = {"ocean", "sunrise", "forest"}
ALLOWED_CLOCK_ACTIONS = {"CLOCK_IN", "CLOCK_OUT"}
ALLOWED_ACCESS_MODES = {"CLOCK_IN", "ACCESS_ONLY"}
MAX_STAFF_PHOTO_BYTES = 5 * 1024 * 1024


class InputError(ValueError):
    """可安全顯示給前端的輸入錯誤。"""


def _text(value: Any, label: str, maximum: int, required: bool = True) -> str:
    result = str(value or "").strip()
    if required and not result:
        raise InputError(f"{label}不可空白")
    if len(result) > maximum:
        raise InputError(f"{label}不可超過 {maximum} 個字")
    return result


def _employee_id(value: Any) -> str:
    result = _text(value, "員工編號", 20).upper()
    if not re.fullmatch(r"[A-Z0-9_-]+", result):
        raise InputError("員工編號格式不正確")
    return result


def validate_operation(payload: dict[str, Any]) -> dict[str, Any]:
    category = _text(payload.get("category"), "類別", 10)
    if category not in ALLOWED_CATEGORIES:
        raise InputError("營運類別不正確")
    operation_date = _text(payload.get("date"), "日期", 10)
    try:
        date.fromisoformat(operation_date)
    except ValueError as exc:
        raise InputError("日期格式不正確") from exc
    campus = _text(payload.get("campus"), "園區代號", 12).upper()
    if not re.fullmatch(r"[A-Z0-9_-]+", campus):
        raise InputError("園區代號格式不正確")
    try:
        count = int(payload.get("count", 0))
    except (TypeError, ValueError) as exc:
        raise InputError("數量必須是整數") from exc
    if count < 0 or count > 9999:
        raise InputError("數量必須介於 0 到 9999")
    return {
        "date": operation_date,
        "campus": campus,
        "category": category,
        "count": count,
        "note": _text(payload.get("note"), "備註", 200, required=False),
    }


def validate_attendance(payload: dict[str, Any]) -> dict[str, str]:
    action = _text(payload.get("action"), "打卡類型", 20).upper()
    if action not in ALLOWED_CLOCK_ACTIONS:
        raise InputError("打卡類型不正確")
    return {"employee_id": _employee_id(payload.get("employee_id")), "action": action}


def validate_employee_access(payload: dict[str, Any]) -> dict[str, str]:
    mode = _text(payload.get("mode"), "進入方式", 20).upper()
    if mode not in ALLOWED_ACCESS_MODES:
        raise InputError("進入方式不正確")
    return {"employee_id": _employee_id(payload.get("employee_id")), "mode": mode}


def validate_staff(payload: dict[str, Any]) -> dict[str, Any]:
    age_value = payload.get("age")
    try:
        age = int(age_value) if str(age_value or "").strip() else None
    except (TypeError, ValueError) as exc:
        raise InputError("年齡必須是整數") from exc
    if age is not None and not 16 <= age <= 100:
        raise InputError("年齡必須介於 16 到 100")
    gender = _text(payload.get("gender"), "性別", 10, required=False)
    return {
        "employee_id": _employee_id(payload.get("employee_id")),
        "display_name": _text(payload.get("display_name"), "姓名", 50),
        "gender": gender,
        "age": age,
        "department": _text(payload.get("department"), "部門", 50),
        "position": _text(payload.get("position"), "職位", 50),
        "traits": _text(payload.get("traits"), "個性特質", 200, required=False),
        "biography": _text(payload.get("biography"), "背景簡述", 1000, required=False),
    }


def validate_staff_photo(value: Any) -> dict[str, Any] | None:
    """驗證前端上傳的員工照片，並依實際檔案特徵決定副檔名。"""
    if value in (None, ""):
        return None
    if not isinstance(value, dict):
        raise InputError("員工照片格式不正確")
    encoded = str(value.get("data", ""))
    match = re.fullmatch(r"data:image/(jpeg|png|webp);base64,([A-Za-z0-9+/=\r\n]+)", encoded)
    if not match:
        raise InputError("員工照片只接受 JPEG、PNG 或 WebP")
    try:
        content = base64.b64decode(match.group(2), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise InputError("員工照片內容無法解析") from exc
    if len(content) < 128 or len(content) > MAX_STAFF_PHOTO_BYTES:
        raise InputError("員工照片大小必須介於 128 Bytes 到 5 MB")
    signatures = {
        "jpg": content.startswith(b"\xff\xd8\xff"),
        "png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
    }
    extension = next((name for name, valid in signatures.items() if valid), "")
    expected = {"jpeg": "jpg", "png": "png", "webp": "webp"}[match.group(1)]
    if not extension or extension != expected:
        raise InputError("員工照片的格式與內容不一致")
    return {"content": content, "extension": extension}


def validate_youtube(payload: dict[str, Any]) -> dict[str, str]:
    """只接受 YouTube 網址，並轉成固定、安全的影片網址。"""
    raw_url = _text(payload.get("url"), "YouTube 網址", 500)
    try:
        parsed = urlparse(raw_url)
    except ValueError as exc:
        raise InputError("YouTube 網址格式不正確") from exc
    if parsed.scheme not in {"http", "https"}:
        raise InputError("YouTube 網址必須使用 http 或 https")
    host = (parsed.hostname or "").lower().removeprefix("www.")
    video_id = ""
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/", 1)[0]
    elif host in {"youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com"}:
        parts = [part for part in parsed.path.split("/") if part]
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        elif len(parts) >= 2 and parts[0] in {"embed", "live", "shorts"}:
            video_id = parts[1]
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise InputError("無法從網址辨識有效的 YouTube 影片")
    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    return {
        "video_id": video_id,
        "watch_url": watch_url,
        "embed_url": f"https://www.youtube.com/embed/{video_id}",
    }


def validate_site_settings(payload: dict[str, Any]) -> dict[str, str]:
    theme = _text(payload.get("theme"), "主題", 20)
    if theme not in ALLOWED_THEMES:
        raise InputError("網站主題不正確")
    return {
        "theme": theme,
        "hero_title": _text(payload.get("hero_title"), "首頁標題", 60),
        "hero_subtitle": _text(payload.get("hero_subtitle"), "首頁說明", 180),
        "announcement": _text(payload.get("announcement"), "公告", 160, required=False),
    }
