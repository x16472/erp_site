# 歷程

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

## 2026-10-09｜修復請求內資料庫連線複用

修正 `backend/data.py` 的連線借用方式：同一 HTTP 請求內的查詢不再讓驅動的 `with` 提前關閉快取連線，請求結束時才統一關閉；查詢失敗時淘汰該連線，避免後續重用失效連線。請求外仍沿用驅動原有的 context manager。

新增連線重用、錯誤後重建及請求外連線行為的回歸測試。專案 `.venv` 執行 13 項單元測試與 Python 編譯均通過；未對正式資料庫執行寫入或修改資料表。

## 2026-10-02｜資安與效能稽核改善

依 `.agents/security_performance_audit.md` 完成資安與效能調整。`POST /api/youtube/resolve` 現在會驗證員工 CSRF Token，`page/static/game.js` 也同步帶入 Token，避免合法操作遭拒。管理員與員工 Session 的 Cookie 解析、逾時清除及續期邏輯已抽成共用 Helper；動態 `IN` 查詢仍保留由 `backend/input.py` `_positive_int_list()` 強制轉為正整數的既有防線。路徑存取與前端輸出轉義原有防護維持不變。

資料庫存取新增單一 HTTP 請求範圍的連線複用：同一請求會依唯讀／寫入及交易模式複用連線，並在請求完成後統一關閉，降低 `training_catalog()` 等多查詢流程反覆建立 ODBC 連線的成本。員工 CSV 同步增加 30 秒成功檢查快取與雙重鎖定檢查，錯誤不會被快取；同期間的公開員工、部門、出勤選項與身分查詢不再重複執行檔案 `stat()` 及資料庫狀態比對。

題目內容的程式碼辨識 Regex 已提升為模組層級常數。交卷時的逐題評分更新及錯題合併、題庫草稿來源狀態與題目新增／更新均改用 `executemany()`；同一批草稿的科目／章節分類結果也會複用。`_default_questions()` 內原有整段註解死碼已移除。

驗證完成 Python 語法編譯、`page/static/game.js` JavaScript 語法檢查及 `git diff --check`。新增 3 項資安／效能回歸測試並全數通過。全套 9 項單元測試為 7 項通過、2 項失敗；失敗仍是修改前即可重現的 `test_choice_question_is_split_into_structured_fields` 與 `test_question_without_answer_stays_reviewable_draft`，兩者皆因既有題目解析結果為 `None`，不屬於本次稽核調整範圍。

## 2026-09-30 05:58:51 +08:00｜員工管理主從式介面重整

依員工管理參考圖重整 `page/staff.html` 的員工資料分頁，將原本左右兩張卡片改為「組織架構、員工清單、員工明細」三區式工作介面。左側新增公司與部門層級、各部門人數、展開／摺疊及顯示已停用員工控制；右上改為可捲動的資料表，提供姓名、編號與職稱搜尋、新增員工入口、在職狀態及列選取效果；右下集中照片、員工欄位、還原、停用與儲存操作。頁面名稱及側邊導覽同步由「員工出缺勤」調整為「員工管理」，原有管理員登入、部門維護與打卡紀錄功能保持不變。

`page/static/staff.js` 新增組織與搜尋篩選、員工列鍵盤操作、選取後帶入明細、目前編輯狀態及停用按鈕控制，仍沿用既有 `/api/admin/staff`、`/api/admin/departments` 與 `/api/admin/attendance` API。`page/static/style.css` 補上桌面主從式工作區、表格固定表頭、狀態標籤、明細表單及 1180px、760px、520px 響應式規則。此次未調整 SQL Server 結構、資料表、欄位、查詢或既有資料。

驗證包含 JavaScript 語法檢查、HTML 解析、Git diff 格式檢查，以及使用不連接資料庫的本機假資料預覽桌面與 390px 手機版。已確認組織架構、表格內部橫向捲動、員工選取帶入與關鍵字搜尋可正常運作。專案單元測試執行 6 項，4 項通過；既有訓練文件解析測試 `test_choice_question_is_split_into_structured_fields` 與 `test_question_without_answer_stays_reviewable_draft` 仍因解析結果為 `None` 失敗，與本次員工管理頁面變更無關。
