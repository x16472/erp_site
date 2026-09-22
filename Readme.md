# 銀盾共同體營運中心

這是一套前後端分離的企業官方網站與內部平台。公開網站呈現企業宗旨、營運規模、營運據點與專業團隊；員工入口整合出勤、營運填報、營運SOP、學術科題庫與內部資訊；後台管理中心則提供受控的網站設定、唯讀資料查閱及待審佇列。

後端使用 Python 與 `pyodbc` 實際連接 `Company_New` SQL Server 資料庫，僅存取 `dbo.Company_*` 應用資料表。網站寫入只發生在這些專用資料表及員工照片資料夾，`.env` 不會由程式自行建立或覆寫。

特別感謝小助手Codex、ChatGPT、Grok給予協助。
## 程式架構

```text
erp_site/
├── .agents/                        #內部開發與資料治理文件（不納入版本控制）
│   ├── agent.md                    #開發協作規範與內部歷程
│   ├── database.md                 #SQL Server結構與資料治理原則
│   └── prd.md                      #銀盾共同體產品需求與檢核結果
├── data/                           #匯入來源、SOP文件與資料庫備份素材
│   ├── exam/                       #營運SOP與題庫 Word、Excel、PDF來源
│   ├── staff.csv                   #員工初始資料與同步來源
│   ├── Company_Schema.sql          #Company資料表結構參考SQL
│   ├── Company_Backend_Tables.bak  #SQL Server備份檔
│   ├── legacy/                     #不由現行程式載入的舊資料封存
│   └── operation_submissions.json  #營運填報暫存資料
├── page/                           #前端網頁與公開靜態素材
│   ├── static/
│   │   ├── appicon.png             #系統識別圖
│   │   └── staff/                  #員工照片，檔名對應員工編號
│   ├── style.css                   #全站共用響應式UI樣式
│   ├── index.html                  #對外官方網站
│   ├── employee-login.html         #員工編號驗證與打卡入口
│   ├── home.html                   #員工工作台、打卡與營運摘要
│   ├── sales.html                  #營運日報、填報摘要、審閱歷程與員工回覆
│   ├── exam.html                   #學科刷題、模擬考、錯題本與術科申論
│   ├── game.html                   #企業宣導影音與YouTube播放器
│   ├── staff.html                  #MIS員工、部門與出缺勤管理
│   └── mis.html                    #MIS網站設定、待審、文件與題庫維護
├── backend/                        #Python後端服務
│   ├── __init__.py                 #後端套件定義
│   ├── app.py                      #HTTP路由、Cookie工作階段、CSRF與存取權限
│   ├── data.py                     #SQL Server查詢、資料表遷移與受控寫入
│   ├── input.py                    #前端輸入清理與驗證
│   ├── doc.py                      #Word、Excel、PDF擷取與營運SOP同步
│   └── time_sync.py                #SQL Server權威時間與台灣工作日校時
├── templates/
│   └── cookiecutter.json           #專案範本設定
├── .env                            #SQL Server與MIS憑證（不納入版本控制）
├── .gitignore                      #Git排除規則
├── requirements.txt                #Python套件清單
├── win_start.bat                   #Windows Port 80啟動與環境檢查
└── Readme.md                       #公開專案說明
```

所有前端 JavaScript 都內嵌於各自 HTML 的 `<script>` 標籤，因此專案沒有獨立的 `script.js`。

## 主要功能

### 公開官方網站

- 響應式企業品牌首頁，支援銀盾藍、勳章紅、鋼鐵灰三種資料庫主題。
- 以羅瓦德莊園、可可藝術沙龍、聯合工匠街與地下堅石礦場呈現四大產業據點。
- 顯示在職員工、管理部門與SOP文件等營運彙總，不公開個人敏感資料。
- 專業團隊只回傳姓名、部門、職位、特質及公開照片。
- 專業團隊可透過部門下拉選單篩選；部門清單與篩選結果皆由 `backend/data.py` 查詢後交由 `backend/app.py` 回傳。
- 其餘首頁區域已統一強化層次、卡片、營運據點、商務合作與行動版版面。

#### 視覺主題參數

MIS 預覽與官方網站共用以下六個 CSS 變數：

| 參數 | 用途 |
| --- | --- |
| `--public-theme-dark` | 頁首、頁尾及主視覺深色底 |
| `--public-theme-mid` | 主視覺漸層、卡片及主要品牌色 |
| `--public-theme-light` | 主視覺光暈及較亮的輔助色 |
| `--public-theme-accent` | 標題強調字及導覽互動色 |
| `--public-theme-detail` | 裝飾線、卡片標記及次要重點色 |
| `--public-theme-surface` | 官方網站頁面底色 |

新增主題時需同步完成三處設定：

1. 在 `page/mis.html` 的視覺主題下拉選單增加唯一英文值與顯示名稱。
2. 在 `backend/input.py` 的 `ALLOWED_THEMES` 加入相同英文值。
3. 在 `page/style.css` 加入以下色票結構：

```css
.public-body[data-theme="custom"],
.settings-preview.custom {
    --public-theme-dark: #111827;
    --public-theme-mid: #374151;
    --public-theme-light: #6b7280;
    --public-theme-accent: #fbbf24;
    --public-theme-detail: #d97706;
    --public-theme-surface: #f9fafb
}
```

### 員工入口與打卡

- 登入頁只顯示必要資訊，員工以員工編號進行身分驗證。
- 「上班打卡並進入」會驗證在職狀態、檢查打卡順序、寫入打卡後建立工作階段。
- 「不打卡進入系統」仍會驗證員工，但不新增出勤紀錄；系統會讀取當日最後一筆打卡時間，未打卡時醒目提示。
- 工作台顯示「打卡時間」及資料庫校準時鐘；未打卡時提供補打卡按鈕。
- 「打卡下班」會寫入下班紀錄後離開；「離開系統」只結束工作階段，不影響出勤資料。
- 首筆必須是上班打卡，上下班必須交替；後端以交易鎖避免連續或同時重複打卡。
- 打卡狀態以台灣工作日換日，前後台切換時都會重新讀取資料庫，不沿用登入當下的暫存狀態。
- 登入頁與工作台以 SQL Server UTC 時間換算台灣時區，計入網路往返延遲並每 60 秒重新校時。
- 工作台提示：未在特定時段補打卡，視同遲到或曠職。

### 營運工作區

- 工作台提供公告、營運指標、部門概況、常用入口與知識搜尋。
- 營運蒐集依營運分類填寫數量、說明與日期，並以待審流程集中管理。
- 新增的營運紀錄會保存建立員工編號，供 MIS 待審佇列依員工分類。
- 員工可查閱自己的日報狀態、完整審閱歷程，並在待審或補件階段回覆管理員。
- 工作台知識區提供 Word、Excel、PDF 營運SOP的分類、搜尋與段落查閱。
- 題庫中心分為學科與術科；學科支援單選、多選、閱讀、程式碼填空、配對、分類練習、模擬考及錯題本，術科申論送交 MIS 人工審核。
- 題目進度、模考倒數與錯題均綁定員工帳號；模考交卷前不回傳正解或解析。
- 企業宣導影音專區由後端驗證影片網址並取得真實標題後嵌入播放。

### 員工出缺勤管理

- 員工文字資料的新增、更新與停用集中於 `page/staff.html`。
- 員工編號是不可變更的主鍵，編輯時輸入框會鎖定並以警示色標示。
- 員工照片只接受 JPEG、PNG、WebP，最大 5 MB；檔名會自動改為員工編號並存入 `page/static/staff`。
- 員工主檔固定依員工編號排序，不使用中文部門名稱定序。
- 管理員可依日期或員工查閱出缺勤紀錄；既有打卡紀錄不因員工停用而刪除。
- 員工資料、部門維護及打卡紀錄拆成三個分頁；部門名稱最多 5 個字，目前由原先 15 筆部門整併為營運部、製造部、財務部、資訊部、福利部與後勤部六個啟用部門。

### 後台管理中心

- 進入 MIS 前必須先通過員工入口驗證，再使用 `.env` 內的管理帳號進行第二層登入。
- 可管理官方網站主題、標題、副標題及公告。
- 可唯讀查閱 10 張 `dbo.Company_*` 應用資料表；後端限制資料表名稱、分頁筆數並遮罩敏感欄位。
- 原「員工資料」與「營運待審」已整合為「待審佇列」。
- 待審佇列左側按員工編號顯示員工，右側顯示其建立的申請事件；可點選員工、事件或事件類別進行篩選。
- MIS 可對營運日報要求補件、核准或退回，每次審閱與員工回覆都會保留歷程。
- MIS 不再提供員工編輯或停用控制，並保留前往 `page/staff.html` 的「查看出缺勤」入口。
- MIS 可維護學科／術科、科目、章節、模考規則與六種題型，文件解析題目一律先進草稿，管理員編修後不受後續同步覆寫。

### 員工 CSV 與照片

- `backend/data.py` 在員工查閱、驗證與維護前掃描 `data/staff.csv`。
- 只有修改時間或檔案大小改變時才以參數化 `MERGE` 合併員工資料。
- CSV 未列出的員工不會自動停用，管理員上傳的既有照片不會被 CSV 覆寫。
- 官網與後台員工名單預設皆由 `backend/data.py` 先按員工編號整理；只有公開專業團隊提供部門條件篩選。

### 驗證與安全

- 員工工作階段與 MIS 工作階段有效時間皆為 8 小時，使用 HttpOnly、SameSite Cookie。
- 每個內部及 MIS API 都會重新查詢 `dbo.Company_Staff`，確認員工仍存在且啟用。
- MIS 工作階段綁定目前員工，避免其他員工沿用既有管理工作階段。
- 員工與管理登入都有失敗頻率限制；寫入操作另需 CSRF Token。
- 打卡由 `backend/time_sync.py` 的 `time.now()` 取得單一 SQL Server 時間快照，保存 UTC 與台灣工作日，避免資料庫與瀏覽器時間不一致。
- 敏感欄位分類與遮罩在後端完成，前端不取得未遮罩內容。

### 前端頁面

| 頁面 | 用途 |
| --- | --- |
| `page/index.html` | 公開官方網站與部門化專業團隊 |
| `page/employee-login.html` | 員工編號驗證、上班打卡或不打卡進入 |
| `page/home.html` | 員工工作台、打卡狀態、補打卡、下班及離開系統 |
| `page/sales.html` | 新增營運日報、填報摘要、審閱歷程與員工回覆 |
| `page/exam.html` | 學科刷題、模擬考、錯題本與術科申論 |
| `page/game.html` | 企業宣導影音、YouTube網址驗證與播放器 |
| `page/staff.html` | 員工主檔、部門與出缺勤分頁管理 |
| `page/mis.html` | 網站設定、唯讀查閱、待審、SOP文件及題庫維護 |

內部系統各頁使用一致的左側導覽列。官方網站不列在側欄中，員工可從工作台的常用入口前往；管理員也可在「官方網站版面設定」直接開啟公開網站確認發布結果。

所有網站圖檔都使用 `page/static` 資料夾內的檔案。

### 後端模組

| 檔案 | 用途 |
| --- | --- |
| `backend/app.py` | HTTP 路由、員工與 MIS 工作階段、CSRF 與 API 權限 |
| `backend/data.py` | SQL Server 查詢、CSV 同步、排序、打卡與受控寫入 |
| `backend/input.py` | 員工入口、打卡、營運、照片、YouTube 與設定輸入驗證 |
| `backend/doc.py` | Word、Excel、PDF 文件擷取與營運SOP資料同步 |
| `backend/time_sync.py` | SQL Server、台灣時區與瀏覽器校時基準 |
| `page/style.css` | 官方網站、員工入口、工作台與 MIS 共用樣式 |
| `database.md` | 資料庫結構、資料治理及正式環境原則 |
| `prd.md` | 產品需求、品牌規則與實作檢核 |
| `win_start.bat` | Windows Port 80 啟動檔 |

## 安裝與啟動

建議使用 Visual Studio Code，並安裝 Microsoft ODBC Driver 17 for SQL Server。

掃描型 PDF 題庫另需安裝 Tesseract OCR，並啟用 `chi_tra` 與 `eng` 語言資料。程式會優先尋找系統 `PATH`，其次尋找 `C:\Program Files\Tesseract-OCR\tesseract.exe`；缺少 OCR 時仍可同步其他文件，MIS 會顯示來源警告。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m backend.app
```
建立一個`.env`檔案，在裡面填入ENV設定
```
DatabaseIP=資料庫IP
DatabasePort=1433
DatabaseName=資料庫
DatabaseUser=資料庫帳號
DatabasePassword=資料庫密碼
BackendWebAdminUser=後台管理員帳號
BackendWebAdminPassword=後台管理員密碼
```
### Windows Port 80

執行 `win_start.bat`。後端監聽 `0.0.0.0:80`，啟動時會列出同一內網可使用的 IPv4 網址。若 Windows 阻擋 Port 80，需以系統管理員身分執行。

本專案不使用 Visual Studio Code Live Server。`page/` 的 HTML、靜態資源與 API 均由 `backend/app.py` 在同一個 Port 80 服務提供，避免跨來源 Cookie、Proxy 與前後端連線設定不一致。

## 目前整合成果

- 對外網站、員工入口、營運工作區、員工管理與 MIS 已形成明確的角色分流。
- 員工可選擇上班打卡或不打卡進入，工作台再依當日狀態提供補打卡、下班與離開功能。
- 公開專業團隊支援部門選單，後台員工資料固定依員工編號管理。
- 員工維護集中於 `page/staff.html`；MIS 原員工分頁改為以員工及事件雙向篩選的待審佇列。
- 營運待審事項會保存建立員工，既有無建立者紀錄仍可查閱。
- 實際 SQL Server 的 17 張 `Company_*` 應用表、CSV、Word／Excel／PDF 文件與 `page/static` 圖片共同形成目前的資料來源。
- SQL Server 資料庫已改名為 `Company_New`，10 張應用表及限制式皆使用 `Company_*` 企業命名；原表自動產生的 25 個預設、主鍵及唯一限制式也已完成實體重新命名。

## 上線注意事項

- 正式環境應使用 HTTPS，並為工作階段 Cookie 加上 Secure 屬性。
- 建議將唯讀查詢與網站專用寫入拆成不同的最小權限資料庫帳號。
- 多程序或多主機部署時，記憶體工作階段應改為集中式儲存。
- 上線前應由共同體管理人員覆核打卡時段、補打卡判定、資料遮罩、待審流程與存取稽核規則。

## 補充資料

### 資料來源與正規化資料表

`backend/data.py` 讀取既有 `.env` 連線 SQL Server。公開、員工與 MIS 功能使用下列 17 張 `dbo.Company_*` 應用資料表；MIS 通用資料查閱仍只開放原有 10 張白名單資料表，審閱歷程、題庫作答與申論答案只能透過受控 API 存取，前端不能送入任意 SQL。

網站使用以下專用資料表：

| 資料表 | 用途 |
| --- | --- |
| `dbo.Company_WebSettings` | 官方網站主題與文字設定 |
| `dbo.Company_Department` | 員工部門主檔與啟用狀態 |
| `dbo.Company_Staff` | 員工主檔 |
| `dbo.Company_Attendance` | 上下班打卡紀錄 |
| `dbo.Company_OperationCategory` | 營運填報分類 |
| `dbo.Company_OperationSubmission` | 營運日報、建立員工與目前審閱狀態 |
| `dbo.Company_OperationActivity` | 日報審閱、補件及員工回覆歷程 |
| `dbo.Company_TrainingDocument` | SOP文件主檔 |
| `dbo.Company_TrainingSection` | SOP文件段落 |
| `dbo.Company_TrainingQuestion` | 學科、術科、來源、解析狀態與結構化題目 |
| `dbo.Company_TrainingAnswer` | 申論題文字答案及人工審核結果 |
| `dbo.Company_TrainingSubject` | 學科／術科科目與模擬考設定 |
| `dbo.Company_TrainingChapter` | 題庫章節與排序 |
| `dbo.Company_TrainingSession` | 員工練習或模擬考階段 |
| `dbo.Company_TrainingSessionQuestion` | 題組快照、作答與標記 |
| `dbo.Company_TrainingWrongQuestion` | 員工錯題本與手動移除狀態 |
| `dbo.Company_ImportState` | `staff.csv` 匯入狀態 |

### API 摘要

| 路徑 | 權限 | 說明 |
| --- | --- | --- |
| `GET /api/public` | 公開 | 官方網站設定與彙總 |
| `GET /api/staff/departments` | 公開 | 公開專業團隊的部門選單 |
| `GET /api/staff/public?department=...` | 公開 | 依部門取得公開專業團隊資料 |
| `POST /api/employee/login` | 公開 | 以 `CLOCK_IN` 或 `ACCESS_ONLY` 驗證並進入 |
| `GET /api/employee/session` | 公開 | 查詢員工工作階段及當日打卡狀態 |
| `GET /api/time` | 公開 | 取得 SQL Server UTC、台灣工作日與校時毫秒值 |
| `POST /api/attendance/clock` | 員工 | 補上班或打卡下班 |
| `POST /api/employee/logout` | 員工 | 結束工作階段，不異動打卡 |
| `POST /api/operations/submit` | 員工 | 新增附帶建立員工的待審事項 |
| `GET /api/operations/mine` | 員工 | 查閱自己的日報與審閱歷程 |
| `POST /api/operations/reply` | 員工 | 回覆日報審閱或補件要求 |
| `GET /api/manuals` | 員工 | SOP文件目錄 |
| `GET /api/manuals/document?id=...` | 員工 | SOP文件段落 |
| `GET /api/compliance/questions` | 員工 | 商業規範與工安檢核題庫 |
| `POST /api/compliance/answer` | 員工 | 後端判斷選擇題或送交申論答案 |
| `GET /api/training/catalog` | 員工 | 取得學科／術科、科目、章節、來源與續作資訊 |
| `POST /api/training/session/start` | 員工 | 建立分類練習或模擬考 |
| `GET/POST /api/training/session*` | 員工 | 續作、儲存答案與交卷 |
| `GET/POST /api/training/wrong*` | 員工 | 取得或手動移除錯題 |
| `GET/POST /api/training/practical*` | 員工 | 術科題目、申論提交與審核狀態 |
| `POST /api/admin/login` | 已驗證員工 | 建立後台管理工作階段 |
| `GET /api/admin/catalog` | 管理員 | 取得可唯讀查閱的 `Company_*` 資料表目錄 |
| `GET /api/admin/table?name=...` | 管理員 | 取得指定 `Company_*` 資料表的遮罩分頁資料 |
| `GET/POST /api/admin/settings` | 管理員 | 讀取或儲存官方網站設定 |
| `GET /api/admin/submissions` | 管理員 | 取得附帶建立員工的待審佇列 |
| `POST /api/admin/submission/review` | 管理員 | 核准、退回或要求補件 |
| `GET/POST/DELETE /api/admin/staff` | 管理員 | 員工主檔查閱、維護與停用，供 `page/staff.html` 使用 |
| `GET/POST/DELETE /api/admin/departments` | 管理員 | 部門主檔查閱、維護與停用 |
| `GET /api/admin/attendance` | 管理員 | 依日期或員工查閱出缺勤 |
| `POST /api/admin/manuals/sync` | 管理員 | 同步文件、必要時 OCR，並匯入結構化題目草稿 |
| `GET /api/admin/manuals/documents` | 管理員 | 查閱含停用狀態的SOP文件 |
| `POST /api/admin/manuals/document` | 管理員 | 啟用或停用SOP文件 |
| `GET /api/admin/compliance/questions` | 管理員 | 查閱完整商業規範與工安題庫 |
| `POST/DELETE /api/admin/compliance/question` | 管理員 | 新增、更新或停用題目 |
| `GET /api/admin/compliance/answers` | 管理員 | 查閱申論答案待審清單 |
| `POST /api/admin/compliance/answer/review` | 管理員 | 審核申論答案並留下回饋 |
| `GET/POST /api/admin/training/*` | 管理員 | 維護科目、章節、模考設定與題目發布狀態 |
