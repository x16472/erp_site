# 歷程

## 2026-09-30 05:58:51 +08:00｜員工管理主從式介面重整

依員工管理參考圖重整 `page/staff.html` 的員工資料分頁，將原本左右兩張卡片改為「組織架構、員工清單、員工明細」三區式工作介面。左側新增公司與部門層級、各部門人數、展開／摺疊及顯示已停用員工控制；右上改為可捲動的資料表，提供姓名、編號與職稱搜尋、新增員工入口、在職狀態及列選取效果；右下集中照片、員工欄位、還原、停用與儲存操作。頁面名稱及側邊導覽同步由「員工出缺勤」調整為「員工管理」，原有管理員登入、部門維護與打卡紀錄功能保持不變。

`page/static/staff.js` 新增組織與搜尋篩選、員工列鍵盤操作、選取後帶入明細、目前編輯狀態及停用按鈕控制，仍沿用既有 `/api/admin/staff`、`/api/admin/departments` 與 `/api/admin/attendance` API。`page/static/style.css` 補上桌面主從式工作區、表格固定表頭、狀態標籤、明細表單及 1180px、760px、520px 響應式規則。此次未調整 SQL Server 結構、資料表、欄位、查詢或既有資料。

驗證包含 JavaScript 語法檢查、HTML 解析、Git diff 格式檢查，以及使用不連接資料庫的本機假資料預覽桌面與 390px 手機版。已確認組織架構、表格內部橫向捲動、員工選取帶入與關鍵字搜尋可正常運作。專案單元測試執行 6 項，4 項通過；既有訓練文件解析測試 `test_choice_question_is_split_into_structured_fields` 與 `test_question_without_answer_stays_reviewable_draft` 仍因解析結果為 `None` 失敗，與本次員工管理頁面變更無關。

## 2026-10-02｜資安與效能稽核改善

依 `.agents/security_performance_audit.md` 完成資安與效能調整。`POST /api/youtube/resolve` 現在會驗證員工 CSRF Token，`page/static/game.js` 也同步帶入 Token，避免合法操作遭拒。管理員與員工 Session 的 Cookie 解析、逾時清除及續期邏輯已抽成共用 Helper；動態 `IN` 查詢仍保留由 `backend/input.py` `_positive_int_list()` 強制轉為正整數的既有防線。路徑存取與前端輸出轉義原有防護維持不變。

資料庫存取新增單一 HTTP 請求範圍的連線複用：同一請求會依唯讀／寫入及交易模式複用連線，並在請求完成後統一關閉，降低 `training_catalog()` 等多查詢流程反覆建立 ODBC 連線的成本。員工 CSV 同步增加 30 秒成功檢查快取與雙重鎖定檢查，錯誤不會被快取；同期間的公開員工、部門、出勤選項與身分查詢不再重複執行檔案 `stat()` 及資料庫狀態比對。

題目內容的程式碼辨識 Regex 已提升為模組層級常數。交卷時的逐題評分更新及錯題合併、題庫草稿來源狀態與題目新增／更新均改用 `executemany()`；同一批草稿的科目／章節分類結果也會複用。`_default_questions()` 內原有整段註解死碼已移除。

驗證完成 Python 語法編譯、`page/static/game.js` JavaScript 語法檢查及 `git diff --check`。新增 3 項資安／效能回歸測試並全數通過。全套 9 項單元測試為 7 項通過、2 項失敗；失敗仍是修改前即可重現的 `test_choice_question_is_split_into_structured_fields` 與 `test_question_without_answer_stays_reviewable_draft`，兩者皆因既有題目解析結果為 `None`，不屬於本次稽核調整範圍。

## 2026-10-09｜修復請求內資料庫連線複用

修正 `backend/data.py` 的連線借用方式：同一 HTTP 請求內的查詢不再讓驅動的 `with` 提前關閉快取連線，請求結束時才統一關閉；查詢失敗時淘汰該連線，避免後續重用失效連線。請求外仍沿用驅動原有的 context manager。

新增連線重用、錯誤後重建及請求外連線行為的回歸測試。專案 `.venv` 執行 13 項單元測試與 Python 編譯均通過；未對正式資料庫執行寫入或修改資料表。

## 2026-10-24｜依目前專案實作重寫 README

重新整理 `Readme.md` 的功能總覽、系統架構、專案結構、環境設定、Windows 容器與本機執行步驟、文件及題庫同步、測試、權限與常見問題。補上 IIS／ARR 與 `C:/inetpub/wwwroot/` 部署方式，將過時的 `test/` 測試路徑修正為 `backend.test_training`；區分首頁健康檢查與資料庫健康 API，說明 `.env` 檔案讀取、image 內含帳密、尚無 volume／HTTPS、來源文件未打包及外部文件工具需求。

依目前原始碼與設定檔核對文件路徑、命令及功能，完成 Markdown 區塊與 Git diff 格式檢查；本次僅修改文件，未啟動服務或連線資料庫。

## 2026-10-24｜統一 IIS 網站部署路徑

依 Phoenix 指定，將 `dockerfile` 的 WORKDIR、backend、page、data、start.bat、.env、requirements.txt、venv 建置／檢查與啟動程序工作目錄統一為 `C:\inetpub\wwwroot`，保留原有 backend/page/data 專案結構及 IIS 至 Python 的反向代理。保留 Phoenix 已處理的 `# escape=` 與反引號續行設定。本次未調整 Compose、volume、HTTPS 或應用程式碼。

目前 Docker 引擎未找到 ERP_Site 容器，無既有啟動記錄可判定所述反覆重啟原因；使用不設定自動重啟的暫存容器驗證本次路徑調整。最終 image `erp-site:servercore-ltsc2022` 建置成功（ID：ca4574a22048）。主機 18080 埠回應 HTTP 200，首頁回應的 SHA-256 與 `wwwroot/page/index.html` 完全一致，/api/health 與 CSS 回應 HTTP 200，/.env 回應 404；W3SVC、WAS 為 Running，容器 healthy，RestartCount=0。測試後停止並移除暫存容器，保留 image。

## 2026-10-24｜Windows Server Core IIS 與 Python venv 容器建置

調整 `dockerfile` 為多階段建置：從 Docker 官方 `python:3.13-windowsservercore-ltsc2022` 取得 Python，最終基底明確使用 `mcr.microsoft.com/windows/servercore:ltsc2022`，啟用內建 IIS 並安裝 Microsoft URL Rewrite、ARR 與 Visual C++ Runtime。建置時建立 `C:\app\.venv`、安裝既有 requirements，沿用未修改的 `start.bat --check`，另檢查 PyMuPDF、Pillow 與 pytesseract 匯入。實測補上 PyMuPDF 所需的 Visual C++ DLL，避免套件安裝成功卻無法載入。

IIS 以 80 埠代理到 `127.0.0.1:8000` 的原有 `backend.app`，容器啟動程序監控 IIS 與 Python，加入 HTTP 健康檢查。Compose 指定小寫 `dockerfile`、image 名稱、80 埠及重新啟動策略。依本次範圍先將既有 `.env` 放入本機 image，未變更其內容；volume、HTTPS、網路調整及外部 OCR／Word 轉檔工具安裝留待後續處理。Dockerfile 使用預設反斜線續行，未使用 `# escape=`。

驗證：Compose 設定、PowerShell 語法、pip check、start.bat --check、文件套件匯入、產生的啟動腳本與 IIS XML 解析均通過。已修正 Windows 命令列剝除雙引號造成的啟動失敗。最終 Windows/amd64 image `erp-site:servercore-ltsc2022` 建置成功（image ID：c775e9ef896c）；暫存容器內首頁、/api/health 與 /static/style.css 經 IIS 均回應 HTTP 200，W3SVC、WAS 均為 Running，Docker 健康狀態為 healthy，健康 API 已成功連線 SQL Server。驗證後停止並移除本次測試容器，保留 image。

## 2026-10-26｜全站滿版與共用區段格式整理

以既有 `style.css` 與員工資料頁為基準，統一內部頁面的滿版寬度及內容間距，恢復共用卡片的寬、窄與滿欄配置，並補齊手機單欄與頂部資訊換行。`section` 集中設定基礎格式，官網大區段留白限定於公開首頁主內容的直接子層；合併產業區段重複規則及既有覆寫，不新增 CSS 變數。待審清單捲動樣式限定於待審工作區，官網頁尾格式也限定於公開頁面。

修正營運日報缺少格線容器結束標籤、影音知識區重複格線容器，以及首頁標題、區段及頁尾的標籤結構。保留原有營運日報編輯內容。透過本機 Chrome 靜態預覽檢查 320、390、768、980、1280、1920px 共 90 個頁面與分頁狀態，未發現整頁橫向溢出，並檢視手機版截圖；`git diff --check` 通過。未連接資料庫或變更後端功能。

## 2026-10-26｜同步資料庫、前端指引與產品需求文件

依目前 backend、page、靜態腳本、部署設定與 README，更新三份內部文件：

- `database.md`：補齊初始化的 17 張應用資料表，區分 MIS 通用查閱的 10 張白名單與 7 張專用業務資料表；更新連線複用、出勤交易、員工 CSV、照片、日報歷程、訓練快照與錯題資料。修正固定資料庫／部門數量、照片路徑及遮罩保證等不精確描述。
- `frontend_pages_guide.md`：整理目前 9 個 HTML 頁面、對應腳本與 API，補上工作面板、多平台影音、縮圖、四種主題及頂部分頁。修正術科查詢與資料表查閱路由，移除以舊行號為基礎的改善清單、失效的 file URI 與已過時的 SOP 閱讀器描述。
- `prd.md`：將一次性的品牌轉型及全域替換指令改為目前產品定位、角色、功能範圍與驗收基準；移除舊資料庫遷移結論及未重新驗證的完成勾選，明確標示工作面板仍為骨架，以及合約／帳務、可見 SOP 閱讀入口、跨裝置影音紀錄同步等目前未提供的功能。

保留既有歷程內容與使用者對 `agents/agent.md` 的修改。本次僅更新指定三份文件並附加本節，依原始碼核對資料表、路由與檔案，完成 Git diff 格式及文件一致性檢查；未啟動服務、連線或修改資料庫、執行程式測試或部署。

## 2026-10-29｜新增 OMV systemd 啟動方式

新增 `start.sh`，以 Linux `.venv/bin/python` 前景執行既有 `backend.app`，預設監聽 `0.0.0.0:8080`，並支援環境變數與後端命令列參數。啟動前檢查 Python 3.11 以上、必要套件與 `.env` 可讀性；`--check` 不連線資料庫。以 `exec` 讓 systemd 直接追蹤 Python 程序。

新增 `deploy/erp-site.service`，使用專用帳號、專案掛載與網路順序、失敗後每 10 秒重新啟動及 journal 記錄。新增 OMV 部署說明，涵蓋 Linux venv、Microsoft 驅動相依套件、MSSQL `10.10.0.4:1433` 設定、目錄權限、服務安裝與健康 API；README 加入部署入口，Git 屬性固定 shell 與 service 檔案使用 LF。

驗證：Git Bash 語法、隔離模擬環境中的缺少 venv／設定檔、套件匯入失敗、檢查模式、含空白路徑、參數轉交、退出碼與監聽環境變數覆寫均通過；確認 shell／service 為無 BOM 的 LF 檔案並完成 Git diff 格式檢查。未登入 OMV、安裝遠端服務、啟動後端或連線資料庫，未修改 `.env`；systemd 與 Linux 原生套件仍需在目標主機驗證。

## 2026-10-30｜Go 主入口、Python gRPC 與資料庫遷移準備

依 Phoenix 要求，將網站入口移至 `cmd/erp/main.go`，SQL Server 存取移至 `internal/database/data.go`。原 Python 業務搬至 `src/erp`，透過 protobuf／gRPC 保留路由、工作階段、CSRF、文件與影音功能；不再由 Python 提供 HTTP 或直接連線 SQL Server。Go 管理靜態檔案、請求限制、工作程序、SQL 查詢白名單、參數綁定、連線池、交易與取消清理。移除舊 backend/app.py、data.py 及已搬移模組，保留 backend 回歸測試。

同步 `start.bat`、`start.sh`、Windows IIS Dockerfile、Compose、systemd 與部署文件。Windows 容器以 Go 編譯階段產生執行檔，Python 改為 3.11，Go 使用內部 8000 埠。一般啟動不執行 DDL，初始化改為明確的 `--init-db`；`--sync-docs` 經 Go 管理文件同步。已編譯本機 `bin/erp-site.exe`，並在專案 `.venv` 補齊 grpcio／protobuf；未改動 `.env`。

依新 DATABASE.md 準備 17 張新表的 CreateTables、SeedData、ColumnMapping、MigrateLegacy 與 RollbackLegacy。腳本提供長度／型別檢查、未知欄位／觸發程序／外部外鍵阻擋、交易鎖、逐表筆數與雙向逐欄核對，保留 LegacyBackup 原表及 Company_* 相容檢視表。完整操作與限制記於 Database/README.md。正式資料庫仍使用既有結構，未套用遷移或初始化。

依可取得的 9 個專案對話、原 agent.md／history.md 與本輪指令重塑 agents/agent.md，合併重複需求並移除過時 Python HTTP、幼兒園品牌、逐行註解及全內嵌 JavaScript 要求；單次範圍限制仍按原任務解讀。同步 README、OMV 文件與相關內部文件。

依最後「先做到可以執行就好」收斂交付。驗證：Go build、go test ./...、go vet ./... 通過；Python 3.11 共 45 項測試通過；start.bat --check 通過。短暫於 127.0.0.1:18765 啟動 Go 與 Python gRPC，使用既有 SQL Server，只讀首頁、/api/health、/api/time、/api/employee/session，全部 HTTP 200 且 JSON 可解析；已關閉測試程序。啟動測試使用 --skip-doc-sync，沒有執行資料寫入或結構遷移。

Compose config 語法檢查通過（沙箱無法讀取使用者 Docker 設定檔而顯示警告）；尚未建置 Windows image、部署 OMV 或在還原資料庫演練遷移。git diff --check 發現原規範檔的一處尾端空白，已僅清除此空白。期間環境審查一度因服務額度拒絕提升權限，後續必要文件寫入與 Python 驗證已獲允許並完成。

## 2026-10-30｜資料庫遷移續作：完成副本演練，正式切換待續

Phoenix 要求開始處理先前備妥的資料庫遷移，隨後指示「先把目前段落做完，未完成工作留在 history.md」。本段落完成既有資料盤點、獨立備份還原、遷移與回復實測；正式資料庫未切換，不延伸執行部署或清理。

已完成：

- 依既有 .env 唯讀盤點 SQL Server 17.0.4065.4 的 Company_New。17 張 Company_* 表共 3,187 筆，未發現文字長度或 INT 範圍阻擋，明確物件授權為 0 筆；未更動或公開 .env。
- 新增 cmd/dbmigrate 與 internal/database/migration.go，提供 inspect、clone、migrate-test、validate-test、rollback-test。clone 建立 COPY_ONLY／CHECKSUM 備份，VERIFYONLY 後還原至全新副本；不使用 REPLACE。執行腳本入口只允許來源名稱加 _Migration_ 的演練資料庫，沒有正式套用入口。
- 還原副本 Company_New_Migration_20261030，完成 17 張新表及相容檢視表切換，所有對應欄位與筆數雙向核對通過。新增 ValidateMigration.sql，驗證 Id／IDENTITY、型別、非主鍵 NULL、末兩欄、外鍵與全部轉換資料。
- 實測修正序列重設 EXEC／CONVERT 語法、員工新增及 CSV 新增須明確設 IsActive=1、連線 socket 5 秒逾時錯用；改為 dial timeout 與各工作 context 期限。Python 父程序監測改用 os.read，修正正常結束時 stdin 緩衝鎖的致命錯誤。
- 新增隔離環境整合測試，實際 SQL 通過員工、部門改名、打卡、日報、文件 MERGE、科目／章節／題目編號與 OUTPUT、訓練 NULL 狀態、申論與 CSV 時間轉換。業務測試寫入均在交易內回復；序列／IDENTITY 可留下號碼間隙。
- Go HTTP → Python gRPC → Go SQL → 新表相容檢視表的首頁、健康、時間及未登入狀態均 HTTP 200。資料異動時 RollbackLegacy 拒絕回切的測試通過，暫存異動已回復；無異動時實際回切副本成功。最後唯讀盤點來源仍為原 17 張實體表，筆數與本次盤點相同。
- Go build、go test ./...、go vet ./... 通過；三項需明確指定演練副本的實際資料庫／gRPC 測試通過。同步 Database/README.md、MigrationValidation.md、Readme.md。具體筆數與驗證範圍見 Database/MigrationValidation.md。

保留狀態：

- 正式來源 Company_New 維持舊結構，未執行正式 DDL／遷移，也未停止正式服務。
- 演練副本已回切舊 Company_* 實體表，但新表仍存在並保留遷移資料。不能直接在同一副本重跑 migrate-test；後續需要建立新的演練副本。
- SQL Server 備份保留在 /var/opt/mssql/data/Company_New_Migration_20261030.bak，副本資料庫及獨立資料檔一併保留，未自動刪除。
- 本機 .deps/migration-inspection.json、migration-validation.json、migration-live-tests.log、migration-rollback.json、migration-source-final.json 保留結構、筆數及測試證據，不進版控，不包含業務列值或帳密。

未完成工作（下次續作）：

1. 正式切換：依 Phoenix 後續安排確認停站時段、所有寫入來源及最新備份，使用本次腳本先重查資料品質。演練後新增的明確物件授權阻擋條件已納入生成腳本；正式前用最新資料重新完整演練。不要沿用舊備份當作正式切換時點。
2. 完整應用驗收：在新副本以實際員工／管理員工作階段驗證登入、CSRF、員工照片、CSV 首次同步、完整練習／交卷／錯題、文件匯入、日報補件與前端 CRUD。現階段完成的是真實 SQL 查詢、代表性 gRPC API 與回復測試，不等於全部瀏覽器使用流程驗收。
3. 正式執行：停站後執行 CreateTables.sql（不可 SeedData）、MigrateLegacy.sql、ValidateMigration.sql，再重啟辨識新結構的 Go 服務並驗收；此步驟尚未執行。
4. 回復規劃：目前自動回切僅適用對應業務欄位未異動時；正式切換後若有新資料，需先規劃人工比對與回補，不可直接回切而丟棄新資料。額外 Remark／CreateTime 異動、自訂授權及外部程式依賴須納入正式操作盤點。
5. 部署驗證：Windows Docker image 建置／啟動與 OMV systemd 實機驗證仍未執行。保留的演練資料庫、備份及 LegacyBackup 清理時機另行決定，不自行清除。

## 2026-10-30｜待辦續作完成與新主要資料庫 Company

目前有效方向：Phoenix 先要求施作未完成工作，之後改為「在新建空資料庫依新規範建立主要資料庫，確認細節後再搬移」。主要資料庫已設為 Company，17 張實體表全部為 0 筆；不匯入舊資料。下列狀態取代前一節的待辦清單，原節保留作為歷程。

已完成：

1. 最新資料演練：建立 Company_New_Migration_Final_20261030 及 Company_New_Migration_Cutover_20261030 副本，使用最新備份、CHECKSUM／VERIFYONLY 與獨立還原檔。完整業務 API 驗證通過員工／管理員登入與 CSRF、照片、部門改名、打卡、日報補件、題庫 CRUD、練習／模考／續作／交卷／錯題、申論審核及 DOCX 匯入。真實 Edge 瀏覽器完成員工與題庫 CRUD、內部頁面及 390px 手機版，已檢視桌面與手機截圖。
2. 回復防護：MigrateLegacy 將每張新表完整 JSON 的 SHA-256 基準存為擴充屬性；RollbackLegacy 同時核對對應欄位與完整基準，Remark、CreateTime 異動也會拒絕回切。四項實際 SQL／gRPC／回復整合測試通過。
3. 原授權正式切換：在 Phoenix 改方向前，已完成 Company_New 的單人維護、COPY_ONLY＋CHECKSUM 備份／VERIFYONLY、單一外層交易建表／遷移／核對與恢復 MULTI_USER。17 張表共 3,187 筆核對通過，LegacyBackup 舊表保留。正式備份為 /var/opt/mssql/data/Company_New_GoMigration_1793359132890659000.bak；報告 .deps/migration-production-cutover.json、migration-production-validation.json。後續依新指示保留此狀態，不再處理舊資料。
4. 新主庫：查到 Phoenix 剛建立的 Company，先確認 ONLINE、可寫且沒有使用者物件。新增 dbmigrate schema-create／schema-validate，在單一交易只執行 CreateTables 與 ValidateSchema，不執行 SeedData 或任何舊資料搬移。17 張實體表、17 張相容檢視表及 4 個序列建立成功；主鍵／IDENTITY、非主鍵 NULL、型別長度、小數精度、文字／數值預設值、末兩欄、唯一索引及外鍵均通過。
5. 主要連線：只將 .env 的 DatabaseName 改為 Company，其餘欄位保留；切換前副本在 .deps/env-before-company-primary.env，不進版控。正常啟動與健康、時間、公開資料、員工／部門清單、登入狀態 API 全部 HTTP 200；再核對新庫仍全為 0 筆。
6. 禁止隱含舊資料匯入：一般啟動預設略過文件同步，CSV 需明確 ERP_ALLOW_STAFF_CSV_IMPORT=1 才啟用；連 force=True 也不能繞過。明確同步文件時若缺少 data/exam，回報錯誤而不把既有文件全部停用。新增對應回歸測試，Python 共 47 項通過；Go test、vet、build 通過。
7. Windows 容器：建置通過，image ID cb55024bd3c6230e84ef303b7afb11c400808f4dc9423c0b20e00a8ccf08cb87。使用官方 Python 3.11.9 安裝程式，依官方公開簽章中繼資料的 SHA-256 校驗，重用 Server Core 基底避免重複大型下載。最終 runtime .env 排除僅供部署的 DokerPublishName／DokerPublishPassword，保留網站必要設定。
8. 容器實測：Windows NAT 不接受僅綁回送的 port publish，改成不發布主機埠，在容器內檢查 IIS→Go→Python→Company。首頁、CSS、健康、時間、公開員工與登入狀態 API 全部 HTTP 200，/.env 為 404，W3SVC／WAS Running，Python 3.11.9，healthy、RestartCount=0。驗收後停止並移除本次暫存容器，image 保留，沒有留下持續執行的網站容器。證據在 .deps/windows-company-validation.json、docker-build-company.log。

最終新庫驗證：.deps/company-final-validation.json，17 張表全為 0 筆。公開結構與驗證說明在 Database/CompanySchemaValidation.md，Readme.md、Database/README.md、Go／OMV 文件已同步。

未完成／暫緩工作：

- OMV 實機部署：Phoenix 提供 docker_user@10.10.0.4，並將部署欄位放在 .env。首次主機 ED25519 指紋未通過 Phoenix 核對，Phoenix 明確回覆「指紋不同，先不要連線」；依指示停止，尚未登入、取得 sudo、傳檔、安裝或啟動遠端服務。帳密不寫入本文、不輸出至記錄。需要先從可信任管道釐清主機指紋，才可另行續作。
- 資料搬移至 Company：依 Phoenix 最新指示延後，不能把 Company_New 切換等同於搬移至 Company。待確認 Company 結構後，另行規劃來源對照、資料品質、先後順序及驗證；不要直接在 Company 重跑對原庫切換的 MigrateLegacy.sql。
- 初始主檔與身分：Company 未放任何種子或假資料，員工與綁定員工的管理員目前沒有可用登入身分。必要類別、部門、員工、科目等建立／導入方案待後續安排，不能自動從舊 CSV 填入。
- 保留資料清理：Company_New、LegacyBackup、演練副本及備份均保留，清理時機另行決定；未自行刪除。

審查紀錄：自動核准審查曾拒絕未驗證主機指紋的 SSH 信任，以及會綁定所有主機介面的 Docker 驗收埠。SSH 依 Phoenix 指示暫停；Docker 已改為不發布埠的容器內測試並完成，沒有繞過拒絕。

## 2026-10-30｜整合專案資料夾與清除退役程式

依 Phoenix 指示，以 backend、page、data 大類整合，保留功能及有職責的同級資料夾。

已完成：

1. 根目錄 cmd、internal、src、proto 集中至 backend；Python 測試由 backend/test_*.py 移至 backend/tests。Go module 留在根目錄，入口為 backend/cmd/erp，Python 模組為 backend.src.erp。
2. 更新 Go imports、Python 匯入與專案根目錄定位、protobuf go_package 及產生器、SQL 產生器、驗收 fixture、start.bat／start.sh、Dockerfile、README 及操作文件。重新產生 Go／Python gRPC 契約，未保留舊路徑轉接副本。
3. 移除無執行期引用的 templates/cookiecutter.json、已轉成 SeedEmployees.sql 的 data/staff.csv，以及不再打包或使用的 data/Company_Schema.sql。舊結構參考及遷移／回復 SQL 仍保留於 Database；資料庫檔、備份、文件原檔未刪除。
4. 移除 Python 未使用的 PAGES 頁面路由表及 BACKEND_ROOT 常數，靜態資源持續由 Go 統一提供。瀏覽器 Go Playground 為獨立 WASM 建置目標，保留其來源及獨立依賴。
5. 清理前來源備份位於忽略版控的 .deps/structure-backup-20261030；刪除候選逐檔雜湊比對一致。初始合併搬移／永久刪除遭自動審查拒絕；補齊備份與引用證據後，分別完成可回復搬移及明確檔案刪除。
6. Go test、vet 及兩個入口 build 通過；Python 46 項測試及 Go --check 通過。本機服務以新結構啟動，首頁 200、Company 健康正常、22 位員工可讀，證據 .deps/structure-startup-validation.json。

7. Windows 容器以新 backend/src 路徑啟動，IIS Running、首頁 200、Company 健康正常及 22 位員工可讀，舊 src 路徑與 Company_Schema.sql 均不存在。驗收不發布主機埠，結束後已移除暫存容器。證據 .deps/docker-build-structure.log、.deps/windows-structure-validation.json。
8. 清除專案來源目錄中可重新產生的 Python bytecode 及空 __pycache__ 目錄；保留 .venv、.deps 的依賴、備份及驗證證據。

未完成／驗證限制：

- 舊 Company_New_Migration_Final_20261030 副本已不在目前伺服器，完整 API CRUD 驗收因目標不存在而無法重跑；本次沒有為測試寫入主庫或建立新資料庫。前輪通過結果不可視為本輪完整驗收。
- 本輪 Windows 映像 34e035f2d9c3 重建及啟動驗證完成；沒有待處理的結構搬移。
- 舊資料搬移仍延後；OMV 指紋不符，繼續依指示暫停 SSH。

## 2026-10-30｜員工改由新資料表維護，移除 CSV 相依

本節取代先前「保持全空、關閉 CSV／文件同步」的有效方向。Phoenix 先要求恢復漏掉的自動匯入，再明確修正為「不要依存 CSV，把 CSV 改成現有新資料表結構」。因此沿用既有內容作一次性初始資料，後續只由資料庫與員工管理維護，舊交易資料搬移仍延後。

已完成：

1. 將原清單轉成 Database/SeedEmployees.sql，使用 Employees／Departments 新欄位；Go 於正常啟動交易內初始化，ImportStates 的 EmployeeSeed.v1 標記防止重啟覆寫、重新啟用或補回員工。同編號既有資料不覆寫。
2. 移除 Python CSV 檔案讀取、定時同步、查詢觸發同步與舊查詢目錄；移除 CSV 環境開關及 Docker 複製。驗收工具也不再讀取 CSV，改攜帶 Database 腳本。
3. Company 已初始化 Employees 22 筆、Departments 6 筆、ImportStates 1 筆，其餘 14 張表為 0 筆；連續兩次啟動成功，schema-validate 通過。證據：.deps/employee-seed-startup-validation.json、.deps/company-employee-seed-validation.json。
4. 恢復文件預設啟動同步，可 --skip-doc-sync 略過；缺少 data/exam 的防護保留，不會清空既有文件。
5. Go test／vet／build 通過；Python 46 項測試通過。無 CSV 的獨立副本完成完整 HTTP 驗收，包括員工新增／更新／照片／停用、部門、打卡、日報、題庫、訓練及 DOCX 匯入。
6. Windows 最終映像 0181b6370f2d 建置成功；不發布主機埠的暫存容器通過 IIS→Go→Python→Company，容器內沒有 staff.csv，仍可讀取 22 位員工與全部照片。驗收容器已停止移除。證據：.deps/docker-build-employee-seed-final.log、.deps/windows-employee-seed-validation.json。
7. 原員工照片保留並經員工管理 API 核對 22 位均有照片，初始 SQL 同時包含對應 PhotoFile。最終結構與筆數核對：.deps/company-employee-seed-final.json。
8. Readme、Go／OMV 操作文件、資料庫說明及 agent 指引同步更新。原 data/staff.csv 僅留作歷史內容，不再是程式或容器相依。

未完成／暫緩：

- 本輪程式、Company 初始化與 Windows 容器驗證均已完成。
- 舊來源至 Company 的交易資料搬移，仍依指示等待確認後安排。
- OMV 指紋不同，依 Phoenix 指示暫停 SSH，不進行部署。

## 2026-10-31｜依四大類歸位並移除資料庫搬移與驗證工具

依 Phoenix 修正，專案內容以 backend、page、data、database 分工。history.md 保留 Phoenix 已整理的全部內容，新紀錄僅附加於末端，依日期往下續寫，不再插入頂端或重排既有段落。

已完成：

1. database/ 集中 SQL Server 執行期 Go 程式、SQL 查詢目錄、CreateTables.sql、SeedData.sql、SeedEmployees.sql；原 backend/internal/database 的執行期部分已搬入。共用 Go gRPC 契約移到 backend/rpc，修正 Go internal 套件存取邊界並重新產生契約。
2. 根目錄 deploy/ 移至 backend/deploy/；docs/ 按內容移至 backend/docs/ 及 page/docs/；gRPC 產生器移至 backend/tools/，瀏覽器 WASM 建置工具移至 page/tools/。根目錄不再保留 deploy、docs、tools。
3. 刪除 dbmigrate 入口與編譯檔、migration.go、cutover.go、blank.go、對應的搬移／空庫驗證測試，以及 ColumnMapping.json、CompanySchemaValidation.md、舊資料庫盤點文件、SQL 搬移產生器與一次性 API／瀏覽器驗收工具。既有業務單元測試、建表、初始資料與執行期功能保留。先前已移除的搬移 SQL 不重建。
4. 更新啟動引用、Dockerfile、README、Go／Python／資料庫規範、部署說明、工具根路徑與文件連結。Docker 排除 database 下的 db、bak 檔，不將現存資料庫檔打包進映像。
5. 核對 Phoenix 最新更新的 DATABASE.md，.env 的位址、連接埠、資料庫名稱、帳號及密碼均一致，未改寫 .env。DATABASE.md 只同步 database 資料夾名稱，連線值完整保留；紀錄不含帳密。本輪未操作實際資料庫、遠端主機或備份。
6. Go test、vet、build 通過；Python 46 項單元測試、搬移後 gRPC 產生器、WASM 腳本語法及現行 Markdown 連結檢查通過。Windows 映像 1cb1d96422ff 建置成功，容器確認 database SQL 與 backend Python 路徑正確、無 db／bak 資料檔，Go --check 通過；本輪未啟動網站或連接資料庫。容器執行完已自動移除，建置紀錄 .deps/docker-build-categories-20261031.log。

清理審查：最初合併搬移與刪除遭自動核准審查拒絕；之後先於忽略版控的 .deps/cleanup-20261031 保留可回復備份，核對引用及檔案雜湊，再分開完成搬移與指定檔案刪除。沒有繞過審查或刪除實際資料庫／備份。

未完成／暫緩：本輪分類與清理已完成。未重新執行真實 SQL 或完整 CRUD；舊搬移／副本驗收相關待辦已依新指示停止續作，不再保留其工具。OMV 連線仍依既有指示暫停。
