# escape=`
# 從 Docker 官方 image 取得 Python，最終基底明確使用 Server Core。
FROM python:3.13-windowsservercore-ltsc2022 AS python_runtime
FROM mcr.microsoft.com/windows/servercore:ltsc2022

LABEL org.opencontainers.image.authors="dog0830430@gmail.com"
SHELL ["powershell", "-NoLogo", "-NoProfile", "-Command", "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"]
COPY --from=python_runtime C:/Python/ C:/Python/

ENV NAME="ERP_Site" `
    PYTHONUNBUFFERED="1" `
    PYTHONDONTWRITEBYTECODE="1" `
    PYTHONIOENCODING="utf-8"

# IIS 對外接收 HTTP；既有 Python HTTP 後端由 ARR 反向代理。
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
COPY backend/ C:/inetpub/wwwroot/backend/
COPY page/ C:/inetpub/wwwroot/page/
COPY data/staff.csv data/Company_Schema.sql C:/inetpub/wwwroot/data/
COPY start.bat C:/inetpub/wwwroot/start.bat
COPY .env C:/inetpub/wwwroot/.env
RUN cmd.exe /S /C 'start.bat --check < NUL'; `
    if ($LASTEXITCODE -ne 0) { throw 'start.bat dependency checks failed.' }; `
    C:\inetpub\wwwroot\.venv\Scripts\python.exe -c 'import pymupdf, PIL, pytesseract'; `
    if ($LASTEXITCODE -ne 0) { throw 'Document dependency checks failed.' }

# 網站與 venv 統一部署至 IIS 根目錄，所有請求仍交由既有後端處理。
RUN $result = Install-WindowsFeature Web-Scripting-Tools; `
    if (-not $result.Success) { throw 'IIS scripting tools installation failed.' }; `
    Import-Module WebAdministration; `
    Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' -Filter 'system.webServer/proxy' -Name enabled -Value $true; `
    Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' -Filter 'system.webServer/proxy' -Name preserveHostHeader -Value $true; `
    Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' -Filter 'system.webServer/proxy' -Name reverseRewriteHostInResponseHeaders -Value $false; `
    Set-Content -LiteralPath C:\inetpub\wwwroot\web.config -Encoding UTF8 -Value '<configuration><system.webServer><rewrite><rules><rule name=''PythonBackend'' stopProcessing=''true''><match url=''(.*)'' /><action type=''Rewrite'' url=''http://127.0.0.1:8000/{R:1}'' appendQueryString=''true'' /></rule></rules></rewrite><httpErrors existingResponse=''PassThrough'' /><caching enabled=''false'' enableKernelCache=''false'' /></system.webServer></configuration>'

# 沿用 start.bat 的啟動命令，改用回送位址及 8000 埠以避開 IIS。
# 同時監控後端及 IIS，任一停止即結束容器。
RUN Set-Content -LiteralPath C:\container-start.ps1 -Encoding UTF8 -Value @(`
    '$ErrorActionPreference = ''Stop''', `
    'if (-not (Test-Path -LiteralPath C:\inetpub\wwwroot\.env -PathType Leaf)) { throw ''Application .env is missing.'' }', `
    '$startInfo = New-Object System.Diagnostics.ProcessStartInfo', `
    '$startInfo.FileName = ''C:\inetpub\wwwroot\.venv\Scripts\python.exe''', `
    '$startInfo.Arguments = ''-m backend.app --host 127.0.0.1 --port 8000''', `
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
