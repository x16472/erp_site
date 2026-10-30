# Go 後端與 Python gRPC

`backend/cmd/erp/main.go` 是唯一服務入口，`page/tools/go-playground/main.go` 僅供瀏覽器 WASM 工具。舊 backend/app.py 的 HTTP 服務由 Go 取代；API 業務轉移至 backend/src/erp/api.py、domain.py，其他文件／影音／輸入模組一併搬到 backend/src/erp。backend/data.py 的 SQL 驅動與 DDL 已由 database/data.go 與 Database 腳本取代。

Go 提供頁面白名單、靜態檔案邊界檢查、HTTP 限流、請求大小與期限；API 的方法、路徑、標頭與本文透過 protobuf 傳給 Python。重複 Set-Cookie 逐筆保留。GET、POST、DELETE 沿用既有契約，工作階段與 CSRF 驗證仍由 Python 業務層執行。

每次 HTTP 或背景工作建立 Go request scope；Python 的資料庫 client 僅傳送查詢代碼、獨立參數與受限動態選項。Go 使用固定查詢目錄及參數綁定，管理 SQL Server 連線池、唯讀／寫入資格、交易所有權與請求取消。交易直到業務 commit 才提交，未提交交易在連線關閉或 scope 結束時回復；不自動重試寫入。

兩個 gRPC 服務綁定 IPv4 回送位址，不公開容器連接埠。每次啟動使用隨機權杖驗證，資料庫操作還需符合 Go 發出的 request scope。日期、小數、位元組與大整數採明確 JSON 型別標記，不用浮點數承載奈秒時間戳。Go 私有端點提供管理員驗證資料給可信任的 Python 程序，HTTP 回應不含帳密或 SQL 錯誤細節。

Go 停止時通知 Python，逾時則回收子程序；Python 監測父程序 stdin EOF 防止孤兒程序。Python 意外停止會讓 Go 結束，由 systemd／Compose 重新啟動。單一服務目前仍只使用一個 Python 工作程序；不支援共享記憶體工作階段的多副本部署。

## 資料庫相容性

啟動時辨識 dbo.Employees 實體表與 dbo.Company_Staff 檢視表，選擇新／舊查詢目錄。新結構透過 17 個單表檢視表保留原業務欄位名稱，實體命名與型別依 DATABASE.md。Python 不執行 DDL、不接受任意 SQL。每次更改內嵌查詢 JSON 後必須重新編譯 Go。切換資料庫結構後必須重啟服務。

`--init-db` 只用於全新資料庫；`--sync-docs` 執行 SOP 同步後退出；`--skip-doc-sync` 預設為 false，一般啟動自動同步文件；員工由 Go 執行 database/SeedEmployees.sql 一次性初始化，不再讀取 CSV，之後由員工管理維護；`--check` 不連資料庫。

## 驗證

Go 測試涵蓋 SQL 參數綁定、查詢白名單、唯讀限制、交易所有權與回復、取消傳遞、型別處理、HTTP 方法與 Cookie、靜態路徑及請求上限。Python 測試涵蓋原業務回歸與真正的本機 gRPC 契約。這些測試不取代真實 SQL Server 遷移、跨語言程序及部署驗收。

修改 protobuf 後使用 requirements-dev.txt 與固定版本 protoc-gen-go／protoc-gen-go-grpc 執行 backend/tools/generate_rpc.py；產生檔不手動修改。實作參考 [gRPC Go 官方文件](https://grpc.io/docs/languages/go/basics/) 與 [Microsoft SQL Server Go 驅動](https://github.com/microsoft/go-mssqldb)。

