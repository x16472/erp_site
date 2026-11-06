# Go 後端與 Python gRPC

`backend/cmd/erp/main.go` 是唯一服務入口，`page/tools/go-playground/playground_js_wasm.go` 僅供瀏覽器 WASM 工具。舊 backend/app.py 的 HTTP 服務由 Go 取代；API 業務轉移至 backend/src/erp/api.py、domain.py，其他文件／影音／輸入模組一併搬到 backend/src/erp。backend/data.py 的 SQL 驅動與 DDL 已由 database/data.go 與 database 腳本取代。

Go 提供頁面白名單、靜態檔案邊界檢查、HTTP 限流、請求大小與期限；API 的方法、路徑、標頭與本文透過 protobuf 傳給 Python。重複 Set-Cookie 逐筆保留，並強制加入 Secure，瀏覽器登入需使用 HTTPS。GET、POST、DELETE 沿用既有契約，工作階段與 CSRF 驗證仍由 Python 業務層執行。

HTTP 預設只監聽 `127.0.0.1`。直接提供 HTTPS 時設定 `--host`、`--port`、`--tls-cert` 與 `--tls-key`；憑證與私鑰也可透過 `ERP_TLS_CERT`、`ERP_TLS_KEY` 指定，最低支援 TLS 1.2。由 Cloudflare Tunnel 等反向代理提供 HTTPS 時，使用 `--tls-proxy` 或 `ERP_TLS_PROXY=1` 明確允許非回送位址的 HTTP 監聽，並以容器網路或防火牆隔離後端埠；程式不依據用戶端傳入的轉送標頭判定信任。HTTP 監聽衝突與 TLS 憑證錯誤會在資料庫工作前回報。

一般 API 的 RPC 期限為 45 秒，文件同步為 10 分鐘；RPC 完成後，回應傳送期限重新設為 15 秒，避免慢速用戶端長期占住並行名額。靜態檔案也使用 15 秒傳送期限。

每次 HTTP 或背景工作建立 Go request scope；Python 的資料庫 client 僅傳送查詢代碼、獨立參數與受限動態選項。Go 使用固定查詢目錄及參數綁定，管理 SQL Server 連線池、唯讀／寫入資格、交易所有權與請求取消。交易直到業務 commit 才提交，未提交交易在連線關閉或 scope 結束時回復；不自動重試寫入。

兩個 gRPC 服務綁定 IPv4 回送位址，不公開容器連接埠。每次啟動使用隨機權杖驗證，資料庫操作還需符合 Go 發出的 request scope。日期、小數、位元組與大整數採明確 JSON 型別標記，不用浮點數承載奈秒時間戳。Go 私有端點提供管理員驗證資料給可信任的 Python 程序，HTTP 回應不含帳密或 SQL 錯誤細節。

Go 停止時先停止背景 SOP 同步與長時間同步請求，取消其資料庫範圍並回復未提交交易；已提交的變更仍會保留。一般 API 等待完成，HTTP 清理期限為 90 秒；之後通知 Python 停止，逾時則回收子程序。systemd 與 Compose 的停止期限為 110 秒，涵蓋 HTTP 與子程序清理。Python 監測父程序 stdin EOF 防止孤兒程序。Python 意外停止會讓 Go 結束，由 systemd／Compose 重新啟動。單一服務目前仍只使用一個 Python 工作程序；不支援共享記憶體工作階段的多副本部署。

## 資料庫相容性

啟動時辨識 dbo.Employees 實體表與 dbo.Company_Staff 檢視表，選擇新／舊查詢目錄。新結構透過 17 個單表檢視表保留原業務欄位名稱，實體命名與型別依 DATABASE.md。Python 不執行 DDL、不接受任意 SQL。每次更改內嵌查詢 JSON 後必須重新編譯 Go。切換資料庫結構後必須重啟服務。

`--init-db` 只用於全新資料庫，順序為建立結構、辨識結構、匯入初始員工，再執行 Python 業務初始化，確保依員工計算的部門狀態正確。`--sync-docs` 執行 SOP 同步後退出；`--skip-doc-sync` 預設為 false，一般啟動會先提供 HTTP 服務，再於背景同步文件。背景同步失敗不關閉網站，記錄階段、gRPC 狀態碼、錯誤類別與耗時，不記錄原始錯誤訊息。員工由 Go 執行 database/SeedEmployees.sql 一次性初始化，不再讀取 CSV，之後由員工管理維護；同一初始化交易以 SeedOperationCategories.sql 補齊日報必要類別，不覆寫既有值。`--check` 不連資料庫，環境檢查期限為 30 秒。

`--check`、`--init-db`、`--sync-docs` 互斥；`--sync-docs` 也不可搭配生效中的略過同步設定。若環境已有 `ERP_SKIP_DOC_SYNC=1`，可使用 `--sync-docs --skip-doc-sync=false` 明確覆寫。維護命令不依賴 HTTP 監聽及 TLS 設定。

## 驗證

Go 測試涵蓋 SQL 參數綁定、查詢白名單、唯讀限制、交易所有權與回復、取消傳遞、型別處理、HTTP 方法與 Cookie、靜態路徑及請求上限。Python 測試涵蓋原業務回歸與真正的本機 gRPC 契約。這些測試不取代真實 SQL Server 遷移、跨語言程序及部署驗收。

修改 protobuf 後使用 requirements-dev.txt 與固定版本 protoc-gen-go／protoc-gen-go-grpc 執行 backend/tools/generate_rpc.py；產生檔不手動修改。實作參考 [gRPC Go 官方文件](https://grpc.io/docs/languages/go/basics/) 與 [Microsoft SQL Server Go 驅動](https://github.com/microsoft/go-mssqldb)。


## 模擬考與營運日報

模擬考建立時透過 Go 資料庫層取得 SQL Server UTC 快照，明確寫入開始與到期時間；讀取題組及儲存答案也以 SQL Server UTC 判斷期限。API 回傳帶時區的 expires_at 與 server_time，前端以單調時鐘倒數並每 60 秒重新校時，不以瀏覽器本機日期直接判斷到期。已交卷的題組仍依原規則提供檢討，未交卷不揭露答案。

GET /api/operations/categories 提供員工可填報的資料庫類別，與既有員工驗證一致。日報與個人紀錄分開載入，提交成功後即使紀錄刷新失敗，也保留成功訊息；使用者可重新整理，避免重複送出。
