# 福祿貝爾營運中心

這是一套前後端分離的幼稚園官方網站與內部園務平台。公開網站呈現教育理念、園務規模、學習日常與教職團隊；員工入口整合出勤、園務填報、教育訓練與內部資訊；後台管理中心則提供受控的網站設定、唯讀資料查閱及待審佇列。

後端使用 Python 與 `pyodbc` 實際連接 SQL Server，僅存取 `dbo.Frobel_*` 應用資料表。網站寫入只發生在這些專用資料表及員工照片資料夾，`.env` 不會由程式建立或修改。

特別感謝小助手Codex、ChatGPT、Grok給予協助。

## 程式架構

```text
erp_site/
├── .agents/                        #內部開發與資料治理文件（不納入版本控制）
│   ├── agent.md                    #開發協作規範與內部歷程
│   ├── database.md                 #SQL Server結構與資料治理原則
│   └── site.md                     #網站資訊架構與頁面角色說明
├── data/                           #匯入來源、教育文件與資料庫備份素材
│   ├── exam/                       #教育訓練Word文件來源
│   ├── staff.csv                   #員工初始資料與同步來源
│   ├── Frobel_1.sql                #資料庫結構參考SQL（一）
│   ├── Frobel_2.sql                #資料庫結構參考SQL（二）
│   ├── Frobel_ALL_Backend_Table.bak #SQL Server備份檔
│   ├── operation_submissions.json  #營運填報暫存資料
│   └── erp_learning.db             #本機教育資料檔
├── static/                         #公開靜態素材
│   ├── appicon.png                 #系統識別圖
│   └── staff/                      #員工照片，檔名對應員工編號
├── templates/
│   └── cookiecutter.json           #專案範本設定
├── .env                            #SQL Server與MIS憑證（不納入版本控制）
├── .gitignore                      #Git排除規則
├── requirements.txt                #Python套件清單
├── win_start.bat                   #Windows Port 80啟動與環境檢查
├── app.py                          #HTTP路由、Cookie工作階段、CSRF與存取權限
├── data.py                         #SQL Server查詢、資料表遷移與受控寫入
├── input.py                        #前端輸入清理與驗證
├── doc.py                          #Word文件轉換、擷取與教育資料同步
├── time_sync.py                    #SQL Server權威時間與台灣工作日校時
├── style.css                       #全站共用響應式UI樣式
├── index.html                      #對外官方網站
├── employee-login.html             #員工編號驗證與打卡入口
├── home.html                       #員工工作台、打卡與園務摘要
├── sales.html                      #營運日報與填報生命週期
├── exam.html                       #教育文件查閱與知識檢核
├── game.html                       #YouTube直播休息站
├── staff.html                      #MIS員工、部門與出缺勤管理
├── mis.html                        #MIS網站設定、待審、文件與題庫維護
└── Readme.md                       #公開專案說明
```

所有前端 JavaScript 都內嵌於各自 HTML 的 `<script>` 標籤，因此專案沒有獨立的 `script.js`。

## 主要功能

### 公開官方網站

- 響應式幼稚園品牌首頁，支援海洋、晨光、森林三種資料庫主題。
- 顯示在職教職員、管理部門與教育文件等營運彙總，不公開個人敏感資料。
- 教職團隊只回傳姓名、部門、職位、特質及公開照片。
- 教職團隊可透過部門下拉選單篩選；部門清單與篩選結果皆由 `data.py` 查詢後交由 `app.py` 回傳。
- 其餘首頁區域已統一強化層次、卡片、學習日常、招生參觀與行動版版面。

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

### 園務工作區

- 工作台提供公告、園務指標、部門概況、常用入口與知識搜尋。
- 營運蒐集依營運分類填寫數量、說明與日期，並以待審流程集中管理。
- 新增的營運紀錄會保存建立員工編號，供 MIS 待審佇列依員工分類。
- 教育訓練提供 Word 文件分類、段落查閱及互動題庫。
- 營運蒐集與教育訓練皆改為分頁介面，將填報、生命週期、文件查閱與知識檢核分開管理。
- YouTube 休閒專區由後端驗證影片網址並取得真實標題後嵌入播放。

### 員工出缺勤管理

- 員工文字資料的新增、更新與停用集中於 `staff.html`。
- 員工編號是不可變更的主鍵，編輯時輸入框會鎖定並以警示色標示。
- 員工照片只接受 JPEG、PNG、WebP，最大 5 MB；檔名會自動改為員工編號並存入 `static/staff`。
- 員工主檔固定依員工編號排序，不使用中文部門名稱定序。
- 管理員可依日期或員工查閱出缺勤紀錄；既有打卡紀錄不因員工停用而刪除。
- 員工資料、部門維護及打卡紀錄拆成三個分頁；性別、年齡與部門採受控選項，必填錯誤會聚焦對應欄位。

### 後台管理中心

- 進入 MIS 前必須先通過員工入口驗證，再使用 `.env` 內的管理帳號進行第二層登入。
- 可管理官方網站主題、標題、副標題及公告。
- 可唯讀查閱 10 張 `dbo.Frobel_*` 應用資料表；後端限制資料表名稱、分頁筆數並遮罩敏感欄位。
- 原「員工資料」與「營運待審」已整合為「待審佇列」。
- 待審佇列左側按員工編號顯示員工，右側顯示其建立的申請事件；可點選員工、事件或事件類別進行篩選。
- MIS 不再提供員工編輯或停用控制，並保留前往 `staff.html` 的「查看出缺勤」入口。
- MIS 新增教育文件與題庫維護分頁，可同步、啟用或停用文件，以及新增、更新、停用知識檢核題目。

### 員工 CSV 與照片

- `data.py` 在員工查閱、驗證與維護前掃描 `data/staff.csv`。
- 只有修改時間或檔案大小改變時才以參數化 `MERGE` 合併員工資料。
- CSV 未列出的員工不會自動停用，管理員上傳的既有照片不會被 CSV 覆寫。
- 官網與後台員工名單預設皆由 `data.py` 先按員工編號整理；只有公開教職團隊提供部門條件篩選。

### 驗證與安全

- 員工工作階段與 MIS 工作階段有效時間皆為 8 小時，使用 HttpOnly、SameSite Cookie。
- 每個內部及 MIS API 都會重新查詢 `dbo.Frobel_Staff`，確認員工仍存在且啟用。
- MIS 工作階段綁定目前員工，避免其他員工沿用既有管理工作階段。
- 員工與管理登入都有失敗頻率限制；寫入操作另需 CSRF Token。
- 打卡由 `time_sync.py` 的 `time.now()` 取得單一 SQL Server 時間快照，保存 UTC 與台灣工作日，避免資料庫與瀏覽器時間不一致。
- 敏感欄位分類與遮罩在後端完成，前端不取得未遮罩內容。

### 前端頁面

| 頁面 | 用途 |
| --- | --- |
| `index.html` | 公開官方網站與部門化教職團隊 |
| `employee-login.html` | 員工編號驗證、上班打卡或不打卡進入 |
| `home.html` | 員工工作台、打卡狀態、補打卡、下班及離開系統 |
| `sales.html` | 營運彙總日報與填報生命週期分頁 |
| `exam.html` | 教育文件與知識檢核分頁 |
| `game.html` | YouTube 網址驗證與播放器 |
| `staff.html` | 員工主檔、部門與出缺勤分頁管理 |
| `mis.html` | 網站設定、唯讀查閱、待審、教育文件及題庫維護 |

內部系統各頁使用一致的左側導覽列。官方網站不列在側欄中，員工可從工作台的常用入口前往；管理員也可在「官方網站版面設定」直接開啟公開網站確認發布結果。

所有網站圖檔都使用 `static` 資料夾內的檔案。

### 後端頁面

| 檔案 | 用途 |
| --- | --- |
| `app.py` | HTTP 路由、員工與 MIS 工作階段、CSRF 與 API 權限 |
| `data.py` | SQL Server 查詢、CSV 同步、排序、打卡與受控寫入 |
| `input.py` | 員工入口、打卡、園務、照片、YouTube 與設定輸入驗證 |
| `doc.py` | Word 文件轉換、擷取與教育資料同步 |
| `time_sync.py` | SQL Server、台灣時區與瀏覽器校時基準 |
| `style.css` | 官方網站、員工入口、工作台與 MIS 共用樣式 |
| `database.md` | 資料庫結構、資料治理及正式環境原則 |
| `site.md` | 網站資訊架構與角色說明 |
| `win_start.bat` | Windows Port 80 啟動檔 |

## 安裝與啟動

建議使用 Visual Studio Code，並安裝 Microsoft ODBC Driver 17 for SQL Server。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
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

本專案不使用 Visual Studio Code Live Server。HTML、靜態資源與 API 均由 `app.py` 在同一個 Port 80 服務提供，避免跨來源 Cookie、Proxy 與前後端連線設定不一致。

## 目前整合成果

- 對外網站、員工入口、園務工作區、員工管理與 MIS 已形成明確的角色分流。
- 員工可選擇上班打卡或不打卡進入，工作台再依當日狀態提供補打卡、下班與離開功能。
- 公開教職團隊支援部門選單，後台員工資料固定依員工編號管理。
- 員工維護集中於 `staff.html`；MIS 原員工分頁改為以員工及事件雙向篩選的待審佇列。
- 營運待審事項會保存建立員工，既有無建立者紀錄仍可查閱。
- 實際 SQL Server 的 10 張 `Frobel_*` 表、CSV、Word 文件與 `static` 圖片共同形成目前的資料來源。
- 已移除舊資料庫的園區、班級、學籍、收費、接送、職務及薪資查詢，避免新資料庫缺表造成 API 失敗。

## 上線注意事項

- 正式環境應使用 HTTPS，並為工作階段 Cookie 加上 Secure 屬性。
- 建議將唯讀查詢與網站專用寫入拆成不同的最小權限資料庫帳號。
- 多程序或多主機部署時，記憶體工作階段應改為集中式儲存。
- 上線前應由園方覆核打卡時段、補打卡判定、資料遮罩、待審流程與存取稽核規則。

## 補充資料

### 資料來源與正規化資料表

`data.py` 讀取既有 `.env` 連線 SQL Server。公開、員工與 MIS 功能只會使用下列 10 張 `dbo.Frobel_*` 應用資料表；不會查詢其他資料表，也不能從前端送入任意 SQL。

網站使用以下專用資料表：

| 資料表 | 用途 |
| --- | --- |
| `dbo.Frobel_WebSettings` | 官方網站主題與文字設定 |
| `dbo.Frobel_Department` | 員工部門主檔與啟用狀態 |
| `dbo.Frobel_Staff` | 員工主檔 |
| `dbo.Frobel_Attendance` | 上下班打卡紀錄 |
| `dbo.Frobel_OperationCategory` | 園務填報分類 |
| `dbo.Frobel_OperationSubmission` | 待審園務紀錄與建立員工 |
| `dbo.Frobel_TrainingDocument` | 教育文件主檔 |
| `dbo.Frobel_TrainingSection` | 教育文件段落 |
| `dbo.Frobel_TrainingQuestion` | 教育訓練題庫 |
| `dbo.Frobel_ImportState` | `staff.csv` 匯入狀態 |

### API 摘要

| 路徑 | 權限 | 說明 |
| --- | --- | --- |
| `GET /api/public` | 公開 | 官方網站設定與彙總 |
| `GET /api/staff/departments` | 公開 | 公開教職團隊的部門選單 |
| `GET /api/staff/public?department=...` | 公開 | 依部門取得公開教職資料 |
| `POST /api/employee/login` | 公開 | 以 `CLOCK_IN` 或 `ACCESS_ONLY` 驗證並進入 |
| `GET /api/employee/session` | 公開 | 查詢員工工作階段及當日打卡狀態 |
| `POST /api/employee/logout` | 員工 | 結束工作階段，不異動打卡 |
| `GET /api/time` | 公開 | 取得 SQL Server UTC、台灣工作日與校時毫秒值 |
| `POST /api/attendance/clock` | 員工 | 補上班或打卡下班 |
| `POST /api/operations/submit` | 員工 | 新增附帶建立員工的待審事項 |
| `GET /api/training` | 員工 | 教育文件目錄 |
| `GET /api/training/document?id=...` | 員工 | 教育文件段落 |
| `POST /api/admin/login` | 已驗證員工 | 建立後台管理工作階段 |
| `GET /api/admin/catalog` | 管理員 | 取得可唯讀查閱的 `Frobel_*` 資料表目錄 |
| `GET /api/admin/table?name=...` | 管理員 | 取得指定 `Frobel_*` 資料表的遮罩分頁資料 |
| `GET/POST /api/admin/settings` | 管理員 | 讀取或儲存官方網站設定 |
| `GET /api/admin/submissions` | 管理員 | 取得附帶建立員工的待審佇列 |
| `GET/POST/DELETE /api/admin/staff` | 管理員 | 員工主檔查閱、維護與停用，供 `staff.html` 使用 |
| `GET/POST/DELETE /api/admin/departments` | 管理員 | 部門主檔查閱、維護與停用 |
| `GET /api/admin/attendance` | 管理員 | 依日期或員工查閱出缺勤 |
| `POST /api/admin/training/sync` | 管理員 | 重新同步教育 Word 文件 |
| `GET /api/admin/training/documents` | 管理員 | 查閱含停用狀態的教育文件 |
| `POST /api/admin/training/document` | 管理員 | 啟用或停用教育文件 |
| `GET /api/admin/training/questions` | 管理員 | 查閱完整教育題庫 |
| `POST/DELETE /api/admin/training/question` | 管理員 | 新增、更新或停用題目 |
