# 前端頁面架構與維護指引

更新日期：2026-10-26。依 `page/`、`page/static/` 與 `backend/src/erp/api.py` 的目前內容整理。本文描述實作，不沿用過往改版指令或未重新驗證的測試結論。

## 架構與權限

前端採原生 HTML、JavaScript ES Modules 與共用 CSS，不需要 Node.js 或打包工具。頁面、靜態資源與 API 由同一 Go HTTP 服務（Python 業務透過 gRPC 執行）提供；容器部署時由 IIS 反向代理。請透過 HTTP 使用，不以直接開啟本機 HTML 作為完整功能驗證。

HTML 路由本身可載入，保護主要由 API 執行。員工頁面透過 `requireEmployee()` 檢查工作階段；員工管理與 MIS 還需管理員工作階段，且管理員身分綁定目前員工。工作面板目前是介面骨架，沒有獨立的完整身分驗證與業務資料流程。

| 頁面 | 腳本 | 目前用途 |
| --- | --- | --- |
| `index.html` | `index.js` | 公開官網、企業理念、四大據點、團隊與合作資訊 |
| `employee-login.html` | `employee-login.js` | 員工編號驗證、上班打卡或不打卡進入 |
| `home.html` | `home.js` | 員工資訊、公告、校時、出勤與快捷入口 |
| `sales.html` | `sales.js` | 營運日報、個人填報歷程與補充回覆 |
| `exam.html` | `exam.js` | 學科刷題、模考、續作、錯題本與術科申論 |
| `workflow.html` | `panel.js`；另引用影音腳本 | 四個環境分頁，內容尚為佔位文字 |
| `game.html` | `panel.js`、`game.js`、`youtube_thumbnail.js` | 五平台影音與 YouTube 縮圖工具 |
| `staff.html` | `staff.js` | 組織、員工維護、部門與出勤管理 |
| `mis.html` | `mis.js` | 官網設定、日報／申論審核、來源同步、題庫與資料查閱 |

上述各頁腳本位於 `page/static/`。入口流程為官網或登入頁 → 員工工作台 → 各業務頁面；管理 API 需再通過 MIS 登入。

## 頁面功能與主要 API

### 官網與員工入口

`index.html` 呈現羅瓦德莊園、可可藝術沙龍、聯合工匠街、地下堅石礦場，並提供企業理念、專業團隊部門篩選與合作資訊。動態內容使用 `GET /api/public`、`GET /api/staff/public`、`GET /api/staff/departments`。圖片使用 `static/png/company/`，團隊照片使用 `static/staff/`；地圖與影音仍依賴外部服務。

`employee-login.html` 使用 `GET /api/time` 校時，透過 `POST /api/employee/login` 傳入員工編號與 `CLOCK_IN` 或 `ACCESS_ONLY`。編號允許英數、底線與連字號，由後端轉為大寫並查驗在職狀態；不打卡進入不新增出勤。

### 員工工作台

`home.html` 顯示員工資訊、官網公告與當日最後打卡狀態，提供補打卡、打卡下班、離開系統，以及營運日報、題庫、官網、影音與工作面板入口。

主要 API 為 `GET /api/employee/session`、`GET /api/public`、`GET /api/time`、`POST /api/attendance/clock`、`POST /api/employee/logout`。離開系統不變更出勤；完整出勤歷史在員工管理頁查詢。

### 營運日報

`sales.html` 提供日期、據點、分類、數量與摘要表單，並顯示填報提醒、營運流程及個人審閱歷程。個人紀錄可查看要求補件、回覆、審核通過與退回結果；允許回覆的紀錄提供補充表單。

主要 API 為 `GET /api/branches`、`GET /api/operations`、`GET /api/time`、`GET /api/operations/mine`、`POST /api/operations/submit`、`POST /api/operations/reply`。本頁沒有合約或帳務生命週期管理功能。

### 題庫練習

`exam.html` 頂部分為學科刷題與術科申論。學科提供科目、章節、來源與題型篩選，建立練習或模考題組，支援續作、題目標記、交卷檢討與錯題移出。練習可即時看答案與解析；模考交卷前不回傳正解與解析。術科採文字作答與管理員人工審核。

| 方法 | 路徑 | 用途 |
| --- | --- | --- |
| GET | `/api/training/catalog` | 科目、章節、來源及個人練習概況 |
| GET | `/api/training/session` | 讀取指定個人題組 |
| POST | `/api/training/session/start` | 建立題組 |
| POST | `/api/training/session/answer` | 保存作答與標記 |
| POST | `/api/training/session/submit` | 交卷與評分 |
| GET | `/api/training/wrong` | 個人錯題 |
| POST | `/api/training/wrong/remove` | 移出錯題 |
| GET | `/api/training/practical` | 術科題目與個人作答狀態 |
| POST | `/api/training/practical/answer` | 送出術科答案 |

本頁不是 SOP 閱讀器；不要將保留的舊合規 API 或文件 API 當成目前分頁功能。

### 工作面板

`workflow.html` 提供「環境一」至「環境四」，由 `panel.js` 切換 `pl1` 至 `pl4`。目前沒有業務表單、資料保存或 SOP 閱讀器。頁面標題仍為「SOP文件」，狀態仍為「播放器就緒」，均不能作為功能完成的依據。

頁面仍引用 `game.js`、`youtube_thumbnail.js`，但缺少這些腳本預期的影音／縮圖 DOM；這不是已完成的影音整合。本次文件更新未修改此介面或腳本。

### 宣導影音與縮圖

`game.html` 頂部提供 YouTube、BiliBili、ニコニコ、Douyin、TikTok 五個分頁。`panel.js` 控制顯示，`game.js` 管理播放器、標題、狀態與各平台本機播放紀錄。

- YouTube 透過 `POST /api/youtube/resolve` 解析一般影片、Shorts、直播、分享及嵌入網址，前端逾時 10 秒。
- 其他四平台透過 `POST /api/media/resolve`，送出 `platform` 與 `url`，前端逾時 12 秒；平台值為 `bilibili`、`niconico`、`douyin`、`tiktok`。
- BiliBili 保留分集；ニコニコ接受影片短網址；Douyin 與 TikTok 接受對應影片及嵌入格式。部分分享短網址與直播僅提供原站連結，完整格式與限制見 README。
- 兩個 API 都要求員工工作階段與 CSRF。取得標題不保證可嵌入播放，來源限制時使用原站連結。
- YouTube 預設載入上次或預設影片；其他平台切換至分頁時才嘗試載入既有紀錄。
- `youtube_thumbnail.js` 直接向 `i.ytimg.com` 載入可用尺寸，提供預覽、下載與另存連結；最多保存 8 筆最近查詢，可清除。
- 播放網址與縮圖紀錄只存目前瀏覽器的 `localStorage`；縮圖工具也可由 `?url=` 預填啟動，不會改動播放器。

`game.js` 仍保留有條件初始化的知識／SOP 程式，後端也保留查詢 API，但目前 HTML 沒有對應搜尋與閱讀介面。

### 員工管理

`staff.html` 頂部分為員工資料、部門維護與打卡紀錄。員工資料採組織架構、清單、明細三區，提供搜尋、在職篩選、列選取、照片預覽與上傳。員工編號在編輯時鎖定，照片限制 JPEG、PNG、WebP 與 5 MiB。部門維護提供新增、更名與停用；打卡紀錄依日期及員工查詢。

主要 API：`GET/POST/DELETE /api/admin/staff`、`GET/POST/DELETE /api/admin/departments`、`GET /api/admin/attendance`。刪除方法在此代表停用，不是移除既有業務紀錄。

### MIS 後台

| 分頁 ID | 功能 |
| --- | --- |
| `settingsPanel` | 銀盾藍、勳章紅、鋼鐵灰、專業白主題，首頁文字、公告及預覽 |
| `queuePanel` | 依員工與事件篩選日報，要求補件、核准、退回及查看歷程 |
| `freeQuetionPanel` | 術科申論人工審核與評語；ID 沿用目前拼字 |
| `trainingPanel` | 來源同步、文件啟停、科目／模考設定與章節維護 |
| `questionPanel` | 題目編輯、草稿發布、停用、批次設定及重新匯入控制 |
| `dataPanel` | 白名單資料表目錄與分頁查閱 |

主要 API 包含 `/api/admin/settings`、`/api/admin/submissions`、`/api/admin/submission/review`、`/api/admin/manuals/documents`、`/api/admin/manuals/sync`、`/api/admin/manuals/document`、`/api/admin/training/taxonomy`、`/api/admin/compliance/questions`、`/api/admin/catalog`、`/api/admin/table`。通用資料查閱不提供任意資料表編輯；員工新增、照片與停用集中在員工管理頁。

## 共用程式與版面契約

- `script.js`：API 請求、錯誤處理、員工與管理員驗證、CSRF 請求工具、時間偏移、文字跳脫、圖片備援與既有管理分頁。
- `panel.js`：使用 `#staffTabs button[data-panel]` 對應 `.portal-content .panel` 的 ID，並以 `display` 切換；目前供影音與工作面板使用。
- `style.css`：官網四主題、登入頁、共用側欄、卡片、表單、表格及響應式規則。
- 七個內部頁面維持相同側欄順序；管理頁底部另標示需管理員登入。頂部可能是主標題或分頁，狀態元素依頁面使用 `apiState` 或 `playerState`。
- 修改 HTML 時需一併核對腳本選擇器、分頁 ID、表單欄位及狀態容器。API 值插入 HTML 時使用跳脫工具或 DOM 文字屬性。
- `aria-live` 用於多處非同步狀態；不得據此宣稱所有元件均已完成無障礙或全裝置驗證。

## 驗證範圍

本次僅核對原始碼、路由、檔案及文件一致性，未啟動服務、連線資料庫或執行瀏覽器測試。實際驗收需檢查登入、資料異動、權限、窄螢幕、鍵盤操作與外部影音限制；Python 單元測試不能取代前端互動驗收。
