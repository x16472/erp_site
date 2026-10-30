# 專案協作規範

本文件彙整 Phoenix 的長期偏好與本專案有效決策；實作與驗證紀錄寫入 history.md。最新明確指令優先，同一需求合併，衝突時採較新決策。

## 溝通與工作範圍

- 稱呼 Phoenix，以台灣繁體中文溝通及註解；直接說明結論、原因與驗證結果，避免粗體、浮誇開場與固定收尾。
- 嚴守當次授權範圍。範圍外動作即使具備 Bypass permissions 也先交由人工判斷；不確定詞彙時直接指出。
- 未指定開發工具時使用 Visual Studio Code；保留既有未提交修改，不以清理為由覆寫其他工作。
- 程式碼縮排正確、命名明確；註解說明核心邏輯與陷阱的原因，長篇說明放 Markdown。不再要求逐行註解。
- 依實作同步 Readme.md 與相關操作文件，將變更、測試及未驗證事項記入 history.md；不把模擬測試寫成正式環境驗收。

## 技術與資料邊界

- 後端由 Go 主導：入口 backend/cmd/erp/main.go，可重用邏輯置 backend/internal/；database/data.go 統一管理 SQL Server。page/tools/go-playground/main.go 僅為瀏覽器工具。
- Python 3.11 業務以 gRPC 連接 Go，模組放 backend/src/erp，不自行開 HTTP 或直接連 SQL Server。遵循 GO.md、PYTHON.md、DATABASE.md。
- Go Modules 與 requirements.txt 管理相依套件。新原始／處理資料使用 data/raw、data/processed 並排除版控；既有 exam 文件入口維持相容；員工資料以新規範資料表維護，不保留執行期 CSV 相依。
- `.env` 沿用實際設定，不公開或另建 `.env.example`；只有明確要求切換主要資料庫時才修改 DatabaseName，其餘欄位保留；MIS 使用 BackendWebAdminUser／BackendWebAdminPassword，由後端驗證。
- 網站只寫入核准的應用資料表，既有外部資料不得任意編輯。前端經 API 取得資料，不填造營運紀錄或將憑證置於瀏覽器。
- 資料庫相關執行期 Go 程式、查詢目錄、建表及初始資料集中 database/。資料庫搬移、回復、盤點、驗證工具與其演練測試已依指示移除，不自行重建或重新加入。一般啟動不得隱含搬移資料。

## 產品與介面

- 現行品牌為「銀盾共同體營運中心」，整合官網、員工工作台與 MIS；舊幼兒園品牌及園務定位已被取代。
- 前端採原生 HTML、共用 CSS 與 JavaScript ES Modules，經同來源 HTTP 使用；不再要求 JavaScript 全部內嵌或直接開本機 HTML。
- 延續 workflow、staff 的結構、共用樣式及導覽，不無故另建整套版型。支援手動深淺色、手機與平板布局（679／680~980／980px 為既有基準），官網四主題沿用現有變數。
- MIS 題庫採組織、清單、明細三區，共用 CRUD 操作置於上方。員工維護集中 staff，不在 MIS 重複建立；MIS 待審以員工與事件聯動呈現。
- Python 3.11 Playground 為上方程式碼、下方終端機；Go Playground 沿用互動方式。瀏覽器 pip、套件記錄及快取不修改後端；python_canvas 與 teris_canvas 樣式、事件須隔離。

## 業務行為

- 員工編號建立後不可更改；姓名、性別、年齡、部門依既有規則必填，性別選單、年齡數值輸入，錯誤焦點明確。照片支援 JPEG／PNG／WebP，最大 5 MB，以員工編號命名。
- 官網只顯示必要員工資訊並提供部門篩選。後台維護員工、部門與打卡紀錄，API 權限由伺服器強制執行。
- 員工入口分 CLOCK_IN 與 ACCESS_ONLY，呈現前次打卡或未打卡狀態；補打卡要有警語，下班打卡與單純離開系統分開。
- SQL Server 為權威時間，依台灣工作日換日；上下班交替且以交易防重。受保護請求重查員工與出勤，前端每 60 秒校時並補償往返時間；登入頁避免揭露內部細節。
- 日報保留提交、核准、退回、要求補件、員工回覆及個人歷程。
- 教育訓練保留單選、多選、閱讀及人工審核申論；移除程式碼填空與連連看，不重新加回。模擬考交卷前不回傳答案／解析，保留快照、續作、錯題本。
- 文件支援 DOCX、DOC、Excel、PDF 與 OCR。舊 DOC 優先 LibreOffice，Windows Word COM 備援，不改原始檔。匯入題目先為草稿，確認後才發布；不恢復已移除的自然語言手動匯入。
- 宣導影音保留 YouTube、BiliBili、ニコニコ、Douyin、TikTok 與 YouTube 縮圖，沿用共用樣式。標題取自實際來源，不以影片 ID 替代；解析或播放失敗明確回報並保留原站連結。

## 部署

- start.bat、start.sh、dockerfile、docker-compose.yml 與 systemd 同步架構；啟動預先編譯的 Go，由 Go 管理 Python 子程序。
- Windows 容器保留 Server Core LTSC 2022、IIS 與 C:/inetpub/wwwroot；Python 使用 3.11 venv。依既有決策先維持可啟動部署，不自行增加 volume／HTTPS。
- OMV 主機以 systemd 執行 Go，連接既有 Docker SQL Server；網站 8080、資料庫 1433 的規劃依現有文件，不擅改正式環境。

## 整理來源與適用方式

本輪讀取可取得的 9 個專案對話：Windows Docker、全域 changelog skill 安裝、YouTube 縮圖、多平台影音、README／內部文件、移除填空／連連看、MIS 題庫版型、OMV systemd、Python／Go Playground；合併原 agent.md、history.md 的較早需求與本輪 Go／資料庫遷移指令。不將系統自動審查或子代理副本當成人類指令，也不聲稱已讀取不可取得的對話。

既往「只改指定前端區塊」「當次不啟動網站」依原任務生效，不當作永久禁止後端變更或測試。全域 skill 安裝等已完成操作只保留歷史，不變成每次必做事項。

2026-10-31 最新方向：Company 為主要資料庫，連線依最新 agents/DATABASE.md 與 .env 一致設定。員工以 database/SeedEmployees.sql 一次性初始化，後續透過員工管理新增、修改及停用，不再依賴 CSV。文件啟動同步保留，缺少來源不可停用既有文件。資料庫搬移、回復及演練工具已移除。OMV 因主機指紋不符繼續暫停 SSH；更新 MSSQL 連線資訊不代表核准恢復 SSH。

專案結構嚴格依 backend／page／data／database 分類：後端與其 docs、deploy、tools 放 backend；前後台頁面、靜態資源及前端 docs、tools 放 page；文件原檔與處理結果放 data；Go 資料庫存取及 SQL 放 database。根目錄不保留獨立 docs、deploy、tools，也不保留資料庫搬移或驗收工具。

history.md 依日期由上往下續寫，新紀錄一律附加於檔案末端；不得在頂端插入、重排既有紀錄或覆寫 Phoenix 手動整理的內容。
