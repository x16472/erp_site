"""SQL Server 唯讀資料存取層。

所有提供給前端的查詢均採欄位白名單與彙總輸出，避免姓名、證件、
地址、電話、銀行帳號與薪資等敏感資料離開資料庫。
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.resolve()

# 本機驗證環境可將依賴放在 .deps；正式環境請使用 requirements.txt。
LOCAL_DEPS = ROOT / ".deps"
if LOCAL_DEPS.is_dir():
    sys.path.insert(0, str(LOCAL_DEPS))

try:
    import pyodbc
except ImportError as exc:  # pragma: no cover - 僅在缺少執行環境時發生
    raise RuntimeError("缺少 pyodbc，請先執行 pip install -r requirements.txt") from exc


class DatabaseUnavailable(RuntimeError):
    """資料庫無法連線或查詢時使用的安全例外。"""


def _load_env() -> dict[str, str]:
    """僅從專案的 .env 載入實際 SQL Server 連線設定。"""
    values: dict[str, str] = {}
    env_path = ROOT / ".env"
    if not env_path.is_file():
        raise DatabaseUnavailable("找不到專案 .env，無法連線 SQL Server。")
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def connect(read_only: bool = True):
    """建立 SQL Server 連線；一般查詢預設使用唯讀意圖。"""
    cfg = _load_env()
    required = ("DatabaseIP", "DatabasePort", "DatabaseName", "DatabaseUser", "DatabasePassword")
    missing = [key for key in required if not cfg.get(key)]
    if missing:
        raise DatabaseUnavailable(f"缺少資料庫設定：{', '.join(missing)}")

    driver = cfg.get("DatabaseDriver", "ODBC Driver 17 for SQL Server")
    connection_string = (
        f"DRIVER={{{driver}}};"
        f"SERVER={cfg['DatabaseIP']},{cfg['DatabasePort']};"
        f"DATABASE={cfg['DatabaseName']};"
        f"UID={cfg['DatabaseUser']};PWD={cfg['DatabasePassword']};"
        "Encrypt=no;TrustServerCertificate=yes;Connection Timeout=5;"
        + ("ApplicationIntent=ReadOnly" if read_only else "")
    )
    try:
        return pyodbc.connect(connection_string, autocommit=True)
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("無法連線至 SQL Server，請檢查網路與資料庫設定。") from exc


def admin_credentials() -> tuple[str, str]:
    """取得 MIS 管理員帳密，只供後端比對，永不傳送至前端。"""
    cfg = _load_env()
    username = cfg.get("BackendWebAdminUser", "")
    password = cfg.get("BackendWebAdminPassword", "")
    if not username or not password:
        raise DatabaseUnavailable(".env 尚未設定 MIS 管理員帳號密碼。")
    return username, password


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
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("SQL Server 查詢失敗，請由管理者確認資料表結構。") from exc


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
    matches = _fetch("""
        SELECT TABLE_SCHEMA AS [schema_name], TABLE_NAME AS [table_name]
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_NAME = ?
    """, (table_name,))
    if len(matches) != 1:
        raise ValueError("找不到指定的資料表")
    return matches[0]["schema_name"], matches[0]["table_name"]


HIGHLY_SENSITIVE_KEYWORDS = (
    "身分證", "居留證", "銀行帳號", "帳戶姓名", "戶籍地址", "通訊地址",
    "聯絡電話", "通訊電話", "行動電話", "緊急聯絡", "薪資", "底薪",
    "津貼", "加給", "所得稅", "投保金額", "勞保金額", "健保費", "勞保費",
    "學費", "月費", "保育費", "交通費", "交通車費", "固定收費", "保額費", "費用",
    "折扣", "減免", "應繳金額", "實繳金額", "發單金額",
)
PERSONAL_KEYWORDS = ("姓名", "出生日期", "血型", "電話", "地址", "員工編號", "學號")
RESTRICTED_TABLE_KEYWORDS = ("薪資", "銀行", "健保", "勞保", "其他收入", "異動金額")


def _classification(column_name: str, table_name: str = "") -> str:
    if any(keyword in table_name for keyword in RESTRICTED_TABLE_KEYWORDS):
        return "restricted"
    if any(keyword in table_name for keyword in ("學籍", "繳費", "交通", "親屬")):
        if column_name == "學生識別碼" or column_name.startswith(("父", "母", "緊", "接", "送")):
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
    """列出所有使用者資料表與實際筆數，不查閱資料列。"""
    return _fetch("""
        SELECT s.name AS [schema], t.name AS [name],
               COALESCE(p.[row_count], 0) AS [row_count],
               COALESCE(c.[column_count], 0) AS [column_count]
        FROM sys.tables t
        JOIN sys.schemas s ON s.schema_id = t.schema_id
        OUTER APPLY (SELECT SUM(rows) AS [row_count] FROM sys.partitions WHERE object_id=t.object_id AND index_id IN (0,1)) p
        OUTER APPLY (SELECT COUNT(*) AS [column_count] FROM sys.columns WHERE object_id=t.object_id) c
        ORDER BY CASE WHEN t.name = N'ALLtable' THEN 0 ELSE 1 END, t.name
    """)


def table_data(table_name: str, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    """唯讀分頁查閱資料表；資料表名稱先比對中繼資料，敏感值再遮罩。"""
    page = max(1, int(page))
    page_size = min(50, max(5, int(page_size)))
    schema_name, verified_name = _resolve_table(table_name)
    columns = _fetch("""
        SELECT COLUMN_NAME AS [name], DATA_TYPE AS [type],
               CASE WHEN IS_NULLABLE = 'YES' THEN CAST(1 AS bit) ELSE CAST(0 AS bit) END AS [nullable]
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
        ORDER BY ORDINAL_POSITION
    """, (schema_name, verified_name))
    for column in columns:
        column["classification"] = _classification(column["name"], verified_name)

    identifiers = ", ".join(_quote_identifier(column["name"]) for column in columns)
    qualified = f"{_quote_identifier(schema_name)}.{_quote_identifier(verified_name)}"
    offset = (page - 1) * page_size
    raw_rows = _fetch(
        f"SELECT {identifiers} FROM {qualified} ORDER BY (SELECT NULL) OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
        (offset, page_size),
    ) if columns else []
    rows = [
        {column["name"]: _mask_value(column["name"], row.get(column["name"]), column["classification"]) for column in columns}
        for row in raw_rows
    ]
    total = int(_fetch(f"SELECT COUNT_BIG(*) AS [count] FROM {qualified}")[0]["count"])
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
    # table 僅能由程式內部白名單呼叫，不接受 API 傳入值。
    allowed = {
        "ALLtable", "分校資料", "學籍資料", "班別名稱", "繳費記錄",
        "薪資表", "異動金額記錄", "繳費明細", "繳費項目", "繳費類別", "繳費班別",
        "搭交通車況",
    }
    if table not in allowed:
        raise ValueError("不允許查詢此資料表")
    return int(_fetch(f"SELECT COUNT_BIG(*) AS [筆數] FROM dbo.[{table}]")[0]["筆數"])


def health() -> dict[str, Any]:
    info = _fetch("SELECT DB_NAME() AS [資料庫], COUNT(*) AS [資料表數] FROM sys.tables")[0]
    return {"status": "ok", "source": "mssql", "database": info["資料庫"], "table_count": info["資料表數"], "mode": "read-only"}


DEFAULT_SITE_SETTINGS = {
    "theme": "ocean",
    "hero_title": "在愛與探索中，陪孩子長成自己的模樣",
    "hero_subtitle": "福祿貝爾以遊戲、自然與生活經驗為核心，讓每個孩子在安全而有溫度的環境裡主動學習。",
    "announcement": "歡迎預約參觀，認識福祿貝爾的學習日常。",
}


def site_settings() -> dict[str, str]:
    """讀取網站設定；管理資料表尚未建立時使用安全預設值。"""
    exists = _fetch("SELECT CASE WHEN OBJECT_ID(N'dbo.Frobel_WebSettings', N'U') IS NULL THEN 0 ELSE 1 END AS [exists]")[0]["exists"]
    if not exists:
        return dict(DEFAULT_SITE_SETTINGS)
    rows = _fetch("SELECT TOP (1) [theme], [hero_title], [hero_subtitle], [announcement] FROM dbo.Frobel_WebSettings WHERE [id] = 1")
    return {**DEFAULT_SITE_SETTINGS, **(rows[0] if rows else {})}


def save_site_settings(settings: dict[str, str], actor: str) -> dict[str, str]:
    """只寫入網站專屬設定表，不接受任意資料表或 SQL。"""
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            cursor.execute("""
                IF OBJECT_ID(N'dbo.Frobel_WebSettings', N'U') IS NULL
                CREATE TABLE dbo.Frobel_WebSettings (
                    id int NOT NULL PRIMARY KEY,
                    theme nvarchar(20) NOT NULL,
                    hero_title nvarchar(60) NOT NULL,
                    hero_subtitle nvarchar(180) NOT NULL,
                    announcement nvarchar(160) NULL,
                    updated_by nvarchar(80) NOT NULL,
                    updated_at datetime2 NOT NULL DEFAULT SYSDATETIME()
                )
            """)
            cursor.execute("""
                MERGE dbo.Frobel_WebSettings AS target
                USING (SELECT 1 AS id) AS source ON target.id = source.id
                WHEN MATCHED THEN UPDATE SET theme=?, hero_title=?, hero_subtitle=?, announcement=?, updated_by=?, updated_at=SYSDATETIME()
                WHEN NOT MATCHED THEN INSERT (id,theme,hero_title,hero_subtitle,announcement,updated_by)
                VALUES (1,?,?,?,?,?);
            """, settings["theme"], settings["hero_title"], settings["hero_subtitle"], settings["announcement"], actor,
                 settings["theme"], settings["hero_title"], settings["hero_subtitle"], settings["announcement"], actor)
            db.commit()
        return settings
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("網站設定寫入失敗，請確認管理帳號的資料表權限。") from exc


def public_overview() -> dict[str, Any]:
    """官方網站可公開的設定與統計，不含園區及個人明細。"""
    return {
        "settings": site_settings(),
        "stats": [
            {"label": "園務據點", "value": _count("分校資料")},
            {"label": "教學班級", "value": _count("班別名稱")},
            {"label": "幼兒學籍", "value": _count("學籍資料")},
        ],
    }


def dashboard() -> dict[str, Any]:
    """回傳幼稚園園務總覽，只包含低敏感度彙總資訊。"""
    return {
        "metrics": [
            {"label": "幼兒學籍", "value": _count("學籍資料"), "unit": "筆", "tone": "green"},
            {"label": "教學班級", "value": _count("班別名稱"), "unit": "班", "tone": "blue"},
            {"label": "教職員資料", "value": _count("ALLtable"), "unit": "筆", "tone": "amber"},
            {"label": "接送服務", "value": _count("搭交通車況"), "unit": "筆", "tone": "purple"},
        ],
        "departments": departments(),
        "branches": branches(),
        "classes": class_overview(),
        "data_domains": data_domains(),
    }


def departments() -> list[dict[str, Any]]:
    return _fetch("""
        SELECT COALESCE(NULLIF(LTRIM(RTRIM([服務部門])), N''), N'尚未設定') AS [name],
               COUNT_BIG(*) AS [count]
        FROM dbo.ALLtable
        GROUP BY COALESCE(NULLIF(LTRIM(RTRIM([服務部門])), N''), N'尚未設定')
        ORDER BY [count] DESC, [name]
    """)


def branches() -> list[dict[str, Any]]:
    return _fetch("""
        SELECT b.[分校代號] AS [code],
               COALESCE(NULLIF(LTRIM(RTRIM(b.[簡稱])), N''), b.[分校代號]) AS [name],
               COUNT(a.[員工識別碼]) AS [headcount]
        FROM dbo.[分校資料] b
        LEFT JOIN dbo.ALLtable a ON a.[分校代號] = b.[分校代號]
        WHERE NULLIF(LTRIM(RTRIM(b.[分校代號])), N'') IS NOT NULL
        GROUP BY b.[分校代號], b.[簡稱]
        ORDER BY [headcount] DESC, [code]
    """)


def job_types() -> list[dict[str, Any]]:
    return _fetch("""
        SELECT [代號] AS [code], [職務類別] AS [name], COALESCE([人數], 0) AS [count]
        FROM dbo.[職務類別]
        WHERE NULLIF(LTRIM(RTRIM([職務類別])), N'') IS NOT NULL
        ORDER BY [代號]
    """)


def class_overview() -> list[dict[str, Any]]:
    """班級名稱與分校代號屬低敏感度園務資料。"""
    return _fetch("""
        SELECT [班別] AS [code], COALESCE(NULLIF(LTRIM(RTRIM([班別名稱])), N''), [班別]) AS [name],
               COALESCE(NULLIF(LTRIM(RTRIM([分校代號])), N''), N'未指定') AS [campus]
        FROM dbo.[班別名稱]
        ORDER BY [分校代號], [班別]
    """)


def operations_process() -> list[dict[str, Any]]:
    """以資料表筆數呈現收費作業的資料生命週期。"""
    definitions = [
        ("收費規則", "繳費類別", "定義學費、餐點、活動與交通費的適用範圍"),
        ("收費項目", "繳費項目", "維護托育服務項目與收費分類"),
        ("班級套用", "繳費班別", "將學期收費規則套用到各班級"),
        ("家長繳費", "繳費記錄", "建立繳費主檔並追蹤收款狀態"),
        ("明細核對", "繳費明細", "核對學費、餐點、交通、減免與實繳差異"),
    ]
    return [
        {"id": f"OP-{index:02d}", "stage": stage, "table": table, "count": _count(table), "description": description}
        for index, (stage, table, description) in enumerate(definitions, 1)
    ]


def data_domains() -> list[dict[str, Any]]:
    """資料域只回傳筆數，不讀取敏感明細。"""
    return [
        {"name": "幼兒學籍", "tables": 6, "records": _count("學籍資料"), "note": "學籍、班級、歷史與異動"},
        {"name": "托育收費", "tables": 11, "records": _count("繳費記錄"), "note": "學費、餐點、交通與減免"},
        {"name": "交通接送", "tables": 3, "records": _count("搭交通車況"), "note": "接送方式、車別與安全聯絡"},
        {"name": "園務人事", "tables": 10, "records": _count("ALLtable"), "note": "教職員、部門、職務與薪酬"},
    ]


def knowledge() -> list[dict[str, Any]]:
    """從實際資料域建立可搜尋的內部資料百科。"""
    domains = data_domains()
    items = [
        ("hr", "園務人事主檔", "園務人事", "教職員、部門、職稱與到職資訊的核心來源。", "ALLtable／人事基本資料", "畫面僅提供彙總資訊；個資與薪酬欄位不得直接開放。"),
        ("campus", "分校與班級", "幼兒學籍", "描述園所據點、班別代碼與班級設定。", "分校資料／班別名稱", "分校代號是跨人事、學籍與收費資料的重要關聯鍵。"),
        ("student", "幼兒學籍生命週期", "幼兒學籍", "涵蓋入園、班級、歷史資料與異動記錄。", "學籍資料／學籍歷史／學籍異動", "轉班、升級與離園應保留歷史軌跡。"),
        ("payment", "托育收費流程", "托育收費", "從收費類別、項目、班別到繳費記錄與明細。", "繳費類別／繳費項目／繳費記錄", "學費、餐點、交通及減免需一併核對。"),
        ("payroll", "教職員薪資與加給", "園務人事", "包含薪資等級、加給、保險與薪資結果。", "薪資等級／薪資表", "屬高度敏感資料，應採最小權限與完整稽核。"),
        ("transport", "幼兒接送管理", "交通接送", "記錄接送車別、接送方式與安全聯絡資訊。", "搭交通車況／交通車別", "接送資訊只開放給有業務需要的園務人員。"),
        ("governance", "兒少資料治理", "系統治理", "透過欄位白名單與唯讀連線保護幼兒及家長資料。", "API／權限矩陣／操作日誌", "前端不得直接連線資料庫，所有查詢都必須由後端控管。"),
    ]
    totals = {item["name"]: item["records"] for item in domains}
    return [
        {"id": row[0], "title": row[1], "category": row[2], "summary": row[3], "keywords": row[4], "detail": row[5], "related": f"目前資料量：{totals.get(row[2], 0):,} 筆（彙總）"}
        for row in items
    ]


def permission_profiles() -> list[dict[str, Any]]:
    """依實際職務類別產生最小權限示意，不視為正式授權設定。"""
    profiles = {
        "專職": {"人事名冊": "部門內唯讀", "班別資料": "檢視／維護", "學籍資料": "依職務申請", "薪資資料": "不可見"},
        "兼職": {"個人資料": "本人唯讀", "班別資料": "授課班別唯讀", "學籍資料": "必要欄位唯讀", "薪資資料": "本人薪資單"},
        "外包車": {"個人資料": "本人唯讀", "交通路線": "指派路線唯讀", "學籍資料": "不可見", "薪資資料": "不可見"},
    }
    notes = {
        "專職": "跨部門查詢與匯出應另行申請並保留稽核記錄。",
        "兼職": "權限應隨排課期間自動到期，避免長期保留。",
        "外包車": "僅提供接送所需資訊，禁止下載完整學籍名冊。",
    }
    return [
        {"id": str(row["code"]), "name": row["name"], "description": f"資料庫登錄人數：{row['count']} 人", "permissions": profiles.get(row["name"], {"園務資料": "依申請唯讀"}), "security_note": notes.get(row["name"], "採最小權限並定期盤點。")}
        for row in job_types()
    ]


def questions() -> list[dict[str, Any]]:
    """園務研習題目不包含任何實際幼兒或教職員資料。"""
    return [
        {"id": 1, "category": "兒少資料", "question": "園務首頁需要顯示幼兒人數時，最合適的做法是？", "options": ["公開完整學籍", "由後端回傳彙總人數", "顯示家長電話", "下載接送地址"], "answer": 1, "explanation": "彙總人數足以支援園務決策，不需暴露幼兒與家長資料。"},
        {"id": 2, "category": "托育收費", "question": "建立新學期繳費記錄前，應先確認什麼？", "options": ["收費類別與項目", "教職員銀行帳號", "家長身分證號", "網站色彩"], "answer": 0, "explanation": "學費、餐點、活動與交通項目是後續發單及明細核對的基礎。"},
        {"id": 3, "category": "權限管理", "question": "兼職教職員的園務資料權限應採哪一種原則？", "options": ["永久管理權", "可看全部學籍", "依授課班級與期限開放", "共用管理員帳號"], "answer": 2, "explanation": "依工作範圍與期限授權，才能符合最小權限原則。"},
        {"id": 4, "category": "接送安全", "question": "幼兒接送資料應如何提供給相關人員？", "options": ["公開全園名冊", "只提供執行接送所需資料", "傳到公開群組", "長期下載留存"], "answer": 1, "explanation": "接送資料只應提供給有業務需要的人員，並限制使用範圍與保存時間。"},
    ]
