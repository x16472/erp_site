"""前端輸入驗證與園務資料蒐集佇列。"""

from __future__ import annotations

import json
import re
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.resolve()
QUEUE_PATH = ROOT / "data" / "operation_submissions.json"
_queue_lock = threading.Lock()

ALLOWED_CATEGORIES = {"出勤", "班級", "接送", "收費", "設備", "餐點", "其他"}
ALLOWED_THEMES = {"ocean", "sunrise", "forest"}


class InputError(ValueError):
    """可安全顯示給前端的輸入錯誤。"""


def _text(value: Any, label: str, maximum: int, required: bool = True) -> str:
    result = str(value or "").strip()
    if required and not result:
        raise InputError(f"{label}不可空白")
    if len(result) > maximum:
        raise InputError(f"{label}不可超過 {maximum} 個字")
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
    campus = _text(payload.get("campus"), "園區代號", 12)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", campus):
        raise InputError("園區代號格式不正確")
    try:
        count = int(payload.get("count", 0))
    except (TypeError, ValueError) as exc:
        raise InputError("數量必須是整數") from exc
    if count < 0 or count > 9999:
        raise InputError("數量必須介於 0 到 9999")
    return {
        "id": f"OPS-{datetime.now():%Y%m%d%H%M%S%f}",
        "date": operation_date,
        "campus": campus.upper(),
        "category": category,
        "count": count,
        "note": _text(payload.get("note"), "備註", 200, required=False),
        "submitted_at": datetime.now().isoformat(timespec="seconds"),
        "status": "待審核",
    }


def add_operation(payload: dict[str, Any]) -> dict[str, Any]:
    item = validate_operation(payload)
    with _queue_lock:
        QUEUE_PATH.parent.mkdir(exist_ok=True)
        items = []
        if QUEUE_PATH.exists():
            try:
                loaded = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
                items = loaded if isinstance(loaded, list) else []
            except (json.JSONDecodeError, OSError):
                items = []
        items.insert(0, item)
        temporary = QUEUE_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(items[:500], ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(QUEUE_PATH)
    return item


def list_operations() -> list[dict[str, Any]]:
    with _queue_lock:
        if not QUEUE_PATH.exists():
            return []
        try:
            loaded = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
            return loaded if isinstance(loaded, list) else []
        except (json.JSONDecodeError, OSError):
            return []


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
