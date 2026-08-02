# 福祿貝爾營運中心

福祿貝爾營運中心是一套前後端分離的幼稚園網站與園務入口。系統包含對外官方網站、全體員工入口、營運資料蒐集、教育訓練、休閒專區及受登入保護的 MIS 管理中心；後端透過 `pyodbc` 實際查詢 SQL Server，並依資料敏感度限制查閱範圍。

## 功能概覽

- 對外官網：介紹教育理念、幼兒學習日常、園務規模、教職團隊與參觀資訊。
- 員工工作台：集中顯示園務指標、班級概況、內部公告、知識搜尋及即時打卡。
- 營運資料蒐集：提供出勤、班級、接送、收費、設備與餐點等日常紀錄表單。
- 教育訓練：提供職掌、SOP、教師手冊查閱與園務安全互動題庫。
- YouTube 直播休息站：網址由後端驗證並取得真實影片標題後播放，支援一般影片、直播、Shorts、分享或嵌入網址。
- MIS 管理中心：提供受保護的官網設定、資料表查閱及待處理紀錄介面。

## 目前新增功能

- 建立公開網站、員工入口與 MIS 管理中心的分眾導覽及響應式版面。
- 串接實際 SQL Server，將園區、班級、學籍、教職員、接送及收費資料轉為網站需要的摘要資訊。
- 新增 MIS 管理員登入、工作階段逾時、登入頻率限制與 CSRF 驗證。
- 新增海洋、晨光及森林三種官網主題，以及首頁標題、副標題與公告管理。
- 新增 SQL Server 資料表目錄、分頁查閱及後端敏感欄位遮罩。
- 新增園務資料輸入驗證、待查核佇列及 MIS 待審紀錄列表。
- 新增正規化員工名冊、官網教職團隊、員工即時打卡及受保護的出缺勤查閱。
- 新增舊版 Word 教育文件轉換、資料庫段落索引、分類搜尋及展開閱讀介面。
- 只保留 Windows Port 80 批次啟動；Ritwick Dey Live Server 使用 Port 5500，並將 `/api` 代理至後端 Port 80。
- 新增資料表白名單、任意 SQL 防護及靜態檔案路徑限制。
- 統一全站品牌、按鈕、表單、資料卡片與行動裝置版面，圖像皆由 `static` 提供。

## 網站角色

| 頁面 | 對象與用途 |
| --- | --- |
| `index.html` | 對外官方網站，呈現教育理念、園區規模與參觀資訊 |
| `home.html` | 全體員工入口，提供園務摘要、公告、快速功能與知識搜尋 |
| `sales.html` | 員工營運蒐集，受理出勤、班級、接送、收費、設備及餐點紀錄 |
| `exam.html` | 員工教育訓練，題庫由後端提供 |
| `game.html` | YouTube 直播休息站與網址轉換播放器 |
| `staff.html` | MIS 員工主檔、照片上傳與出缺勤查閱，使用管理帳密登入 |
| `mis.html` | MIS 管理中心，登入後管理官網內容、唯讀查閱資料表與檢視待處理紀錄 |

所有頁面共用一致的導覽與視覺語言，圖檔只使用 `static` 資料夾內的資源。官方網站支援海洋、晨光與森林三種主題，管理員儲存後即可由資料庫設定套用。

## 實際資料來源

`data.py` 讀取既有 `.env` 連線資訊並連接 SQL Server，不會建立或修改 `.env`。園務摘要主要使用：

- `學籍資料`：幼兒學籍彙總。
- `班別名稱`：班級代號、名稱與園區。
- `ALLtable`：教職員整合主檔與部門彙總。
- `搭交通車況`：接送服務彙總。
- `分校資料`：園區代號與人力彙總。
- `繳費類別`、`繳費項目`、`繳費班別`、`繳費記錄`、`繳費明細`：托育收費流程。

MIS 管理中心可查閱其他使用者資料表。後端會先比對 SQL Server 中繼資料、限制每頁筆數，並遮罩兒少、聯絡、證件、銀行、薪資、保險及稅務等敏感資料。前端不能送入任意 SQL，也沒有任意資料表編輯功能。

## 管理端與寫入範圍

管理端帳號由 `.env` 的 `BackendWebAdminUser` 與 `BackendWebAdminPassword` 提供，密碼只在伺服器端比對，不會傳送到前端。登入工作階段有效時間為 8 小時，並具有 HttpOnly、SameSite Cookie、CSRF 驗證及登入失敗頻率限制。

資料寫入嚴格限制為兩類：

1. 官網版型與文字設定只會寫入專案專用的 `dbo.Frobel_WebSettings`。此資料表會在管理員第一次儲存設定時建立，其他既有資料表仍為唯讀。
2. 員工營運蒐集寫入 `dbo.Frobel_OperationSubmission`，搭配分類資料表進行正規化，供 MIS 查核。
3. 員工資料與打卡分別寫入 `dbo.Frobel_Staff` 與 `dbo.Frobel_Attendance`；員工端只取得本次打卡時間。
4. 教育文件、段落及題庫分開存放於三張教育訓練資料表，原始 Word 文件不會被修改。

## 專案結構

| 檔案 | 用途 |
| --- | --- |
| `app.py` | HTTP 服務、路由、管理端工作階段與 JSON API |
| `data.py` | SQL Server 連線、唯讀查詢、資料遮罩與官網設定寫入 |
| `input.py` | 員工、打卡、營運與官網設定的輸入驗證 |
| `doc.py` | 舊 Word 文件轉換、`python-docx` 擷取與教育資料同步 |
| `style.css` | 官方網站、員工入口及管理中心共用樣式 |
| `database.md` | 資料庫連線、安全範圍與部署注意事項 |
| `site.md` | 頁面資訊架構、角色與操作流程 |
| `start_windows_80.bat` | Windows 正式啟動，使用 Port 80 |

## 安裝與啟動

建議使用 Visual Studio Code 開啟專案，並確認電腦已安裝 Microsoft ODBC Driver 17 for SQL Server。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

首次匯入舊版 `.doc` 教育文件時需安裝 LibreOffice；系統會以無介面模式轉換，再交由 `python-docx` 擷取內容。

### Windows Port 80

執行 `start_windows_80.bat`，本機可開啟 `http://127.0.0.1`；同一內網裝置可使用啟動時列出的內網 IP。若 Port 80 已被其他服務占用，需先停止該服務。

### Ritwick Dey Live Server Port 5500

1. 在 VS Code 安裝 [Live Server（ritwickdey.LiveServer）](https://marketplace.visualstudio.com/items?itemName=ritwickdey.LiveServer)。
2. 執行 `start_windows_80.bat`，保持 Python API 的 Port 80 運作。
3. 在 VS Code 點擊狀態列的「Go Live」，或對 `index.html` 選擇「Open with Live Server」。
4. 開啟 `http://localhost:5500`。

專案的 `.vscode/settings.json` 已將 Live Server 固定於 Port 5500，並透過擴充功能內建的 Proxy 將 `/api` 轉送至 `http://localhost:80`。前端只使用同來源的 `/api` 路徑，MIS 登入 Cookie 不需依賴跨來源 CORS 設定。

## API 摘要

| 路徑 | 權限 | 說明 |
| --- | --- | --- |
| `GET /api/public` | 公開 | 官網文字、主題與公開彙總 |
| `GET /api/dashboard` | 員工入口 | 園務彙總與班級摘要 |
| `GET /api/knowledge` | 員工入口 | 園務知識內容 |
| `GET /api/staff/public` | 公開 | 適合官網展示的教職員基本資料 |
| `GET /api/training` | 員工入口 | 教育文件分類與目錄 |
| `GET /api/training/document?id=...` | 員工入口 | 指定教育文件的段落內容 |
| `GET /api/operations` | 員工入口 | 營運流程說明 |
| `POST /api/operations/submit` | 員工入口 | 新增待 MIS 查核的營運紀錄 |
| `POST /api/attendance/clock` | 員工入口 | 寫入上班或下班打卡並回傳本次時間 |
| `POST /api/admin/login` | 公開 | 建立 MIS 管理工作階段 |
| `GET /api/admin/catalog` | 管理員 | 取得資料表目錄 |
| `GET /api/admin/table?name=...` | 管理員 | 取得遮罩後的分頁資料 |
| `GET/POST /api/admin/settings` | 管理員 | 讀取或儲存官網設定 |
| `GET /api/admin/submissions` | 管理員 | 檢視待查核營運紀錄 |
| `GET/POST/DELETE /api/admin/staff` | 管理員 | 查閱、維護或停用員工資料 |
| `GET /api/admin/attendance` | 管理員 | 依日期或員工查閱出缺勤 |
| `POST /api/admin/training/sync` | 管理員 | 重新轉換並同步教育 Word 文件 |

## 上線注意事項

- 正式環境應透過反向代理啟用 HTTPS，並將管理 Cookie 加上 Secure 屬性。
- 園務唯讀查詢與官網設定寫入最好使用不同的最小權限資料庫帳號。
- 目前登入工作階段存放在單一 Python 程序記憶體；多主機部署時應改用集中式工作階段儲存。
- 上線前應由園方依兒少資料政策覆核欄位遮罩規則、網路來源限制與存取稽核。

## 專案現況

目前網站已形成符合幼稚園實務的分眾平台：對外官網聚焦教育品牌與招生資訊，員工端支援日常園務，MIS 端提供登入保護、受控資料查閱與官網內容管理。後端保留 SQL Server 真實資料串接，同時以白名單寫入、敏感資料遮罩及待查核佇列降低誤改正式資料的風險。

## 對話更新歷程

- 完成「福祿貝爾營運中心」前後端分離架構，前端頁面以 API 讀取資料，並實際串接既有 SQL Server。
- 既有園務資料表維持唯讀；網站寫入功能僅使用 `dbo.Frobel_*` 專用資料表，包含官網設定、員工主檔、出缺勤、營運待審及教育訓練資料。
- 建立 MIS 登入、HttpOnly Cookie、CSRF 驗證、登入頻率限制、資料表白名單與敏感欄位遮罩。
- 新增園務官網、員工工作台、營運蒐集、教育訓練、YouTube 休息站、員工與出缺勤、MIS 管理等分眾頁面。
- 從 `data/staff.csv` 匯入員工主檔，官網只公開姓名、部門、職位、特質與照片；年齡與背景資料僅供 MIS 維護。
- 員工工作台已串接員工名冊與即時打卡；第一筆必須上班打卡，後續上、下班需交替，並使用資料庫交易鎖避免連續打卡。
- `staff.html` 已整合 MIS 員工主檔、照片預覽、照片上傳及出缺勤查閱。照片僅接受 JPEG、PNG、WebP，最大 5 MB，並以不可變更的員工編號自動命名。
- 教育訓練已支援舊版 Word 文件轉換、段落擷取、分類搜尋與展開閱讀；目前已同步 23 份文件與 565 個整理後段落。
- `doc.py` 已強化 LibreOffice／Word 備援、逾時、損壞文件、長內容分段及同步鎖定處理。
- YouTube 休息站改為由 `input.py` 驗證網址，再由後端取得真實影片標題與嵌入資訊；前端不再顯示影片代碼，並提供逾時處理。
- 啟動方式統一保留 `start_windows_80.bat`；服務可監聽內網介面，啟動時會列出可供同一內網使用的 IPv4 位址。VS Code Live Server 可透過 Proxy 轉送 API。
- 專案 Python 虛擬環境已修正，並安裝 `pyodbc`、`python-docx`；VS Code 已設定使用專案直譯器與工作區模組路徑。
