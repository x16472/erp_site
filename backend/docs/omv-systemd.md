# OMV 上以 systemd 執行網站

部署目標為 OMV 主機 `10.10.0.4`，網站由主機上的 Go 提供，Python 3.11 由 Go 以 gRPC 管理，連線至同一主機 Docker 容器對外發布的 MSSQL `10.10.0.4:1433`。網站預設使用 `8080` 埠，網址為 <http://10.10.0.4:8080/>。

以下為在 OMV 上手動執行的部署步驟，範例專案路徑為 `/opt/erp_site`。若使用 OMV 資料磁碟的實際路徑，請一併調整所有命令，以及服務範本中的 `RequiresMountsFor`、`WorkingDirectory` 和 `ExecStart`。

## 1. 準備 Linux 執行環境

需要 Go 1.23+ 與 Python 3.11。請先依主機版本安裝這兩種執行環境；系統預設 Python 若不是 3.11，不可直接代用。先確認 OMV 上的 Python 版本，再安裝 Debian 套件：

```bash
go version
python3.11 --version
sudo apt-get update
sudo apt-get install python3.11 python3.11-venv
```

SQL Server 使用 Go 驅動，不需要 Python SQL 驅動或 ODBC。若套件庫沒有 Python 3.11，需先準備相容的 3.11 安裝。

將專案放到 `/opt/erp_site`，另外安全地準備原有 `.env`。Windows 的 `.venv` 與 `.deps` 不可複製到 OMV，請在 Linux 建立新的虛擬環境；正式服務不使用 `.deps`。

```bash
sudo useradd --system --user-group --create-home --home-dir /var/lib/erp-site --shell /usr/sbin/nologin erp-site
sudo chown -R erp-site:erp-site /opt/erp_site
sudo chmod 600 /opt/erp_site/.env
cd /opt/erp_site
sudo -u erp-site python3.11 -m venv .venv
sudo -u erp-site .venv/bin/python -m pip install -r requirements.txt
sudo -u erp-site .venv/bin/python -m pip check
sudo -u erp-site go mod download
sudo -u erp-site go build -trimpath -o bin/erp-site ./backend/cmd/erp
```

`useradd` 僅在首次建立服務帳號時執行。服務帳號需要專案目錄的讀取與穿越權限，以及 `page/static/staff/` 與 `data/exam/` 的寫入權限，分別用於員工照片與文件快取。若專案位於 OMV 共用資料夾，需一併確認上層目錄的權限與 ACL。

需要舊版 DOC 轉檔或掃描文件 OCR 時，再安裝對應工具：

```bash
sudo apt-get install libreoffice-writer tesseract-ocr tesseract-ocr-chi-tra tesseract-ocr-eng
```

## 2. 確認資料庫設定

在 OMV 上的專案 `.env` 確認以下兩個欄位，其餘資料庫名稱、帳號、密碼與 MIS 管理員帳密沿用實際設定：

```dotenv
DatabaseIP=10.10.0.4
DatabasePort=1433
```

`.env` 是由 Go 直接解析的設定檔，請勿用 `source .env` 載入。systemd 的 `EnvironmentFile` 也不能取代此檔案。MSSQL 容器必須已將 TCP 1433 發布到主機 `10.10.0.4`，且資料庫帳號具備應用資料存取所需權限；只有明確初始化／遷移才需要 DDL 權限。

先進行不連線資料庫的環境檢查：

```bash
sudo -u erp-site /bin/bash /opt/erp_site/start.sh --check
```

`--check` 檢查 Python 3.11 與套件匯入，不驗證帳密、資料庫連線或連接埠是否可用。腳本不會自行安裝套件、修改 `.env` 或控制 MSSQL 容器。

## 3. 安裝與啟動 systemd 服務

確認 `backend/deploy/erp-site.service` 中的路徑與服務帳號符合實際環境後執行：

```bash
sudo install -m 644 /opt/erp_site/backend/deploy/erp-site.service /etc/systemd/system/erp-site.service
sudo systemd-analyze verify /etc/systemd/system/erp-site.service
sudo systemctl daemon-reload
sudo systemctl enable --now erp-site.service
sudo systemctl status erp-site.service --no-pager
sudo journalctl -u erp-site.service -n 100 --no-pager
```

服務啟動時辨識資料庫結構，不執行 DDL；Go 一次性執行 database/SeedEmployees.sql 初始化員工與部門，後續不覆寫人工維護結果，也不讀取 CSV。文件預設自動同步，可用 --skip-doc-sync 略過。全新資料庫先明確執行 `bash start.sh --init-db`；確認部署資料庫正確後再啟動。網站程式直接由 systemd 執行，SQL Server 仍由既有 Docker 容器提供。

服務會等網路上線並排在 Docker 服務之後啟動，但這不代表 MSSQL 已就緒。若資料庫版本辨識因 MSSQL 尚未就緒而失敗，systemd 會每 10 秒重試；其他啟動錯誤也會持續重試，需從 journal 檢查原因。`systemctl status` 顯示 active 僅代表程序已啟動，請繼續確認健康 API：

```bash
curl --fail --show-error http://10.10.0.4:8080/api/health
```

內網用戶也需能連線至 OMV 的 TCP 8080。若此埠已占用，可修改服務範本的 `WEB_PORT`，重新安裝範本後執行 `daemon-reload` 與 `restart`。

## 4. 維護

```bash
sudo systemctl restart erp-site.service
sudo systemctl stop erp-site.service
sudo journalctl -u erp-site.service -f
```

更新 Go 程式或內嵌 SQL 後須重新編譯，再重新啟動服務；更新 Python 程式或 `.env` 後也需重啟；相依套件更新時，先用服務帳號在 Linux venv 安裝 `requirements.txt` 並執行 `pip check`、`start.sh --check`。服務停止與主機關機由 systemd 傳遞訊號給 Go，再由 Go 停止 Python 工作程序，不需額外背景程序或 PID 檔案。

手動前景執行可使用 `bash start.sh`；可傳入既有後端參數，例如 `bash start.sh --port 8081 --skip-doc-sync`。命令列參數會覆寫監聽環境變數。`--skip-doc-sync` 僅略過文件同步，仍會辨識資料庫版本；不執行結構初始化。

目前 OMV SSH 主機指紋未通過 Phoenix 核對，依指示暫停連線；尚未在遠端安裝或啟動本次 Go 服務。部署帳號設定由 .env 的 DokerPublishName／DokerPublishPassword 提供，不將值寫入文件或記錄。
