# SQL Server 資料存取與治理

更新日期：2026-10-26。本文件依目前原始碼說明資料結構與行為，未實查部署中的資料庫。安裝與部署另見 [Readme.md](../Readme.md)。

## 連線與初始化

- 使用 `mssql-python` 存取 SQL Server，版本由 `requirements.txt` 固定。
- `backend/data.py` 僅讀取根目錄 `.env` 的 `DatabaseIP`、`DatabasePort`、`DatabaseName`、`DatabaseUser`、`DatabasePassword`；同名作業系統環境變數不能取代此檔案。
- 實際資料庫名稱依 `.env` 設定。`data/Company_Schema.sql` 是以 `Company_New` 為目標的結構參考，不代表目前部署狀態或最新完整結構。
- 啟動執行 `ensure_application_schema()`，建立缺少的資料表、補齊欄位與索引，並處理預設分類、部門及員工 CSV；帳號須有相應的結構更新與資料讀寫權限。
- 查詢採唯讀連線意圖，維護流程使用可寫入連線，兩者仍使用同一組帳密；唯讀意圖不等同權限隔離。
- 連線逾時為 5 秒，目前使用 `Encrypt=no;TrustServerCertificate=yes`。

單一 HTTP 請求以 `connection_scope()` 依讀寫與交易模式複用連線，請求結束後統一關閉；查詢失敗時淘汰失效連線。請求外仍由各自的 context manager 管理。

## 應用資料表

初始化程式目前包含 17 張 `dbo.Company_*` 資料表。`APPLICATION_TABLES` 的 10 張開放 MIS 通用查閱；`WORKFLOW_TABLES` 的 7 張供專用業務 API 使用，不會自動出現在通用目錄。

| 資料表 | 用途與主要關聯 | MIS 通用查閱 |
| --- | --- | --- |
| `Company_WebSettings` | 官網主題、主標題、副標題、公告與更新者 | 是 |
| `Company_Department` | 部門名稱、啟用狀態與更新資訊 | 是 |
| `Company_Staff` | 員工編號主鍵、個人資料、部門名稱、照片檔名與在職狀態 | 是 |
| `Company_Attendance` | 打卡動作、時間、台灣工作日、來源 IP；關聯員工 | 是 |
| `Company_OperationCategory` | 營運分類與顯示順序 | 是 |
| `Company_OperationSubmission` | 建立員工、分類、日期、據點、數量與審核狀態 | 是 |
| `Company_TrainingDocument` | 來源文件、變更資訊、啟用及解析狀態 | 是 |
| `Company_TrainingSection` | 文件段落與排序；關聯文件 | 是 |
| `Company_TrainingQuestion` | 題型、科目、章節、答案、解析、來源、發布狀態與匯入鎖定 | 是 |
| `Company_ImportState` | 員工 CSV 修改時間、大小、匯入筆數與時間 | 是 |
| `Company_OperationActivity` | 日報送出、補件要求、回覆、核准與退回歷程 | 否 |
| `Company_TrainingAnswer` | 術科申論答案、審核狀態、審核者與回饋 | 否 |
| `Company_TrainingSubject` | 學科／術科科目及模考題數、時間、及格分數 | 否 |
| `Company_TrainingChapter` | 科目下的章節代碼、名稱與排序 | 否 |
| `Company_TrainingSession` | 員工題組、模式、設定、時間、狀態與成績 | 否 |
| `Company_TrainingSessionQuestion` | 題組順序、題目快照、作答、標記與評分 | 否 |
| `Company_TrainingWrongQuestion` | 員工與題目組合主鍵、錯題加入及移出時間 | 否 |

資料表設有主鍵、外鍵、部分唯一限制與數值檢查。員工的 `department` 目前儲存部門名稱，沒有以部門 ID 外鍵連接；由業務程式驗證啟用部門，更名時同步員工資料。題目結構、答案、題組設定與作答快照使用 JSON 欄位。

## 資料範圍與權限

公開 API 提供網站設定、彙總統計、公開員工介紹、部門篩選與時間；員工及部門筆數依資料庫計算，不固定為特定數量。員工業務 API 要求有效工作階段，重新查核在職身分及當日打卡狀態，個人日報、題組與錯題依員工身分限制存取。管理功能另需綁定同一員工的 MIS 工作階段，資料異動依路由驗證 CSRF Token。

MIS 通用查閱驗證白名單與 SQL Server 中繼資料，每頁限制 5 至 50 筆，依欄位名稱分類與遮罩。此規則不等同所有專用 API 的輸出：員工維護等 API 依用途提供欄位。現有遮罩主要比對中文關鍵字，不能視為可自動辨識所有英文敏感欄位。

前端不能提交任意 SQL。資料值使用參數化查詢，動態資料表與欄位識別字經白名單或中繼資料驗證。

## 出勤與員工維護

```text
前端表單 → app.py 驗證身分與 CSRF → input.py 驗證輸入
         → data.py 執行資料存取 → app.py 回傳業務結果
```

- 員工編號轉為大寫，最多 20 字，允許英數字、底線與連字號；既有編號不提供更名操作。
- 姓名、性別、年齡、部門及職位為維護必填欄位。性別限男、女、其他；年齡為 16 至 100；部門最多 5 字且須為啟用部門。
- 公開名冊依員工編號排序並提供部門篩選；管理名冊依在職狀態及員工編號排序。
- 員工停用保留業務紀錄；仍有在職員工的部門不可停用。
- 打卡接受 `CLOCK_IN`、`CLOCK_OUT`。每個台灣工作日先上班、之後交替；交易以 `UPDLOCK`、`HOLDLOCK` 鎖定員工，避免同時請求重複打卡。
- `backend/time_sync.py` 以 SQL Server 時間產生 UTC、台灣工作日及顯示時間。登入頁與工作台透過 `/api/time` 每 60 秒更新時間偏移。
- 不打卡進入仍驗證員工並讀取當日最後打卡；離開系統不異動出勤，打卡下班會執行下班卡。完整日期／員工出勤紀錄由管理 API 提供。

## 日報與審核

日報包含日期、據點代碼、既定分類、0 至 9999 的數量與最多 200 字備註。據點代碼驗證英數、底線與連字號格式；備註以關鍵字及格式攔截部分個資，不是任意文字的完整個資辨識。

日報寫入 `Company_OperationSubmission`，以 `submitted_by` 記錄建立員工，操作歷程另存 `Company_OperationActivity`。管理員可要求補件、審核通過或退回；員工可對允許回覆的個人日報補充內容，更新為「員工已回覆」。審核及回覆使用交易；未記錄建立員工的舊資料仍可由管理端查閱。

## CSV 與照片

`data/staff.csv` 為批次同步來源。成功檢查快取 30 秒，管理流程可強制檢查；修改時間與大小未變時不重複匯入。變更以參數化 `MERGE` 合併，狀態記錄於 `Company_ImportState`。

CSV 異動可能覆寫對應員工的文字資料；未列出的員工不會自動停用。既有照片優先保留，未設定時才依員工編號尋找照片。

照片由管理表單上傳，接受 JPEG、PNG、WebP，單張上限 5 MiB；由 `app.py` 保存至 `page/static/staff/`，檔名由員工編號產生。資料庫只保存照片檔名。

## 文件、題庫與作答

`backend/doc.py` 處理 `data/exam/` 的 DOCX、DOC、XLSX、XLS、PDF。舊 DOC 優先使用 LibreOffice，Windows Word COM 為備援；轉檔快取在 `.converted/`。掃描 PDF 另需 Tesseract 與語言資料。

啟動預設同步 SOP，可用 `--skip-doc-sync` 略過。MIS 來源同步另處理題庫草稿，回報解析警告與失敗來源。來源檔案與快取留在檔案系統，文件資訊、段落與題目存於資料庫。

題型包含單選、多選、閱讀、填空、配對與申論，依學科／術科、科目與章節分類。來源指紋協助辨識重複匯入；管理員維護草稿、發布、停用與匯入鎖定。員工題組保存題目快照；練習可即時取得答案與解析，模考交卷前不回傳正解與解析。申論由管理員審核，錯題本可移出題目。

文件查詢 API 仍保留，但 `game.html` 沒有 SOP 閱讀入口，`workflow.html` 也僅有環境分頁佔位內容。

## 儲存與部署邊界

- 員工與管理員工作階段存於 Python 程序記憶體，重新啟動後失效。
- 各平台最近播放網址與 YouTube 最近 8 筆縮圖查詢存於瀏覽器 `localStorage`，不寫入 SQL Server。
- 影音標題由 `backend/media.py` 或 YouTube oEmbed 流程取得，沒有影音業務資料表。
- Compose 尚無 volume；重建容器可能遺失容器內照片與文件快取，SQL Server 資料另由資料庫保存。
- 網站目前使用 HTTP，Cookie 設有 HttpOnly、SameSite=Strict，尚無 Secure。HTTPS、資料庫加密、集中工作階段與檔案持久化均不能視為已完成。
