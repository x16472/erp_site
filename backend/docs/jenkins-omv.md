# Jenkins 與 OMV Alpine 容器部署

## 架構

瀏覽器經 Cloudflare HTTPS → `cloudflare/cloudflared:2026.10.5` → `http://erp_service:8080` → Go／Python → 既有 MSSQL 容器。網站映像使用 `python:3.11-alpine3.22`，目前限定 Linux x86-64（`linux/amd64`）。不需要 IIS，也不需要在 OMV 主機安裝 Go 或 Python。

## Jenkins 設定

1. 建立標籤為 `linux-docker` 的 Linux x86-64 agent，準備 Git、Docker Engine（Linux 容器）及 Docker Compose v2；Jenkins 執行帳號需能操作 Docker daemon。
2. 安裝 Jenkins Pipeline 與 Git 外掛。建立 Pipeline from SCM，或使用 Multibranch Pipeline，Script Path 設為根目錄 `Jenkinsfile`。私有 repository 的 SCM 憑證在 Jenkins 設定。
3. agent 需能下載官方 Go／Python 映像、Alpine 套件、Go modules、PyPI 套件及 MuPDF 原始碼。預留原生編譯所需記憶體與磁碟空間。
4. pipeline 依序 checkout、檢查 Compose、執行 `go_check` 的 go vet 靜態檢查，再透過 `docker compose build erp_service` 建置 `runtime`。檢查或建置失敗會停止；同一 job 不並行，整體逾時為 120 分鐘。
5. 成功後網站映像保留於 agent 使用的 Docker daemon，標籤為 `erp-site:ci-<BUILD_NUMBER>-<完整 Git commit>`。Jenkins 保存 `image-tag.txt`、`image-id.txt`，不保存映像 tar、不推送 registry、不自動部署。Docker 建置階段可使用快取；相關來源或套件變更時會重新執行。

建置不需要網站 `.env`、MSSQL 連線或 Cloudflare token。靜態檢查與建置在容器中執行，agent 不需安裝 Go 或 Python。自動測試程式及其 Docker 目標已依 Phoenix 指示移除。`.dockerignore` 排除 `.env`、`secrets/`、本機 venv 與 CI 中繼檔案。Jenkins 的紀錄保留設定不會清除 Docker 映像或快取，磁碟清理由維運規劃。

PyMuPDF 1.26.4 的 [PyPI 發行檔](https://pypi.org/project/pymupdf/1.26.4/#files) 未提供 musllinux wheel，因此 `python_build` 階段安裝編譯工具建立 wheel，最終映像不帶入編譯工具。未更動既有 Python 相依版本；不能將此配置視為已支援 ARM。

## OMV 部署準備

使用固定的專案目錄及 Compose project 名稱，避免 named volume 名稱因移動資料夾而改變。準備既有 `.env`，資料庫 IP／port 指向 OMV 上已發布的 MSSQL 埠；資料庫名稱、帳密與 MIS 管理員設定沿用實際值。網站容器的 localhost 不是 MSSQL 容器，Compose 也不會替 MSSQL 開埠或初始化資料庫。

在 OMV 的專案根目錄準備 `data/` 與 `secrets/`。將 Cloudflare remotely-managed Tunnel 的 token 單獨存成 `secrets/cloudflared-token.txt`，內容只放 token，不放 `TUNNEL_TOKEN=`。檔案已排除版控與 Docker build context，不要提交或寫入 Jenkins 紀錄。

Cloudflared 映像以非 root 使用者執行；Compose 的檔案型 secret 直接掛載主機檔案，需確保容器使用者可讀取。可讓 `secrets/` 目錄由部署帳號持有且權限為 `700`，token 檔為 `644`；父目錄限制主機上的其他使用者，容器只取得單一唯讀 secret。不要把含 token 的命令存入 shell history。

在 Cloudflare Tunnel 後台新增網站的公開網域路由，Service 設為 `HTTP`，URL 設為 `erp_service:8080`。不使用 `localhost:8080`，因為 localhost 在 cloudflared 容器內指向自身。Tunnel 需要 OMV 對外連線；不需要為 Tunnel 額外發布主機連接埠。此設定使用官方 [`--token-file`](https://developers.cloudflare.com/tunnel/reference/run-parameters/) 參數。

Compose 設定 `ERP_TLS_PROXY=1`，容器內的 HTTP 只供受隔離的反向代理使用；主機埠僅發布於 `127.0.0.1:8080`，供 OMV 本機健康檢查，不再向內網公開明文登入入口。瀏覽器請使用 Tunnel 的 HTTPS 網域，工作階段 Cookie 強制設定 Secure。Cloudflare 的帳號、網域與路由需在實際後台設定，本次程式修改不會自動建立。

## 建置與啟動

在 OMV 直接建置：

```bash
docker compose config --quiet
docker compose build erp_service
docker compose up -d
```

若 Jenkins 與 OMV 共用同一個 Docker daemon，從成功建置的 `image-tag.txt` 取得映像名稱，部署時使用該標籤：

```bash
export ERP_IMAGE='erp-site:ci-建置編號-完整commit'
docker compose up -d --no-build
```

上述值必須換成實際標籤。如果 Jenkins 使用另一台 Docker 主機，需先透過既有私有 registry 或 `docker save`／`docker load` 將映像交付至 OMV；本 pipeline 未預設 registry 或傳輸帳密。

第一次切換容器前，確認既有 systemd 網站沒有占用 8080，並由維運人員將原服務的員工照片複製至本 Compose 的 `staff_photos` volume。新的 named volume 不會自動取得舊服務檔案。`data/` 包含來源文件與快取，應放在固定且備份的 OMV 資料路徑。

## 驗證與維護

```bash
docker compose ps
docker compose logs --tail 100 erp_service cloudflared
curl --fail --show-error http://127.0.0.1:8080/api/health
```

網站健康檢查通過才啟動 cloudflared。確認 Tunnel 已連線後，再透過實際公開網域檢查首頁與登入。本機健康檢查不等於公開網域驗收。SOP 同步在網站啟動後於背景執行，健康檢查成功不表示文件同步完成，可由同步完成或失敗的記錄確認。`restart: unless-stopped` 會在程序退出時重啟，單純 unhealthy 不會自動重啟。

更新程式需重建映像並重新建立網站容器；更新 `.env` 後需重啟網站。更新 token 檔後可用 `docker compose up -d --force-recreate cloudflared` 重新建立 Tunnel 容器，讓檔案掛載更新。`docker compose down` 保留照片 volume；不要使用 `down -v`，除非確定要刪除照片資料。

本次未操作遠端 OMV、既有 MSSQL 或 Cloudflare 帳號。先前 SSH 主機指紋尚待核對的限制維持有效。

## 前端模組與教育訓練更新檢查

前端使用瀏覽器原生 ESM；發布前以實際瀏覽器確認模組載入與操作。runtime 必須包含整個 `page/`：HTML 僅引用 `static/js/script.js`，入口再載入 API、主題、分頁及各頁控制器；Canvas 模組與 module Worker 位於 `static/js/canvas/`。Go WASM 配套檔仍在 `static/golang-runtime/`，Python Worker 保留 Pyodide 0.25.1／Python 3.11 的固定版本。

本次題庫程式更新需重建映像以更新 Go 內嵌 SQL，正常結構不需資料重編或增加應用帳號的 ALTER 權限。既有資料庫若已遺失 QuestionNo 或外鍵，需另外完成一次性關聯修復，詳見題庫維護文件。重新建立容器後，確認題庫的科目與章節連動、內部編號不顯示，以及 exam.html 的 SOP 目錄與章節查閱。健康 API 成功不代表這些介面流程已驗收；既有作答關聯另見 [題庫維護](question-bank.md)。
