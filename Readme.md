# 銀盾共同體營運中心
>   這是一套前後端分離的企業官方網站與內部平台。公開網站呈現企業宗旨、營運規模、營運據點與專業團隊；<br>
>   員工入口整合出勤、營運填報、營運SOP、學術科題庫與內部資訊；後台管理中心則提供受控的網站設定、唯讀資料查閱及待審佇列。

銀盾共同體的公開網站與內部營運平台。系統由 Python 原生 HTTP 服務提供前端頁面、靜態資源與 API，並透過 `pyodbc` 連接 SQL Server。

主要用途包含：

- 公開企業網站與團隊資訊
- 員工登入、上下班打卡與營運資料填報
- 學科題庫、模擬考、錯題本與術科申論
- 宣導影音、知識條目與營運 SOP 查詢
- 員工、部門、出缺勤及 MIS 後台管理

## 專案結構

```text
erp_site/
├─ backend/
│  ├─ app.py               # HTTP 服務、路由、工作階段與權限
│  ├─ data.py              # SQL Server 查詢、遷移與資料寫入
│  ├─ input.py             # 輸入驗證與清理
│  ├─ doc.py               # Word、Excel、PDF 與 OCR 文件處理
│  └─ time_sync.py         # SQL Server 時間與台灣工作日換算
├─ data/
│  ├─ exam/                # 題庫與 SOP 來源文件
│  ├─ staff.csv            # 員工初始或同步資料
│  └─ Company_Schema.sql   # 資料表結構參考
├─ page/
│  ├─ *.html               # 各功能頁面
│  └─ static/
│     ├─ script.js         # 全站共用 ES module
│     ├─ <頁面名稱>.js     # 各頁專屬事件與畫面邏輯
│     ├─ style.css         # 全站共用樣式
│     ├─ png/              # 網站圖片
│     └─ staff/            # 員工照片
├─ tests/                  # 自動化測試
├─ requirements.txt        # Python 相依套件
├─ start.bat               # Windows 啟動與套件檢查
└─ Readme.md
```

## 前端頁面

| 頁面 | 用途 |
| --- | --- |
| `index.html` | 公開企業網站、營運據點與專業團隊 |
| `employee-login.html` | 員工驗證、上班打卡或不打卡進入 |
| `home.html` | 員工工作台、公告、校時與打卡操作 |
| `sales.html` | 營運資料填報、審閱歷程與補充回覆 |
| `exam.html` | 學科練習、模擬考、錯題本與術科申論 |
| `game.html` | YouTube／Bilibili 宣導影音、知識條目與營運 SOP |
| `staff.html` | 員工、部門與出缺勤管理 |
| `mis.html` | 網站設定、待審佇列、資料查閱、文件與題庫管理 |

所有頁面使用 `type="module"` 載入 `page/static/<頁面名稱>.js`，再由頁面模組引用 `page/static/script.js` 的共用 API、登入導向、安全跳脫、CSRF 寫入及共用事件。

## 核心功能

### 員工與出勤

- 員工以員工編號驗證，可選擇上班打卡或直接進入。
- 上下班紀錄以 SQL Server 時間為準，並依台灣時區計算工作日。
- 工作台提供補打卡、下班打卡與單純離開系統。
- 員工、部門及歷史出勤紀錄由管理頁面集中維護。

### 營運與審核

- 員工可提交營運資料、查閱自己的審核歷程並回覆補件要求。
- MIS 可依員工或事件類別篩選待審資料，執行核准、退回或要求補件。
- 每次提交、審核與回覆都保留活動歷程。

### 題庫

- 學科支援單選、多選、閱讀、程式碼填空與配對題。
- 支援分類練習、模擬考、倒數計時、續作、錯題本及逐題檢討。
- 模擬考交卷前不回傳正解與解析。
- 術科採申論作答，由 MIS 人工審核並提供回饋。
- 題組保存題目快照，避免題目修改影響既有成績。

### 文件、知識與影音

- `game.html` 整合宣導影音、知識條目搜尋及營運 SOP 閱讀。
- SOP 支援分類、文件列表與段落閱讀。
- 管理員可同步 Word、Excel 與 PDF；題目解析結果先進入草稿。
- PDF 優先使用原生文字，必要時才以 300 DPI 執行繁中／英文 OCR。

## 安裝需求

- Windows 與 Python 3
- Microsoft ODBC Driver 17 for SQL Server
- 可連線的 SQL Server
- 掃描型 PDF 才需要 Tesseract OCR，以及 `chi_tra`、`eng` 語言資料

安裝 Python 套件：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 環境設定

在專案根目錄建立 `.env`：

```dotenv
DatabaseIP=資料庫位址
DatabasePort=1433
DatabaseName=資料庫名稱
DatabaseUser=資料庫帳號
DatabasePassword=資料庫密碼
BackendWebAdminUser=MIS管理員帳號
BackendWebAdminPassword=MIS管理員密碼
```

`.env` 含有敏感資訊，不應提交至版本控制。

## 啟動

先檢查虛擬環境與必要套件：

```powershell
.\start.bat --check
```

以 Port 80 啟動並開放內網存取：

```powershell
.\start.bat
```

若 Windows 拒絕使用 Port 80，請以系統管理員身分執行。也可直接指定其他連接埠：

```powershell
.\.venv\Scripts\python.exe -m backend.app --host 127.0.0.1 --port 8080
```

啟動時會確認應用資料表，並同步 `data/exam` 中可讀取的 SOP 文件。可使用 `--skip-doc-sync` 略過啟動同步。

本專案不需要 Visual Studio Code Live Server；HTML、ES modules、圖片與 API 都由 `backend.app` 在同一來源提供。

## 測試

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 安全原則

- 員工與 MIS 使用不同層級的工作階段驗證。
- Cookie 使用 HttpOnly 與 SameSite；寫入操作需通過 CSRF 驗證。
- 後端只允許既定資料表、欄位與 API 操作，前端不能提交任意 SQL。
- 查閱資料表時由後端遮罩敏感內容。
- 正式環境應使用 HTTPS、最小權限資料庫帳號及集中式工作階段儲存。

特別感謝 Codex、ChatGPT 與 Grok 在開發過程中提供協助。
