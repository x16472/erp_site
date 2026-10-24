# 使用Windows Server Core 2022 基礎映像檔
FROM mcr.microsoft.com/windows/servercore:ltsc2022
# 設定映像檔的元數據（Metadata）標籤，此處用來註明該映像檔的作者或維護者信箱
LABEL org.opencontainers.image.authors="dog0830430@gmail.com"
# 在這裡定義變數 NAME
ENV NAME="ERP_Site"
# 在映像檔建置過程中執行命令，此處調用 Windows 的 DISM 工具來啟用 IIS 網頁伺服器功能，且不自動重啟
# 啟用 IIS 功能
RUN dism.exe /online /enable-feature /all /featurename:iis-webserver /NoRestart

# 使用標準 PowerShell 下載與靜默安裝 Python
SHELL ["powershell", "-Command", "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"]

# 網址為真實的實體下載路徑，並固定安裝在 C:\Python311 目錄下
RUN Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" -OutFile "C:\python-installer.exe" ; \
    Start-Process C:\python-installer.exe -ArgumentList '/quiet InstallAllUsers=1 TargetDir=C:\Python311 Include_test=0 PrependPath=1' -Wait ; \
    Remove-Item C:\python-installer.exe

# 在 Docker 環境變數中把 Python 實體安裝路徑寫死，確保後續步驟與容器執行時都能抓到
ENV PATH="C:\Python311;C:\Python311\Scripts;${PATH}"

# 切換回傳統 CMD 模式
SHELL ["cmd", "/S", "/C"]

# 設定工作目錄
WORKDIR C:\inetpub\wwwroot

# 複製 requirements.txt 並在建置階段建立 venv
COPY requirements.txt .

# 執行虛擬環境與套件安裝（此時有了第 19 行的 ENV PATH，python 指令絕對 100% 認得）
RUN python -m venv .venv
RUN .\.venv\Scripts\python.exe -m pip install --upgrade pip
RUN .\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 複製其餘所有的專案程式碼與檔案
COPY . .

# 容器運行時執行的指令
CMD [ "cmd.exe", "/c", "C:\inetpub\wwwroot\start.bat" ]