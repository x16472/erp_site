"""前端輸入驗證層。

此模組只負責清理與驗證輸入；通過後由 app.py 交給 data.py 寫入
SQL Server，避免驗證、HTTP 與資料存取責任混在一起。
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import uuid
from datetime import date
from typing import Any
from urllib.parse import parse_qs, urlparse

ALLOWED_CATEGORIES = {"出勤", "業務進度", "物流調度", "帳務", "設備", "餐飲服務", "其他"}
ALLOWED_THEMES = {"shield", "medal", "steel"}
ALLOWED_CLOCK_ACTIONS = {"CLOCK_IN", "CLOCK_OUT"}
ALLOWED_ACCESS_MODES = {"CLOCK_IN", "ACCESS_ONLY"}
ALLOWED_GENDERS = {"男", "女", "其他"}
ALLOWED_OPERATION_REVIEW_STATUSES = {"要求補件", "審核通過", "已退回"}
ALLOWED_QUESTION_TYPES = {"single_choice", "multiple_choice", "reading", "fill_blank", "matching", "essay"}
ALLOWED_QUESTION_DOMAINS = {"academic", "practical"}
ALLOWED_QUESTION_STATUSES = {"draft", "published", "disabled"}
ALLOWED_TRAINING_MODES = {"practice", "mock"}
ALLOWED_ESSAY_REVIEW_STATUSES = {"審核通過", "需修正"}
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


def validate_operation_reply(payload: dict[str, Any]) -> dict[str, str]:
    return {
        "id": _text(payload.get("id"), "營運日報編號", 40),
        "message": _text(payload.get("message"), "回覆內容", 1000),
    }


def validate_operation_review(payload: dict[str, Any]) -> dict[str, str]:
    status = _text(payload.get("status"), "審閱狀態", 20)
    if status not in ALLOWED_OPERATION_REVIEW_STATUSES:
        raise InputError("審閱狀態不正確")
    message = _text(payload.get("message"), "審閱意見", 1000, required=status == "要求補件")
    return {
        "id": _text(payload.get("id"), "營運日報編號", 40),
        "status": status,
        "message": message,
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
        raise InputError("SOP文件編號不正確") from exc
    if document_id <= 0 or not isinstance(payload.get("is_active"), bool):
        raise InputError("SOP文件狀態不正確")
    return {"id": document_id, "is_active": payload["is_active"]}


def _require_published(status: str, condition: bool, message: str) -> None:
    """只有 status == 'published' 才強制檢查"""
    if status == "published" and not condition:
        raise InputError(message)


def _validate_choice_type(
    question_type: str,
    options: list[str],
    answers: list[int],
    status: str,
) -> None:
    _require_published(
        status,
        2 <= len(options) <= 6,
        "選擇題必須有 2 到 6 個選項",
    )
    _require_published(
        status,
        bool(answers) and all(0 <= a < len(options) for a in answers),
        "正確答案超出選項範圍",
    )
    if question_type in {"single_choice", "reading"}:
        _require_published(
            status,
            len(answers) == 1,
            "單選題與閱讀測驗只能設定一個正確答案",
        )


def _validate_essay(options: list, answers: list) -> None:
    if options or answers:
        raise InputError("申論題不可設定選項或標準答案")


def _validate_reading(passage: str, status: str) -> None:
    _require_published(status, bool(passage), "閱讀測驗必須提供閱讀文章")


def _validate_structure(
    question_type: str,
    structure: dict,
    answers: list,
    status: str,
) -> None:
    if question_type == "fill_blank":
        key = "blanks"
    elif question_type == "matching":
        key = "left"
    else:
        return

    _require_published(
        status,
        bool(structure.get(key)) and bool(answers),
        "發布前必須完成題型結構與正確答案",
    )


def validate_compliance_question(payload: dict[str, Any]) -> dict[str, Any]:
    # --- 基本 ID 與必要欄位 ---
    try:
        question_id = int(payload.get("id") or 0)
        document_id = int(payload.get("document_id") or 0) or None
        subject_id = int(payload.get("subject_id") or 0)
        chapter_id = int(payload.get("chapter_id") or 0)
    except (TypeError, ValueError) as exc:
        raise InputError("題目或文件編號不正確") from exc

    if subject_id <= 0 or chapter_id <= 0:
        raise InputError("請選擇科目與章節")

    domain = _text(payload.get("domain") or "academic", "題庫領域", 20)
    if domain not in ALLOWED_QUESTION_DOMAINS:
        raise InputError("題庫領域不正確")

    question_type = _text(payload.get("question_type") or "single_choice", "題型", 30)
    if question_type not in ALLOWED_QUESTION_TYPES:
        raise InputError("題型不正確")

    if (domain == "practical") != (question_type == "essay"):
        raise InputError("術科僅能使用申論題，申論題也必須歸入術科")

    status = _text(payload.get("status") or "draft", "題目狀態", 20)
    if status not in ALLOWED_QUESTION_STATUSES:
        raise InputError("題目狀態不正確")

    # --- options ---
    options_value = payload.get("options")
    if not isinstance(options_value, list):
        raise InputError("選項格式不正確")
    options = [_text(v, f"選項 {i + 1}", 1000) for i, v in enumerate(options_value)]

    # --- answers ---
    answers_value = payload.get("answers", [])
    if not isinstance(answers_value, list):
        raise InputError("正確答案格式不正確")

    if question_type in {"single_choice", "multiple_choice", "reading"}:
        try:
            answers = sorted({int(v) for v in answers_value})
        except (TypeError, ValueError) as exc:
            raise InputError("正確答案格式不正確") from exc
    else:
        answers = [_text(v, f"答案 {i + 1}", 1000) for i, v in enumerate(answers_value)]

    passage = _text(payload.get("passage"), "閱讀文章", 5000, required=False)

    # --- 依題型驗證 ---
    if question_type == "essay":
        _validate_essay(options, answers)
    elif question_type in {"single_choice", "multiple_choice", "reading"}:
        _validate_choice_type(question_type, options, answers, status)
        if question_type == "reading":
            _validate_reading(passage, status)

    # --- content_blocks ---
    content_blocks_value = payload.get("content_blocks")
    if content_blocks_value in (None, []):
        content_blocks = [
            {"type": "text", "content": _text(payload.get("question"), "題目", 500)}
        ]
    elif not isinstance(content_blocks_value, list):
        raise InputError("題目內容格式不正確")
    else:
        content_blocks = []
        for i, block in enumerate(content_blocks_value):
            if not isinstance(block, dict) or block.get("type") not in {"text", "code"}:
                raise InputError("題目內容只支援文字與程式碼區塊")
            content_blocks.append({
                "type": block["type"],
                "content": _text(block.get("content"), f"內容區塊 {i + 1}", 5000),
            })

    # --- structure ---
    structure = payload.get("structure") or {}
    if not isinstance(structure, dict):
        raise InputError("題型結構不正確")

    _validate_structure(question_type, structure, answers, status)

    return {
        "id": question_id,
        "document_id": document_id,
        "subject_id": subject_id,
        "chapter_id": chapter_id,
        "domain": domain,
        "question_type": question_type,
        "category": _text(payload.get("category"), "題目分類", 50, required=False),
        "chapter_name": _text(payload.get("chapter_name"), "章節名稱", 120, required=False),
        "question": _text(payload.get("question"), "題目", 500),
        "content_blocks": content_blocks,
        "structure": structure,
        "passage": passage,
        "options": options,
        "answers": answers,
        "status": status,
        "explanation": _text(
            payload.get("explanation"),
            "答案解說",
            1000,
            required=status == "published" and question_type != "essay",
        ),
    }
def _positive_int_list(value: Any, label: str) -> list[int]:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise InputError(f"{label}格式不正確")
    try:
        result = sorted({int(item) for item in value})
    except (TypeError, ValueError) as exc:
        raise InputError(f"{label}格式不正確") from exc
    if any(item <= 0 for item in result):
        raise InputError(f"{label}格式不正確")
    return result


def validate_training_start(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        subject_id = int(payload.get("subject_id"))
        question_count = int(10 if payload.get("question_count") in (None, "") else payload.get("question_count"))
    except (TypeError, ValueError) as exc:
        raise InputError("科目或題數不正確") from exc
    mode = _text(payload.get("mode") or "practice", "作答模式", 20)
    if mode not in ALLOWED_TRAINING_MODES or subject_id <= 0:
        raise InputError("作答模式或科目不正確")
    if question_count not in {0, 10, 20}:
        raise InputError("練習題數只接受 10、20 或全部")
    question_types_value = payload.get("question_types") or []
    if not isinstance(question_types_value, list):
        raise InputError("題型篩選格式不正確")
    question_types = sorted({str(value) for value in question_types_value})
    allowed_academic = ALLOWED_QUESTION_TYPES - {"essay"}
    if any(value not in allowed_academic for value in question_types):
        raise InputError("題型篩選不正確")
    return {
        "subject_id": subject_id,
        "mode": mode,
        "question_count": question_count,
        "chapter_ids": _positive_int_list(payload.get("chapter_ids"), "章節篩選"),
        "source_ids": _positive_int_list(payload.get("source_ids"), "來源篩選"),
        "question_types": question_types,
    }


def _session_id(value: Any) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise InputError("作答階段編號不正確") from exc


def validate_training_answer(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        order = int(payload.get("order"))
    except (TypeError, ValueError) as exc:
        raise InputError("題號不正確") from exc
    response = payload.get("response") or {}
    if not isinstance(response, dict) or not isinstance(response.get("answers", []), list):
        raise InputError("作答內容格式不正確")
    if order <= 0 or len(json.dumps(response, ensure_ascii=False)) > 12000:
        raise InputError("作答內容不正確或過長")
    return {
        "session_id": _session_id(payload.get("session_id")),
        "order": order,
        "response": response,
        "flagged": bool(payload.get("flagged")),
    }


def validate_training_session_action(payload: dict[str, Any]) -> str:
    return _session_id(payload.get("session_id"))


def validate_training_wrong_remove(payload: dict[str, Any]) -> int:
    try:
        question_id = int(payload.get("question_id"))
    except (TypeError, ValueError) as exc:
        raise InputError("題目編號不正確") from exc
    if question_id <= 0:
        raise InputError("題目編號不正確")
    return question_id


def validate_training_subject(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        subject_id = int(payload.get("id") or 0)
        question_count = int(payload.get("mock_question_count") or 40)
        duration = int(payload.get("mock_duration_minutes") or 45)
        pass_score = int(payload.get("mock_pass_score") or 70)
    except (TypeError, ValueError) as exc:
        raise InputError("科目設定格式不正確") from exc
    domain = _text(payload.get("domain"), "題庫領域", 20)
    if domain not in ALLOWED_QUESTION_DOMAINS:
        raise InputError("題庫領域不正確")
    if domain == "academic" and not (1 <= question_count <= 200 and 1 <= duration <= 300 and 1 <= pass_score <= 100):
        raise InputError("模考設定超出允許範圍")
    if domain == "practical":
        question_count = duration = pass_score = 0
    return {
        "id": subject_id,
        "domain": domain,
        "name": _text(payload.get("name"), "科目名稱", 100),
        "mock_question_count": question_count,
        "mock_duration_minutes": duration,
        "mock_pass_score": pass_score,
        "is_active": bool(payload.get("is_active", True)),
    }


def validate_training_chapter(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        chapter_id = int(payload.get("id") or 0)
        subject_id = int(payload.get("subject_id"))
        display_order = int(payload.get("display_order") or 0)
    except (TypeError, ValueError) as exc:
        raise InputError("章節設定格式不正確") from exc
    code = _text(payload.get("code"), "章節代碼", 30).upper()
    if not re.fullmatch(r"[A-Z0-9_-]+", code) or subject_id <= 0 or not 0 <= display_order <= 9999:
        raise InputError("章節設定不正確")
    return {
        "id": chapter_id,
        "subject_id": subject_id,
        "code": code,
        "name": _text(payload.get("name"), "章節名稱", 120),
        "display_order": display_order,
        "is_active": bool(payload.get("is_active", True)),
    }


def validate_training_question_status(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        question_id = int(payload.get("id"))
    except (TypeError, ValueError) as exc:
        raise InputError("題目編號不正確") from exc
    status = _text(payload.get("status"), "題目狀態", 20)
    if question_id <= 0 or status not in ALLOWED_QUESTION_STATUSES:
        raise InputError("題目狀態不正確")
    return {"id": question_id, "status": status}


def validate_training_question_bulk(payload: dict[str, Any]) -> dict[str, Any]:
    ids = _positive_int_list(payload.get("ids"), "題目清單")
    if not ids or len(ids) > 500:
        raise InputError("請選擇 1 至 500 題")
    status_value = str(payload.get("status") or "").strip()
    if status_value and status_value not in ALLOWED_QUESTION_STATUSES:
        raise InputError("批次狀態不正確")
    try:
        subject_id = int(payload.get("subject_id") or 0) or None
        chapter_id = int(payload.get("chapter_id") or 0) or None
    except (TypeError, ValueError) as exc:
        raise InputError("批次分類格式不正確") from exc
    if bool(chapter_id) != bool(subject_id):
        raise InputError("批次分類必須同時指定科目與章節")
    if not status_value and not subject_id:
        raise InputError("請指定要套用的狀態或分類")
    return {"ids": ids, "status": status_value or None, "subject_id": subject_id, "chapter_id": chapter_id}


def validate_compliance_answer(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        question_id = int(payload.get("question_id"))
    except (TypeError, ValueError) as exc:
        raise InputError("題目編號不正確") from exc
    answers_value = payload.get("answers", [])
    if not isinstance(answers_value, list):
        raise InputError("作答格式不正確")
    try:
        answers = sorted({int(value) for value in answers_value})
    except (TypeError, ValueError) as exc:
        raise InputError("作答格式不正確") from exc
    return {
        "question_id": question_id,
        "answers": answers,
        "answer_text": _text(payload.get("answer_text"), "申論答案", 5000, required=False),
    }


def validate_essay_review(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        answer_id = int(payload.get("id"))
    except (TypeError, ValueError) as exc:
        raise InputError("申論答案編號不正確") from exc
    status = _text(payload.get("status"), "審核狀態", 20)
    if status not in ALLOWED_ESSAY_REVIEW_STATUSES:
        raise InputError("申論審核狀態不正確")
    return {
        "id": answer_id,
        "status": status,
        "feedback": _text(payload.get("feedback"), "審核回饋", 1000, required=status == "需修正"),
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
