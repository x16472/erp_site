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

ALLOWED_CATEGORIES = {"出勤", "業務進度", "物流調度", "帳務", "設備", "餐飲服務", "其他"}
ALLOWED_THEMES = {"shield", "medal", "steel"}
ALLOWED_CLOCK_ACTIONS = {"CLOCK_IN", "CLOCK_OUT"}
ALLOWED_ACCESS_MODES = {"CLOCK_IN", "ACCESS_ONLY"}
ALLOWED_GENDERS = {"男", "女", "其他"}
MAX_STAFF_PHOTO_BYTES = 5 * 1024 * 1024
PRIVATE_NOTE_PATTERN = re.compile(
    r"(身分證|居留證|姓名|電話|手機|地址|電子郵件|e-?mail|"
    r"\b[A-Z][12]\d{8}\b|\b09\d{8}\b|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,})",
    re.IGNORECASE,
)


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
    campus = _text(payload.get("campus"), "營運據點代號", 12).upper()
    if not re.fullmatch(r"[A-Z0-9_-]+", campus):
        raise InputError("營運據點代號格式不正確")
    try:
        count = int(payload.get("count", 0))
    except (TypeError, ValueError) as exc:
        raise InputError("數量必須是整數") from exc
    if count < 0 or count > 9999:
        raise InputError("數量必須介於 0 到 9999")
    note = _text(payload.get("note"), "備註", 200, required=False)
    if PRIVATE_NOTE_PATTERN.search(note):
        raise InputError("備註不得包含可辨識個人的姓名、證件、電話、地址或電子郵件")
    return {
        "date": operation_date,
        "campus": campus,
        "category": category,
        "count": count,
        "note": note,
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
    """以 match-case 分欄驗證必填員工欄位，對應後端 switch-case 規則。"""
    result: dict[str, Any] = {}
    for field in ("employee_id", "display_name", "gender", "age", "department", "position"):
        match field:
            case "employee_id":
                result[field] = _employee_id(payload.get(field))
            case "display_name":
                result[field] = _text(payload.get(field), "姓名", 50)
            case "gender":
                gender = _text(payload.get(field), "性別", 10)
                if gender not in ALLOWED_GENDERS:
                    raise InputError("性別選項不正確")
                result[field] = gender
            case "age":
                try:
                    age = int(_text(payload.get(field), "年齡", 3))
                except (TypeError, ValueError) as exc:
                    raise InputError("年齡必須是整數") from exc
                if not 16 <= age <= 100:
                    raise InputError("年齡必須介於 16 到 100")
                result[field] = age
            case "department":
                result[field] = _text(payload.get(field), "部門", 5)
            case "position":
                result[field] = _text(payload.get(field), "職位", 50)
    result["traits"] = _text(payload.get("traits"), "個性特質", 200, required=False)
    result["biography"] = _text(payload.get("biography"), "背景簡述", 1000, required=False)
    return result


def validate_department(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        department_id = int(payload.get("id") or 0)
    except (TypeError, ValueError) as exc:
        raise InputError("部門編號不正確") from exc
    if department_id < 0:
        raise InputError("部門編號不正確")
    return {"id": department_id, "name": _text(payload.get("name"), "部門名稱", 5)}


def validate_operations_manual_state(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        document_id = int(payload.get("id"))
    except (TypeError, ValueError) as exc:
        raise InputError("營運SOP文件編號不正確") from exc
    if document_id <= 0 or not isinstance(payload.get("is_active"), bool):
        raise InputError("營運SOP文件狀態不正確")
    return {"id": document_id, "is_active": payload["is_active"]}


def validate_compliance_question(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        question_id = int(payload.get("id") or 0)
        document_id = int(payload.get("document_id") or 0) or None
        answer = int(payload.get("answer"))
    except (TypeError, ValueError) as exc:
        raise InputError("題目編號或答案設定不正確") from exc
    options_value = payload.get("options")
    if not isinstance(options_value, list):
        raise InputError("選項格式不正確")
    options = [_text(value, f"選項 {index + 1}", 200) for index, value in enumerate(options_value)]
    if not 2 <= len(options) <= 6:
        raise InputError("題目必須有 2 到 6 個選項")
    if not 0 <= answer < len(options):
        raise InputError("正確答案超出選項範圍")
    return {
        "id": question_id,
        "document_id": document_id,
        "category": _text(payload.get("category"), "題目分類", 50),
        "question": _text(payload.get("question"), "題目", 500),
        "options": options,
        "answer": answer,
        "explanation": _text(payload.get("explanation"), "答案解說", 1000),
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
