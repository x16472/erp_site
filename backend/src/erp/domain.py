"""銀盾共同體業務流程，透過 Go gRPC 查詢目錄存取資料。
公開與管理員回應依各自的欄位白名單及權限輸出。
"""
from __future__ import annotations

import json
import threading
import uuid
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from . import time_sync as time

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PAGE_ROOT = PROJECT_ROOT / "page"
_REQUEST_CONNECTIONS = threading.local()

from . import database_client as database


class DatabaseUnavailable(RuntimeError):
    """資料庫無法連線或查詢時使用的安全例外。"""


def _new_connection(read_only: bool, autocommit: bool):
    """透過 Go 資料庫服務取得目前請求專屬的連線代碼。"""
    try:
        return database.connect(read_only=read_only, autocommit=autocommit)
    except database.Error as exc:
        raise DatabaseUnavailable("無法取得 Go 資料庫連線。") from exc


@contextmanager
def connect(read_only: bool = True, autocommit: bool = True):
    """借用 SQL Server 連線；請求內的連線由 connection_scope 統一釋放。"""
    connections = getattr(_REQUEST_CONNECTIONS, "connections", None)
    if connections is None:
        with _new_connection(read_only, autocommit) as connection:
            yield connection
        return

    key = (read_only, autocommit)
    connection = connections.get(key)
    if connection is None:
        connection = _new_connection(read_only, autocommit)
        connections[key] = connection
    try:
        yield connection
    except BaseException:
        # 查詢失敗後不再借出可能已失效或處於未完成交易的連線。
        connections.pop(key, None)
        try:
            connection.close()
        except database.Error:
            pass
        raise


@contextmanager
def connection_scope():
    """在單一 HTTP 請求內複用連線，並於請求完成後確實釋放。"""
    if getattr(_REQUEST_CONNECTIONS, "connections", None) is not None:
        yield
        return

    connections: dict[tuple[bool, bool], Any] = {}
    _REQUEST_CONNECTIONS.connections = connections
    try:
        yield
    finally:
        del _REQUEST_CONNECTIONS.connections
        for connection in connections.values():
            try:
                connection.close()
            except database.Error:
                pass


def admin_credentials() -> tuple[str, str]:
    """取得 後台管理員帳密，只供後端比對，永不傳送至前端。"""
    try:
        return database.admin_credentials()
    except database.Error as exc:
        raise DatabaseUnavailable("無法取得管理員驗證設定。") from exc


def _fetch(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    """執行固定的唯讀查詢並轉為可序列化字典。"""
    try:
        with connect() as db:
            cursor = db.cursor()
            cursor.execute(query, params)
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, (_json_value(value) for value in row))) for row in cursor.fetchall()]
    except DatabaseUnavailable:
        raise
    except database.Error as exc:
        raise DatabaseUnavailable("SQL Server 查詢失敗，請檢查連線與資料表結構。") from exc


def _json_value(value: Any) -> Any:
    """將 SQL Server 型別轉成 JSON 可傳輸格式。"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.hex()[:32]
    return str(value)


def _quote_identifier(value: str) -> str:
    """引用已由資料庫中繼資料驗證過的識別名稱。"""
    return f"[{value.replace(']', ']]')}]"


def _resolve_table(table_name: str) -> tuple[str, str]:
    """僅解析銀盾共同體白名單內的應用資料表。"""
    if table_name not in APPLICATION_TABLES:
        raise ValueError("只允許查閱銀盾共同體應用資料表")
    matches = _fetch('domain._resolve_table.1', (table_name,))
    if len(matches) != 1:
        raise ValueError("找不到指定的資料表")
    return matches[0]["schema_name"], matches[0]["table_name"]


HIGHLY_SENSITIVE_KEYWORDS = (
    "身分證", "居留證", "銀行帳號", "帳戶姓名", "戶籍地址", "通訊地址",
    "聯絡電話", "通訊電話", "行動電話", "緊急聯絡", "薪資", "底薪",
    "津貼", "加給", "所得稅", "投保金額", "勞保金額", "健保費", "勞保費",
    "交易費", "服務費", "成本", "費用", "折扣", "減免", "應收金額", "實收金額",
)
PERSONAL_KEYWORDS = ("姓名", "出生日期", "血型", "電話", "地址", "員工編號", "客戶編號")
RESTRICTED_TABLE_KEYWORDS = ("薪資", "銀行", "健保", "勞保", "其他收入", "異動金額")


def _classification(column_name: str, table_name: str = "") -> str:
    """依資料表欄位推導查閱分類。"""
    if any(keyword in table_name for keyword in RESTRICTED_TABLE_KEYWORDS):
        return "restricted"
    if any(keyword in column_name for keyword in HIGHLY_SENSITIVE_KEYWORDS):
        return "restricted"
    if any(keyword in column_name for keyword in PERSONAL_KEYWORDS):
        return "personal"
    return "internal"


def _mask_value(column_name: str, value: Any, level: str | None = None) -> Any:
    """敏感欄位一律在後端遮罩，原始值不進入 HTTP 回應。"""
    if value is None:
        return None
    level = level or _classification(column_name)
    if level == "restricted":
        return "••••••"
    if level == "personal":
        text = str(value)
        if "姓名" in column_name and len(text) >= 2:
            return text[0] + "○" * max(1, len(text) - 2) + text[-1]
        if len(text) <= 3:
            return text[0] + "••"
        return text[:2] + "••••" + text[-2:]
    return value


def table_catalog() -> list[dict[str, Any]]:
    """只列出目前資料庫允許查閱的 Company 應用資料表。"""
    rows = _fetch('domain.table_catalog.1')
    allowed_rows = [row for row in rows if row["schema"] == "dbo" and row["name"] in APPLICATION_TABLES]
    for row in allowed_rows:
        row["display_name"] = TABLE_DISPLAY_NAMES.get(row["name"], row["name"])
    return allowed_rows


def table_data(table_name: str, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    """唯讀分頁查閱資料表；資料表名稱先比對中繼資料，敏感值再遮罩。"""
    page = max(1, int(page))
    page_size = min(50, max(5, int(page_size)))
    schema_name, verified_name = _resolve_table(table_name)
    columns = _fetch('domain.table_data.1', (schema_name, verified_name))
    if verified_name == "Company_TrainingQuestion":
        columns = [column for column in columns if column["name"].lower() not in {"id", "questionno", "question_id"}]
    for column in columns:
        column["classification"] = _classification(column["name"], verified_name)

    identifiers = ", ".join(_quote_identifier(column["name"]) for column in columns)
    qualified = f"{_quote_identifier(schema_name)}.{_quote_identifier(verified_name)}"
    offset = (page - 1) * page_size
    raw_rows = _fetch(
        database.statement('domain.table_data.2', identifiers, qualified),
        (offset, page_size),
    ) if columns else []
    rows = [
        {column["name"]: _mask_value(column["name"], row.get(column["name"]), column["classification"]) for column in columns}
        for row in raw_rows
    ]
    total = int(_fetch(database.statement('domain.table_data.3', qualified))[0]["count"])
    return {
        "schema": schema_name,
        "table": verified_name,
        "page": page,
        "page_size": page_size,
        "total": total,
        "columns": columns,
        "rows": rows,
        "read_only": True,
    }


def _count(table: str) -> int:
    """僅統計附圖列出的應用資料表，不接受其他資料庫表名。"""
    if table not in APPLICATION_TABLES:
        raise ValueError("不允許查詢此資料表")
    return int(_fetch(database.statement('domain._count.1', table))[0]["筆數"])


def health() -> dict[str, Any]:
    """回傳資料庫與銀盾應用表健康狀態。"""
    info = _fetch('domain.health.1')[0]
    return {"status": "ok", "source": "mssql", "database": info["資料庫"], "table_count": len(table_catalog()), "mode": "company-only"}


DEFAULT_SITE_SETTINGS = {
    "theme": "shield",
    "hero_title": "銀盾共同體｜誠信連結每一份事業",
    "hero_subtitle": "以家族為核心、誠信與慷慨為本，整合行政、商務、生產與資源服務，讓成員共享成果並拓展事業。",
    "announcement": "LIVE AND LET LIVE.｜共生、誠信、共享成果。",
}


def site_settings() -> dict[str, str]:
    """讀取網站設定；管理資料表尚未建立時使用安全預設值。"""
    exists = _fetch('domain.site_settings.1')[0]["exists"]
    if not exists:
        return dict(DEFAULT_SITE_SETTINGS)
    rows = _fetch('domain.site_settings.2')
    return {**DEFAULT_SITE_SETTINGS, **(rows[0] if rows else {})}


def save_site_settings(settings: dict[str, str], actor: str) -> dict[str, str]:
    """只寫入網站專屬設定表，不接受任意資料表或 SQL。"""
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            cursor.execute('domain.save_site_settings.1', settings["theme"], settings["hero_title"], settings["hero_subtitle"], settings["announcement"], actor,
                 settings["theme"], settings["hero_title"], settings["hero_subtitle"], settings["announcement"], actor)
            db.commit()
        return settings
    except database.Error as exc:
        raise DatabaseUnavailable("網站設定寫入失敗，請確認管理帳號的資料表權限。") from exc


def public_overview() -> dict[str, Any]:
    """官方網站可公開的設定與 Company 應用資料彙總。"""
    return {
        "settings": site_settings(),
        "stats": [
            {"label": "專業成員", "value": int(_fetch('domain.public_overview.1')[0]["count"])},
            {"label": "營運部門", "value": int(_fetch('domain.public_overview.2')[0]["count"])},
            {"label": "營運SOP", "value": int(_fetch('domain.public_overview.3')[0]["count"])},
        ],
    }


def dashboard() -> dict[str, Any]:
    """回傳只依附圖所列資料表產生的工作台彙總。"""
    return {
        "metrics": [
            {"label": "在職員工", "value": int(_fetch('domain.dashboard.1')[0]["count"]), "unit": "位", "tone": "green"},
            {"label": "本日打卡", "value": int(_fetch('domain.dashboard.2')[0]["count"]), "unit": "筆", "tone": "blue"},
            {"label": "待審日報", "value": int(_fetch('domain.dashboard.3')[0]["count"]), "unit": "筆", "tone": "amber"},
            {"label": "營運SOP", "value": int(_fetch('domain.dashboard.4')[0]["count"]), "unit": "份", "tone": "purple"},
        ],
        "departments": departments(),
        "branches": branches(),
        "classes": [],
        "data_domains": [],
    }


def departments() -> list[dict[str, Any]]:
    """回傳可用部門清單。"""
    return _fetch('domain.departments.1')


def branches() -> list[dict[str, Any]]:
    """回傳四大固定營運據點及各據點既有日報數量。"""
    return _fetch('domain.branches.1')


def operation_categories() -> list[dict[str, Any]]:
    """提供資料庫中可供日報填報的類別與排序。"""
    return _fetch('domain.operation_categories.1')


def operations_process() -> list[dict[str, Any]]:
    """以營運分類與待審日報呈現目前可用的生命週期。"""
    return _fetch('domain.operations_process.1')


def knowledge() -> list[dict[str, Any]]:
    """新資料庫未提供獨立知識主檔，工作台保留空結果等待後續建檔。"""
    return []


def _default_questions() -> list[dict[str, Any]]:
    """提供不含實際員工或客戶資料的商業營運檢核題目。"""
    return []


APPLICATION_TABLES = (
    "Company_WebSettings", "Company_Department", "Company_Staff", "Company_Attendance",
        "Company_OperationCategory", "Company_OperationSubmission",
    "Company_TrainingDocument", "Company_TrainingSection", "Company_TrainingQuestion",
    "Company_ImportState",
)
WORKFLOW_TABLES = (
    "Company_OperationActivity", "Company_TrainingAnswer", "Company_TrainingSubject",
    "Company_TrainingChapter", "Company_TrainingSession",
    "Company_TrainingSessionQuestion", "Company_TrainingWrongQuestion",
)

# 對外顯示使用企業語意，實際查詢仍以 Company_* 白名單為準。
TABLE_DISPLAY_NAMES = {
    "Company_WebSettings": "網站設定",
    "Company_Department": "部門主檔",
    "Company_Staff": "員工主檔",
    "Company_Attendance": "出缺勤紀錄",
    "Company_OperationCategory": "營運分類",
        "Company_OperationSubmission": "營運日報",
    "Company_TrainingDocument": "SOP文件",
    "Company_TrainingSection": "SOP文件段落",
    "Company_TrainingQuestion": "營運題庫",
        "Company_ImportState": "資料匯入狀態",
}

def _migrate_business_seed_data(cursor) -> None:
    """確保銀盾共同體的七種營運分類存在且排序一致。"""
    desired_categories = ("出勤", "業務進度", "物流調度", "帳務", "設備", "餐飲服務", "其他")
    cursor.execute('domain._migrate_business_seed_data.1')
    for order, category in enumerate(desired_categories, 1):
        cursor.execute(
            'domain._migrate_business_seed_data.2',
            category,
            category,
            order,
        )
    for order, category in enumerate(desired_categories, 1):
        cursor.execute('domain._migrate_business_seed_data.3', order, category)
    cursor.execute('domain._migrate_business_seed_data.4')
    cursor.execute(
        'domain._migrate_business_seed_data.5'
    )


def _normalize_company_departments(cursor) -> None:
    """確保六個短名稱部門存在，並停用沒有在職員工的部門。"""
    for department_name in ("營運部", "製造部", "財務部", "資訊部", "研發部", "業務部"):
        cursor.execute(
            'domain._normalize_company_departments.1',
            department_name,
            department_name,
        )
    cursor.execute(
        'domain._normalize_company_departments.2'
    )


def initialize_business_data() -> dict[str, Any]:
    """在 Go 完成建表後，初始化既有分類與來源資料並回傳狀態。"""
    try:
        with connect(read_only=False, autocommit=False) as db:
            cursor = db.cursor()
            _migrate_business_seed_data(cursor)
            cursor.execute('domain.ensure_application_schema.1')
            academic_subject_id = cursor.execute(
                'domain.ensure_application_schema.2'
            ).fetchone()[0]
            practical_subject_id = cursor.execute(
                'domain.ensure_application_schema.3'
            ).fetchone()[0]
            for subject_id in (academic_subject_id, practical_subject_id):
                cursor.execute('domain.ensure_application_schema.4', subject_id, subject_id)
            count = cursor.execute('domain.ensure_application_schema.5').fetchone()[0]
            if not count:
                for item in _default_questions():
                    cursor.execute('domain.ensure_application_schema.6', item["category"], item["question"], json.dumps(item["options"], ensure_ascii=False),
                         item["answer"], item["explanation"], json.dumps([item["answer"]]))
            academic_chapter_id = cursor.execute(
                'domain.ensure_application_schema.7',
                academic_subject_id,
            ).fetchone()[0]
            practical_chapter_id = cursor.execute(
                'domain.ensure_application_schema.8',
                practical_subject_id,
            ).fetchone()[0]
            cursor.execute('domain.ensure_application_schema.9', practical_subject_id, academic_subject_id, practical_chapter_id, academic_chapter_id)
            _normalize_company_departments(cursor)
            cursor.execute('domain.ensure_application_schema.10')
            db.commit()
        return {"tables": list(APPLICATION_TABLES + WORKFLOW_TABLES), "status": "ready"}
    except database.Error as exc:
        raise DatabaseUnavailable("網站應用資料表建立失敗，請確認資料庫帳號具備建表權限。") from exc


def _staff_order(sort_by: str) -> str:
    """依白名單排序選項建立查詢代碼與受限選項。"""
    if sort_by == "department":
        return "department, employee_id"
    if sort_by in {"", "employee_id"}:
        return "employee_id"
    raise ValueError("員工排序方式不正確")


def public_staff(department: str = "") -> list[dict[str, Any]]:
    """僅回傳適合官網公開的員工基本介紹。"""
    return _fetch('domain.public_staff.1', (department, department))


def public_staff_departments() -> list[dict[str, Any]]:
    """提供官網部門選單，部門順序依各部門最前面的員工編號決定。"""
    return _fetch('domain.public_staff_departments.1')


def attendance_staff_options(sort_by: str = "employee_id") -> list[dict[str, Any]]:
    """提供員工工作台打卡選單；不包含年齡、背景等管理欄位。"""
    return _fetch(database.statement('domain.attendance_staff_options.1', _staff_order(sort_by)))


def staff_records() -> list[dict[str, Any]]:
    """取得管理員可查閱的員工欄位與狀態。"""
    return _fetch('domain.staff_records.1')


def employee_identity(employee_id: str) -> dict[str, Any]:
    """以 SQL Server 員工主檔驗證工作台登入身分。"""
    rows = _fetch('domain.employee_identity.1', (employee_id,))
    if not rows:
        raise ValueError("員工編號不存在或已停用")
    return rows[0]


def server_time() -> dict[str, Any]:
    """回傳 SQL Server 權威時間，供前端以網路往返時間校準本機時鐘。"""
    try:
        with connect() as db:
            current = time.now(db.cursor())
        return {
            "current_time": current["iso_time"],
            "unix_ms": current["unix_ms"],
            "work_date": current["work_date"].isoformat(),
            "source": "SERVER_CLOCK",
        }
    except database.Error as exc:
        raise DatabaseUnavailable("無法取得 SQL Server 校時資料。") from exc


def attendance_status(employee_id: str) -> dict[str, Any] | None:
    """只回傳員工當日最後一筆打卡，供不打卡登入與工作台提示。"""
    rows = _fetch('domain.attendance_status.1', (employee_id,))
    return rows[0] if rows else None


def admin_departments() -> list[dict[str, Any]]:
    """回傳員工維護使用的部門清單。"""
    return _fetch('domain.admin_departments.1')


def save_department(item: dict[str, Any], actor: str) -> dict[str, Any]:
    """在交易中儲存部門並維持員工部門關聯。"""
    try:
        with connect(read_only=False, autocommit=False) as db:
            cursor = db.cursor()
            if item["id"]:
                old = cursor.execute(
                    'domain.save_department.1',
                    item["id"],
                ).fetchone()
                if not old:
                    raise ValueError("找不到指定部門")
                cursor.execute('domain.save_department.2', item["name"], actor, item["id"])
                if old[0] != item["name"]:
                    cursor.execute(
                        'domain.save_department.3',
                        item["name"], actor, old[0],
                    )
                department_id = item["id"]
            else:
                row = cursor.execute('domain.save_department.4', item["name"]).fetchone()
                if row:
                    cursor.execute('domain.save_department.5', actor, row[0])
                    department_id = row[0]
                else:
                    department_id = cursor.execute('domain.save_department.6', item["name"], actor).fetchone()[0]
            db.commit()
        return {"id": department_id, "name": item["name"], "is_active": True}
    except database.IntegrityError as exc:
        raise ValueError("部門名稱已存在") from exc
    except database.Error as exc:
        raise DatabaseUnavailable("部門資料儲存失敗。") from exc


def deactivate_department(department_id: int, actor: str) -> dict[str, Any]:
    """停用指定部門並保留既有歷史紀錄。"""
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            row = cursor.execute('domain.deactivate_department.1', department_id).fetchone()
            if not row:
                raise ValueError("找不到指定部門")
            if row[1]:
                raise ValueError("此部門仍有在職員工，無法停用")
            cursor.execute('domain.deactivate_department.2', actor, department_id)
        return {"id": department_id, "is_active": False}
    except database.Error as exc:
        raise DatabaseUnavailable("部門停用失敗。") from exc


def save_staff(item: dict[str, Any], actor: str, photo_file: str | None = None) -> dict[str, Any]:
    """儲存已驗證的員工資料並回傳結果。"""
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            department = cursor.execute('domain.save_staff.1', item["department"]).fetchone()
            if not department:
                raise ValueError("請選擇有效的部門")
            existing = cursor.execute(
                'domain.save_staff.2',
                item["employee_id"],
            ).fetchone()
            photo = photo_file if photo_file is not None else (existing[0] if existing else None)
            cursor.execute('domain.save_staff.3', item["employee_id"], item["display_name"], item["gender"], item["age"], item["department"], item["position"], item["traits"], item["biography"], photo, actor,
                 item["employee_id"], item["display_name"], item["gender"], item["age"], item["department"], item["position"], item["traits"], item["biography"], photo, actor)
        return {**item, "photo_file": photo, "is_active": True}
    except database.Error as exc:
        raise DatabaseUnavailable("員工資料儲存失敗。") from exc


def deactivate_staff(employee_id: str, actor: str) -> dict[str, Any]:
    """停用指定員工，不刪除其業務紀錄。"""
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            cursor.execute('domain.deactivate_staff.1', actor, employee_id)
            if cursor.rowcount == 0:
                raise ValueError("找不到指定員工")
        return {"employee_id": employee_id, "is_active": False}
    except database.Error as exc:
        raise DatabaseUnavailable("員工資料停用失敗。") from exc


def _validate_attendance_sequence(last_action: str | None, new_action: str) -> None:
    """打卡必須以上班開始，並依上班、下班順序交替。"""
    if last_action is None and new_action == "CLOCK_OUT":
        raise ValueError("尚未完成上班打卡，不能直接下班打卡")
    if last_action == new_action:
        label = "上班" if new_action == "CLOCK_IN" else "下班"
        raise ValueError(f"已完成{label}打卡，不能連續打卡兩次")


def clock_attendance(item: dict[str, str], source_ip: str) -> dict[str, Any]:
    """以 SQL Server 時間及交易鎖記錄交替上下班打卡。"""
    try:
        with connect(read_only=False, autocommit=False) as db:
            cursor = db.cursor()
            # 鎖定員工主檔列，讓同一員工的同時打卡請求依序完成檢查與寫入。
            exists = cursor.execute('domain.clock_attendance.1', item["employee_id"]).fetchone()
            if not exists:
                raise ValueError("員工編號不存在或已停用")
            current = time.now(cursor)
            previous = cursor.execute('domain.clock_attendance.2', item["employee_id"], current["work_date"]).fetchone()
            _validate_attendance_sequence(previous[0] if previous else None, item["action"])
            cursor.execute('domain.clock_attendance.3', item["employee_id"], item["action"], current["local_time"], current["utc_time"], current["work_date"], source_ip)
            db.commit()
        return {"employee_id": item["employee_id"], "action": item["action"], "clocked_at": current["iso_time"]}
    except database.Error as exc:
        raise DatabaseUnavailable("打卡寫入失敗。") from exc


def attendance_records(day: str = "", employee_id: str = "") -> list[dict[str, Any]]:
    """依篩選條件回傳管理員可查閱的打卡紀錄。"""
    return _fetch('domain.attendance_records.1', (day, day, employee_id, employee_id))


def add_operation(item: dict[str, Any], employee_id: str) -> dict[str, Any]:
    """以員工身分建立日報及提交事件。"""
    submission_id = f"OPS-{datetime.now(tz=UTC):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:6].upper()}"
    try:
        with connect(read_only=False, autocommit=False) as db:
            cursor = db.cursor()
            row = cursor.execute('domain.add_operation.1', submission_id, item["date"], item["campus"], item["category"], item["count"], item["note"], employee_id).fetchone()
            cursor.execute('domain.add_operation.2', submission_id, employee_id)
            db.commit()
        return {"id": submission_id, **item, "submitted_by": employee_id, "status": "待審核", "submitted_at": _json_value(row[0])}
    except database.Error as exc:
        raise DatabaseUnavailable("營運紀錄寫入失敗。") from exc


def _operation_submissions(employee_id: str = "") -> list[dict[str, Any]]:
    """取得指定員工或管理範圍的日報及事件歷程。"""
    rows = _fetch('domain._operation_submissions.1', (employee_id, employee_id))
    if not rows:
        return rows
    activities = _fetch('domain._operation_submissions.2', (employee_id, employee_id))
    by_submission: dict[str, list[dict[str, Any]]] = {}
    for activity in activities:
        by_submission.setdefault(activity.pop("submission_id"), []).append(activity)
    for row in rows:
        row["activities"] = by_submission.get(row["id"], [])
    return rows


def operation_submissions() -> list[dict[str, Any]]:
    """回傳管理員可查閱的日報清單。"""
    return _operation_submissions()


def employee_operation_submissions(employee_id: str) -> list[dict[str, Any]]:
    """只回傳目前員工的日報與歷程。"""
    return _operation_submissions(employee_id)


def review_operation(item: dict[str, str], reviewer_id: str) -> dict[str, Any]:
    """在交易中更新審核狀態並記錄管理員事件。"""
    action_types = {"要求補件": "CHANGES_REQUESTED", "審核通過": "APPROVED", "已退回": "REJECTED"}
    try:
        with connect(read_only=False, autocommit=False) as db:
            cursor = db.cursor()
            row = cursor.execute('domain.review_operation.1', item["id"]).fetchone()
            if not row:
                raise ValueError("找不到指定營運日報")
            cursor.execute(
                'domain.review_operation.2',
                item["status"], item["id"],
            )
            cursor.execute('domain.review_operation.3', item["id"], action_types[item["status"]], item["message"] or None, reviewer_id)
            db.commit()
        return {"id": item["id"], "status": item["status"]}
    except database.Error as exc:
        raise DatabaseUnavailable("營運日報審閱失敗。") from exc


def reply_operation(item: dict[str, str], employee_id: str) -> dict[str, Any]:
    """驗證日報歸屬與補件狀態後記錄員工回覆。"""
    try:
        with connect(read_only=False, autocommit=False) as db:
            cursor = db.cursor()
            row = cursor.execute('domain.reply_operation.1', item["id"], employee_id).fetchone()
            if not row:
                raise ValueError("找不到可回覆的營運日報")
            if row[0] in {"審核通過", "已退回"}:
                raise ValueError("此營運日報已結案，無法再回覆")
            cursor.execute(
                'domain.reply_operation.2',
                item["id"],
            )
            cursor.execute('domain.reply_operation.3', item["id"], item["message"], employee_id)
            db.commit()
        return {"id": item["id"], "status": "員工已回覆"}
    except database.Error as exc:
        raise DatabaseUnavailable("營運日報回覆失敗。") from exc


def upsert_operations_manuals(documents: list[dict[str, Any]]) -> int:
    """將 doc.py 擷取的文件與段落寫入正規化資料表。"""
    try:
        with connect(read_only=False, autocommit=False) as db:
            cursor = db.cursor()
            existing = {
                row[0]: {"id": row[1], "size": row[2], "modified": row[3]}
                for row in cursor.execute('domain.upsert_operations_manuals.1').fetchall()
            }
            cursor.execute('domain.upsert_operations_manuals.2')
            for document in documents:
                previous = existing.get(document["file_name"])
                if previous and previous["size"] == document["size"] and previous["modified"] == document["modified"]:
                    cursor.execute('domain.upsert_operations_manuals.3', previous["id"])
                    continue
                cursor.execute('domain.upsert_operations_manuals.4', document["file_name"], document["title"], document["category"], document["size"], document["modified"],
                     document["file_name"], document["title"], document["category"], document["size"], document["modified"])
                document_id = cursor.execute('domain.upsert_operations_manuals.5', document["file_name"]).fetchone()[0]
                cursor.execute('domain.upsert_operations_manuals.6', document_id)
                for order, section in enumerate(document["sections"], 1):
                    cursor.execute('domain.upsert_operations_manuals.7', document_id, order, section["heading"], section["content"])
            db.commit()
        return len(documents)
    except database.Error as exc:
        raise DatabaseUnavailable("SOP文件寫入失敗。") from exc


def operations_manual_catalog() -> list[dict[str, Any]]:
    """取得可閱讀的 SOP 文件目錄。"""
    return _fetch('domain.operations_manual_catalog.1')


def operations_manual_document(document_id: int) -> dict[str, Any]:
    """依文件編號回傳文件及內容區段。"""
    docs = _fetch('domain.operations_manual_document.1', (document_id,))
    if not docs:
        raise ValueError("找不到指定SOP文件")
    docs[0]["sections"] = _fetch('domain.operations_manual_document.2', (document_id,))
    return docs[0]


def _loads_json(value: Any, fallback: Any) -> Any:
    """解析資料庫 JSON，無效或空值時回傳指定預設值。"""
    try:
        return json.loads(value) if value not in (None, "") else fallback
    except (TypeError, json.JSONDecodeError):
        return fallback


def _question_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    """將題目整理成保留作答時內容的快照。"""
    return {
        "id": int(row["id"]),
        "domain": row.get("domain") or "academic",
        "subject": row.get("subject") or "未分類",
        "chapter": row.get("chapter") or row.get("category") or "未分類",
        "source": row.get("source") or "人工建立",
        "source_locator": row.get("source_locator") or "",
        "question_type": row["question_type"],
        "question": row["question"],
        "content_blocks": _loads_json(row.get("content_json"), [{"type": "text", "content": row["question"]}]),
        "options": _loads_json(row.get("options_json"), []),
        "answers": _loads_json(row.get("answer_json"), []),
        "structure": _loads_json(row.get("structure_json"), {}),
        "passage": row.get("passage") or "",
        "explanation": row.get("explanation") or "",
    }


def _published_question_rows(
    subject_id: int,
    chapter_ids: list[int] | None = None,
    document_ids: list[int] | None = None,
    question_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """依已驗證條件查詢可使用的發布題目。"""
    params: list[Any] = [subject_id]
    filters = (chapter_ids or [], document_ids or [], question_types or [])
    for values in filters:
        params.extend(values)
    return _fetch(database.statement('domain._published_question_rows.1', json.dumps([len(values) for values in filters])), tuple(params))


def training_catalog(employee_id: str) -> dict[str, Any]:
    """彙整科目、章節與題數供訓練入口顯示。"""
    subjects = _fetch('domain.training_catalog.1')
    chapters = _fetch('domain.training_catalog.2')
    progress_rows = _fetch('domain.training_catalog.3', (employee_id,))
    progress_by_chapter = {row["chapter_id"]: row for row in progress_rows}
    for chapter in chapters:
        progress = progress_by_chapter.get(chapter["id"], {})
        chapter["attempted_count"] = int(progress.get("attempted_count", 0))
        chapter["correct_count"] = int(progress.get("correct_count", 0))
        chapter["progress_percent"] = min(
            100,
            round(chapter["attempted_count"] * 100 / max(1, int(chapter["question_count"]))),
        )
    sources = _fetch('domain.training_catalog.4')
    resumable = _fetch('domain.training_catalog.5', (employee_id,))
    wrong_count = _fetch('domain.training_catalog.6', (employee_id,))[0]["count"]
    return {
        "subjects": subjects,
        "chapters": chapters,
        "sources": sources,
        "resumable": resumable[0] if resumable else None,
        "wrong_count": wrong_count,
    }


def _training_utc(value: str | datetime) -> datetime:
    """訓練到期欄位以 UTC 儲存，補足 DATETIME2 沒有時區的資訊。"""
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _training_now() -> datetime:
    """使用 SQL Server UTC 快照判定剩餘作答時間。"""
    try:
        with connect() as db:
            return _training_utc(time.now(db.cursor())["utc_time"])
    except database.Error as exc:
        raise DatabaseUnavailable("無法取得模擬考計時資料。") from exc


def _public_session_payload(session: dict[str, Any], rows: list[dict[str, Any]], *, include_review: bool = False) -> dict[str, Any]:
    """依交卷狀態過濾答案，產生對外工作階段資料。"""
    questions = []
    for row in rows:
        snapshot = _loads_json(row["snapshot_json"], {})
        response = _loads_json(row.get("response_json"), {})
        question = {
            key: value for key, value in snapshot.items()
            if include_review or key not in {"answers", "explanation"}
        }
        question.update({
            "order": row["question_order"],
            "response": response,
            "flagged": bool(row.get("is_flagged")),
            "correct": row.get("is_correct") if include_review else None,
        })
        questions.append(question)
    return {
        "id": session["id"],
        "mode": session["mode"],
        "status": session["status"],
        "subject_id": session["subject_id"],
        "started_at": session["started_at"],
        "expires_at": _training_utc(session["expires_at"]).isoformat() if session.get("expires_at") else None,
        "server_time": session.get("server_time"),
        "submitted_at": session.get("submitted_at"),
        "score": session.get("score"),
        "config": _loads_json(session.get("config_json"), {}),
        "questions": questions,
    }


def start_training_session(item: dict[str, Any], employee_id: str) -> dict[str, Any]:
    """建立員工訓練工作階段與固定題目快照。"""
    subject_rows = _fetch('domain.start_training_session.1', (item["subject_id"],))
    if not subject_rows or subject_rows[0]["domain"] != "academic":
        raise ValueError("找不到可用的學科科目")
    subject = subject_rows[0]
    rows = _published_question_rows(
        item["subject_id"], item["chapter_ids"], item["source_ids"], item["question_types"],
    )
    count = subject["mock_question_count"] if item["mode"] == "mock" else item["question_count"]
    if item["mode"] == "mock" and len(rows) < count:
        raise ValueError(f"目前只有 {len(rows)} 題可用，尚不足模擬考設定的 {count} 題")
    if not rows:
        raise ValueError("目前篩選條件沒有可作答的題目")
    import random
    random.SystemRandom().shuffle(rows)
    rows = rows if count == 0 else rows[:count]
    session_id = str(uuid.uuid4())
    duration = int(subject.get("mock_duration_minutes") or 0) if item["mode"] == "mock" else 0
    if item["mode"] == "mock" and duration <= 0:
        raise ValueError("模擬考時間必須大於 0 分鐘，請先由管理員設定科目規則")
    config = {
        "question_count": len(rows),
        "pass_score": int(subject["mock_pass_score"]) if item["mode"] == "mock" else None,
        "chapter_ids": item["chapter_ids"],
        "source_ids": item["source_ids"],
        "question_types": item["question_types"],
    }
    try:
        with connect(read_only=False, autocommit=False) as db:
            cursor = db.cursor()
            started_at = _training_utc(time.now(cursor)["utc_time"]).replace(tzinfo=None)
            expires_at = started_at + timedelta(minutes=duration) if duration else None
            cursor.execute('domain.start_training_session.2', session_id, employee_id, item["subject_id"], item["mode"], json.dumps(config), started_at, expires_at)
            for order, row in enumerate(rows, 1):
                cursor.execute('domain.start_training_session.3', session_id, row["id"], order, json.dumps(_question_snapshot(row), ensure_ascii=False))
            db.commit()
    except database.Error as exc:
        raise DatabaseUnavailable("無法建立本次題組。") from exc
    return training_session(session_id, employee_id)


def training_session(session_id: str, employee_id: str) -> dict[str, Any]:
    """驗證工作階段歸屬並回傳可公開的作答狀態。"""
    sessions = _fetch('domain.training_session.1', (session_id, employee_id))
    if not sessions:
        raise ValueError("找不到指定的作答階段")
    session = sessions[0]
    now_utc = _training_now()
    session["server_time"] = now_utc.isoformat()
    if session["status"] == "in_progress" and session.get("expires_at"):
        if _training_utc(session["expires_at"]) <= now_utc:
            return submit_training_session(session_id, employee_id)
    rows = _fetch('domain.training_session.2', (session_id,))
    return _public_session_payload(session, rows, include_review=session["status"] == "submitted")


def _grade_snapshot(snapshot: dict[str, Any], response: dict[str, Any]) -> bool:
    """依題目快照與作答計算客觀題結果。"""
    question_type = snapshot.get("question_type")
    expected = snapshot.get("answers", [])
    supplied = response.get("answers", [])
    if question_type in {"single_choice", "multiple_choice", "reading"}:
        try:
            return sorted({int(value) for value in supplied}) == sorted({int(value) for value in expected})
        except (TypeError, ValueError):
            return False
    # 舊題組使用建立時的快照評分，保留已移除題型的歷史作答相容性。
    if question_type == "fill_blank":
        normalized = [str(value).strip() for value in supplied]
        return normalized == [str(value).strip() for value in expected]
    if question_type == "matching":
        return supplied == expected
    return False


def _record_wrong(cursor, employee_id: str, question_id: int) -> None:
    """為指定員工更新單題錯題紀錄。"""
    _record_wrong_many(cursor, [(employee_id, question_id)])


def _record_wrong_many(cursor, records: list[tuple[str, int]]) -> None:
    """在目前交易中批次合併員工錯題紀錄。"""
    if not records:
        return
    cursor.executemany('domain._record_wrong_many.1', records)


def save_training_answer(item: dict[str, Any], employee_id: str) -> dict[str, Any]:
    """驗證作答工作階段後儲存答案及標記。"""
    rows = _fetch('domain.save_training_answer.1', (item["session_id"], employee_id, item["order"]))
    if not rows or rows[0]["status"] != "in_progress":
        raise ValueError("此題組目前無法作答")
    row = rows[0]
    if row.get("expires_at") and _training_utc(row["expires_at"]) <= _training_now():
        submit_training_session(item["session_id"], employee_id)
        raise ValueError("模擬考時間已到，系統已自動交卷")
    snapshot = _loads_json(row["snapshot_json"], {})
    correct = _grade_snapshot(snapshot, item["response"])
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            cursor.execute('domain.save_training_answer.2', json.dumps(item["response"], ensure_ascii=False), int(item["flagged"]),
                 int(correct), item["session_id"], item["order"])
            if not correct and item["response"].get("answers") not in (None, [], ""):
                _record_wrong(cursor, employee_id, row["question_id"])
    except database.Error as exc:
        raise DatabaseUnavailable("作答儲存失敗。") from exc
    result = {"saved": True, "flagged": item["flagged"]}
    if row["mode"] == "practice":
        result.update({
            "correct": correct,
            "answers": snapshot.get("answers", []),
            "explanation": snapshot.get("explanation", ""),
        })
    return result


def submit_training_session(session_id: str, employee_id: str) -> dict[str, Any]:
    """在交易中交卷、評分並更新錯題本。"""
    sessions = _fetch('domain.submit_training_session.1', (session_id, employee_id))
    if not sessions:
        raise ValueError("找不到指定的作答階段")
    session = sessions[0]
    rows = _fetch('domain.submit_training_session.2', (session_id,))
    if session["status"] != "submitted":
        correct_count = 0
        try:
            with connect(read_only=False, autocommit=False) as db:
                cursor = db.cursor()
                grade_updates: list[tuple[int, str, int]] = []
                wrong_records: list[tuple[str, int]] = []
                for row in rows:
                    snapshot = _loads_json(row["snapshot_json"], {})
                    response = _loads_json(row.get("response_json"), {})
                    correct = _grade_snapshot(snapshot, response)
                    correct_count += int(correct)
                    grade_updates.append((int(correct), session_id, row["question_order"]))
                    if not correct and response.get("answers") not in (None, [], ""):
                        wrong_records.append((employee_id, row["question_id"]))
                    row["is_correct"] = correct
                if grade_updates:
                    cursor.executemany('domain.submit_training_session.3', grade_updates)
                _record_wrong_many(cursor, wrong_records)
                score = round(correct_count * 100 / max(1, len(rows)), 2)
                cursor.execute('domain.submit_training_session.4', score, session_id, employee_id)
                db.commit()
            session.update({"status": "submitted", "score": score, "submitted_at": datetime.now(UTC).isoformat()})
        except database.Error as exc:
            raise DatabaseUnavailable("交卷失敗。") from exc
    return _public_session_payload(session, rows, include_review=True)


def training_wrong_questions(employee_id: str) -> list[dict[str, Any]]:
    """取得指定員工仍有效的錯題清單。"""
    rows = _fetch('domain.training_wrong_questions.1', (employee_id,))
    return [{**_question_snapshot(row), "added_at": row["added_at"]} for row in rows]


def remove_training_wrong(question_id: int, employee_id: str) -> dict[str, Any]:
    """移除指定員工錯題本中的題目。"""
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            cursor.execute('domain.remove_training_wrong.1', employee_id, question_id)
        return {"id": question_id, "removed": True}
    except database.Error as exc:
        raise DatabaseUnavailable("無法移除錯題。") from exc


def compliance_questions() -> list[dict[str, Any]]:
    """相容舊前端的已發布學科題目，不傳送答案與解析。"""
    rows = _fetch('domain.compliance_questions.1')
    for row in rows:
        row["options"] = _loads_json(row.pop("options_json"), [])
        row["content_blocks"] = _loads_json(row.pop("content_json"), [{"type": "text", "content": row["question"]}])
        row["structure"] = _loads_json(row.pop("structure_json"), {})
    return rows


def operations_manuals_admin() -> list[dict[str, Any]]:
    """回傳含停用狀態的SOP文件，供 MIS 維護。"""
    return _fetch('domain.operations_manuals_admin.1')


def _ensure_training_classification(cursor, domain: str, subject_name: str, chapter_code: str, chapter_name: str) -> tuple[int, int]:
    """在匯入交易中取得或建立科目與章節編號。"""
    cursor.execute('domain._ensure_training_classification.1', domain, subject_name, domain, subject_name)
    subject_id = cursor.execute(
        'domain._ensure_training_classification.2',
        domain, subject_name,
    ).fetchone()[0]
    cursor.execute('domain._ensure_training_classification.3', subject_id, chapter_code, subject_id, chapter_code, chapter_name, 999 if chapter_code == "UNSORTED" else 0)
    chapter_id = cursor.execute(
        'domain._ensure_training_classification.4',
        subject_id, chapter_code,
    ).fetchone()[0]
    return int(subject_id), int(chapter_id)


def import_training_question_drafts(
    drafts: list[dict[str, Any]], warnings: list[dict[str, str]] | None = None,
    failures: list[dict[str, str]] | None = None,
) -> dict[str, int]:
    """以來源指紋冪等匯入草稿，絕不覆寫管理員已鎖定的題目。"""
    result = {"created": 0, "updated": 0, "locked": 0, "duplicates": 0}
    warnings = warnings or []
    failures = failures or []
    if not drafts and not warnings and not failures:
        return result
    try:
        with connect(read_only=False, autocommit=False) as db:
            cursor = db.cursor()
            documents = {
                row[0]: row[1]
                for row in cursor.execute('domain.import_training_question_drafts.1').fetchall()
            }
            draft_counts: dict[str, int] = {}
            for draft in drafts:
                source_name = draft.get("source_document", "")
                draft_counts[source_name] = draft_counts.get(source_name, 0) + 1
            warning_messages: dict[str, list[str]] = {}
            for warning in warnings:
                warning_messages.setdefault(warning.get("source", ""), []).append(warning.get("message", ""))
            failure_messages: dict[str, list[str]] = {}
            for failure in failures:
                failure_messages.setdefault(failure.get("source", ""), []).append(failure.get("message", ""))
            source_updates = []
            for source_name in set(draft_counts) | set(warning_messages) | set(failure_messages):
                messages = failure_messages.get(source_name) or warning_messages.get(source_name, [])
                source_updates.append((
                    "question_bank" if draft_counts.get(source_name) or failure_messages.get(source_name) else "manual",
                    "failed" if failure_messages.get(source_name) else (
                        "warning" if warning_messages.get(source_name) else "parsed"
                    ),
                    "；".join(messages)[:1000] or None,
                    source_name,
                ))
            if source_updates:
                cursor.executemany('domain.import_training_question_drafts.2', source_updates)
            seen: set[str] = set()
            classification_cache: dict[tuple[str, str, str, str], tuple[int, int]] = {}
            question_updates = []
            question_inserts = []
            for draft in drafts:
                fingerprint = draft["source_fingerprint"]
                if fingerprint in seen:
                    result["duplicates"] += 1
                    continue
                seen.add(fingerprint)
                classification = (
                    draft.get("domain", "academic"),
                    draft.get("subject") or "未分類",
                    draft.get("chapter_code") or "UNSORTED",
                    draft.get("chapter") or "未分類",
                )
                if classification not in classification_cache:
                    classification_cache[classification] = _ensure_training_classification(
                        cursor, *classification,
                    )
                subject_id, chapter_id = classification_cache[classification]
                document_id = documents.get(draft.get("source_document"))
                previous = cursor.execute('domain.import_training_question_drafts.3', fingerprint, document_id, draft.get("source_question_key"), fingerprint).fetchone()
                if previous and (previous[1] or previous[2] is not None):
                    result["locked"] += 1
                    continue
                values = (
                    document_id, subject_id, chapter_id, draft.get("domain", "academic"),
                    draft.get("chapter") or "未分類", draft["question"][:500],
                    json.dumps(draft.get("options", []), ensure_ascii=False),
                    int(draft.get("answers", [0])[0] if draft.get("answers") else 0),
                    draft.get("explanation", "")[:1000], draft["question_type"],
                    json.dumps(draft.get("answers", [])),
                    json.dumps(draft.get("stem_blocks", []), ensure_ascii=False),
                    json.dumps(draft.get("structure", {}), ensure_ascii=False),
                    draft.get("source_locator", "")[:300], draft.get("source_question_key", "")[:200],
                    fingerprint, float(draft.get("parse_confidence", 0)),
                    json.dumps(draft.get("parse_warnings", []), ensure_ascii=False),
                )
                if previous:
                    question_updates.append((*values, previous[0]))
                    result["updated"] += 1
                else:
                    question_inserts.append(values)
                    result["created"] += 1
            if question_updates:
                cursor.executemany('domain.import_training_question_drafts.4', question_updates)
            if question_inserts:
                cursor.executemany('domain.import_training_question_drafts.5', question_inserts)
            db.commit()
        return result
    except database.Error as exc:
        raise DatabaseUnavailable("題庫草稿匯入失敗。") from exc


def training_taxonomy_admin() -> dict[str, Any]:
    """取得管理端科目與章節清單。"""
    return {
        "subjects": _fetch('domain.training_taxonomy_admin.1'),
        "chapters": _fetch('domain.training_taxonomy_admin.2'),
    }


def save_training_subject(item: dict[str, Any]) -> dict[str, Any]:
    """驗證編號後新增或更新科目及模擬考設定。"""
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            if item["id"]:
                current = cursor.execute(
                    'domain.save_training_subject.1', item["id"]
                ).fetchone()
                if not current:
                    raise ValueError("找不到指定科目")
                if current[0] != item["domain"] and cursor.execute(
                    'domain.save_training_subject.2', item["id"]
                ).fetchone()[0]:
                    raise ValueError("已有題目的科目不可變更學科／術科領域")
                cursor.execute('domain.save_training_subject.3', item["domain"], item["name"], item["mock_question_count"],
                     item["mock_duration_minutes"], item["mock_pass_score"],
                     int(item["is_active"]), item["id"])
                subject_id = item["id"]
            else:
                subject_id = cursor.execute('domain.save_training_subject.4', item["domain"], item["name"], item["mock_question_count"],
                     item["mock_duration_minutes"], item["mock_pass_score"], int(item["is_active"])).fetchone()[0]
        return {**item, "id": int(subject_id)}
    except database.Error as exc:
        raise DatabaseUnavailable("科目設定儲存失敗。") from exc


def save_training_chapter(item: dict[str, Any]) -> dict[str, Any]:
    """新增或更新指定科目下的章節。"""
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            if item["id"]:
                current = cursor.execute(
                    'domain.save_training_chapter.1', item["id"]
                ).fetchone()
                if not current:
                    raise ValueError("找不到指定章節")
                if int(current[0]) != item["subject_id"] and cursor.execute(
                    'domain.save_training_chapter.2', item["id"]
                ).fetchone()[0]:
                    raise ValueError("已有題目的章節不可移至其他科目")
                cursor.execute('domain.save_training_chapter.3', item["subject_id"], item["code"], item["name"], item["display_order"],
                     int(item["is_active"]), item["id"])
                chapter_id = item["id"]
            else:
                chapter_id = cursor.execute('domain.save_training_chapter.4', item["subject_id"], item["code"], item["name"], item["display_order"],
                     int(item["is_active"])).fetchone()[0]
        return {**item, "id": int(chapter_id)}
    except database.Error as exc:
        raise DatabaseUnavailable("章節設定儲存失敗。") from exc


def set_operations_manual_state(document_id: int, is_active: bool) -> dict[str, Any]:
    """更新來源文件狀態並回傳管理端結果。"""
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            cursor.execute(
                'domain.set_operations_manual_state.1',
                int(is_active), document_id,
            )
            if cursor.rowcount == 0:
                raise ValueError("找不到指定SOP文件")
        return {"id": document_id, "is_active": is_active}
    except database.Error as exc:
        raise DatabaseUnavailable("SOP文件狀態更新失敗。") from exc


def compliance_questions_admin() -> list[dict[str, Any]]:
    """取得管理員可編輯的題目資料。"""
    rows = _fetch('domain.compliance_questions_admin.1')
    for row in rows:
        row["options"] = _loads_json(row.pop("options_json"), [])
        row["answers"] = _loads_json(row.pop("answer_json"), [])
        row["content_blocks"] = _loads_json(row.pop("content_json"), [{"type": "text", "content": row["question"]}])
        row["structure"] = _loads_json(row.pop("structure_json"), {})
        row["parse_warnings"] = _loads_json(row.pop("parse_warnings_json"), [])
    return rows


def save_compliance_question(item: dict[str, Any]) -> dict[str, Any]:
    """儲存已驗證題目，保留管理員修改標記。"""
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            options_json = json.dumps(item["options"], ensure_ascii=False)
            answer_json = json.dumps(item["answers"], ensure_ascii=False)
            content_json = json.dumps(item["content_blocks"], ensure_ascii=False)
            structure_json = json.dumps(item["structure"], ensure_ascii=False)
            correct_index = item["answers"][0] if item["answers"] and isinstance(item["answers"][0], int) else 0
            category = item.get("chapter_name") or item.get("category") or "未分類"
            is_active = int(item["status"] == "published")
            if item["id"]:
                cursor.execute('domain.save_compliance_question.1', item["document_id"], item["subject_id"], item["chapter_id"], item["domain"],
                     category, item["question"], options_json, correct_index, item["explanation"],
                     item["question_type"], answer_json, content_json, structure_json,
                     item["passage"] or None, item["status"], is_active, item["id"])
                if cursor.rowcount == 0:
                    raise ValueError("找不到指定題目")
                question_id = item["id"]
            else:
                question_id = cursor.execute('domain.save_compliance_question.2', item["document_id"], item["subject_id"], item["chapter_id"], item["domain"],
                     category, item["question"], options_json, correct_index, item["explanation"],
                     item["question_type"], answer_json, content_json, structure_json,
                     item["passage"] or None, item["status"], is_active).fetchone()[0]
        return {**item, "id": int(question_id), "is_active": bool(is_active), "admin_locked": True}
    except database.Error as exc:
        raise DatabaseUnavailable("營運檢核題庫儲存失敗。") from exc


def grade_compliance_answer(item: dict[str, Any], employee_id: str) -> dict[str, Any]:
    """評分客觀題，申論則建立待人工審核紀錄。"""
    rows = _fetch('domain.grade_compliance_answer.1', (item["question_id"],))
    if not rows:
        raise ValueError("找不到指定題目")
    question = rows[0]
    if question["question_type"] == "essay":
        if not item["answer_text"]:
            raise ValueError("請輸入申論答案")
        try:
            with connect(read_only=False) as db:
                answer_id = db.cursor().execute('domain.grade_compliance_answer.2', item["question_id"], employee_id, item["answer_text"]).fetchone()[0]
            return {"id": answer_id, "status": "待審核", "is_essay": True}
        except database.Error as exc:
            raise DatabaseUnavailable("申論答案送審失敗。") from exc

    options = json.loads(question["options_json"])
    if not item["answers"] or any(answer < 0 or answer >= len(options) for answer in item["answers"]):
        raise ValueError("作答選項不正確")
    expected = sorted(set(json.loads(question["answer_json"])))
    is_correct = item["answers"] == expected
    return {
        "is_essay": False,
        "correct": is_correct,
        "answers": expected,
        "explanation": question["explanation"],
    }


def practical_questions(employee_id: str) -> list[dict[str, Any]]:
    """回傳已發布的術科申論題目。"""
    rows = _fetch('domain.practical_questions.1', (employee_id,))
    for row in rows:
        row["content_blocks"] = _loads_json(row.pop("content_json"), [{"type": "text", "content": row["question"]}])
    return rows


def compliance_essay_answers_admin() -> list[dict[str, Any]]:
    """取得待審及已審的申論作答清單。"""
    return _fetch('domain.compliance_essay_answers_admin.1')


def review_compliance_essay(item: dict[str, Any], reviewer_id: str) -> dict[str, Any]:
    """儲存管理員的申論審核狀態與回饋。"""
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            cursor.execute('domain.review_compliance_essay.1', item["status"], item["feedback"] or None, reviewer_id, item["id"])
            if cursor.rowcount == 0:
                raise ValueError("找不到指定申論答案")
        return {"id": item["id"], "status": item["status"]}
    except database.Error as exc:
        raise DatabaseUnavailable("申論答案審核失敗。") from exc


def delete_compliance_question(question_id: int) -> dict[str, Any]:
    # 保留題目關聯與來源指紋，避免破壞歷史作答或讓同步重新建立已刪除的題目。
    """以軟刪除停用題目並保留既有作答關聯。"""
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            cursor.execute('domain.delete_compliance_question.1', question_id)
            if cursor.rowcount == 0:
                raise ValueError("找不到指定題目，或題目已刪除")
        return {"id": question_id, "deleted": True}
    except database.Error as exc:
        raise DatabaseUnavailable("題庫題目刪除失敗。") from exc


def deactivate_compliance_question(question_id: int) -> dict[str, Any]:
    """停用指定題目並回傳更新狀態。"""
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            cursor.execute(
                'domain.deactivate_compliance_question.1',
                question_id,
            )
            if cursor.rowcount == 0:
                raise ValueError("找不到指定題目")
        return {"id": question_id, "is_active": False}
    except database.Error as exc:
        raise DatabaseUnavailable("營運檢核題庫停用失敗。") from exc


def set_training_question_status(question_id: int, status: str) -> dict[str, Any]:
    """驗證發布條件後更新題目狀態。"""
    if status not in {"draft", "published", "disabled"}:
        raise ValueError("題目狀態不正確")
    rows = _fetch('domain.set_training_question_status.1', (question_id,))
    if not rows:
        raise ValueError("找不到指定題目")
    row = rows[0]
    if status == "published" and row["question_type"] not in {"single_choice", "multiple_choice", "reading", "essay"}:
        raise ValueError("此題型已不支援，請先編輯為支援的題型")
    if status == "published" and row["question_type"] != "essay":
        answers = _loads_json(row["answer_json"], [])
        options = _loads_json(row["options_json"], [])
        if not answers or not row["explanation"]:
            raise ValueError("發布前必須完成正確答案與解析")
        if row["question_type"] in {"single_choice", "multiple_choice", "reading"} and len(options) < 2:
            raise ValueError("發布前必須完成至少兩個選項")
    try:
        with connect(read_only=False) as db:
            db.cursor().execute('domain.set_training_question_status.2', status, int(status == "published"), question_id)
        return {"id": question_id, "status": status, "is_active": status == "published"}
    except database.Error as exc:
        raise DatabaseUnavailable("題目狀態更新失敗。") from exc


def unlock_training_question_import(question_id: int) -> dict[str, Any]:
    """由管理員明確授權下一次來源同步覆寫指定題目。"""
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            cursor.execute('domain.unlock_training_question_import.1', question_id)
            if cursor.rowcount == 0:
                raise ValueError("此題目沒有可重新匯入的來源")
        return {"id": question_id, "unlocked": True}
    except database.Error as exc:
        raise DatabaseUnavailable("無法解除題目的匯入保護。") from exc


def update_training_questions_bulk(item: dict[str, Any]) -> dict[str, Any]:
    """在交易中批次更新已驗證的題目設定。"""
    placeholders = str(len(item["ids"]))
    try:
        if item["subject_id"]:
            chapters = _fetch('domain.update_training_questions_bulk.1', (item["subject_id"], item["chapter_id"]))
            if not chapters:
                raise ValueError("指定章節不屬於所選科目")
            with connect(read_only=False) as db:
                db.cursor().execute(database.statement('domain.update_training_questions_bulk.2', placeholders), item["subject_id"], item["chapter_id"], *item["ids"])
        if item["status"]:
            for question_id in item["ids"]:
                set_training_question_status(question_id, item["status"])
        return {"updated": len(item["ids"]), **item}
    except database.Error as exc:
        raise DatabaseUnavailable("題目批次更新失敗。") from exc


# ==============================================================================
# 穿越冒險與休閒 RPG
# ==============================================================================
from . import adventure


def adventure_worlds() -> list[dict[str, Any]]:
    """取得對玩家開放的冒險世界清單。"""
    rows = _fetch("domain.adventure_worlds.1")
    return [
        {
            "world_no": r["WorldNo"],
            "world_name": r["WorldName"],
            "description": r["Description"],
            "current_version_no": r["CurrentVersionNo"],
            "traits": adventure_world_traits(r["WorldNo"], r["CurrentVersionNo"]),
        }
        for r in rows
    ]


def adventure_world_traits(world_no: str, version_no: str) -> list[dict[str, Any]]:
    """僅提供已發布版本的建角選項。"""
    rows = _fetch("domain.adventure_version.1", (world_no, version_no))
    content = json.loads(rows[0]["Content"]) if rows else {}
    return [{"id": t["id"], "name": t.get("name", t["id"]), "desc": t.get("desc", "")}
            for t in content.get("traits", [])]


def _adventure_display_no(prefix: str, identity: Any) -> str:
    """使用資料列流水號顯示，UUID 保留供內部識別與關聯。"""
    return f"{prefix}{int(identity):06d}" if identity is not None else ""


def adventure_saves(employee_id: str) -> list[dict[str, Any]]:
    """取得指定員工的所有冒險存檔清單。"""
    rows = _fetch("domain.adventure_saves.1", (employee_id,))
    saves = []
    for r in rows:
        state = json.loads(r["StateJson"] or "{}")
        char = json.loads(r["CharacterSnapshot"] or "{}")
        saves.append({
            "save_no": r["SaveNo"],
            "save_display_no": _adventure_display_no("SAVE_", r.get("SaveDisplayId")),
            "version_display_no": _adventure_display_no("V", r.get("VersionDisplayId")),
            "employee_no": r["EmployeeNo"],
            "world_no": r["WorldNo"],
            "world_name": r["WorldName"],
            "slot_index": r["SlotIndex"],
            "version_no": r["VersionNo"],
            "revision": r["Revision"],
            "turn": state.get("turn", 1),
            "location_id": state.get("location_id", ""),
            "time_of_day": state.get("time_of_day", "morning"),
            "hp": state.get("character", {}).get("hp", 100),
            "max_hp": state.get("character", {}).get("max_hp", 100),
            "gold": state.get("character", {}).get("gold", 50),
            "character": char,
            "create_time": _json_value(r["CreateTime"]),
        })
    return saves


def adventure_create_save(employee_id: str, world_no: str, slot_index: int, trait_id: str = "") -> dict[str, Any]:
    """為登入員工在指定世界的存檔槽建立新角色與存檔。"""
    if slot_index not in (1, 2, 3):
        raise ValueError("存檔欄位必須為 1、2 或 3。")

    # 取得世界資訊
    world_rows = _fetch("domain.adventure_worlds.2", (world_no,))
    if not world_rows or not world_rows[0].get("IsOpen"):
        raise ValueError("該冒險世界不存在或尚未對外開放。")
    current_version_no = world_rows[0].get("CurrentVersionNo", "")
    if not current_version_no:
        raise ValueError("該世界尚未發布任何有效版本。")

    # 取得不可變版本劇本
    ver_rows = _fetch("domain.adventure_version.1", (world_no, current_version_no))
    if not ver_rows or not ver_rows[0].get("Content"):
        raise ValueError("無法取得該版本的劇本內容。")
    script = json.loads(ver_rows[0]["Content"])

    # 取得員工身分快照
    emp = employee_identity(employee_id)
    emp_snapshot = {
        "employee_id": emp["employee_id"],
        "display_name": emp["display_name"],
        "department": emp["department"],
        "position": emp["position"],
        "photo_file": emp.get("photo_file", ""),
    }

    initial_state = adventure.create_initial_state(emp_snapshot, script, trait_id)
    save_no = "SAVE_" + uuid.uuid5(uuid.NAMESPACE_URL, json.dumps([employee_id, world_no, slot_index])).hex

    try:
        with connect(read_only=False, autocommit=False) as db:
            cursor = db.cursor()
            existing = _fetch("domain.adventure_saves.1", (employee_id,))
            if any(s["WorldNo"] == world_no and s["SlotIndex"] == slot_index for s in existing):
                return adventure_state(next(s["SaveNo"] for s in existing if s["WorldNo"] == world_no and s["SlotIndex"] == slot_index), employee_id)

            cursor.execute(
                "domain.adventure_saves.3",
                save_no,
                employee_id,
                world_no,
                slot_index,
                current_version_no,
                json.dumps(emp_snapshot, ensure_ascii=False),
                json.dumps(initial_state, ensure_ascii=False),
            )
            db.commit()
    except database.IntegrityError:
        return adventure_state(save_no, employee_id)
    except database.Error as exc:
        raise DatabaseUnavailable("建立存檔失敗。") from exc

    return adventure_state(save_no, employee_id)


def adventure_state(save_no: str, employee_id: str) -> dict[str, Any]:
    """取得指定存檔的可見狀態、當前地點資訊、NPC 與可用行動。"""
    rows = _fetch("domain.adventure_saves.2", (save_no, employee_id))
    if not rows:
        raise ValueError("找不到指定存檔或無存取權限。")
    save = rows[0]

    world_no = save["WorldNo"]
    version_no = save["VersionNo"]
    state = json.loads(save["StateJson"] or "{}")

    # 讀取劇本
    ver_rows = _fetch("domain.adventure_version.1", (world_no, version_no))
    if not ver_rows:
        raise ValueError("無法讀取存檔所關聯的劇本版本。")
    script = json.loads(ver_rows[0]["Content"])

    return adventure_view(save, script, state)


def adventure_view(save: dict[str, Any], script: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """從同一修訂號產生玩家視圖，不再另外讀取資料庫。"""
    save_no, world_no, version_no = save["SaveNo"], save["WorldNo"], save["VersionNo"]
    available_actions = adventure.get_available_actions(script, state)
    current_loc_id = state.get("location_id", "")
    current_loc = script.get("locations", {}).get(current_loc_id, {})
    current_time = state.get("time_of_day", "morning")

    # 取得目前地點的所有 NPC（經員工角色替換處理）
    npcs_in_scene = []
    for npc_id, npc_data in script.get("npcs", {}).items():
        schedule = npc_data.get("schedule", {})
        npc_loc = schedule.get(current_time, schedule.get("default", ""))
        if npc_loc == current_loc_id:
            effective_npc = adventure.get_effective_npc(npc_id, script, state)
            npcs_in_scene.append(effective_npc)

    # 物品清單加上定義資訊
    inventory_items = []
    for entry in state.get("inventory", []):
        item_id = entry.get("item_id")
        item_def = script.get("items", {}).get(item_id, {})
        inventory_items.append({
            "item_id": item_id,
            "count": entry.get("count", 1),
            "equipped": entry.get("equipped", False),
            "name": item_def.get("name", item_id),
            "type": item_def.get("type", "misc"),
            "description": item_def.get("description", ""),
        })

    # 任務清單加上名稱與描述
    quests_info = []
    for q_id, q_data in state.get("quests", {}).items():
        q_def = script.get("quests", {}).get(q_id, {})
        quests_info.append({
            "quest_id": q_id,
            "name": q_def.get("name", q_id),
            "description": q_def.get("description", ""),
            "stage": q_data.get("stage", 1),
            "completed": q_data.get("completed", False),
            "method_used": q_data.get("method_used", ""),
        })

    # 人物關係
    relationships_info = []
    for npc_id, aff in state.get("relationships", {}).items():
        if npc_id not in state.get("met_npcs", []) and npc_id not in [n["id"] for n in npcs_in_scene]:
            continue
        effective_npc = adventure.get_effective_npc(npc_id, script, state)
        relationships_info.append({
            "npc_id": npc_id,
            "name": effective_npc.get("name", npc_id),
            "title": effective_npc.get("title", ""),
            "affinity": aff,
        })

    return {
        "save_no": save_no,
        "save_display_no": _adventure_display_no("SAVE_", save.get("SaveDisplayId")),
        "version_display_no": _adventure_display_no("V", save.get("VersionDisplayId")),
        "world_no": world_no,
        "world_name": save.get("WorldName", ""),
        "slot_index": save["SlotIndex"],
        "version_no": version_no,
        "revision": save["Revision"],
        "state": {
            "turn": state.get("turn", 1),
            "time_of_day": current_time,
            "time_name": adventure.TIME_PHASE_NAMES.get(current_time, "白天"),
            "location_id": current_loc_id,
            "character": state.get("character", {}),
            "inventory": inventory_items,
            "equipment": state.get("equipment", {}),
            "quests": quests_info,
            "clues": state.get("clues", []),
            "relationships": relationships_info,
            "interaction": bool(state.get("interaction")),
            "combat": ({k: state["combat"][k] for k in ("enemy_name", "enemy_hp", "enemy_max_hp", "round")} if state.get("combat") else None),
            "flags": {k: v for k, v in state.get("flags", {}).items() if k in ("game_ended", "ending_id")},
            "recent_logs": state.get("recent_logs", [])[-25:],
        },
        "location": {
            "id": current_loc_id,
            "name": current_loc.get("name", "未知地點"),
            "description": current_loc.get("description", ""),
            "exits": [
                {"id": eid, "name": script.get("locations", {}).get(eid, {}).get("name", eid)}
                for eid in current_loc.get("exits", [])
            ],
            "objects": [{k: o.get(k, "") for k in ("id", "name", "description")} for o in current_loc.get("objects", []) if adventure.evaluate_condition(o.get("condition"), state)],
            "activities": [{k: o.get(k, "") for k in ("id", "name", "description")} for o in current_loc.get("activities", []) if adventure.evaluate_condition(o.get("condition"), state)],
        },
        "npcs_in_scene": [{k: n.get(k, "") for k in ("id", "name", "title", "bio", "photo_file")} for n in npcs_in_scene],
        "available_actions": [{k: v for k, v in a.items() if k not in ("flow_id", "next_node_id")} for a in available_actions],
    }


def adventure_history(save_no: str, employee_id: str, before_turn: int = 0, limit: int = 20) -> list[dict[str, Any]]:
    """游標分頁取得存檔歷史行動與事件紀錄。"""
    rows = _fetch("domain.adventure_saves.2", (save_no, employee_id))
    if not rows:
        raise ValueError("找不到指定存檔或無存取權限。")

    turn_rows = _fetch("domain.adventure_turns.3", (save_no, before_turn, before_turn, max(1, min(100, limit))))
    results = []
    for r in turn_rows:
        results.append({
            "cursor": r["Id"],
            "turn_index": r["TurnIndex"],
            "request_id": r["RequestId"],
            "action_id": r["ActionId"],
            "action_input": json.loads(r["ActionInput"] or "{}"),
            "roll_result": json.loads(r["RollResult"] or "{}"),
            "state_diff": json.loads(r["StateDiff"] or "{}"),
            "response": json.loads(r["ResponseJson"] or "{}"),
            "create_time": _json_value(r["CreateTime"]),
        })
    return results


def adventure_action(
    employee_id: str,
    save_no: str,
    request_id: str,
    expected_revision: int,
    action_data: dict[str, Any],
) -> dict[str, Any]:
    """提交冒險結構化行動，具備單一交易、冪等防重與樂觀鎖。"""
    if not isinstance(action_data, dict) or not request_id or len(request_id) > 50:
        raise ValueError("行動格式或 request_id 不合法。")

    try:
        with connect(read_only=False, autocommit=False) as db:
            cursor = db.cursor()

            # 1. 查詢存檔
            cursor.execute("domain.adventure_saves.lock", save_no, employee_id)
            save_rows = cursor.fetchall()
            if not save_rows:
                db.rollback()
                raise ValueError("存檔不存在或無權限。")

            current_revision = save_rows[0][5]
            world_no = save_rows[0][2]
            version_no = save_rows[0][4]
            current_state_json = save_rows[0][7]

            # 2. 冪等檢查
            cursor.execute("domain.adventure_turns.1", save_no, request_id)
            turn_rows = cursor.fetchall()
            if turn_rows:
                existing_input = json.loads(turn_rows[0][4] or "{}")
                if existing_input == action_data:
                    cached_response = json.loads(turn_rows[0][7] or "{}")
                    db.commit()
                    return cached_response
                else:
                    db.rollback()
                    raise ValueError("相同請求識別碼搭配不同行動內容，請求遭拒。")

            # 3. 樂觀鎖比對
            if current_revision != expected_revision:
                db.rollback()
                raise ValueError("CONFLICT:存檔修訂號不符，已被其他操作更新，請重新整理取得最新狀態。")

            # 4. 取得劇本
            cursor.execute("domain.adventure_version.1", world_no, version_no)
            ver_rows = cursor.fetchall()
            if not ver_rows or not ver_rows[0][3]:
                db.rollback()
                raise ValueError("無法讀取劇本資料。")
            script = json.loads(ver_rows[0][3])

            # 5. 規則引擎推進
            current_state = json.loads(current_state_json or "{}")
            new_state, logs, actions, roll_result = adventure.advance(script, current_state, action_data)

            state_diff = {
                "turn": {"old": current_state.get("turn"), "new": new_state.get("turn")},
                "hp": {"old": current_state.get("character", {}).get("hp"), "new": new_state.get("character", {}).get("hp")},
                "gold": {"old": current_state.get("character", {}).get("gold"), "new": new_state.get("character", {}).get("gold")},
            }

            next_revision = current_revision + 1
            response_payload = {
                "save_no": save_no,
                "revision": next_revision,
                "new_logs": logs,
                "roll_result": roll_result,
                "state_diff": state_diff,
            }

            save = dict(zip(("SaveNo", "EmployeeNo", "WorldNo", "SlotIndex", "VersionNo", "Revision", "CharacterSnapshot", "StateJson", "IsActive", "CreateTime", "WorldName", "SaveDisplayId", "VersionDisplayId"), save_rows[0]))
            save["Revision"] = next_revision
            response_payload.update(adventure_view(save, script, new_state))

            # 6. 寫入 AdventureTurns
            cursor.execute(
                "domain.adventure_turns.2",
                save_no,
                new_state.get("turn", 1),
                request_id,
                expected_revision,
                action_data.get("action", ""),
                json.dumps(action_data, ensure_ascii=False),
                json.dumps(roll_result, ensure_ascii=False),
                json.dumps(state_diff, ensure_ascii=False),
                json.dumps(response_payload, ensure_ascii=False),
            )

            # 7. 更新 AdventureSaves
            cursor.execute(
                "domain.adventure_saves.4",
                json.dumps(new_state, ensure_ascii=False),
                save_no,
                expected_revision,
            )
            if cursor.rowcount == 0:
                db.rollback()
                raise ValueError("CONFLICT:存檔儲存衝突，狀態已變更。")

            db.commit()

        return response_payload
    except database.Error as exc:
        raise DatabaseUnavailable("行動結果尚未確認，請使用相同請求識別碼重試。") from exc


def admin_adventure_worlds() -> list[dict[str, Any]]:
    """管理員取得所有世界清單（含草稿狀態與版本號）。"""
    rows = _fetch("domain.admin_adventure_worlds.1")
    return [
        {
            "world_no": r["WorldNo"],
            "world_name": r["WorldName"],
            "description": r["Description"],
            "is_open": bool(r["IsOpen"]),
            "current_version_no": r["CurrentVersionNo"],
            "draft_revision": r["DraftRevision"] or 1,
            "draft_updated_by": r["UpdatedBy"] or "",
            "draft_create_time": r["DraftCreateTime"],
        }
        for r in rows
    ]


def admin_save_world(world_no: str, world_name: str, description: str, is_open: bool, current_version_no: str) -> dict[str, Any]:
    """管理員建立或更新世界基礎設定。"""
    if not world_no or len(world_no) > 50 or not world_name or len(world_name) > 50:
        raise ValueError("世界編號與名稱必填且不可超過 50 字。")
    try:
        with connect(read_only=False, autocommit=False) as db:
            cursor = db.cursor()
            existing = _fetch("domain.adventure_worlds.2", (world_no,))
            if existing:
                cursor.execute("domain.admin_adventure_worlds.3", world_name, description, int(is_open), existing[0]["CurrentVersionNo"], world_no)
            else:
                cursor.execute("domain.admin_adventure_worlds.2", world_no, world_name, description, 0, "")
                demo = adventure.create_demo_chapter()
                demo["world_no"] = world_no
                demo["world_name"] = world_name
                demo["description"] = description
                cursor.execute("domain.admin_adventure_draft.2", world_no, 1, json.dumps(demo, ensure_ascii=False), "admin", world_no, json.dumps(demo, ensure_ascii=False), "admin")
            db.commit()
        return {"world_no": world_no, "saved": True}
    except database.Error as exc:
        raise DatabaseUnavailable("世界設定儲存失敗。") from exc


def admin_adventure_draft(world_no: str) -> dict[str, Any]:
    """取得指定世界的草稿內容與修訂號。"""
    rows = _fetch("domain.admin_adventure_draft.1", (world_no,))
    if not rows:
        raise ValueError("世界草稿不存在。")
    return {
        "world_no": rows[0]["WorldNo"],
        "revision": rows[0]["Revision"],
        "content": json.loads(rows[0]["Content"] or "{}"),
        "updated_by": rows[0]["UpdatedBy"],
        "create_time": rows[0]["CreateTime"],
    }


def admin_save_draft(world_no: str, expected_revision: int, content: dict[str, Any], updated_by: str) -> dict[str, Any]:
    """管理員儲存世界草稿，具備樂觀修訂號鎖定。"""
    if not isinstance(content, dict):
        raise ValueError("草稿必須為物件。")
    content_json = json.dumps(content, ensure_ascii=False)
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            cursor.execute("domain.admin_adventure_draft.2", world_no, expected_revision, content_json, updated_by, world_no, content_json, updated_by)
            if cursor.rowcount == 0:
                raise ValueError("CONFLICT:草稿版本已被其他管理員更新（修訂號不符），請重新載入後再儲存。")
        return {"world_no": world_no, "revision": expected_revision + 1, "saved": True}
    except database.Error as exc:
        raise DatabaseUnavailable("儲存草稿失敗。") from exc


def admin_staff_options() -> list[dict[str, Any]]:
    """取得合格在職員工列表以供作者建立 NPC 角色映射。"""
    rows = _fetch("domain.admin_adventure_staff.1")
    return [
        {
            "employee_id": r["employee_id"],
            "display_name": r["display_name"],
            "department": r["department"],
            "position": r["position"],
            "photo_file": r.get("photo_file", ""),
            "traits": r.get("traits", ""),
        }
        for r in rows
    ]


def admin_validate_draft(content: dict[str, Any]) -> dict[str, Any]:
    """驗證草稿結構。"""
    errors = adventure.validate_draft(content)
    return {"valid": len(errors) == 0, "errors": errors}


def admin_test_run(content: dict[str, Any], initial_state: dict[str, Any] | None, action: dict[str, Any], rng_seed: int = 42) -> dict[str, Any]:
    """試跑器模擬執行。"""
    return adventure.simulate_test_run(content, initial_state, action, rng_seed)


def admin_publish_draft(world_no: str, expected_revision: int, published_by: str) -> dict[str, Any]:
    """驗證並發布草稿為不可變版本快照，並更新世界的目前版本。"""
    try:
        with connect(read_only=False, autocommit=False) as db:
            cursor = db.cursor()
            cursor.execute("domain.admin_adventure_draft.lock", world_no)
            rows = cursor.fetchall()
            if not rows or rows[0][1] != expected_revision:
                raise ValueError("CONFLICT:發布草稿已過期，請重新載入。")
            content = json.loads(rows[0][2])
            for npc in content.get("npcs", {}).values():
                employee_id = npc.get("mapped_employee_id")
                npc.pop("mapped_employee_snapshot", None)
                if employee_id:
                    employee = employee_identity(employee_id)
                    npc["mapped_employee_snapshot"] = {k: employee.get(k, "") for k in
                        ("employee_id", "display_name", "department", "position", "photo_file")}
            errors = adventure.validate_draft(content)
            if errors:
                raise ValueError("劇本驗證未通過：" + "；".join(errors))
            version_no = "VER_" + uuid.uuid4().hex
            cursor.execute("domain.admin_adventure_publish.1", world_no, version_no,
                           json.dumps(content, ensure_ascii=False), published_by)
            published_version = cursor.fetchone()
            if not published_version or published_version[0] is None:
                db.rollback()
                raise DatabaseUnavailable("發布版本未回傳流水號，請重新編譯並重啟 Go 服務後再試。")
            version_display_no = _adventure_display_no("V", published_version[0])
            cursor.execute("domain.admin_adventure_publish.2", version_no, world_no)
            db.commit()
        return {"world_no": world_no, "version_no": version_no,
                "version_display_no": version_display_no, "published": True}
    except database.Error as exc:
        raise DatabaseUnavailable("發布世界版本失敗。") from exc
