# 銀盾共同體營運中心

銀盾共同體營運中心整合企業官網、員工工作台與 MIS 後台，提供出勤管理、營運填報、教育訓練與企業宣導功能。前端使用原生 HTML、CSS 與 JavaScript，後端使用 Python HTTP 服務，業務資料存放於 SQL Server。

目前提供 Windows 本機執行與 Windows 容器部署兩種方式。容器以 Windows Server Core LTSC 2022 為基底，啟用內建 IIS，並在網站目錄建立 Python venv。

## 功能總覽

| 功能 | 說明 |
| --- | --- |
| 企業官網 | 企業資訊、四大產業據點、公開員工資料與部門篩選、合作資訊與地圖；後台可調整首頁文字、公告與四種視覺主題 |
| 員工入口 | 以有效員工編號登入，可選擇上班打卡或僅進入系統 |
| 工作台與出勤 | 伺服器校時、出勤狀態、上下班打卡與常用入口 |
| 員工管理 | 組織架構、員工搜尋與明細、員工照片、部門維護及打卡紀錄查詢 |
| 營運填報 | 日報提交、個人填報歷程、補件回覆，以及管理端核准、退回與要求補件 |
| 教育訓練 | 分類練習、模擬考、續作、逐題檢討、錯題本與術科申論 |
| 文件與題庫 | 來源文件同步與狀態維護、題目草稿審核、科目與章節維護、題目發布與停用 |
| 工作面板 | 四個環境分頁的介面骨架，目前為佔位內容 |
| 企業宣導 | YouTube、BiliBili、ニコニコ、Douyin、TikTok 分頁播放與標題解析，以及 YouTube 縮圖下載 |
| MIS 後台 | 官網設定、資料表查閱、營運與申論審核、教育資料管理 |

學科題型包含單選、多選與閱讀；程式碼填空以單選題呈現，術科申論由管理員人工審核。模擬考交卷前不回傳正解與解析，作答紀錄保留題目快照。

## 前端介面與資源

前端採原生 HTML、共用 CSS 與 JavaScript ES Modules，不需要 Node.js 或前端打包工具。請透過 Python 或 IIS 提供的 HTTP 網址使用，讓模組載入、同來源 API 與工作階段驗證正常運作。

- 公開官網包含企業理念、四大產業據點、部門篩選名冊與合作資訊。據點圖片使用 `page/static/png/company/` 的相對路徑，可隨網站部署位址載入。
- MIS 官網設定提供銀盾藍（`shield`）、勳章紅（`medal`）、鋼鐵灰（`steel`）及專業白（`white`）四種主題，並提供首頁預覽。
- 七個內部頁面共用「工作台、營運日報、題庫練習、工作面板、宣導影音、員工管理、後台管理」側邊導覽。一般頁面側欄標示「內部使用」，員工管理與 MIS 則標示需管理員登入。
- 內部頁面統一內容寬度、卡片間距與表單樣式，透過 CSS 媒體查詢調整窄螢幕的導覽、欄位、員工清單與縮圖排列。
- 員工入口以醒目時鐘、員工編號及兩種進入方式呈現；題庫、員工管理、MIS、宣導影音與工作面板將分頁導覽置於頂部狀態列。

## 系統架構

```mermaid
flowchart LR
    Browser[瀏覽器] --> IIS[IIS：80 埠]
    IIS -->|ARR／URL Rewrite| Python[Python HTTP 服務：127.0.0.1:8000]
    Python --> SQL[SQL Server]
    Python --> Files[網頁、員工照片與來源文件]
```

上圖為容器部署架構。IIS 將網站與 API 請求轉送給 `backend.app`，由 Python 處理頁面、靜態資源、權限及資料存取。網站部署於 `C:/inetpub/wwwroot/`，保留 `backend/`、`page/` 與 `data/` 的目錄結構。

本機執行時，`start.bat` 直接啟動 Python，使用 `0.0.0.0:80` 提供網站與 API。前端與後端使用同一來源，無須額外的前端建置流程。

## 專案結構

```text
erp_site/
├─ backend/
│  ├─ app.py                 # HTTP 路由、登入、工作階段與檔案回應
│  ├─ data.py                # SQL Server 查詢、交易、資料表初始化與資料維護
│  ├─ input.py               # 輸入驗證與資料清理
│  ├─ media.py               # BiliBili、ニコニコ、Douyin、TikTok 標題取得
│  ├─ doc.py                 # 文件轉換、文字擷取、OCR 與來源同步
│  ├─ time_sync.py           # SQL Server 權威時間與台灣工作日換算
│  ├─ test_media.py          # 影音網址、標題解析與外部請求限制測試
│  └─ test_training.py       # 題目解析、作答驗證、安全與資料庫連線回歸測試
├─ page/
│  ├─ *.html                 # 官網、員工頁面與後台
│  ├─ workflow.html          # 工作面板的四個環境分頁骨架
│  └─ static/
│     ├─ script.js            # 共用 API、身分驗證、校時與分頁工具
│     ├─ style.css            # 全站樣式、官網主題與響應式版面
│     ├─ panel.js             # 宣導影音與工作面板的分頁顯示控制
│     ├─ game.js              # 多平台播放器、標題與播放紀錄
│     ├─ youtube_thumbnail.js # YouTube 縮圖解析、預覽、下載與本機紀錄
│     ├─ *.js                 # 各頁互動邏輯
│     ├─ ico/                 # 網頁圖示
│     ├─ png/company/         # 官網產業據點圖片
│     ├─ png/product/         # 工具與產品圖片素材
│     └─ staff/               # 員工照片，依員工編號命名
├─ data/
│  ├─ staff.csv              # 員工同步來源
│  ├─ Company_Schema.sql     # 資料表結構參考
│  └─ exam/                  # 自行準備的 SOP 與題庫來源文件
├─ templates/
│  └─ cookiecutter.json      # 專案範本參數
├─ dockerfile                # Windows image 建置與容器啟動設定
├─ docker-compose.yml        # 容器服務、image 名稱與連接埠設定
├─ requirements.txt          # 固定版本的 Python 直接相依套件
├─ start.bat                 # Windows 本機啟動與基本套件檢查
├─ .dockerignore             # Docker 建置內容排除規則
├─ .env                      # 自行準備的資料庫與管理員設定，不納入 Git
├─ CHANGELOG.md              # 版本變更紀錄
└─ Readme.md
```

`data/exam/` 與轉檔快取屬於執行環境資料，未隨 Git 提供。系統透過 `data.py` 初始化應用資料表；`Company_Schema.sql` 作為結構參考。

## 環境設定

兩種執行方式都需要可連線的 SQL Server，以及專案根目錄的 `.env`。設定欄位如下，請自行填入實際值：

| 欄位 | 用途 |
| --- | --- |
| `DatabaseIP` | SQL Server 位址；容器部署時須能從容器內連線 |
| `DatabasePort` | SQL Server TCP 連接埠 |
| `DatabaseName` | 使用的資料庫名稱 |
| `DatabaseUser` | 資料庫帳號 |
| `DatabasePassword` | 資料庫密碼 |
| `BackendWebAdminUser` | MIS 管理員帳號 |
| `BackendWebAdminPassword` | MIS 管理員密碼 |

資料庫與管理員設定由程式直接讀取 `.env` 檔案，僅設定同名的作業系統環境變數無法取代此檔案。程式未使用 `DatabaseDriver` 欄位，SQL Server 存取套件由 `requirements.txt` 安裝。

啟動時會執行應用資料表初始化與結構更新，因此資料庫帳號須具備相應的建表、結構更新及業務資料讀寫權限。完成初始化後，程式預設同步 `data/exam/` 內的 SOP 文件；文件同步失敗會記錄訊息，資料庫初始化失敗則會中止啟動。

## Windows 容器部署

### 執行需求

- 使用 Windows 容器模式的 Docker 與 Docker Compose。
- 可執行 Windows Server Core LTSC 2022 容器的主機環境。
- 可下載官方 image、Microsoft 安裝程式與 Python 套件的網路連線。
- 已完成上述 `.env` 設定，且容器可連線至 SQL Server。
- 主機的 80 埠可供網站使用。

### 建置與啟動

在專案根目錄執行：

```powershell
docker compose build erp_service
docker compose up -d
```

建置後的 image 名稱為 `erp-site:servercore-ltsc2022`，容器名稱為 `ERP_Site`。瀏覽 [網站首頁](http://localhost/) 或 [資料庫健康 API](http://localhost/api/health) 確認服務。

Dockerfile 從官方 `python:3.13-windowsservercore-ltsc2022` image 取得 Python，最終基底為 `mcr.microsoft.com/windows/servercore:ltsc2022`。建置流程包含 IIS、ARR、URL Rewrite、Visual C++ Runtime、venv 與 Python 套件安裝，並檢查 `start.bat --check`、文件套件匯入、產生的啟動腳本及 IIS XML。

容器啟動時，Python 使用 `127.0.0.1:8000`，IIS 使用 80 埠。啟動程序會監控 Python 與 IIS，任一停止便結束容器；Compose 設定為 `restart: unless-stopped`。

### 狀態與維護

```powershell
# 查看服務與健康狀態
docker compose ps

# 查看最近的啟動訊息
docker compose logs --tail 100 erp_service

# 持續追蹤記錄；Ctrl+C 結束追蹤
docker compose logs -f erp_service

# 停止服務並移除 Compose 容器與網路
docker compose down
```

目前 image 的健康檢查請求為首頁 `/`，用來確認 IIS 至 Python 的 HTTP 路徑；`/api/health` 另會讀取 SQL Server，供資料庫連線診斷。

### 目前部署行為

- `.env` 會被複製進 image，因此 image 含有部署環境的機密設定；分享或發布 image 前需先處理其中的帳密。
- 網站程式與 `.env` 更新後，需要重新建置並更新容器，可執行 `docker compose up -d --build`。
- 尚未設定 volume。員工照片與文件快取等寫入容器的檔案，會在容器移除或重建時遺失；SQL Server 中的資料仍由資料庫保存。
- `.dockerignore` 排除 `data/` 內多數資料，Dockerfile 只複製 `staff.csv` 與 `Company_Schema.sql`，目前 image 不包含本機的 `data/exam/` 文件。
- 目前提供 HTTP，未設定 HTTPS。
- Image 未安裝 Tesseract、LibreOffice 或 Microsoft Word；需要 OCR 或舊版 DOC 轉檔時，須另外準備對應執行環境。

## Windows 本機執行

容器使用 Python 3.13。本機可使用 Python 3.13 建立專案虛擬環境，再安裝相同相依套件：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start.bat --check
.\start.bat
```

`start.bat --check` 只檢查 venv 與基本套件匯入，不測試 SQL Server 連線。`start.bat` 固定使用 80 埠；若發生連接埠占用或權限錯誤，可改用以下開發命令：

```powershell
.\.venv\Scripts\python.exe -m backend.app --host 127.0.0.1 --port 8080
```

啟動後開啟 [本機網站](http://127.0.0.1:8080/) 或 [資料庫健康 API](http://127.0.0.1:8080/api/health)。略過啟動時的 SOP 文件同步：

```powershell
.\.venv\Scripts\python.exe -m backend.app --host 127.0.0.1 --port 8080 --skip-doc-sync
```

直接執行 `backend.app` 時，也可用作業系統環境變數 `SILVER_SHIELD_HOST`、`SILVER_SHIELD_PORT` 設定預設監聽位址與連接埠。命令列參數優先；`start.bat` 與容器啟動程序已有明確指定值。這兩個變數不會從專案 `.env` 自動載入。

## 頁面與使用流程

| 頁面 | 使用方式 |
| --- | --- |
| `/`、`/index.html` | 公開企業官網 |
| `/employee-login.html` | 員工登入，選擇上班打卡或僅進入系統 |
| `/home.html` | 員工工作台、出勤狀態與常用入口 |
| `/sales.html` | 提交營運日報、查看審閱結果與回覆補件 |
| `/exam.html` | 學科刷題、模擬考、未完成題組續作、錯題本與術科申論 |
| `/workflow.html` | 工作面板，提供「環境一」至「環境四」佔位分頁 |
| `/game.html` | 五個影音平台分頁、影片標題、原站連結與 YouTube 縮圖下載 |
| `/staff.html` | 員工組織、明細、部門與打卡紀錄管理 |
| `/mis.html` | 官網設定、資料查閱、營運與教育訓練管理 |

員工先以在職員工編號登入，再進入工作台；管理功能還需通過 MIS 帳密驗證。HTML 頁面可被載入，資料讀取與寫入權限由各 API 在後端驗證。

上下班打卡依序交替，系統以 SQL Server 時間換算台灣工作日，並透過交易控制避免重複打卡。營運日報可由管理員要求補件、核准或退回，員工可查閱個人紀錄並回覆。

員工管理採組織架構、員工清單與員工明細三區介面，提供搜尋與停用員工篩選。員工照片支援 JPEG、PNG 與 WebP，單張上限為 5 MB。

工作面板可由側邊導覽及員工工作台的快捷入口開啟。目前僅建立四個環境分頁與切換介面，尚未串接業務資料或提供 SOP 文件閱讀功能。

### 多平台宣導影音

在 `/game.html` 頂部分頁選擇平台，貼上對應網址並按「轉換並播放」。後端先驗證平台、網域與影片識別碼，再取得來源提供的標題並產生嵌入網址。

| 平台 | 可解析的影片格式 | 僅提供原站連結的格式 |
| --- | --- | --- |
| YouTube | 一般影片、直播、Shorts、分享短網址與嵌入網址 | 禁止嵌入的影片可改由「YouTube 開啟」觀看 |
| BiliBili | BV／av 影片與嵌入網址，保留 `p` 分集 | `b23.tv` 分享短網址、直播 |
| ニコニコ | 一般影片、`nico.ms` 影片短網址與嵌入網址 | 直播 |
| Douyin | 一般影片、`modal_id` 網址、分享影片與嵌入網址 | `v.douyin.com` 分享短網址、直播 |
| TikTok | 一般影片、分享影片與播放器／嵌入網址 | 分享短網址、直播 |

YouTube 使用 `/api/youtube/resolve` 與 oEmbed 取得影片資訊，前端設有 10 秒逾時。其他四個平台共用 `/api/media/resolve`，由 `backend/media.py` 讀取固定來源的 API、XML 或嵌入頁面，前端設有 12 秒逾時。TikTok 優先讀取符合目前影片 ID 的說明，缺少資料時再嘗試 oEmbed，避免將其他影片或頁面標題當成影片標題。

兩個解析 API 都需要員工工作階段與 CSRF Token。各平台最近成功載入的網址分別保存在目前瀏覽器的 `localStorage`，不寫入 SQL Server。YouTube 進入頁面時會載入上次網址或預設影片；其他平台先還原輸入值，首次切換到該分頁時才嘗試載入既有紀錄。

僅提供原站連結時，不建立嵌入播放器，也不以影片 ID 代替標題。來源未填寫標題、無法取得標題與來源服務失敗會分別回報；成功取得標題仍可能因來源的登入、地區或嵌入限制而無法播放，可使用原站連結觀看。

### YouTube 縮圖

縮圖工具與播放器使用各自的輸入表單：

1. 貼上影片網址或 11 碼影片 ID，按「取得縮圖」。
2. 工具直接從 YouTube 圖片來源 `i.ytimg.com` 載入圖片，檢查實際尺寸並排除無效或逾時的縮圖。
3. 從可用的 HD（1280 × 720）、SD（640 × 480）、HQ（480 × 360）、MQ（320 × 180）尺寸中選擇下載；並非每部影片都有所有尺寸。
4. 瀏覽器無法直接下載時，介面會提供「開啟縮圖」連結，開啟後可另存圖片。

縮圖最近查詢最多保留 8 筆影片 ID，儲存在目前瀏覽器的 `localStorage`，可點選重新查詢或清除紀錄，不寫入 SQL Server。也可使用 `/game.html?url=影片網址或ID` 預填並啟動縮圖查詢；此參數只控制縮圖工具。

目前 `game.html` 的可見介面提供多平台影音與 YouTube 縮圖工具，未提供知識搜尋或 SOP 閱讀入口。後端仍保留文件查詢 API，來源文件管理與同步則位於 MIS。

## 影音解析 API

以下請求皆使用 JSON，並帶入員工工作階段 Cookie 與 `X-CSRF-Token` 標頭：

| 路徑 | 請求內容 | 成功回應 |
| --- | --- | --- |
| `POST /api/youtube/resolve` | `{"url":"YouTube 影片網址"}` | `data` 包含 `video_id`、`title`、`watch_url`、`embed_url` |
| `POST /api/media/resolve` | `{"platform":"bilibili","url":"對應平台影片網址"}` | `data` 包含 `platform`、`video_id`、`title`、`title_status`、`watch_url`、`embed_url` |

`platform` 支援 `bilibili`、`niconico`、`douyin`、`tiktok`。`title_status` 為 `available`（已取得標題）、`empty`（來源未填寫標題）或 `unavailable`（僅提供原站連結，此時 `embed_url` 為空字串）。無效輸入回傳 HTTP 400；來源資訊取得失敗回傳 HTTP 503 與 `EXTERNAL_SERVICE_UNAVAILABLE`。

## 文件與題庫同步

來源文件放在 `data/exam/`。支援 DOCX、舊版 DOC、Excel（含 XLSX、XLS）與 PDF；舊版 DOC 轉換結果快取在 `data/exam/.converted/`，保留原始文件。

| 文件類型 | 額外需求 |
| --- | --- |
| DOCX、Excel、可擷取文字的 PDF | 安裝 `requirements.txt` 中的套件 |
| 舊版 DOC | 優先使用 LibreOffice；Windows 本機可使用已安裝的 Microsoft Word COM 作為備援 |
| 掃描型 PDF | Tesseract OCR 與 `chi_tra`、`eng` 語言資料，搭配 PyMuPDF、Pillow、pytesseract |

Tesseract 可透過 PATH 或 `C:\Program Files\Tesseract-OCR\tesseract.exe` 尋找；LibreOffice 可透過 PATH 或 `C:\Program Files\LibreOffice\program\soffice.exe` 尋找。

解析文件並顯示摘要，不寫入資料庫；遇到舊版 DOC 時仍可能產生轉檔快取：

```powershell
.\.venv\Scripts\python.exe -m backend.doc
```

將 SOP 同步至 SQL Server：

```powershell
.\.venv\Scripts\python.exe -m backend.doc --sync
```

MIS 的來源同步功能會同步 SOP 與題庫草稿，並回報解析警告及失敗來源。管理員確認草稿後再發布題目，也可維護科目、章節、題目狀態與批次設定。

## 測試與檢查

測試檔案位於 `backend/test_training.py` 與 `backend/test_media.py`，在專案根目錄執行：

```powershell
.\.venv\Scripts\python.exe -m unittest backend.test_training backend.test_media -v
```

現有測試涵蓋題目解析、OCR 缺失回報、訓練輸入驗證、模擬考答案保護、CSRF 驗證、員工同步快取，以及請求內資料庫連線重用。

影音測試另外涵蓋平台網址驗證、分集保留、來源標題解析、TikTok 影片對應與空白標題、僅原站連結、逾時、回應大小限制、禁止重新導向，以及 XML 實體拒絕處理。外部來源使用模擬回應，不代表第三方平台即時可用或影片可實際播放。

檢查 Python 套件與 Compose 設定：

```powershell
.\.venv\Scripts\python.exe -m pip check
docker compose config --quiet
```

## 權限與資料保護

- 員工與 MIS 使用各自的工作階段 Cookie，包含 HttpOnly、SameSite=Strict 與 8 小時有效期限。
- 受保護的資料異動 API 驗證登入身分與 CSRF Token，登入失敗也有次數限制。
- 工作階段存放在 Python 程序記憶體中，重新啟動後需重新登入。
- 後端驗證輸入、限制資料表與欄位存取，管理端資料表查閱會遮罩敏感欄位。
- 網頁與靜態資源採允許路徑及目錄邊界檢查，`.env` 與後端原始碼不透過網站提供下載。
- 多平台影音解析限制允許的網域、網址格式與固定查詢端點，拒絕含帳密或指定連接埠的輸入；`media.py` 禁止跟隨重新導向，單次回應上限為 2 MiB，並限制來源請求時間。
- 目前 SQL Server 連線字串使用 `Encrypt=no;TrustServerCertificate=yes`；網站 TLS 與資料庫加密需依部署需求另行設定。

## 常見問題

| 狀況 | 檢查方式 |
| --- | --- |
| 找不到 `.venv` 或缺少套件 | 重新執行本機環境安裝命令；確認從專案根目錄啟動 |
| 啟動失敗或容器反覆重新啟動 | 查看 `docker compose logs --tail 100 erp_service`，確認 `.env`、資料庫連線及初始化權限 |
| 網站開啟但 API 回應 503 | 使用 `/api/health` 檢查 SQL Server；確認執行環境可連線到設定的資料庫位址與連接埠 |
| 80 埠已被占用 | 本機改用 8080；容器部署則檢查主機既有服務與 Compose 的連接埠設定 |
| SOP 清單沒有來源文件 | 確認 `data/exam/` 中存在支援的檔案；目前 image 未打包該目錄 |
| 掃描 PDF 或舊版 DOC 無法解析 | 確認 Tesseract 語言資料或文件轉檔工具已安裝且可被程式找到 |
| 影音無法取得標題或回傳 503 | 確認員工登入、平台與網址是否相符，以及伺服器至來源平台的網路連線；來源拒絕存取時可稍後重試 |
| 影片有標題但無法播放，或只顯示原站連結 | 使用各平台的原站連結；短網址可改貼完整影片網址，並確認來源的登入、地區與嵌入限制 |
| 工作面板僅顯示分頁文字 | 目前為環境分頁骨架，尚未串接業務內容 |
| YouTube 縮圖沒有部分尺寸或無法下載 | 僅顯示實際可用尺寸；確認可連線至 `i.ytimg.com`，直接下載失敗時使用「開啟縮圖」另存圖片 |
| 修改程式或 `.env` 後容器仍使用舊設定 | 重新建置 image 並更新容器 |

特別感謝 Codex、ChatGPT 與 Grok 在開發過程中提供協助。
