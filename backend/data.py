"""銀盾共同體 SQL Server 受控資料存取層。
所有提供給前端的查詢均採欄位白名單與彙總輸出，避免姓名、證件、
地址、電話、銀行帳號與薪資等敏感資料離開資料庫。
"""
from __future__ import annotations

import csv
import json
import sys
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

try:
    from . import time_sync as time
except ImportError:  # 支援直接執行 backend/data.py
    import time_sync as time

BACKEND_ROOT = Path(__file__).parent.resolve()
PROJECT_ROOT = BACKEND_ROOT.parent
PAGE_ROOT = PROJECT_ROOT / "page"
STAFF_CSV = PROJECT_ROOT / "data" / "staff.csv"
STAFF_SYNC_LOCK = threading.Lock()

# 本機驗證環境可將依賴放在 .deps；正式環境請使用 requirements.txt。
LOCAL_DEPS = PROJECT_ROOT / ".deps"
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
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        raise DatabaseUnavailable("找不到專案 .env，無法連線 SQL Server。")
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def connect(read_only: bool = True, autocommit: bool = True):
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
        + ("ApplicationIntent=ReadOnly;" if read_only else "")
    )
    try:
        return pyodbc.connect(connection_string, autocommit=autocommit)
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("無法連線至 SQL Server，請檢查網路與資料庫設定。") from exc


def admin_credentials() -> tuple[str, str]:
    """取得 後台管理員帳密，只供後端比對，永不傳送至前端。"""
    cfg = _load_env()
    username = cfg.get("BackendWebAdminUser", "")
    password = cfg.get("BackendWebAdminPassword", "")
    if not username or not password:
        raise DatabaseUnavailable(".env 尚未設定 後台管理員帳號密碼。")
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
    """僅解析銀盾共同體白名單內的應用資料表。"""
    if table_name not in APPLICATION_TABLES:
        raise ValueError("只允許查閱銀盾共同體應用資料表")
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
    "交易費", "服務費", "成本", "費用", "折扣", "減免", "應收金額", "實收金額",
)
PERSONAL_KEYWORDS = ("姓名", "出生日期", "血型", "電話", "地址", "員工編號", "客戶編號")
RESTRICTED_TABLE_KEYWORDS = ("薪資", "銀行", "健保", "勞保", "其他收入", "異動金額")


def _classification(column_name: str, table_name: str = "") -> str:
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
    rows = _fetch("""
        SELECT s.name AS [schema], t.name AS [name],
               COALESCE(p.[row_count], 0) AS [row_count],
               COALESCE(c.[column_count], 0) AS [column_count]
        FROM sys.tables t
        JOIN sys.schemas s ON s.schema_id = t.schema_id
        OUTER APPLY (SELECT SUM(rows) AS [row_count] FROM sys.partitions WHERE object_id=t.object_id AND index_id IN (0,1)) p
        OUTER APPLY (SELECT COUNT(*) AS [column_count] FROM sys.columns WHERE object_id=t.object_id) c
        ORDER BY t.name
    """)
    allowed_rows = [row for row in rows if row["schema"] == "dbo" and row["name"] in APPLICATION_TABLES]
    for row in allowed_rows:
        row["display_name"] = TABLE_DISPLAY_NAMES.get(row["name"], row["name"])
    return allowed_rows


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
    """僅統計附圖列出的應用資料表，不接受其他資料庫表名。"""
    if table not in APPLICATION_TABLES:
        raise ValueError("不允許查詢此資料表")
    return int(_fetch(f"SELECT COUNT_BIG(*) AS [筆數] FROM dbo.[{table}]")[0]["筆數"])


def health() -> dict[str, Any]:
    """回傳資料庫與銀盾應用表健康狀態。"""
    info = _fetch("SELECT DB_NAME() AS [資料庫]")[0]
    return {"status": "ok", "source": "mssql", "database": info["資料庫"], "table_count": len(table_catalog()), "mode": "company-only"}


DEFAULT_SITE_SETTINGS = {
    "theme": "shield",
    "hero_title": "銀盾共同體｜誠信連結每一份事業",
    "hero_subtitle": "以家族為核心、誠信與慷慨為本，整合行政、商務、生產與資源服務，讓成員共享成果並拓展事業。",
    "announcement": "LIVE AND LET LIVE.｜共生、誠信、共享成果。",
}


def site_settings() -> dict[str, str]:
    """讀取網站設定；管理資料表尚未建立時使用安全預設值。"""
    exists = _fetch("SELECT CASE WHEN OBJECT_ID(N'dbo.Company_WebSettings', N'U') IS NULL THEN 0 ELSE 1 END AS [exists]")[0]["exists"]
    if not exists:
        return dict(DEFAULT_SITE_SETTINGS)
    rows = _fetch("SELECT TOP (1) [theme], [hero_title], [hero_subtitle], [announcement] FROM dbo.Company_WebSettings WHERE [id] = 1")
    return {**DEFAULT_SITE_SETTINGS, **(rows[0] if rows else {})}


def save_site_settings(settings: dict[str, str], actor: str) -> dict[str, str]:
    """只寫入網站專屬設定表，不接受任意資料表或 SQL。"""
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            cursor.execute("""
                IF OBJECT_ID(N'dbo.Company_WebSettings', N'U') IS NULL
                CREATE TABLE dbo.Company_WebSettings (
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
                MERGE dbo.Company_WebSettings AS target
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
    """官方網站可公開的設定與 Company 應用資料彙總。"""
    return {
        "settings": site_settings(),
        "stats": [
            {"label": "專業成員", "value": int(_fetch("SELECT COUNT_BIG(*) AS [count] FROM dbo.Company_Staff WHERE is_active=1")[0]["count"])},
            {"label": "營運部門", "value": int(_fetch("SELECT COUNT_BIG(*) AS [count] FROM dbo.Company_Department WHERE is_active=1")[0]["count"])},
            {"label": "營運SOP", "value": int(_fetch("SELECT COUNT_BIG(*) AS [count] FROM dbo.Company_TrainingDocument WHERE is_active=1")[0]["count"])},
        ],
    }


def dashboard() -> dict[str, Any]:
    """回傳只依附圖所列資料表產生的工作台彙總。"""
    return {
        "metrics": [
            {"label": "在職員工", "value": int(_fetch("SELECT COUNT_BIG(*) AS [count] FROM dbo.Company_Staff WHERE is_active=1")[0]["count"]), "unit": "位", "tone": "green"},
            {"label": "本日打卡", "value": int(_fetch("SELECT COUNT_BIG(*) AS [count] FROM dbo.Company_Attendance WHERE work_date=CONVERT(date,SYSUTCDATETIME() AT TIME ZONE 'UTC' AT TIME ZONE 'Taipei Standard Time')")[0]["count"]), "unit": "筆", "tone": "blue"},
            {"label": "待審日報", "value": int(_fetch("SELECT COUNT_BIG(*) AS [count] FROM dbo.Company_OperationSubmission WHERE status=N'待審核'")[0]["count"]), "unit": "筆", "tone": "amber"},
            {"label": "營運SOP", "value": int(_fetch("SELECT COUNT_BIG(*) AS [count] FROM dbo.Company_TrainingDocument WHERE is_active=1")[0]["count"]), "unit": "份", "tone": "purple"},
        ],
        "departments": departments(),
        "branches": branches(),
        "classes": [],
        "data_domains": [],
    }


def departments() -> list[dict[str, Any]]:
    return _fetch("""
        SELECT d.department_name AS [name],COUNT_BIG(s.employee_id) AS [count]
        FROM dbo.Company_Department d
        LEFT JOIN dbo.Company_Staff s ON s.department=d.department_name AND s.is_active=1
        WHERE d.is_active=1
        GROUP BY d.department_name
        ORDER BY [count] DESC,[name]
    """)


def branches() -> list[dict[str, Any]]:
    """回傳四大固定營運據點及各據點既有日報數量。"""
    return _fetch("""
        WITH campuses AS (
            SELECT * FROM (VALUES
                (N'MANOR',N'羅瓦德莊園',1),
                (N'SALON',N'可可藝術沙龍',2),
                (N'CRAFT',N'聯合工匠街',3),
                (N'MINE',N'地下堅石礦場',4)
            ) AS source(code,name,display_order)
        )
        SELECT c.code,c.name,COUNT_BIG(s.submission_id) AS [headcount]
        FROM campuses c
        LEFT JOIN dbo.Company_OperationSubmission s ON s.campus_code=c.code
        GROUP BY c.code,c.name,c.display_order
        ORDER BY c.display_order
    """)


def operations_process() -> list[dict[str, Any]]:
    """以營運分類與待審日報呈現目前可用的生命週期。"""
    return _fetch("""
        SELECT CONCAT(N'OP-',RIGHT(N'00'+CONVERT(nvarchar(2),c.display_order),2)) AS id,
               c.category_code AS stage,N'Company_OperationSubmission' AS [table],
               COUNT_BIG(s.submission_id) AS [count],
               N'依營運分類彙整待審與已填報日報。' AS [description]
        FROM dbo.Company_OperationCategory c
        LEFT JOIN dbo.Company_OperationSubmission s ON s.category_code=c.category_code
        GROUP BY c.category_code,c.display_order
        ORDER BY c.display_order
    """)


def knowledge() -> list[dict[str, Any]]:
    """新資料庫未提供獨立知識主檔，工作台保留空結果等待後續建檔。"""
    return []


def _default_questions() -> list[dict[str, Any]]:
    """提供不含實際員工或客戶資料的商業營運檢核題目。"""
    return [
#         {"id": 1, "category": "資料治理",
#           "question": "營運儀表板需要顯示人員規模時，最合適的做法是？",
#           "options": [
#               "公開完整員工主檔", "由後端回傳彙總人數", "顯示私人聯絡方式", "下載薪資明細"
#               ],
#           "answer": 1, "explanation": "彙總數字足以支援營運判斷，不需暴露成員個人資料。"},
#         {"id": 2, "category": "合約覆核", "question": "建立商業合約或帳務紀錄前，應優先確認什麼？", "options": [
#             "交易項目與授權範圍", "員工私人帳號", "客戶證件影本", "網站配色"
#             ], "answer": 0, "explanation": "先確認交易標的、責任與授權，才能維持完整且可稽核的紀錄。"},
#         {"id": 3, "category": "權限管理", "question": "專案協作人員的內部資料權限應採哪一種原則？", "options": ["永久管理權", "開放全部資料", "依工作範圍與期限開放", "共用管理員帳號"], "answer": 2, "explanation": "依實際職責與期限授權，才能符合最小權限原則。"},
#         {"id": 4, "category": "工安管理", "question": "進入製造區或礦場前，最先應完成哪項程序？", "options": ["跳過現場點名", "確認防護裝備與作業許可", "自行修改機具設定", "將安全資料公開轉傳"], "answer": 1, "explanation": "高風險作業必須先確認個人防護、現場授權與設備狀態。"},
    ]


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
    cursor.execute("UPDATE dbo.Company_OperationCategory SET display_order=display_order+100 WHERE display_order<100")
    for order, category in enumerate(desired_categories, 1):
        cursor.execute(
            "IF NOT EXISTS (SELECT 1 FROM dbo.Company_OperationCategory WHERE category_code=?) "
            "INSERT dbo.Company_OperationCategory (category_code,display_order) VALUES (?,?)",
            category,
            category,
            order,
        )
    for order, category in enumerate(desired_categories, 1):
        cursor.execute("UPDATE dbo.Company_OperationCategory SET display_order=? WHERE category_code=?", order, category)
    cursor.execute("DELETE dbo.Company_OperationCategory WHERE display_order>=100")
    cursor.execute(
        """UPDATE dbo.Company_WebSettings
           SET theme=CASE theme
               WHEN N'ocean' THEN N'shield'
               WHEN N'sunrise' THEN N'medal'
               WHEN N'forest' THEN N'steel'
               ELSE theme END
           WHERE theme IN (N'ocean',N'sunrise',N'forest')"""
    )


def _normalize_company_departments(cursor) -> None:
    """確保六個短名稱部門存在，並停用沒有在職員工的部門。"""
    for department_name in ("營運部", "製造部", "財務部", "資訊部", "福利部", "後勤部"):
        cursor.execute(
            """IF NOT EXISTS (SELECT 1 FROM dbo.Company_Department WHERE department_name=?)
               INSERT dbo.Company_Department (department_name,updated_by) VALUES (?,N'prd-migration')""",
            department_name,
            department_name,
        )
    cursor.execute(
        """UPDATE d SET is_active=CASE WHEN EXISTS (
                   SELECT 1 FROM dbo.Company_Staff s WHERE s.department=d.department_name AND s.is_active=1
               ) THEN 1 ELSE 0 END,
               updated_by=N'prd-migration',updated_at=SYSDATETIME()
           FROM dbo.Company_Department d"""
    )


def ensure_application_schema() -> dict[str, Any]:
    """建立 Company 正規化資料表並更新商業基礎資料。"""
    statements = [
        """IF OBJECT_ID(N'dbo.Company_WebSettings', N'U') IS NULL
        CREATE TABLE dbo.Company_WebSettings (
            id int NOT NULL PRIMARY KEY,
            theme nvarchar(20) NOT NULL,
            hero_title nvarchar(60) NOT NULL,
            hero_subtitle nvarchar(180) NOT NULL,
            announcement nvarchar(160) NULL,
            updated_by nvarchar(80) NOT NULL,
            updated_at datetime2 NOT NULL DEFAULT SYSDATETIME()
        )""",
        """IF OBJECT_ID(N'dbo.Company_Staff', N'U') IS NULL
        CREATE TABLE dbo.Company_Staff (
            employee_id nvarchar(20) NOT NULL PRIMARY KEY,
            display_name nvarchar(50) NOT NULL,
            gender nvarchar(10) NULL,
            age smallint NULL,
            department nvarchar(50) NOT NULL,
            position nvarchar(50) NOT NULL,
            traits nvarchar(200) NULL,
            biography nvarchar(1000) NULL,
            photo_file nvarchar(100) NULL,
            is_active bit NOT NULL DEFAULT 1,
            updated_by nvarchar(80) NOT NULL,
            updated_at datetime2 NOT NULL DEFAULT SYSDATETIME(),
            CONSTRAINT CK_Company_Staff_Age CHECK (age IS NULL OR age BETWEEN 16 AND 100)
        )""",
        """IF OBJECT_ID(N'dbo.Company_Department', N'U') IS NULL
        CREATE TABLE dbo.Company_Department (
            department_id int IDENTITY(1,1) NOT NULL PRIMARY KEY,
            department_name nvarchar(50) NOT NULL UNIQUE,
            is_active bit NOT NULL DEFAULT 1,
            updated_by nvarchar(80) NOT NULL,
            updated_at datetime2 NOT NULL DEFAULT SYSDATETIME()
        )""",
        """IF OBJECT_ID(N'dbo.Company_Attendance', N'U') IS NULL
        CREATE TABLE dbo.Company_Attendance (
            attendance_id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
            employee_id nvarchar(20) NOT NULL,
            action nvarchar(20) NOT NULL,
            clocked_at datetime2 NOT NULL DEFAULT SYSDATETIME(),
            clocked_at_utc datetime2 NULL,
            work_date date NULL,
            source_ip nvarchar(45) NULL,
            CONSTRAINT FK_Company_Attendance_Staff FOREIGN KEY (employee_id) REFERENCES dbo.Company_Staff(employee_id),
            CONSTRAINT CK_Company_Attendance_Action CHECK (action IN (N'CLOCK_IN', N'CLOCK_OUT'))
        )""",
        """IF COL_LENGTH(N'dbo.Company_Attendance', N'clocked_at_utc') IS NULL
        ALTER TABLE dbo.Company_Attendance ADD clocked_at_utc datetime2 NULL""",
        """IF COL_LENGTH(N'dbo.Company_Attendance', N'work_date') IS NULL
        ALTER TABLE dbo.Company_Attendance ADD work_date date NULL""",
        """UPDATE dbo.Company_Attendance
        SET clocked_at_utc=COALESCE(clocked_at_utc,clocked_at),
            work_date=COALESCE(work_date,CONVERT(date,clocked_at AT TIME ZONE 'UTC' AT TIME ZONE 'Taipei Standard Time'))
        WHERE clocked_at_utc IS NULL OR work_date IS NULL""",
        """IF OBJECT_ID(N'dbo.Company_OperationCategory', N'U') IS NULL
        CREATE TABLE dbo.Company_OperationCategory (
            category_code nvarchar(10) NOT NULL PRIMARY KEY,
            display_order tinyint NOT NULL UNIQUE
        )""",
        """IF OBJECT_ID(N'dbo.Company_OperationSubmission', N'U') IS NULL
        CREATE TABLE dbo.Company_OperationSubmission (
            submission_id nvarchar(40) NOT NULL PRIMARY KEY,
            operation_date date NOT NULL,
            campus_code nvarchar(12) NOT NULL,
            category_code nvarchar(10) NOT NULL,
            quantity int NOT NULL,
            note nvarchar(200) NULL,
            submitted_by nvarchar(20) NULL,
            status nvarchar(20) NOT NULL DEFAULT N'待審核',
            submitted_at datetime2 NOT NULL DEFAULT SYSDATETIME(),
            CONSTRAINT FK_Company_OperationSubmission_Category FOREIGN KEY (category_code) REFERENCES dbo.Company_OperationCategory(category_code),
            CONSTRAINT FK_Company_OperationSubmission_Staff FOREIGN KEY (submitted_by) REFERENCES dbo.Company_Staff(employee_id),
            CONSTRAINT CK_Company_OperationSubmission_Quantity CHECK (quantity BETWEEN 0 AND 9999)
        )""",
        """IF COL_LENGTH(N'dbo.Company_OperationSubmission', N'submitted_by') IS NULL
        ALTER TABLE dbo.Company_OperationSubmission ADD submitted_by nvarchar(20) NULL""",
        """IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_Company_OperationSubmission_Staff')
        ALTER TABLE dbo.Company_OperationSubmission ADD CONSTRAINT FK_Company_OperationSubmission_Staff
        FOREIGN KEY (submitted_by) REFERENCES dbo.Company_Staff(employee_id)""",
        """IF OBJECT_ID(N'dbo.Company_OperationActivity', N'U') IS NULL
        CREATE TABLE dbo.Company_OperationActivity (
            activity_id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
            submission_id nvarchar(40) NOT NULL,
            action_type nvarchar(30) NOT NULL,
            message nvarchar(1000) NULL,
            actor_employee_id nvarchar(20) NULL,
            actor_role nvarchar(20) NOT NULL,
            created_at datetime2 NOT NULL DEFAULT SYSDATETIME(),
            CONSTRAINT FK_Company_OperationActivity_Submission FOREIGN KEY (submission_id) REFERENCES dbo.Company_OperationSubmission(submission_id) ON DELETE CASCADE,
            CONSTRAINT FK_Company_OperationActivity_Staff FOREIGN KEY (actor_employee_id) REFERENCES dbo.Company_Staff(employee_id)
        )""",
        """IF OBJECT_ID(N'dbo.Company_TrainingDocument', N'U') IS NULL
        CREATE TABLE dbo.Company_TrainingDocument (
            document_id int IDENTITY(1,1) NOT NULL PRIMARY KEY,
            file_name nvarchar(260) NOT NULL UNIQUE,
            title nvarchar(200) NOT NULL,
            role_category nvarchar(80) NOT NULL,
            source_size bigint NOT NULL,
            source_modified nvarchar(40) NOT NULL,
            is_active bit NOT NULL DEFAULT 1,
            imported_at datetime2 NOT NULL DEFAULT SYSDATETIME()
        )""",
        """IF OBJECT_ID(N'dbo.Company_TrainingSection', N'U') IS NULL
        CREATE TABLE dbo.Company_TrainingSection (
            section_id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
            document_id int NOT NULL,
            section_order int NOT NULL,
            heading nvarchar(300) NOT NULL,
            content nvarchar(max) NOT NULL,
            CONSTRAINT FK_Company_TrainingSection_Document FOREIGN KEY (document_id) REFERENCES dbo.Company_TrainingDocument(document_id) ON DELETE CASCADE,
            CONSTRAINT UQ_Company_TrainingSection_Order UNIQUE (document_id, section_order)
        )""",
        """IF OBJECT_ID(N'dbo.Company_TrainingQuestion', N'U') IS NULL
        CREATE TABLE dbo.Company_TrainingQuestion (
            question_id int IDENTITY(1,1) NOT NULL PRIMARY KEY,
            document_id int NULL,
            category nvarchar(50) NOT NULL,
            question nvarchar(500) NOT NULL,
            options_json nvarchar(max) NOT NULL,
            correct_index tinyint NOT NULL,
            explanation nvarchar(1000) NOT NULL,
            question_type nvarchar(30) NOT NULL DEFAULT N'single_choice',
            answer_json nvarchar(max) NOT NULL DEFAULT N'[]',
            passage nvarchar(max) NULL,
            is_active bit NOT NULL DEFAULT 1,
            CONSTRAINT FK_Company_TrainingQuestion_Document FOREIGN KEY (document_id) REFERENCES dbo.Company_TrainingDocument(document_id),
            CONSTRAINT CK_Company_TrainingQuestion_Answer CHECK (correct_index BETWEEN 0 AND 9)
        )""",
        """IF COL_LENGTH(N'dbo.Company_TrainingQuestion', N'question_type') IS NULL
        ALTER TABLE dbo.Company_TrainingQuestion ADD question_type nvarchar(30) NULL""",
        """IF COL_LENGTH(N'dbo.Company_TrainingQuestion', N'answer_json') IS NULL
        ALTER TABLE dbo.Company_TrainingQuestion ADD answer_json nvarchar(max) NULL""",
        """IF COL_LENGTH(N'dbo.Company_TrainingQuestion', N'passage') IS NULL
        ALTER TABLE dbo.Company_TrainingQuestion ADD passage nvarchar(max) NULL""",
        """UPDATE dbo.Company_TrainingQuestion
        SET question_type=COALESCE(question_type,N'single_choice'),
            answer_json=COALESCE(answer_json,CONCAT(N'[',CONVERT(nvarchar(3),correct_index),N']'))
        WHERE question_type IS NULL OR answer_json IS NULL""",
        """IF OBJECT_ID(N'dbo.Company_TrainingAnswer', N'U') IS NULL
        CREATE TABLE dbo.Company_TrainingAnswer (
            answer_id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
            question_id int NOT NULL,
            employee_id nvarchar(20) NOT NULL,
            answer_text nvarchar(max) NOT NULL,
            status nvarchar(20) NOT NULL DEFAULT N'待審核',
            feedback nvarchar(1000) NULL,
            submitted_at datetime2 NOT NULL DEFAULT SYSDATETIME(),
            reviewed_by nvarchar(20) NULL,
            reviewed_at datetime2 NULL,
            CONSTRAINT FK_Company_TrainingAnswer_Question FOREIGN KEY (question_id) REFERENCES dbo.Company_TrainingQuestion(question_id),
            CONSTRAINT FK_Company_TrainingAnswer_Employee FOREIGN KEY (employee_id) REFERENCES dbo.Company_Staff(employee_id),
            CONSTRAINT FK_Company_TrainingAnswer_Reviewer FOREIGN KEY (reviewed_by) REFERENCES dbo.Company_Staff(employee_id)
        )""",
        """IF OBJECT_ID(N'dbo.Company_TrainingSubject', N'U') IS NULL
        CREATE TABLE dbo.Company_TrainingSubject (
            subject_id int IDENTITY(1,1) NOT NULL PRIMARY KEY,
            domain nvarchar(20) NOT NULL,
            subject_name nvarchar(100) NOT NULL,
            mock_question_count int NOT NULL DEFAULT 40,
            mock_duration_minutes int NOT NULL DEFAULT 45,
            mock_pass_score int NOT NULL DEFAULT 70,
            is_active bit NOT NULL DEFAULT 1,
            CONSTRAINT UQ_Company_TrainingSubject UNIQUE (domain,subject_name)
        )""",
        """IF OBJECT_ID(N'dbo.Company_TrainingChapter', N'U') IS NULL
        CREATE TABLE dbo.Company_TrainingChapter (
            chapter_id int IDENTITY(1,1) NOT NULL PRIMARY KEY,
            subject_id int NOT NULL,
            chapter_code nvarchar(30) NOT NULL,
            chapter_name nvarchar(120) NOT NULL,
            display_order int NOT NULL DEFAULT 0,
            is_active bit NOT NULL DEFAULT 1,
            CONSTRAINT FK_Company_TrainingChapter_Subject FOREIGN KEY (subject_id) REFERENCES dbo.Company_TrainingSubject(subject_id),
            CONSTRAINT UQ_Company_TrainingChapter UNIQUE (subject_id,chapter_code)
        )""",
        """IF COL_LENGTH(N'dbo.Company_TrainingDocument', N'source_kind') IS NULL
        ALTER TABLE dbo.Company_TrainingDocument ADD source_kind nvarchar(30) NOT NULL CONSTRAINT DF_Company_TrainingDocument_SourceKind DEFAULT N'manual' WITH VALUES""",
        """IF COL_LENGTH(N'dbo.Company_TrainingDocument', N'parse_status') IS NULL
        ALTER TABLE dbo.Company_TrainingDocument ADD parse_status nvarchar(30) NULL""",
        """IF COL_LENGTH(N'dbo.Company_TrainingDocument', N'parse_message') IS NULL
        ALTER TABLE dbo.Company_TrainingDocument ADD parse_message nvarchar(1000) NULL""",
        """IF COL_LENGTH(N'dbo.Company_TrainingQuestion', N'domain') IS NULL
        ALTER TABLE dbo.Company_TrainingQuestion ADD domain nvarchar(20) NOT NULL CONSTRAINT DF_Company_TrainingQuestion_Domain DEFAULT N'academic' WITH VALUES""",
        """IF COL_LENGTH(N'dbo.Company_TrainingQuestion', N'subject_id') IS NULL
        ALTER TABLE dbo.Company_TrainingQuestion ADD subject_id int NULL""",
        """IF COL_LENGTH(N'dbo.Company_TrainingQuestion', N'chapter_id') IS NULL
        ALTER TABLE dbo.Company_TrainingQuestion ADD chapter_id int NULL""",
        """IF COL_LENGTH(N'dbo.Company_TrainingQuestion', N'content_json') IS NULL
        ALTER TABLE dbo.Company_TrainingQuestion ADD content_json nvarchar(max) NULL""",
        """IF COL_LENGTH(N'dbo.Company_TrainingQuestion', N'structure_json') IS NULL
        ALTER TABLE dbo.Company_TrainingQuestion ADD structure_json nvarchar(max) NULL""",
        """IF COL_LENGTH(N'dbo.Company_TrainingQuestion', N'source_locator') IS NULL
        ALTER TABLE dbo.Company_TrainingQuestion ADD source_locator nvarchar(300) NULL""",
        """IF COL_LENGTH(N'dbo.Company_TrainingQuestion', N'source_question_key') IS NULL
        ALTER TABLE dbo.Company_TrainingQuestion ADD source_question_key nvarchar(200) NULL""",
        """IF COL_LENGTH(N'dbo.Company_TrainingQuestion', N'source_fingerprint') IS NULL
        ALTER TABLE dbo.Company_TrainingQuestion ADD source_fingerprint char(64) NULL""",
        """IF COL_LENGTH(N'dbo.Company_TrainingQuestion', N'parse_confidence') IS NULL
        ALTER TABLE dbo.Company_TrainingQuestion ADD parse_confidence decimal(5,2) NULL""",
        """IF COL_LENGTH(N'dbo.Company_TrainingQuestion', N'parse_warnings_json') IS NULL
        ALTER TABLE dbo.Company_TrainingQuestion ADD parse_warnings_json nvarchar(max) NULL""",
        """IF COL_LENGTH(N'dbo.Company_TrainingQuestion', N'status') IS NULL
        ALTER TABLE dbo.Company_TrainingQuestion ADD status nvarchar(20) NOT NULL CONSTRAINT DF_Company_TrainingQuestion_Status DEFAULT N'published' WITH VALUES""",
        """IF COL_LENGTH(N'dbo.Company_TrainingQuestion', N'admin_locked') IS NULL
        ALTER TABLE dbo.Company_TrainingQuestion ADD admin_locked bit NOT NULL CONSTRAINT DF_Company_TrainingQuestion_AdminLocked DEFAULT 0 WITH VALUES""",
        """IF COL_LENGTH(N'dbo.Company_TrainingQuestion', N'updated_at') IS NULL
        ALTER TABLE dbo.Company_TrainingQuestion ADD updated_at datetime2 NOT NULL CONSTRAINT DF_Company_TrainingQuestion_UpdatedAt DEFAULT SYSDATETIME() WITH VALUES""",
        """IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_Company_TrainingQuestion_Subject')
        ALTER TABLE dbo.Company_TrainingQuestion ADD CONSTRAINT FK_Company_TrainingQuestion_Subject
        FOREIGN KEY (subject_id) REFERENCES dbo.Company_TrainingSubject(subject_id)""",
        """IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_Company_TrainingQuestion_Chapter')
        ALTER TABLE dbo.Company_TrainingQuestion ADD CONSTRAINT FK_Company_TrainingQuestion_Chapter
        FOREIGN KEY (chapter_id) REFERENCES dbo.Company_TrainingChapter(chapter_id)""",
        """IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_Company_TrainingQuestion_Fingerprint' AND object_id=OBJECT_ID(N'dbo.Company_TrainingQuestion'))
        CREATE UNIQUE INDEX UX_Company_TrainingQuestion_Fingerprint ON dbo.Company_TrainingQuestion(source_fingerprint) WHERE source_fingerprint IS NOT NULL""",
        """IF OBJECT_ID(N'dbo.Company_TrainingSession', N'U') IS NULL
        CREATE TABLE dbo.Company_TrainingSession (
            session_id uniqueidentifier NOT NULL PRIMARY KEY,
            employee_id nvarchar(20) NOT NULL,
            subject_id int NOT NULL,
            mode nvarchar(20) NOT NULL,
            status nvarchar(20) NOT NULL DEFAULT N'in_progress',
            config_json nvarchar(max) NOT NULL,
            started_at datetime2 NOT NULL DEFAULT SYSUTCDATETIME(),
            expires_at datetime2 NULL,
            submitted_at datetime2 NULL,
            score decimal(5,2) NULL,
            CONSTRAINT FK_Company_TrainingSession_Employee FOREIGN KEY (employee_id) REFERENCES dbo.Company_Staff(employee_id),
            CONSTRAINT FK_Company_TrainingSession_Subject FOREIGN KEY (subject_id) REFERENCES dbo.Company_TrainingSubject(subject_id)
        )""",
        """IF OBJECT_ID(N'dbo.Company_TrainingSessionQuestion', N'U') IS NULL
        CREATE TABLE dbo.Company_TrainingSessionQuestion (
            session_question_id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
            session_id uniqueidentifier NOT NULL,
            question_id int NOT NULL,
            question_order int NOT NULL,
            snapshot_json nvarchar(max) NOT NULL,
            response_json nvarchar(max) NULL,
            is_flagged bit NOT NULL DEFAULT 0,
            is_correct bit NULL,
            answered_at datetime2 NULL,
            CONSTRAINT FK_Company_TrainingSessionQuestion_Session FOREIGN KEY (session_id) REFERENCES dbo.Company_TrainingSession(session_id) ON DELETE CASCADE,
            CONSTRAINT FK_Company_TrainingSessionQuestion_Question FOREIGN KEY (question_id) REFERENCES dbo.Company_TrainingQuestion(question_id),
            CONSTRAINT UQ_Company_TrainingSessionQuestion_Order UNIQUE (session_id,question_order)
        )""",
        """IF OBJECT_ID(N'dbo.Company_TrainingWrongQuestion', N'U') IS NULL
        CREATE TABLE dbo.Company_TrainingWrongQuestion (
            employee_id nvarchar(20) NOT NULL,
            question_id int NOT NULL,
            added_at datetime2 NOT NULL DEFAULT SYSUTCDATETIME(),
            removed_at datetime2 NULL,
            CONSTRAINT PK_Company_TrainingWrongQuestion PRIMARY KEY (employee_id,question_id),
            CONSTRAINT FK_Company_TrainingWrongQuestion_Employee FOREIGN KEY (employee_id) REFERENCES dbo.Company_Staff(employee_id),
            CONSTRAINT FK_Company_TrainingWrongQuestion_Question FOREIGN KEY (question_id) REFERENCES dbo.Company_TrainingQuestion(question_id)
        )""",
        """IF OBJECT_ID(N'dbo.Company_ImportState', N'U') IS NULL
        CREATE TABLE dbo.Company_ImportState (
            source_key nvarchar(100) NOT NULL PRIMARY KEY,
            source_modified bigint NOT NULL,
            source_size bigint NOT NULL,
            imported_rows int NOT NULL,
            imported_at datetime2 NOT NULL DEFAULT SYSDATETIME()
        )""",
    ]
    try:
        with connect(read_only=False, autocommit=False) as db:
            cursor = db.cursor()
            for statement in statements:
                cursor.execute(statement)
            _migrate_business_seed_data(cursor)
            cursor.execute("""
                MERGE dbo.Company_TrainingSubject AS target
                USING (VALUES
                    (N'academic',N'通用知識',40,45,70),
                    (N'practical',N'術科申論',0,0,0)
                ) AS source(domain,subject_name,question_count,duration_minutes,pass_score)
                ON target.domain=source.domain AND target.subject_name=source.subject_name
                WHEN MATCHED THEN UPDATE SET is_active=1
                WHEN NOT MATCHED THEN INSERT
                    (domain,subject_name,mock_question_count,mock_duration_minutes,mock_pass_score,is_active)
                    VALUES (source.domain,source.subject_name,source.question_count,source.duration_minutes,source.pass_score,1);
            """)
            academic_subject_id = cursor.execute(
                "SELECT subject_id FROM dbo.Company_TrainingSubject WHERE domain=N'academic' AND subject_name=N'通用知識'"
            ).fetchone()[0]
            practical_subject_id = cursor.execute(
                "SELECT subject_id FROM dbo.Company_TrainingSubject WHERE domain=N'practical' AND subject_name=N'術科申論'"
            ).fetchone()[0]
            for subject_id in (academic_subject_id, practical_subject_id):
                cursor.execute("""
                    IF NOT EXISTS (SELECT 1 FROM dbo.Company_TrainingChapter WHERE subject_id=? AND chapter_code=N'UNSORTED')
                    INSERT dbo.Company_TrainingChapter (subject_id,chapter_code,chapter_name,display_order)
                    VALUES (?,N'UNSORTED',N'未分類',999)
                """, subject_id, subject_id)
            count = cursor.execute("SELECT COUNT(*) FROM dbo.Company_TrainingQuestion").fetchone()[0]
            if not count:
                for item in _default_questions():
                    cursor.execute("""
                        INSERT dbo.Company_TrainingQuestion
                        (category,question,options_json,correct_index,explanation,question_type,answer_json)
                        VALUES (?,?,?,?,?,N'single_choice',?)
                    """, item["category"], item["question"], json.dumps(item["options"], ensure_ascii=False),
                         item["answer"], item["explanation"], json.dumps([item["answer"]]))
            academic_chapter_id = cursor.execute(
                "SELECT chapter_id FROM dbo.Company_TrainingChapter WHERE subject_id=? AND chapter_code=N'UNSORTED'",
                academic_subject_id,
            ).fetchone()[0]
            practical_chapter_id = cursor.execute(
                "SELECT chapter_id FROM dbo.Company_TrainingChapter WHERE subject_id=? AND chapter_code=N'UNSORTED'",
                practical_subject_id,
            ).fetchone()[0]
            cursor.execute("""
                UPDATE dbo.Company_TrainingQuestion
                SET domain=CASE WHEN question_type=N'essay' THEN N'practical' ELSE N'academic' END,
                    subject_id=CASE WHEN question_type=N'essay' THEN ? ELSE ? END,
                    chapter_id=CASE WHEN question_type=N'essay' THEN ? ELSE ? END,
                    status=CASE WHEN is_active=1 THEN N'published' ELSE N'disabled' END,
                    content_json=COALESCE(content_json,CONCAT(N'[{"type":"text","content":',
                        N'"',STRING_ESCAPE(question,'json'),N'"}]')),
                    structure_json=COALESCE(structure_json,N'{}'),
                    parse_warnings_json=COALESCE(parse_warnings_json,N'[]')
                WHERE subject_id IS NULL OR chapter_id IS NULL OR content_json IS NULL
            """, practical_subject_id, academic_subject_id, practical_chapter_id, academic_chapter_id)
            _sync_staff_csv_cursor(cursor)
            _normalize_company_departments(cursor)
            cursor.execute("""
                INSERT dbo.Company_Department (department_name,updated_by)
                SELECT DISTINCT s.department,N'schema-sync'
                FROM dbo.Company_Staff s
                WHERE s.department<>N''
                  AND NOT EXISTS (
                      SELECT 1 FROM dbo.Company_Department d WHERE d.department_name=s.department
                  )
            """)
            db.commit()
        return {"tables": list(APPLICATION_TABLES + WORKFLOW_TABLES), "status": "ready"}
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("網站應用資料表建立失敗，請確認資料庫帳號具備建表權限。") from exc


def _staff_photo_file(employee_id: str) -> str | None:
    for extension in ("jpg", "png", "webp"):
        candidate = PAGE_ROOT / "static" / "staff" / f"{employee_id}.{extension}"
        if candidate.is_file():
            return candidate.name
    return None


def _sync_staff_csv_cursor(cursor) -> int:
    """CSV 有異動時才合併員工主檔；未列於 CSV 的資料不會被停用。"""
    if not STAFF_CSV.is_file():
        return 0
    state = STAFF_CSV.stat()
    previous = cursor.execute(
        "SELECT source_modified,source_size FROM dbo.Company_ImportState WHERE source_key=N'staff.csv'"
    ).fetchone()
    if previous and previous[0] == state.st_mtime_ns and previous[1] == state.st_size:
        return 0

    imported = 0
    with STAFF_CSV.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            employee_id = str(row.get("員工編號", "")).strip().upper()
            if not employee_id:
                continue
            age_text = str(row.get("年齡", "")).strip()
            age = int(age_text) if age_text.isdigit() else None
            photo = _staff_photo_file(employee_id)
            cursor.execute("""
                MERGE dbo.Company_Staff AS target
                USING (SELECT ? AS employee_id) AS source ON target.employee_id=source.employee_id
                WHEN MATCHED THEN UPDATE SET
                    display_name=?,gender=?,age=?,department=?,position=?,traits=?,biography=?,
                    photo_file=COALESCE(target.photo_file,?),is_active=1,
                    updated_by=N'csv-import',updated_at=SYSDATETIME()
                WHEN NOT MATCHED THEN INSERT
                    (employee_id,display_name,gender,age,department,position,traits,biography,photo_file,updated_by)
                    VALUES (?,?,?,?,?,?,?,?,?,N'csv-import');
            """, employee_id, row.get("姓名", ""), row.get("性別", ""), age,
                 row.get("部門", ""), row.get("職位", ""), row.get("個性特質", ""),
                 row.get("生平背景簡述", ""), photo, employee_id, row.get("姓名", ""),
                 row.get("性別", ""), age, row.get("部門", ""), row.get("職位", ""),
                 row.get("個性特質", ""), row.get("生平背景簡述", ""), photo)
            imported += 1
    cursor.execute("""
        MERGE dbo.Company_ImportState AS target
        USING (SELECT N'staff.csv' AS source_key) AS source ON target.source_key=source.source_key
        WHEN MATCHED THEN UPDATE SET source_modified=?,source_size=?,imported_rows=?,imported_at=SYSDATETIME()
        WHEN NOT MATCHED THEN INSERT (source_key,source_modified,source_size,imported_rows)
        VALUES (N'staff.csv',?,?,?);
    """, state.st_mtime_ns, state.st_size, imported, state.st_mtime_ns, state.st_size, imported)
    return imported


def sync_staff_csv() -> int:
    """掃描 data/staff.csv，並在檔案內容更新後同步 SQL Server。"""
    with STAFF_SYNC_LOCK:
        try:
            with connect(read_only=False, autocommit=False) as db:
                imported = _sync_staff_csv_cursor(db.cursor())
                db.commit()
                return imported
        except OSError as exc:
            raise DatabaseUnavailable("員工 CSV 無法讀取。") from exc
        except pyodbc.Error as exc:
            raise DatabaseUnavailable("員工 CSV 同步失敗。") from exc


def _staff_order(sort_by: str) -> str:
    if sort_by == "department":
        return "department, employee_id"
    if sort_by in {"", "employee_id"}:
        return "employee_id"
    raise ValueError("員工排序方式不正確")


def public_staff(department: str = "") -> list[dict[str, Any]]:
    """僅回傳適合官網公開的員工基本介紹。"""
    sync_staff_csv()
    return _fetch("""
        SELECT display_name, department, position, traits, photo_file
        FROM dbo.Company_Staff
        WHERE is_active=1 AND (?=N'' OR department=?)
        ORDER BY employee_id
    """, (department, department))


def public_staff_departments() -> list[dict[str, Any]]:
    """提供官網部門選單，部門順序依各部門最前面的員工編號決定。"""
    sync_staff_csv()
    return _fetch("""
        SELECT department,COUNT(*) AS staff_count
        FROM dbo.Company_Staff
        WHERE is_active=1 AND department<>N''
        GROUP BY department
        ORDER BY MIN(employee_id)
    """)


def attendance_staff_options(sort_by: str = "employee_id") -> list[dict[str, Any]]:
    """提供員工工作台打卡選單；不包含年齡、背景等管理欄位。"""
    sync_staff_csv()
    return _fetch(f"""
        SELECT employee_id, display_name, department, position
        FROM dbo.Company_Staff
        WHERE is_active=1
        ORDER BY {_staff_order(sort_by)}
    """)


def staff_records() -> list[dict[str, Any]]:
    sync_staff_csv()
    return _fetch("""
        SELECT employee_id,display_name,gender,age,department,position,traits,biography,photo_file,is_active,updated_by,updated_at
        FROM dbo.Company_Staff ORDER BY is_active DESC, employee_id
    """)


def employee_identity(employee_id: str) -> dict[str, Any]:
    """以 SQL Server 員工主檔驗證工作台登入身分。"""
    sync_staff_csv()
    rows = _fetch("""
        SELECT employee_id,display_name,department,position
        FROM dbo.Company_Staff WHERE employee_id=? AND is_active=1
    """, (employee_id,))
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
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("無法取得 SQL Server 校時資料。") from exc


def attendance_status(employee_id: str) -> dict[str, Any] | None:
    """只回傳員工當日最後一筆打卡，供不打卡登入與工作台提示。"""
    rows = _fetch("""
        SELECT TOP (1) employee_id,action,
               CONVERT(nvarchar(33),CONVERT(datetime2,clocked_at_utc AT TIME ZONE 'UTC' AT TIME ZONE 'Taipei Standard Time'),126)+N'+08:00' AS clocked_at
        FROM dbo.Company_Attendance
        WHERE employee_id=? AND work_date=CONVERT(date,SYSUTCDATETIME() AT TIME ZONE 'UTC' AT TIME ZONE 'Taipei Standard Time')
        ORDER BY clocked_at DESC,attendance_id DESC
    """, (employee_id,))
    return rows[0] if rows else None


def admin_departments() -> list[dict[str, Any]]:
    """回傳員工維護使用的部門清單。"""
    return _fetch("""
        SELECT d.department_id AS id,d.department_name AS name,d.is_active,
               COUNT(s.employee_id) AS staff_count,d.updated_by,d.updated_at
        FROM dbo.Company_Department d
        LEFT JOIN dbo.Company_Staff s ON s.department=d.department_name AND s.is_active=1
        GROUP BY d.department_id,d.department_name,d.is_active,d.updated_by,d.updated_at
        ORDER BY d.is_active DESC,d.department_id
    """)


def save_department(item: dict[str, Any], actor: str) -> dict[str, Any]:
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            if item["id"]:
                old = cursor.execute(
                    "SELECT department_name FROM dbo.Company_Department WHERE department_id=?",
                    item["id"],
                ).fetchone()
                if not old:
                    raise ValueError("找不到指定部門")
                cursor.execute("""
                    UPDATE dbo.Company_Department
                    SET department_name=?,is_active=1,updated_by=?,updated_at=SYSDATETIME()
                    WHERE department_id=?
                """, item["name"], actor, item["id"])
                if old[0] != item["name"]:
                    cursor.execute(
                        "UPDATE dbo.Company_Staff SET department=?,updated_by=?,updated_at=SYSDATETIME() WHERE department=?",
                        item["name"], actor, old[0],
                    )
                department_id = item["id"]
            else:
                row = cursor.execute("""
                    SELECT department_id FROM dbo.Company_Department WHERE department_name=?
                """, item["name"]).fetchone()
                if row:
                    cursor.execute("""
                        UPDATE dbo.Company_Department SET is_active=1,updated_by=?,updated_at=SYSDATETIME()
                        WHERE department_id=?
                    """, actor, row[0])
                    department_id = row[0]
                else:
                    department_id = cursor.execute("""
                        INSERT dbo.Company_Department (department_name,updated_by)
                        OUTPUT inserted.department_id VALUES (?,?)
                    """, item["name"], actor).fetchone()[0]
        return {"id": department_id, "name": item["name"], "is_active": True}
    except pyodbc.IntegrityError as exc:
        raise ValueError("部門名稱已存在") from exc
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("部門資料儲存失敗。") from exc


def deactivate_department(department_id: int, actor: str) -> dict[str, Any]:
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            row = cursor.execute("""
                SELECT d.department_name,COUNT(s.employee_id)
                FROM dbo.Company_Department d
                LEFT JOIN dbo.Company_Staff s ON s.department=d.department_name AND s.is_active=1
                WHERE d.department_id=? GROUP BY d.department_name
            """, department_id).fetchone()
            if not row:
                raise ValueError("找不到指定部門")
            if row[1]:
                raise ValueError("此部門仍有在職員工，無法停用")
            cursor.execute("""
                UPDATE dbo.Company_Department SET is_active=0,updated_by=?,updated_at=SYSDATETIME()
                WHERE department_id=?
            """, actor, department_id)
        return {"id": department_id, "is_active": False}
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("部門停用失敗。") from exc


def save_staff(item: dict[str, Any], actor: str, photo_file: str | None = None) -> dict[str, Any]:
    sync_staff_csv()
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            department = cursor.execute("""
                SELECT 1 FROM dbo.Company_Department WHERE department_name=? AND is_active=1
            """, item["department"]).fetchone()
            if not department:
                raise ValueError("請選擇有效的部門")
            existing = cursor.execute(
                "SELECT photo_file FROM dbo.Company_Staff WHERE employee_id=?",
                item["employee_id"],
            ).fetchone()
            photo = photo_file if photo_file is not None else (existing[0] if existing else None)
            cursor.execute("""
                MERGE dbo.Company_Staff AS target
                USING (SELECT ? AS employee_id) AS source ON target.employee_id=source.employee_id
                WHEN MATCHED THEN UPDATE SET display_name=?,gender=?,age=?,department=?,position=?,traits=?,biography=?,photo_file=?,is_active=1,updated_by=?,updated_at=SYSDATETIME()
                WHEN NOT MATCHED THEN INSERT (employee_id,display_name,gender,age,department,position,traits,biography,photo_file,updated_by)
                VALUES (?,?,?,?,?,?,?,?,?,?);
            """, item["employee_id"], item["display_name"], item["gender"], item["age"], item["department"], item["position"], item["traits"], item["biography"], photo, actor,
                 item["employee_id"], item["display_name"], item["gender"], item["age"], item["department"], item["position"], item["traits"], item["biography"], photo, actor)
        return {**item, "photo_file": photo, "is_active": True}
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("員工資料儲存失敗。") from exc


def deactivate_staff(employee_id: str, actor: str) -> dict[str, Any]:
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            cursor.execute("UPDATE dbo.Company_Staff SET is_active=0,updated_by=?,updated_at=SYSDATETIME() WHERE employee_id=?", actor, employee_id)
            if cursor.rowcount == 0:
                raise ValueError("找不到指定員工")
        return {"employee_id": employee_id, "is_active": False}
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("員工資料停用失敗。") from exc


def _validate_attendance_sequence(last_action: str | None, new_action: str) -> None:
    """打卡必須以上班開始，並依上班、下班順序交替。"""
    if last_action is None and new_action == "CLOCK_OUT":
        raise ValueError("尚未完成上班打卡，不能直接下班打卡")
    if last_action == new_action:
        label = "上班" if new_action == "CLOCK_IN" else "下班"
        raise ValueError(f"已完成{label}打卡，不能連續打卡兩次")


def clock_attendance(item: dict[str, str], source_ip: str) -> dict[str, Any]:
    try:
        with connect(read_only=False, autocommit=False) as db:
            cursor = db.cursor()
            # 鎖定員工主檔列，讓同一員工的同時打卡請求依序完成檢查與寫入。
            exists = cursor.execute("""
                SELECT 1 FROM dbo.Company_Staff WITH (UPDLOCK, HOLDLOCK)
                WHERE employee_id=? AND is_active=1
            """, item["employee_id"]).fetchone()
            if not exists:
                raise ValueError("員工編號不存在或已停用")
            current = time.now(cursor)
            previous = cursor.execute("""
                SELECT TOP (1) action
                FROM dbo.Company_Attendance
                WHERE employee_id=? AND work_date=?
                ORDER BY clocked_at DESC, attendance_id DESC
            """, item["employee_id"], current["work_date"]).fetchone()
            _validate_attendance_sequence(previous[0] if previous else None, item["action"])
            cursor.execute("""
                INSERT dbo.Company_Attendance (employee_id,action,clocked_at,clocked_at_utc,work_date,source_ip)
                VALUES (?,?,?,?,?,?)
            """, item["employee_id"], item["action"], current["local_time"], current["utc_time"], current["work_date"], source_ip)
            db.commit()
        return {"employee_id": item["employee_id"], "action": item["action"], "clocked_at": current["iso_time"]}
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("打卡寫入失敗。") from exc


def attendance_records(day: str = "", employee_id: str = "") -> list[dict[str, Any]]:
    return _fetch("""
        SELECT a.attendance_id,a.employee_id,s.display_name,s.department,s.position,a.action,
               CONVERT(nvarchar(33),CONVERT(datetime2,a.clocked_at_utc AT TIME ZONE 'UTC' AT TIME ZONE 'Taipei Standard Time'),126)+N'+08:00' AS clocked_at
        FROM dbo.Company_Attendance a
        JOIN dbo.Company_Staff s ON s.employee_id=a.employee_id
        WHERE (?=N'' OR a.work_date=CONVERT(date,?))
          AND (?=N'' OR a.employee_id=?)
        ORDER BY a.clocked_at DESC
    """, (day, day, employee_id, employee_id))


def add_operation(item: dict[str, Any], employee_id: str) -> dict[str, Any]:
    submission_id = f"OPS-{datetime.now(tz=timezone.utc):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:6].upper()}"
    try:
        with connect(read_only=False, autocommit=False) as db:
            cursor = db.cursor()
            row = cursor.execute("""
                INSERT dbo.Company_OperationSubmission
                (submission_id,operation_date,campus_code,category_code,quantity,note,submitted_by)
                OUTPUT inserted.submitted_at
                VALUES (?,?,?,?,?,?,?)
            """, submission_id, item["date"], item["campus"], item["category"], item["count"], item["note"], employee_id).fetchone()
            cursor.execute("""
                INSERT dbo.Company_OperationActivity
                (submission_id,action_type,message,actor_employee_id,actor_role)
                VALUES (?,N'SUBMITTED',NULL,?,N'employee')
            """, submission_id, employee_id)
            db.commit()
        return {"id": submission_id, **item, "submitted_by": employee_id, "status": "待審核", "submitted_at": _json_value(row[0])}
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("營運紀錄寫入失敗。") from exc


def _operation_submissions(employee_id: str = "") -> list[dict[str, Any]]:
    rows = _fetch("""
        SELECT o.submission_id AS id,o.operation_date AS [date],o.campus_code AS campus,
               o.category_code AS category,o.quantity AS [count],o.note,o.status,o.submitted_at,
               o.submitted_by,s.display_name AS submitted_by_name,s.department AS submitted_by_department
        FROM dbo.Company_OperationSubmission o
        LEFT JOIN dbo.Company_Staff s ON s.employee_id=o.submitted_by
        WHERE (?=N'' OR o.submitted_by=?)
        ORDER BY o.submitted_at DESC
    """, (employee_id, employee_id))
    if not rows:
        return rows
    activities = _fetch("""
        SELECT a.activity_id AS id,a.submission_id,a.action_type,a.message,a.actor_role,
               a.actor_employee_id,s.display_name AS actor_name,a.created_at
        FROM dbo.Company_OperationActivity a
        LEFT JOIN dbo.Company_Staff s ON s.employee_id=a.actor_employee_id
        WHERE (?=N'' OR EXISTS (
            SELECT 1 FROM dbo.Company_OperationSubmission o
            WHERE o.submission_id=a.submission_id AND o.submitted_by=?
        ))
        ORDER BY a.created_at,a.activity_id
    """, (employee_id, employee_id))
    by_submission: dict[str, list[dict[str, Any]]] = {}
    for activity in activities:
        by_submission.setdefault(activity.pop("submission_id"), []).append(activity)
    for row in rows:
        row["activities"] = by_submission.get(row["id"], [])
    return rows


def operation_submissions() -> list[dict[str, Any]]:
    return _operation_submissions()


def employee_operation_submissions(employee_id: str) -> list[dict[str, Any]]:
    return _operation_submissions(employee_id)


def review_operation(item: dict[str, str], reviewer_id: str) -> dict[str, Any]:
    action_types = {"要求補件": "CHANGES_REQUESTED", "審核通過": "APPROVED", "已退回": "REJECTED"}
    try:
        with connect(read_only=False, autocommit=False) as db:
            cursor = db.cursor()
            row = cursor.execute("""
                SELECT submission_id FROM dbo.Company_OperationSubmission WITH (UPDLOCK,HOLDLOCK)
                WHERE submission_id=?
            """, item["id"]).fetchone()
            if not row:
                raise ValueError("找不到指定營運日報")
            cursor.execute(
                "UPDATE dbo.Company_OperationSubmission SET status=? WHERE submission_id=?",
                item["status"], item["id"],
            )
            cursor.execute("""
                INSERT dbo.Company_OperationActivity
                (submission_id,action_type,message,actor_employee_id,actor_role)
                VALUES (?,?,?,?,N'admin')
            """, item["id"], action_types[item["status"]], item["message"] or None, reviewer_id)
            db.commit()
        return {"id": item["id"], "status": item["status"]}
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("營運日報審閱失敗。") from exc


def reply_operation(item: dict[str, str], employee_id: str) -> dict[str, Any]:
    try:
        with connect(read_only=False, autocommit=False) as db:
            cursor = db.cursor()
            row = cursor.execute("""
                SELECT status FROM dbo.Company_OperationSubmission WITH (UPDLOCK,HOLDLOCK)
                WHERE submission_id=? AND submitted_by=?
            """, item["id"], employee_id).fetchone()
            if not row:
                raise ValueError("找不到可回覆的營運日報")
            if row[0] in {"審核通過", "已退回"}:
                raise ValueError("此營運日報已結案，無法再回覆")
            cursor.execute(
                "UPDATE dbo.Company_OperationSubmission SET status=N'員工已回覆' WHERE submission_id=?",
                item["id"],
            )
            cursor.execute("""
                INSERT dbo.Company_OperationActivity
                (submission_id,action_type,message,actor_employee_id,actor_role)
                VALUES (?,N'EMPLOYEE_REPLY',?,?,N'employee')
            """, item["id"], item["message"], employee_id)
            db.commit()
        return {"id": item["id"], "status": "員工已回覆"}
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("營運日報回覆失敗。") from exc


def upsert_operations_manuals(documents: list[dict[str, Any]]) -> int:
    """將 doc.py 擷取的文件與段落寫入正規化資料表。"""
    try:
        with connect(read_only=False, autocommit=False) as db:
            cursor = db.cursor()
            existing = {
                row[0]: {"id": row[1], "size": row[2], "modified": row[3]}
                for row in cursor.execute("SELECT file_name,document_id,source_size,source_modified FROM dbo.Company_TrainingDocument").fetchall()
            }
            cursor.execute("UPDATE dbo.Company_TrainingDocument SET is_active=0")
            for document in documents:
                previous = existing.get(document["file_name"])
                if previous and previous["size"] == document["size"] and previous["modified"] == document["modified"]:
                    cursor.execute("UPDATE dbo.Company_TrainingDocument SET is_active=1 WHERE document_id=?", previous["id"])
                    continue
                cursor.execute("""
                    MERGE dbo.Company_TrainingDocument AS target
                    USING (SELECT ? AS file_name) AS source ON target.file_name=source.file_name
                    WHEN MATCHED THEN UPDATE SET title=?,role_category=?,source_size=?,source_modified=?,is_active=1,imported_at=SYSDATETIME()
                    WHEN NOT MATCHED THEN INSERT (file_name,title,role_category,source_size,source_modified,is_active)
                    VALUES (?,?,?,?,?,1);
                """, document["file_name"], document["title"], document["category"], document["size"], document["modified"],
                     document["file_name"], document["title"], document["category"], document["size"], document["modified"])
                document_id = cursor.execute("SELECT document_id FROM dbo.Company_TrainingDocument WHERE file_name=?", document["file_name"]).fetchone()[0]
                cursor.execute("DELETE FROM dbo.Company_TrainingSection WHERE document_id=?", document_id)
                for order, section in enumerate(document["sections"], 1):
                    cursor.execute("""
                        INSERT dbo.Company_TrainingSection (document_id,section_order,heading,content)
                        VALUES (?,?,?,?)
                    """, document_id, order, section["heading"], section["content"])
            db.commit()
        return len(documents)
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("SOP文件寫入失敗。") from exc


def operations_manual_catalog() -> list[dict[str, Any]]:
    return _fetch("""
        SELECT d.document_id AS id,d.title,d.role_category AS category,d.file_name,
               COUNT(s.section_id) AS section_count,d.imported_at
        FROM dbo.Company_TrainingDocument d
        LEFT JOIN dbo.Company_TrainingSection s ON s.document_id=d.document_id
        WHERE d.is_active=1
        GROUP BY d.document_id,d.title,d.role_category,d.file_name,d.imported_at
        ORDER BY d.role_category,d.title
    """)


def operations_manual_document(document_id: int) -> dict[str, Any]:
    docs = _fetch("""
        SELECT document_id AS id,title,role_category AS category,file_name
        FROM dbo.Company_TrainingDocument WHERE document_id=? AND is_active=1
    """, (document_id,))
    if not docs:
        raise ValueError("找不到指定SOP文件")
    docs[0]["sections"] = _fetch("""
        SELECT section_order AS [order],heading,content
        FROM dbo.Company_TrainingSection WHERE document_id=? ORDER BY section_order
    """, (document_id,))
    return docs[0]


def _loads_json(value: Any, fallback: Any) -> Any:
    try:
        return json.loads(value) if value not in (None, "") else fallback
    except (TypeError, json.JSONDecodeError):
        return fallback


def _question_snapshot(row: dict[str, Any]) -> dict[str, Any]:
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
    conditions = ["q.subject_id=?", "q.domain=N'academic'", "q.status=N'published'", "q.is_active=1", "q.question_type<>N'essay'"]
    params: list[Any] = [subject_id]
    for column, values in (
        ("q.chapter_id", chapter_ids or []),
        ("q.document_id", document_ids or []),
        ("q.question_type", question_types or []),
    ):
        if values:
            conditions.append(f"{column} IN ({','.join('?' for _ in values)})")
            params.extend(values)
    return _fetch(f"""
        SELECT q.question_id AS id,q.domain,s.subject_name AS subject,
               c.chapter_name AS chapter,d.file_name AS source,q.source_locator,
               q.question_type,q.question,q.content_json,q.options_json,q.answer_json,
               q.structure_json,q.passage,q.explanation
        FROM dbo.Company_TrainingQuestion q
        JOIN dbo.Company_TrainingSubject s ON s.subject_id=q.subject_id
        LEFT JOIN dbo.Company_TrainingChapter c ON c.chapter_id=q.chapter_id
        LEFT JOIN dbo.Company_TrainingDocument d ON d.document_id=q.document_id
        WHERE {' AND '.join(conditions)}
        ORDER BY q.question_id
    """, tuple(params))


def training_catalog(employee_id: str) -> dict[str, Any]:
    subjects = _fetch("""
        SELECT s.subject_id AS id,s.domain,s.subject_name AS name,
               s.mock_question_count,s.mock_duration_minutes,s.mock_pass_score,
               COUNT(CASE WHEN q.status=N'published' AND q.is_active=1 THEN 1 END) AS question_count
        FROM dbo.Company_TrainingSubject s
        LEFT JOIN dbo.Company_TrainingQuestion q ON q.subject_id=s.subject_id
        WHERE s.is_active=1
        GROUP BY s.subject_id,s.domain,s.subject_name,s.mock_question_count,
                 s.mock_duration_minutes,s.mock_pass_score
        ORDER BY CASE WHEN s.domain=N'academic' THEN 0 ELSE 1 END,s.subject_name
    """)
    chapters = _fetch("""
        SELECT c.chapter_id AS id,c.subject_id,c.chapter_code AS code,c.chapter_name AS name,
               COUNT(CASE WHEN q.status=N'published' AND q.is_active=1 THEN 1 END) AS question_count
        FROM dbo.Company_TrainingChapter c
        LEFT JOIN dbo.Company_TrainingQuestion q ON q.chapter_id=c.chapter_id
        WHERE c.is_active=1
        GROUP BY c.chapter_id,c.subject_id,c.chapter_code,c.chapter_name,c.display_order
        ORDER BY c.subject_id,c.display_order,c.chapter_code
    """)
    progress_rows = _fetch("""
        SELECT q.chapter_id,
               COUNT(DISTINCT sq.question_id) AS attempted_count,
               COUNT(DISTINCT CASE WHEN sq.is_correct=1 THEN sq.question_id END) AS correct_count
        FROM dbo.Company_TrainingSession s
        JOIN dbo.Company_TrainingSessionQuestion sq ON sq.session_id=s.session_id
        JOIN dbo.Company_TrainingQuestion q ON q.question_id=sq.question_id
        WHERE s.employee_id=? AND s.status=N'submitted' AND q.chapter_id IS NOT NULL
        GROUP BY q.chapter_id
    """, (employee_id,))
    progress_by_chapter = {row["chapter_id"]: row for row in progress_rows}
    for chapter in chapters:
        progress = progress_by_chapter.get(chapter["id"], {})
        chapter["attempted_count"] = int(progress.get("attempted_count", 0))
        chapter["correct_count"] = int(progress.get("correct_count", 0))
        chapter["progress_percent"] = min(
            100,
            round(chapter["attempted_count"] * 100 / max(1, int(chapter["question_count"]))),
        )
    sources = _fetch("""
        SELECT DISTINCT d.document_id AS id,d.title,d.file_name,q.subject_id
        FROM dbo.Company_TrainingDocument d
        JOIN dbo.Company_TrainingQuestion q ON q.document_id=d.document_id
        WHERE d.is_active=1 AND q.status=N'published' AND q.is_active=1
        ORDER BY d.title
    """)
    resumable = _fetch("""
        SELECT TOP 1 CONVERT(nvarchar(36),session_id) AS id,mode,subject_id,started_at,expires_at
        FROM dbo.Company_TrainingSession
        WHERE employee_id=? AND status=N'in_progress'
        ORDER BY started_at DESC
    """, (employee_id,))
    wrong_count = _fetch("""
        SELECT COUNT(*) AS [count] FROM dbo.Company_TrainingWrongQuestion
        WHERE employee_id=? AND removed_at IS NULL
    """, (employee_id,))[0]["count"]
    return {
        "subjects": subjects,
        "chapters": chapters,
        "sources": sources,
        "resumable": resumable[0] if resumable else None,
        "wrong_count": wrong_count,
    }


def _public_session_payload(session: dict[str, Any], rows: list[dict[str, Any]], *, include_review: bool = False) -> dict[str, Any]:
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
        "expires_at": session.get("expires_at"),
        "submitted_at": session.get("submitted_at"),
        "score": session.get("score"),
        "config": _loads_json(session.get("config_json"), {}),
        "questions": questions,
    }


def start_training_session(item: dict[str, Any], employee_id: str) -> dict[str, Any]:
    subject_rows = _fetch("""
        SELECT subject_id AS id,domain,mock_question_count,mock_duration_minutes,mock_pass_score
        FROM dbo.Company_TrainingSubject WHERE subject_id=? AND is_active=1
    """, (item["subject_id"],))
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
    duration = int(subject["mock_duration_minutes"]) if item["mode"] == "mock" else 0
    expires_at = (datetime.utcnow() + timedelta(minutes=duration)) if duration else None
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
            cursor.execute("""
                INSERT dbo.Company_TrainingSession
                (session_id,employee_id,subject_id,mode,status,config_json,expires_at)
                VALUES (?,?,?, ?,N'in_progress',?,?)
            """, session_id, employee_id, item["subject_id"], item["mode"], json.dumps(config), expires_at)
            for order, row in enumerate(rows, 1):
                cursor.execute("""
                    INSERT dbo.Company_TrainingSessionQuestion
                    (session_id,question_id,question_order,snapshot_json)
                    VALUES (?,?,?,?)
                """, session_id, row["id"], order, json.dumps(_question_snapshot(row), ensure_ascii=False))
            db.commit()
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("無法建立本次題組。") from exc
    return training_session(session_id, employee_id)


def training_session(session_id: str, employee_id: str) -> dict[str, Any]:
    sessions = _fetch("""
        SELECT CONVERT(nvarchar(36),session_id) AS id,mode,status,subject_id,
               config_json,started_at,expires_at,submitted_at,score
        FROM dbo.Company_TrainingSession WHERE session_id=? AND employee_id=?
    """, (session_id, employee_id))
    if not sessions:
        raise ValueError("找不到指定的作答階段")
    session = sessions[0]
    if session["status"] == "in_progress" and session.get("expires_at"):
        expires = datetime.fromisoformat(session["expires_at"])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc):
            return submit_training_session(session_id, employee_id)
    rows = _fetch("""
        SELECT question_order,snapshot_json,response_json,is_flagged,is_correct
        FROM dbo.Company_TrainingSessionQuestion WHERE session_id=? ORDER BY question_order
    """, (session_id,))
    return _public_session_payload(session, rows, include_review=session["status"] == "submitted")


def _grade_snapshot(snapshot: dict[str, Any], response: dict[str, Any]) -> bool:
    question_type = snapshot.get("question_type")
    expected = snapshot.get("answers", [])
    supplied = response.get("answers", [])
    if question_type in {"single_choice", "multiple_choice", "reading"}:
        try:
            return sorted({int(value) for value in supplied}) == sorted({int(value) for value in expected})
        except (TypeError, ValueError):
            return False
    if question_type == "fill_blank":
        normalized = [str(value).strip() for value in supplied]
        return normalized == [str(value).strip() for value in expected]
    if question_type == "matching":
        return supplied == expected
    return False


def _record_wrong(cursor, employee_id: str, question_id: int) -> None:
    cursor.execute("""
        MERGE dbo.Company_TrainingWrongQuestion AS target
        USING (SELECT ? AS employee_id,? AS question_id) AS source
        ON target.employee_id=source.employee_id AND target.question_id=source.question_id
        WHEN MATCHED THEN UPDATE SET removed_at=NULL,added_at=SYSUTCDATETIME()
        WHEN NOT MATCHED THEN INSERT (employee_id,question_id) VALUES (source.employee_id,source.question_id);
    """, employee_id, question_id)


def save_training_answer(item: dict[str, Any], employee_id: str) -> dict[str, Any]:
    rows = _fetch("""
        SELECT s.mode,s.status,s.expires_at,sq.question_id,sq.snapshot_json
        FROM dbo.Company_TrainingSession s
        JOIN dbo.Company_TrainingSessionQuestion sq ON sq.session_id=s.session_id
        WHERE s.session_id=? AND s.employee_id=? AND sq.question_order=?
    """, (item["session_id"], employee_id, item["order"]))
    if not rows or rows[0]["status"] != "in_progress":
        raise ValueError("此題組目前無法作答")
    row = rows[0]
    if row.get("expires_at"):
        expires = datetime.fromisoformat(row["expires_at"])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc):
            submit_training_session(item["session_id"], employee_id)
            raise ValueError("模擬考時間已到，系統已自動交卷")
    snapshot = _loads_json(row["snapshot_json"], {})
    correct = _grade_snapshot(snapshot, item["response"])
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            cursor.execute("""
                UPDATE dbo.Company_TrainingSessionQuestion
                SET response_json=?,is_flagged=?,is_correct=?,answered_at=SYSUTCDATETIME()
                WHERE session_id=? AND question_order=?
            """, json.dumps(item["response"], ensure_ascii=False), int(item["flagged"]),
                 int(correct), item["session_id"], item["order"])
            if not correct and item["response"].get("answers") not in (None, [], ""):
                _record_wrong(cursor, employee_id, row["question_id"])
    except pyodbc.Error as exc:
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
    sessions = _fetch("""
        SELECT CONVERT(nvarchar(36),session_id) AS id,mode,status,subject_id,
               config_json,started_at,expires_at,submitted_at,score
        FROM dbo.Company_TrainingSession WHERE session_id=? AND employee_id=?
    """, (session_id, employee_id))
    if not sessions:
        raise ValueError("找不到指定的作答階段")
    session = sessions[0]
    rows = _fetch("""
        SELECT sq.question_order,sq.question_id,sq.snapshot_json,sq.response_json,sq.is_flagged,sq.is_correct
        FROM dbo.Company_TrainingSessionQuestion sq WHERE sq.session_id=? ORDER BY sq.question_order
    """, (session_id,))
    if session["status"] != "submitted":
        correct_count = 0
        try:
            with connect(read_only=False, autocommit=False) as db:
                cursor = db.cursor()
                for row in rows:
                    snapshot = _loads_json(row["snapshot_json"], {})
                    response = _loads_json(row.get("response_json"), {})
                    correct = _grade_snapshot(snapshot, response)
                    correct_count += int(correct)
                    cursor.execute("""
                        UPDATE dbo.Company_TrainingSessionQuestion SET is_correct=?
                        WHERE session_id=? AND question_order=?
                    """, int(correct), session_id, row["question_order"])
                    if not correct and response.get("answers") not in (None, [], ""):
                        _record_wrong(cursor, employee_id, row["question_id"])
                    row["is_correct"] = correct
                score = round(correct_count * 100 / max(1, len(rows)), 2)
                cursor.execute("""
                    UPDATE dbo.Company_TrainingSession
                    SET status=N'submitted',submitted_at=SYSUTCDATETIME(),score=?
                    WHERE session_id=? AND employee_id=?
                """, score, session_id, employee_id)
                db.commit()
            session.update({"status": "submitted", "score": score, "submitted_at": datetime.now(timezone.utc).isoformat()})
        except pyodbc.Error as exc:
            raise DatabaseUnavailable("交卷失敗。") from exc
    return _public_session_payload(session, rows, include_review=True)


def training_wrong_questions(employee_id: str) -> list[dict[str, Any]]:
    rows = _fetch("""
        SELECT q.question_id AS id,q.domain,s.subject_name AS subject,c.chapter_name AS chapter,
               d.file_name AS source,q.source_locator,q.question_type,q.question,q.content_json,
               q.options_json,q.answer_json,q.structure_json,q.passage,q.explanation,w.added_at
        FROM dbo.Company_TrainingWrongQuestion w
        JOIN dbo.Company_TrainingQuestion q ON q.question_id=w.question_id
        JOIN dbo.Company_TrainingSubject s ON s.subject_id=q.subject_id
        LEFT JOIN dbo.Company_TrainingChapter c ON c.chapter_id=q.chapter_id
        LEFT JOIN dbo.Company_TrainingDocument d ON d.document_id=q.document_id
        WHERE w.employee_id=? AND w.removed_at IS NULL
        ORDER BY w.added_at DESC
    """, (employee_id,))
    return [{**_question_snapshot(row), "added_at": row["added_at"]} for row in rows]


def remove_training_wrong(question_id: int, employee_id: str) -> dict[str, Any]:
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            cursor.execute("""
                UPDATE dbo.Company_TrainingWrongQuestion SET removed_at=SYSUTCDATETIME()
                WHERE employee_id=? AND question_id=? AND removed_at IS NULL
            """, employee_id, question_id)
        return {"id": question_id, "removed": True}
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("無法移除錯題。") from exc


def compliance_questions() -> list[dict[str, Any]]:
    """相容舊前端的已發布學科題目，不傳送答案與解析。"""
    rows = _fetch("""
        SELECT TOP 20 q.question_id AS id,q.category,q.question,q.question_type,
               q.options_json,q.passage,q.content_json,q.structure_json
        FROM dbo.Company_TrainingQuestion q
        WHERE q.status=N'published' AND q.is_active=1 AND q.domain=N'academic'
        ORDER BY q.question_id
    """)
    for row in rows:
        row["options"] = _loads_json(row.pop("options_json"), [])
        row["content_blocks"] = _loads_json(row.pop("content_json"), [{"type": "text", "content": row["question"]}])
        row["structure"] = _loads_json(row.pop("structure_json"), {})
    return rows


def operations_manuals_admin() -> list[dict[str, Any]]:
    """回傳含停用狀態的SOP文件，供 MIS 維護。"""
    return _fetch("""
        SELECT d.document_id AS id,d.title,d.role_category AS category,d.file_name,
               d.source_size,d.source_modified,d.source_kind,d.parse_status,d.parse_message,
               d.is_active,d.imported_at,
               COUNT(s.section_id) AS section_count
        FROM dbo.Company_TrainingDocument d
        LEFT JOIN dbo.Company_TrainingSection s ON s.document_id=d.document_id
        GROUP BY d.document_id,d.title,d.role_category,d.file_name,d.source_size,
                 d.source_modified,d.source_kind,d.parse_status,d.parse_message,d.is_active,d.imported_at
        ORDER BY d.is_active DESC,d.role_category,d.title
    """)


def _ensure_training_classification(cursor, domain: str, subject_name: str, chapter_code: str, chapter_name: str) -> tuple[int, int]:
    cursor.execute("""
        IF NOT EXISTS (SELECT 1 FROM dbo.Company_TrainingSubject WHERE domain=? AND subject_name=?)
        INSERT dbo.Company_TrainingSubject
            (domain,subject_name,mock_question_count,mock_duration_minutes,mock_pass_score)
        VALUES (?,?,40,45,70)
    """, domain, subject_name, domain, subject_name)
    subject_id = cursor.execute(
        "SELECT subject_id FROM dbo.Company_TrainingSubject WHERE domain=? AND subject_name=?",
        domain, subject_name,
    ).fetchone()[0]
    cursor.execute("""
        IF NOT EXISTS (SELECT 1 FROM dbo.Company_TrainingChapter WHERE subject_id=? AND chapter_code=?)
        INSERT dbo.Company_TrainingChapter (subject_id,chapter_code,chapter_name,display_order)
        VALUES (?,?,?,?)
    """, subject_id, chapter_code, subject_id, chapter_code, chapter_name, 999 if chapter_code == "UNSORTED" else 0)
    chapter_id = cursor.execute(
        "SELECT chapter_id FROM dbo.Company_TrainingChapter WHERE subject_id=? AND chapter_code=?",
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
                for row in cursor.execute("SELECT file_name,document_id FROM dbo.Company_TrainingDocument").fetchall()
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
            for source_name in set(draft_counts) | set(warning_messages) | set(failure_messages):
                messages = failure_messages.get(source_name) or warning_messages.get(source_name, [])
                cursor.execute("""
                    UPDATE dbo.Company_TrainingDocument
                    SET source_kind=?,parse_status=?,parse_message=?
                    WHERE file_name=?
                """, "question_bank" if draft_counts.get(source_name) or failure_messages.get(source_name) else "manual",
                     "failed" if failure_messages.get(source_name) else (
                         "warning" if warning_messages.get(source_name) else "parsed"
                     ),
                     "；".join(messages)[:1000] or None,
                     source_name)
            seen: set[str] = set()
            for draft in drafts:
                fingerprint = draft["source_fingerprint"]
                if fingerprint in seen:
                    result["duplicates"] += 1
                    continue
                seen.add(fingerprint)
                subject_id, chapter_id = _ensure_training_classification(
                    cursor,
                    draft.get("domain", "academic"),
                    draft.get("subject") or "未分類",
                    draft.get("chapter_code") or "UNSORTED",
                    draft.get("chapter") or "未分類",
                )
                document_id = documents.get(draft.get("source_document"))
                previous = cursor.execute("""
                    SELECT question_id,admin_locked FROM dbo.Company_TrainingQuestion
                    WHERE source_fingerprint=? OR
                          (document_id=? AND source_question_key=?)
                    ORDER BY CASE WHEN source_fingerprint=? THEN 0 ELSE 1 END
                """, fingerprint, document_id, draft.get("source_question_key"), fingerprint).fetchone()
                if previous and previous[1]:
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
                    cursor.execute("""
                        UPDATE dbo.Company_TrainingQuestion
                        SET document_id=?,subject_id=?,chapter_id=?,domain=?,category=?,question=?,
                            options_json=?,correct_index=?,explanation=?,question_type=?,answer_json=?,
                            content_json=?,structure_json=?,source_locator=?,source_question_key=?,
                            source_fingerprint=?,parse_confidence=?,parse_warnings_json=?,
                            status=N'draft',is_active=0,updated_at=SYSDATETIME()
                        WHERE question_id=? AND admin_locked=0
                    """, *values, previous[0])
                    result["updated"] += 1
                else:
                    cursor.execute("""
                        INSERT dbo.Company_TrainingQuestion
                        (document_id,subject_id,chapter_id,domain,category,question,options_json,
                         correct_index,explanation,question_type,answer_json,content_json,structure_json,
                         source_locator,source_question_key,source_fingerprint,parse_confidence,
                         parse_warnings_json,status,is_active,admin_locked)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,N'draft',0,0)
                    """, *values)
                    result["created"] += 1
            db.commit()
        return result
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("題庫草稿匯入失敗。") from exc


def training_taxonomy_admin() -> dict[str, Any]:
    return {
        "subjects": _fetch("""
            SELECT subject_id AS id,domain,subject_name AS name,mock_question_count,
                   mock_duration_minutes,mock_pass_score,is_active
            FROM dbo.Company_TrainingSubject ORDER BY domain,subject_name
        """),
        "chapters": _fetch("""
            SELECT chapter_id AS id,subject_id,chapter_code AS code,chapter_name AS name,
                   display_order,is_active
            FROM dbo.Company_TrainingChapter ORDER BY subject_id,display_order,chapter_code
        """),
    }


def save_training_subject(item: dict[str, Any]) -> dict[str, Any]:
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            if item["id"]:
                current = cursor.execute(
                    "SELECT domain FROM dbo.Company_TrainingSubject WHERE subject_id=?", item["id"]
                ).fetchone()
                if not current:
                    raise ValueError("找不到指定科目")
                if current[0] != item["domain"] and cursor.execute(
                    "SELECT COUNT(*) FROM dbo.Company_TrainingQuestion WHERE subject_id=?", item["id"]
                ).fetchone()[0]:
                    raise ValueError("已有題目的科目不可變更學科／術科領域")
                cursor.execute("""
                    UPDATE dbo.Company_TrainingSubject
                    SET domain=?,subject_name=?,mock_question_count=?,mock_duration_minutes=?,
                        mock_pass_score=?,is_active=? WHERE subject_id=?
                """, item["domain"], item["name"], item["mock_question_count"],
                     item["mock_duration_minutes"], item["mock_pass_score"],
                     int(item["is_active"]), item["id"])
                subject_id = item["id"]
            else:
                subject_id = cursor.execute("""
                    INSERT dbo.Company_TrainingSubject
                    (domain,subject_name,mock_question_count,mock_duration_minutes,mock_pass_score,is_active)
                    OUTPUT inserted.subject_id VALUES (?,?,?,?,?,?)
                """, item["domain"], item["name"], item["mock_question_count"],
                     item["mock_duration_minutes"], item["mock_pass_score"], int(item["is_active"])).fetchone()[0]
        return {**item, "id": int(subject_id)}
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("科目設定儲存失敗。") from exc


def save_training_chapter(item: dict[str, Any]) -> dict[str, Any]:
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            if item["id"]:
                current = cursor.execute(
                    "SELECT subject_id FROM dbo.Company_TrainingChapter WHERE chapter_id=?", item["id"]
                ).fetchone()
                if not current:
                    raise ValueError("找不到指定章節")
                if int(current[0]) != item["subject_id"] and cursor.execute(
                    "SELECT COUNT(*) FROM dbo.Company_TrainingQuestion WHERE chapter_id=?", item["id"]
                ).fetchone()[0]:
                    raise ValueError("已有題目的章節不可移至其他科目")
                cursor.execute("""
                    UPDATE dbo.Company_TrainingChapter
                    SET subject_id=?,chapter_code=?,chapter_name=?,display_order=?,is_active=?
                    WHERE chapter_id=?
                """, item["subject_id"], item["code"], item["name"], item["display_order"],
                     int(item["is_active"]), item["id"])
                chapter_id = item["id"]
            else:
                chapter_id = cursor.execute("""
                    INSERT dbo.Company_TrainingChapter
                    (subject_id,chapter_code,chapter_name,display_order,is_active)
                    OUTPUT inserted.chapter_id VALUES (?,?,?,?,?)
                """, item["subject_id"], item["code"], item["name"], item["display_order"],
                     int(item["is_active"])).fetchone()[0]
        return {**item, "id": int(chapter_id)}
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("章節設定儲存失敗。") from exc


def set_operations_manual_state(document_id: int, is_active: bool) -> dict[str, Any]:
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            cursor.execute(
                "UPDATE dbo.Company_TrainingDocument SET is_active=? WHERE document_id=?",
                int(is_active), document_id,
            )
            if cursor.rowcount == 0:
                raise ValueError("找不到指定SOP文件")
        return {"id": document_id, "is_active": is_active}
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("SOP文件狀態更新失敗。") from exc


def compliance_questions_admin() -> list[dict[str, Any]]:
    rows = _fetch("""
        SELECT q.question_id AS id,q.document_id,q.subject_id,q.chapter_id,q.domain,
               s.subject_name AS subject,c.chapter_code,c.chapter_name AS chapter,
               d.file_name AS source,q.category,q.question,q.question_type,
               q.options_json,q.answer_json,q.content_json,q.structure_json,q.passage,
               q.explanation,q.source_locator,q.parse_confidence,q.parse_warnings_json,
               q.status,q.admin_locked,q.is_active
        FROM dbo.Company_TrainingQuestion q
        LEFT JOIN dbo.Company_TrainingSubject s ON s.subject_id=q.subject_id
        LEFT JOIN dbo.Company_TrainingChapter c ON c.chapter_id=q.chapter_id
        LEFT JOIN dbo.Company_TrainingDocument d ON d.document_id=q.document_id
        ORDER BY CASE q.status WHEN N'draft' THEN 0 WHEN N'published' THEN 1 ELSE 2 END,q.question_id
    """)
    for row in rows:
        row["options"] = _loads_json(row.pop("options_json"), [])
        row["answers"] = _loads_json(row.pop("answer_json"), [])
        row["content_blocks"] = _loads_json(row.pop("content_json"), [{"type": "text", "content": row["question"]}])
        row["structure"] = _loads_json(row.pop("structure_json"), {})
        row["parse_warnings"] = _loads_json(row.pop("parse_warnings_json"), [])
    return rows


def save_compliance_question(item: dict[str, Any]) -> dict[str, Any]:
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
                cursor.execute("""
                    UPDATE dbo.Company_TrainingQuestion
                    SET document_id=?,subject_id=?,chapter_id=?,domain=?,category=?,question=?,
                        options_json=?,correct_index=?,explanation=?,question_type=?,answer_json=?,
                        content_json=?,structure_json=?,passage=?,status=?,is_active=?,
                        admin_locked=1,updated_at=SYSDATETIME()
                    WHERE question_id=?
                """, item["document_id"], item["subject_id"], item["chapter_id"], item["domain"],
                     category, item["question"], options_json, correct_index, item["explanation"],
                     item["question_type"], answer_json, content_json, structure_json,
                     item["passage"] or None, item["status"], is_active, item["id"])
                if cursor.rowcount == 0:
                    raise ValueError("找不到指定題目")
                question_id = item["id"]
            else:
                question_id = cursor.execute("""
                    INSERT dbo.Company_TrainingQuestion
                    (document_id,subject_id,chapter_id,domain,category,question,options_json,
                     correct_index,explanation,question_type,answer_json,content_json,structure_json,
                     passage,status,is_active,admin_locked)
                    OUTPUT inserted.question_id VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
                """, item["document_id"], item["subject_id"], item["chapter_id"], item["domain"],
                     category, item["question"], options_json, correct_index, item["explanation"],
                     item["question_type"], answer_json, content_json, structure_json,
                     item["passage"] or None, item["status"], is_active).fetchone()[0]
        return {**item, "id": question_id, "is_active": bool(is_active), "admin_locked": True}
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("營運檢核題庫儲存失敗。") from exc


def grade_compliance_answer(item: dict[str, Any], employee_id: str) -> dict[str, Any]:
    rows = _fetch("""
        SELECT question_id AS id,question_type,options_json,answer_json,explanation
        FROM dbo.Company_TrainingQuestion WHERE question_id=? AND is_active=1 AND status=N'published'
    """, (item["question_id"],))
    if not rows:
        raise ValueError("找不到指定題目")
    question = rows[0]
    if question["question_type"] == "essay":
        if not item["answer_text"]:
            raise ValueError("請輸入申論答案")
        try:
            with connect(read_only=False) as db:
                answer_id = db.cursor().execute("""
                    INSERT dbo.Company_TrainingAnswer (question_id,employee_id,answer_text)
                    OUTPUT inserted.answer_id VALUES (?,?,?)
                """, item["question_id"], employee_id, item["answer_text"]).fetchone()[0]
            return {"id": answer_id, "status": "待審核", "is_essay": True}
        except pyodbc.Error as exc:
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
    rows = _fetch("""
        SELECT q.question_id AS id,s.subject_name AS subject,c.chapter_name AS chapter,
               q.question,q.content_json,q.source_locator,
               latest.status AS answer_status,latest.feedback,latest.submitted_at
        FROM dbo.Company_TrainingQuestion q
        JOIN dbo.Company_TrainingSubject s ON s.subject_id=q.subject_id
        LEFT JOIN dbo.Company_TrainingChapter c ON c.chapter_id=q.chapter_id
        OUTER APPLY (
            SELECT TOP 1 a.status,a.feedback,a.submitted_at
            FROM dbo.Company_TrainingAnswer a
            WHERE a.question_id=q.question_id AND a.employee_id=?
            ORDER BY a.submitted_at DESC
        ) latest
        WHERE q.domain=N'practical' AND q.question_type=N'essay'
          AND q.status=N'published' AND q.is_active=1
        ORDER BY q.question_id
    """, (employee_id,))
    for row in rows:
        row["content_blocks"] = _loads_json(row.pop("content_json"), [{"type": "text", "content": row["question"]}])
    return rows


def compliance_essay_answers_admin() -> list[dict[str, Any]]:
    return _fetch("""
        SELECT a.answer_id AS id,a.question_id,q.category,q.question,a.employee_id,
               s.display_name AS employee_name,a.answer_text,a.status,a.feedback,
               a.submitted_at,a.reviewed_by,a.reviewed_at
        FROM dbo.Company_TrainingAnswer a
        JOIN dbo.Company_TrainingQuestion q ON q.question_id=a.question_id
        JOIN dbo.Company_Staff s ON s.employee_id=a.employee_id
        ORDER BY CASE WHEN a.status=N'待審核' THEN 0 ELSE 1 END,a.submitted_at DESC
    """)


def review_compliance_essay(item: dict[str, Any], reviewer_id: str) -> dict[str, Any]:
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            cursor.execute("""
                UPDATE dbo.Company_TrainingAnswer
                SET status=?,feedback=?,reviewed_by=?,reviewed_at=SYSDATETIME()
                WHERE answer_id=?
            """, item["status"], item["feedback"] or None, reviewer_id, item["id"])
            if cursor.rowcount == 0:
                raise ValueError("找不到指定申論答案")
        return {"id": item["id"], "status": item["status"]}
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("申論答案審核失敗。") from exc


def deactivate_compliance_question(question_id: int) -> dict[str, Any]:
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            cursor.execute(
                "UPDATE dbo.Company_TrainingQuestion SET is_active=0,status=N'disabled',admin_locked=1,updated_at=SYSDATETIME() WHERE question_id=?",
                question_id,
            )
            if cursor.rowcount == 0:
                raise ValueError("找不到指定題目")
        return {"id": question_id, "is_active": False}
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("營運檢核題庫停用失敗。") from exc


def set_training_question_status(question_id: int, status: str) -> dict[str, Any]:
    if status not in {"draft", "published", "disabled"}:
        raise ValueError("題目狀態不正確")
    rows = _fetch("""
        SELECT question_type,options_json,answer_json,structure_json,explanation
        FROM dbo.Company_TrainingQuestion WHERE question_id=?
    """, (question_id,))
    if not rows:
        raise ValueError("找不到指定題目")
    row = rows[0]
    if status == "published" and row["question_type"] != "essay":
        answers = _loads_json(row["answer_json"], [])
        options = _loads_json(row["options_json"], [])
        structure = _loads_json(row["structure_json"], {})
        if not answers or not row["explanation"]:
            raise ValueError("發布前必須完成正確答案與解析")
        if row["question_type"] in {"single_choice", "multiple_choice", "reading"} and len(options) < 2:
            raise ValueError("發布前必須完成至少兩個選項")
        if row["question_type"] in {"fill_blank", "matching"} and not structure:
            raise ValueError("發布前必須完成題型結構")
    try:
        with connect(read_only=False) as db:
            db.cursor().execute("""
                UPDATE dbo.Company_TrainingQuestion
                SET status=?,is_active=?,admin_locked=1,updated_at=SYSDATETIME()
                WHERE question_id=?
            """, status, int(status == "published"), question_id)
        return {"id": question_id, "status": status, "is_active": status == "published"}
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("題目狀態更新失敗。") from exc


def unlock_training_question_import(question_id: int) -> dict[str, Any]:
    """由管理員明確授權下一次來源同步覆寫指定題目。"""
    try:
        with connect(read_only=False) as db:
            cursor = db.cursor()
            cursor.execute("""
                UPDATE dbo.Company_TrainingQuestion
                SET admin_locked=0,status=N'draft',is_active=0,updated_at=SYSDATETIME()
                WHERE question_id=? AND source_fingerprint IS NOT NULL
            """, question_id)
            if cursor.rowcount == 0:
                raise ValueError("此題目沒有可重新匯入的來源")
        return {"id": question_id, "unlocked": True}
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("無法解除題目的匯入保護。") from exc


def update_training_questions_bulk(item: dict[str, Any]) -> dict[str, Any]:
    placeholders = ",".join("?" for _ in item["ids"])
    try:
        if item["subject_id"]:
            chapters = _fetch("""
                SELECT chapter_id FROM dbo.Company_TrainingChapter
                WHERE subject_id=? AND chapter_id=?
            """, (item["subject_id"], item["chapter_id"]))
            if not chapters:
                raise ValueError("指定章節不屬於所選科目")
            with connect(read_only=False) as db:
                db.cursor().execute(f"""
                    UPDATE dbo.Company_TrainingQuestion
                    SET subject_id=?,chapter_id=?,admin_locked=1,updated_at=SYSDATETIME()
                    WHERE question_id IN ({placeholders})
                """, item["subject_id"], item["chapter_id"], *item["ids"])
        if item["status"]:
            for question_id in item["ids"]:
                set_training_question_status(question_id, item["status"])
        return {"updated": len(item["ids"]), **item}
    except pyodbc.Error as exc:
        raise DatabaseUnavailable("題目批次更新失敗。") from exc
