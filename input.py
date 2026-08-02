"""前端輸入驗證層。

此模組只負責清理與驗證輸入；通過後由 app.py 交給 data.py 寫入
SQL Server，避免驗證、HTTP 與資料存取責任混在一起。
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

ALLOWED_CATEGORIES = {"出勤", "班級", "接送", "收費", "設備", "餐點", "其他"}
ALLOWED_THEMES = {"ocean", "sunrise", "forest"}
ALLOWED_CLOCK_ACTIONS = {"CLOCK_IN", "CLOCK_OUT"}


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
