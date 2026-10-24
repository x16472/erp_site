## [Unreleased] - 2026-10-24

### Added

- 新增 Windows 容器建置與 Docker Compose 部署設定。(6820fbd、d396610)

### Changed

- 容器採用 Windows Server Core LTSC 2022 與官方 Python image，整合內建 IIS、Python venv、HTTP 健康檢查及服務監控。
- 網站檔案、venv 與啟動工作目錄統一部署至 `C:/inetpub/wwwroot/`，由 IIS 將請求轉送至 Python 後端。
- 員工管理改為組織架構、員工清單與明細三區介面，支援搜尋、在職狀態篩選、鍵盤選取及響應式版面。
- 資料庫連線改為單一 HTTP 請求內複用，並透過員工 CSV 同步快取及批次資料寫入，減少重複連線與查詢。

### Fixed

- 修復請求內快取連線提前關閉造成的資料庫存取錯誤，查詢失敗時淘汰失效連線。(a4ecb0f)
- 補齊 Visual C++ Runtime，修復 Windows 容器中 PyMuPDF 無法載入原生 DLL 的問題。
- 修復建置時引號遺失造成的容器啟動腳本錯誤，並加入啟動腳本與 IIS XML 解析檢查。

### Security

- 為 `POST /api/youtube/resolve` 加入員工 CSRF Token 驗證，並同步調整前端請求。
