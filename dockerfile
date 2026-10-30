# escape=`
# Go 編譯與最終 Server Core 分階段；Python 使用官方固定版本安裝程式。
FROM golang:1.23-windowsservercore-ltsc2022 AS go_build
WORKDIR C:/build
COPY go.mod go.sum ./
RUN go mod download
COPY backend/cmd/ ./backend/cmd/
COPY backend/internal/ ./backend/internal/
COPY backend/rpc/ ./backend/rpc/
COPY database/ ./database/
RUN go build -trimpath -o C:/build/erp-site.exe ./backend/cmd/erp

FROM mcr.microsoft.com/windows/servercore:ltsc2022 AS runtime_config
SHELL ["powershell", "-NoLogo", "-NoProfile", "-Command", "$ErrorActionPreference = 'Stop';"]
COPY .env C:/config/.env
# 部署帳密只供部署端使用，不進入最終網站 image。
RUN $lines = Get-Content -LiteralPath C:\config\.env; `
    $lines | Where-Object { $_ -notmatch '^\s*DokerPublish(Name|Password)\s*=' } | Set-Content -LiteralPath C:\config\.env -Encoding UTF8

FROM mcr.microsoft.com/windows/servercore:ltsc2022

LABEL org.opencontainers.image.authors="dog0830430@gmail.com"
SHELL ["powershell", "-NoLogo", "-NoProfile", "-Command", "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"]

RUN Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile C:\python-installer.exe; `
    $digest = (Get-FileHash -LiteralPath C:\python-installer.exe -Algorithm SHA256).Hash; `
    if ($digest -ne '5EE42C4EEE1E6B4464BB23722F90B45303F79442DF63083F05322F1785F5FDDE') { throw 'Python installer checksum mismatch.' }; `
    $process = Start-Process C:\python-installer.exe -ArgumentList @('/quiet', 'InstallAllUsers=1', 'TargetDir=C:\Python', 'Include_launcher=0', 'Include_test=0', 'Include_doc=0', 'Include_tcltk=0', 'Shortcuts=0', 'AssociateFiles=0') -Wait -WindowStyle Hidden -PassThru; `
    if ($process.ExitCode -notin @(0, 3010)) { throw ('Python installation failed: ' + $process.ExitCode) }; `
    Remove-Item -LiteralPath C:\python-installer.exe

ENV NAME="ERP_Site" `
    WEB_HOST="127.0.0.1" `
    WEB_PORT="8000" `
    PYTHONUNBUFFERED="1" `
    PYTHONDONTWRITEBYTECODE="1" `
    PYTHONIOENCODING="utf-8"

# IIS 對外接收 HTTP，ARR 轉送至 Go 主程式。
RUN $result = Install-WindowsFeature Web-Server; `
    if (-not $result.Success) { throw 'IIS installation failed.' }; `
    Invoke-WebRequest -Uri 'https://download.microsoft.com/download/1/2/8/128E2E22-C1B9-44A4-BE2A-5859ED1D4592/rewrite_amd64_en-US.msi' -OutFile C:\rewrite.msi; `
    Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/?LinkID=615136' -OutFile C:\arr.msi; `
    foreach ($installer in @('C:\rewrite.msi', 'C:\arr.msi')) { `
    $process = Start-Process msiexec.exe -ArgumentList @('/i', $installer, '/qn', '/norestart') -Wait -WindowStyle Hidden -PassThru; `
    if ($process.ExitCode -notin @(0, 3010)) { throw ('MSI installation failed: ' + $process.ExitCode) }; `
    Remove-Item -LiteralPath $installer; `
    }

WORKDIR C:/inetpub/wwwroot
COPY requirements.txt C:/inetpub/wwwroot/requirements.txt
RUN C:\Python\python.exe -m venv C:\inetpub\wwwroot\.venv; `
    if ($LASTEXITCODE -ne 0) { throw 'venv creation failed.' }; `
    C:\inetpub\wwwroot\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements.txt; `
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }; `
    C:\inetpub\wwwroot\.venv\Scripts\python.exe -m pip check; `
    if ($LASTEXITCODE -ne 0) { throw 'Dependency compatibility check failed.' }

# PyMuPDF 的原生模組需要完整的 Visual C++ Runtime。
RUN Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile C:\vc_redist.x64.exe; `
    $process = Start-Process C:\vc_redist.x64.exe -ArgumentList @('/install', '/quiet', '/norestart') -Wait -WindowStyle Hidden -PassThru; `
    if ($process.ExitCode -notin @(0, 1638, 3010)) { throw ('Visual C++ Runtime installation failed: ' + $process.ExitCode) }; `
    Remove-Item -LiteralPath C:\vc_redist.x64.exe

# 明確指定來源，避免把 Git 或本機 .venv 打包進 image。
COPY --from=go_build C:/build/erp-site.exe C:/inetpub/wwwroot/bin/erp-site.exe
COPY backend/src/ C:/inetpub/wwwroot/backend/src/
COPY backend/__init__.py C:/inetpub/wwwroot/backend/__init__.py
COPY database/*.sql C:/inetpub/wwwroot/database/
COPY page/ C:/inetpub/wwwroot/page/
COPY start.bat C:/inetpub/wwwroot/start.bat
COPY --from=runtime_config C:/config/.env C:/inetpub/wwwroot/.env
RUN cmd.exe /S /C 'start.bat --check < NUL'; `
    if ($LASTEXITCODE -ne 0) { throw 'start.bat dependency checks failed.' }; `
    C:\inetpub\wwwroot\.venv\Scripts\python.exe -c 'import pymupdf, PIL, pytesseract'; `
    if ($LASTEXITCODE -ne 0) { throw 'Document dependency checks failed.' }

# 網站與 venv 統一部署至 IIS 根目錄，所有請求仍交由既有後端處理。
RUN $result = Install-WindowsFeature Web-Scripting-Tools; `
    if (-not $result.Success) { throw 'IIS scripting tools installation failed.' }; `
    Import-Module WebAdministration; `
    Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' -Filter 'system.webServer/proxy' -Name enabled -Value $true; `
    Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' -Filter 'system.webServer/proxy' -Name timeout -Value '00:11:00'; `
    Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' -Filter 'system.webServer/proxy' -Name preserveHostHeader -Value $true; `
    Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' -Filter 'system.webServer/proxy' -Name reverseRewriteHostInResponseHeaders -Value $false; `
    Set-Content -LiteralPath C:\inetpub\wwwroot\web.config -Encoding UTF8 -Value '<configuration><system.webServer><rewrite><rules><rule name=''GoBackend'' stopProcessing=''true''><match url=''(.*)'' /><action type=''Rewrite'' url=''http://127.0.0.1:8000/{R:1}'' appendQueryString=''true'' /></rule></rules></rewrite><httpErrors existingResponse=''PassThrough'' /><caching enabled=''false'' enableKernelCache=''false'' /></system.webServer></configuration>'

# 沿用 start.bat 的啟動命令，改用回送位址及 8000 埠以避開 IIS。
# 同時監控後端及 IIS，任一停止即結束容器。
RUN Set-Content -LiteralPath C:\container-start.ps1 -Encoding UTF8 -Value @(`
    '$ErrorActionPreference = ''Stop''', `
    'if (-not (Test-Path -LiteralPath C:\inetpub\wwwroot\.env -PathType Leaf)) { throw ''Application .env is missing.'' }', `
    '$startInfo = New-Object System.Diagnostics.ProcessStartInfo', `
    '$startInfo.FileName = ''C:\inetpub\wwwroot\bin\erp-site.exe''', `
    '$startInfo.Arguments = ''--root C:\inetpub\wwwroot''', `
    '$startInfo.WorkingDirectory = ''C:\inetpub\wwwroot''', `
    '$startInfo.UseShellExecute = $false', `
    '$startInfo.CreateNoWindow = $true', `
    '$backend = [System.Diagnostics.Process]::Start($startInfo)', `
    'try {', `
    '    Start-Service W3SVC', `
    '    while (-not $backend.WaitForExit(1000)) {', `
    '        if ((Get-Service W3SVC).Status -ne ''Running'' -or (Get-Service WAS).Status -ne ''Running'') { throw ''IIS stopped.'' }', `
    '    }', `
    '    exit $backend.ExitCode', `
    '} finally {', `
    '    if (-not $backend.HasExited) { $backend.Kill(); $backend.WaitForExit() }', `
    '    Stop-Service W3SVC -ErrorAction SilentlyContinue', `
    '}' `
    ); `
    $tokens = $null; $parseErrors = $null; `
    $null = [System.Management.Automation.Language.Parser]::ParseFile('C:\container-start.ps1', [ref]$tokens, [ref]$parseErrors); `
    if ($parseErrors.Count) { throw ($parseErrors | Out-String) }; `
    $null = [xml](Get-Content -LiteralPath C:\inetpub\wwwroot\web.config -Raw)

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 `
    CMD powershell -NoLogo -NoProfile -Command "try { $response = Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1/ -TimeoutSec 5; if ($response.StatusCode -ne 200) { exit 1 } } catch { exit 1 }"
ENTRYPOINT ["powershell.exe", "-NoLogo", "-NoProfile", "-File", "C:\\container-start.ps1"]
CMD []
