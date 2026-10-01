# 銀盾共同體營運中心

銀盾共同體營運中心是一套整合公開官網、員工入口與 MIS 管理功能的企業營運平台。系統以前端原生 HTML、CSS、JavaScript 搭配 Python 原生 HTTP 服務實作，由同一個服務提供網頁、靜態資源與 API，並透過 `pyodbc` 連接 SQL Server。

目前涵蓋以下用途：

- 公開企業資訊、營運據點與專業團隊展示
- 員工身分驗證、上下班打卡與出勤狀態查詢
- 營運日報填報、補件回覆與管理端審核
- 學科練習、模擬考、錯題本與術科申論
- 宣導影音、知識條目與營運 SOP 查閱
- 員工、部門、出缺勤、網站內容及教育資料管理

## 系統架構

```text
瀏覽器
  ├─ 公開官網
  ├─ 員工入口
  └─ MIS 管理介面
       │
       ▼
Python ThreadingHTTPServer
  ├─ 頁面與靜態資源
  ├─ 工作階段、CSRF 與輸入驗證
  ├─ 營運及教育訓練 API
  └─ 文件解析與同步
       │
       ▼
SQL Server
```

本專案不需要 Visual Studio Code Live Server，也沒有 Node.js 或 npm 建置流程。所有 HTML、ES modules、圖片與 `/api` 請求皆由 `backend.app` 以同一來源提供。

## 技術組成

| 類別 | 使用技術 |
| --- | --- |
| 後端 | Python 3.12、`http.server.ThreadingHTTPServer` |
| 前端 | HTML5、CSS、原生 JavaScript ES modules |
| 資料庫 | Microsoft SQL Server、ODBC Driver 17、`pyodbc` |
| 文件處理 | `python-docx`、`openpyxl`、`xlrd`、`pypdf` |
| PDF 與 OCR | PyMuPDF、Pillow、Tesseract、`pytesseract` |
| 測試 | Python `unittest` |

## 專案結構

```text
erp_site/
├─ backend/
│  ├─ app.py               # HTTP 服務、路由、工作階段與權限控制
│  ├─ data.py              # SQL Server 結構、查詢、交易與資料寫入
│  ├─ input.py             # API 輸入驗證與資料清理
│  ├─ doc.py               # Word、Excel、PDF 與 OCR 文件處理
│  └─ time_sync.py         # SQL Server 權威時間與台灣工作日換算
├─ data/
│  ├─ exam/                # SOP 與題庫來源文件，本機資料不納入版本控制
│  ├─ staff.csv            # 員工初始同步資料
│  └─ Company_Schema.sql   # SQL Server 資料表結構參考
├─ page/
│  ├─ *.html               # 公開官網、員工入口與管理頁面
│  └─ static/
│     ├─ script.js         # 共用 API、登入導向、CSRF 與頁面工具
│     ├─ <頁面名稱>.js      # 各頁事件與畫面邏輯
│     ├─ style.css         # 全站共用樣式
│     ├─ png/              # 官網圖片
│     └─ staff/            # 以員工編號命名的員工照片
├─ templates/
│  └─ cookiecutter.json    # 專案範本設定
├─ test/
│  └─ test_training.py     # 題庫解析、輸入及回應安全測試
├─ requirements.txt        # Python 相依套件
├─ start.bat               # Windows 啟動與套件檢查
└─ Readme.md
```

## 功能頁面

| 頁面 | 存取層級 | 用途 |
| --- | --- | --- |
| `index.html` | 公開 | 企業資訊、營運據點、部門篩選與專業團隊 |
| `employee-login.html` | 公開入口 | 驗證在職員工，可選擇打卡或不打卡進入 |
| `home.html` | 員工 | 工作台、公告、校時、補打卡、下班打卡與登出 |
| `sales.html` | 員工 | 營運日報填報、資料生命週期、審閱歷程與補件回覆 |
| `exam.html` | 員工 | SOP 查閱、分類練習、模擬考、錯題本與術科申論 |
| `game.html` | 員工 | 宣導影音、知識條目與營運 SOP 閱讀 |
| `staff.html` | 員工＋MIS | 員工組織與名冊、員工與部門維護及出勤紀錄查詢 |
| `mis.html` | 員工＋MIS | 待審佇列、網站設定、資料查閱、文件與題庫管理 |

## 核心流程

### 員工登入與出勤

- 員工編號會向 SQL Server 即時驗證是否存在且仍在職。
- 「上班打卡並進入」會建立出勤紀錄；「不打卡進入系統」只建立員工工作階段。
- 上下班必須依序交替，並以資料庫交易鎖避免重複或同時打卡。
- 打卡時間與工作日以 SQL Server 回傳的台灣時間為準，前端定期重新校時。
- 員工工作階段與 MIS 管理工作階段各自獨立，閒置有效期限為 8 小時。

### 員工與部門管理

- 公開官網只顯示可公開的在職員工資料，並可依部門篩選。
- `staff.html` 提供組織樹、關鍵字搜尋、部門篩選及停用員工檢視。
- MIS 可新增、編輯或停用員工與部門，既有員工編號不可變更。
- 員工照片支援 JPEG、PNG 與 WebP，檔案大小上限為 5 MB，儲存時會自動改為員工編號。

### 營運填報與審核

- 員工可提交營運資料、查看自己的審核歷程，並回覆補件要求。
- MIS 可依員工或事件類別篩選待審事項，執行核准、退回或要求補件。
- 提交、審核與回覆皆保留活動歷程。

### 題庫與申論

- 學科支援單選、多選、閱讀、程式碼填空與配對題。
- 支援分類練習、模擬考、倒數計時、續作、逐題檢討及錯題本。
- 模擬考交卷前不會將正解與解析回傳前端。
- 術科採申論作答，由 MIS 人工審核並提供回饋。
- 題組會保存題目快照，避免後續修改題目影響既有作答紀錄。

### 文件與影音

- 系統可讀取 DOCX、DOC、XLSX、XLS 與 PDF 格式的營運文件。
- 舊版 DOC 需要 LibreOffice，或在 Windows 上使用 Microsoft Word 作為轉檔備援。
- PDF 優先擷取原生文字；掃描頁面才以 300 DPI 執行繁體中文與英文 OCR。
- 題目解析結果先存為待審草稿，由 MIS 確認後發布。
- YouTube 網址由後端驗證並解析標題，前端不直接信任使用者輸入的嵌入網址。

## 安裝需求

- Windows
- Python 3.12
- Microsoft ODBC Driver 17 for SQL Server
- 可連線且具備應用資料表權限的 SQL Server
- 處理掃描型 PDF 時需額外安裝 Tesseract OCR，以及 `chi_tra`、`eng` 語言資料
- 處理舊版 DOC 時需安裝 LibreOffice 或 Microsoft Word

建立虛擬環境並安裝套件：

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
DatabaseDriver=ODBC Driver 17 for SQL Server
BackendWebAdminUser=MIS管理員帳號
BackendWebAdminPassword=MIS管理員密碼
```

`DatabaseDriver` 可省略，預設為 `ODBC Driver 17 for SQL Server`。`.env` 含有敏感資訊，已由 `.gitignore` 排除，請勿提交或公開其內容。

服務也接受以下選用環境變數：

```dotenv
SILVER_SHIELD_HOST=0.0.0.0
SILVER_SHIELD_PORT=80
```

## 啟動方式

先檢查專案虛擬環境與必要套件：

```powershell
.\start.bat --check
```

以 Port 80 啟動並開放同一內網存取：

```powershell
.\start.bat
```

Port 80 可能需要系統管理員權限。若只供本機開發，可改用其他連接埠：

```powershell
.\.venv\Scripts\python.exe -m backend.app --host 127.0.0.1 --port 8080
```

啟動時會建立或更新應用所需資料表，並同步 `data/exam/` 中可讀取的 SOP 文件。若暫時不需要文件同步，可使用：

```powershell
.\.venv\Scripts\python.exe -m backend.app --host 127.0.0.1 --port 8080 --skip-doc-sync
```

啟動後可透過以下網址確認服務與資料庫狀態：

```text
http://127.0.0.1:8080/api/health
```

## 文件同步

只解析來源文件並顯示結果，不寫入資料庫：

```powershell
.\.venv\Scripts\python.exe -m backend.doc
```

解析 SOP 並同步至 SQL Server：

```powershell
.\.venv\Scripts\python.exe -m backend.doc --sync
```

完整的 SOP、題庫草稿同步與審核功能也可在 MIS 管理頁執行。

## 測試

執行現有單元測試：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s test -v
```

目前測試涵蓋題目結構解析、缺少 OCR 時的錯誤回報、訓練輸入驗證，以及模擬考作答期間不洩漏答案。

## 安全設計

- 員工與 MIS 使用不同的工作階段 Cookie；進入 MIS 前必須先通過員工驗證。
- Cookie 設為 HttpOnly 與 SameSite；登入後的資料寫入皆需通過 CSRF 驗證。
- 登入失敗會受到次數與時間限制，降低暴力嘗試風險。
- 後端只允許既定資料表、欄位與 API 操作，前端無法提交任意 SQL。
- 管理端查閱資料表時會由後端遮罩敏感欄位。
- 靜態檔案路徑經過白名單與目錄邊界檢查，不會公開 `.env` 或專案內部檔案。
- 正式環境仍應加上 HTTPS、反向代理、最小權限資料庫帳號及集中式工作階段儲存。

特別感謝 Codex、ChatGPT 與 Grok 在開發過程中提供協助。
