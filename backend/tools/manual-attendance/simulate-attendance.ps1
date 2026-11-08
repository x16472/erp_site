param(
    [ValidateSet('Prepare', 'Apply')]
    [string]$Phase,
    [string]$Workspace,
    [string]$EnvPath = (Join-Path $PSScriptRoot '..\..\..\.env'),
    [switch]$Preview
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Open-AttendanceConnection {
    param([string]$Path)

    $settings = @{}
    foreach ($line in [IO.File]::ReadAllLines($Path)) {
        $text = $line.Trim().TrimStart([char]0xFEFF)
        if (-not $text -or $text.StartsWith('#') -or -not $text.Contains('=')) { continue }
        $key, $value = $text.Split([char[]]@('='), 2, [StringSplitOptions]::None)
        $settings[$key.Trim()] = $value.Trim().Trim([char[]]@('"', "'"))
    }
    foreach ($key in @('DatabaseIP', 'DatabaseName', 'DatabaseUser', 'DatabasePassword')) {
        if (-not $settings[$key]) { throw "缺少資料庫設定：$key" }
    }
    $builder = New-Object System.Data.SqlClient.SqlConnectionStringBuilder
    $builder['Data Source'] = $settings.DatabaseIP
    if ($settings['DatabasePort']) { $builder['Data Source'] += ',' + $settings['DatabasePort'] }
    $builder['Initial Catalog'] = $settings.DatabaseName
    $builder['User ID'] = $settings.DatabaseUser
    $builder['Password'] = $settings.DatabasePassword
    $builder['Connect Timeout'] = 10
    $builder['Encrypt'] = $false
    $builder['TrustServerCertificate'] = $true
    $builder['Application Name'] = 'ManualAttendanceSimulator'
    $connection = New-Object System.Data.SqlClient.SqlConnection ($builder.ToString())
    try { $connection.Open() } catch {
        $connection.Dispose()
        throw '無法連線 SQL Server，請檢查 .env 與網路。'
    }
    return $connection
}

function Assert-AttendanceSchema {
    param($Connection)

    $command = $Connection.CreateCommand()
    try {
        $command.CommandText = @'
SELECT COUNT(*) FROM sys.columns
WHERE object_id = OBJECT_ID(N'dbo.AttendanceRecords', N'U')
AND name IN (N'EmployeeNo', N'AttendanceAction', N'ClockedAt', N'ClockedAtUtc',
             N'WorkDate', N'SourceIp', N'Remark');
'@
        if ([int]$command.ExecuteScalar() -ne 7) {
            throw 'dbo.AttendanceRecords 欄位與截圖不符，已停止。'
        }
    } finally { $command.Dispose() }
}

function New-AttendancePlan {
    param($Snapshot, [string[]]$Lines)

    $start = [DateTimeOffset]::ParseExact($Snapshot.Start, 'o', [Globalization.CultureInfo]::InvariantCulture)
    $expectedAction = if ($start.Hour -lt 12) { 'CLOCK_IN' } else { 'CLOCK_OUT' }
    if ($Snapshot.Action -cne $expectedAction) { throw '打卡動作與本機執行時間不符。' }
    $employees = @($Snapshot.Employees)
    if ($Lines.Count -ne $employees.Count) { throw '員工名單與亂數筆數不符。' }
    $previous = 0
    $seen = @{}
    for ($index = 0; $index -lt $Lines.Count; $index++) {
        if ($Lines[$index] -notmatch '^([A-Za-z0-9_-]{1,50}),(\d{1,9})(\.\d{1,3})?$') { throw '亂數檔案格式錯誤。' }
        $employee = $Matches[1]
        $offset = [int]$Matches[2]
        if ($employee -cne $employees[$index] -or $employee -in @('K002', 'K020') -or $seen.ContainsKey($employee)) {
            throw '名單含排除、重複或不符的員工編號。'
        }
        if ($offset -le $previous -or $offset - $previous -gt 600) { throw '員工間隔必須為 1 至 600 秒。' }
        # 產生 0 到 999 毫秒的亂數
        $randomMs = Get-Random -Minimum 0 -Maximum 1000
        # 同時累加秒數與隨機毫秒數
        $clock = $start.AddSeconds($offset).AddMilliseconds($randomMs)
        if ($clock.Date -ne $start.Date) { throw '模擬時間跨日，已取消整批操作。' }
        $seen[$employee] = $true
        $previous = $offset
        [pscustomobject]@{ EmployeeNo = $employee; Clock = $clock; Action = $expectedAction }
    }
}

function Invoke-AttendanceTool {
    if (-not $Phase -or -not $Workspace) { throw '請使用 simulate-attendance.bat 執行。' }
    if ($Phase -eq 'Prepare') {
        $start = [DateTimeOffset]::Now
        $connection = Open-AttendanceConnection $EnvPath
        try {
            Assert-AttendanceSchema $connection
            $command = $connection.CreateCommand()
            try {
                $command.CommandText = @'
SELECT EmployeeNo FROM dbo.Employees
WHERE IsActive = 1 AND EmployeeNo NOT IN (N'K002', N'K020')
ORDER BY EmployeeNo;
'@
                $reader = $command.ExecuteReader()
                $employees = @()
                try {
                    while ($reader.Read()) {
                        $employee = $reader.GetString(0)
                        if ($employee -cnotmatch '^[A-Za-z0-9_-]{1,50}$') { throw '員工編號含不支援的字元。' }
                        $employees += $employee
                    }
                } finally { $reader.Dispose() }
            } finally { $command.Dispose() }
        } finally { $connection.Dispose() }
        $snapshot = @{
            Start = $start.ToString('o')
            Action = $(if ($start.Hour -lt 12) { 'CLOCK_IN' } else { 'CLOCK_OUT' })
            Employees = @($employees)
        }
        $snapshot | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Workspace 'context.json') -Encoding UTF8
        [IO.File]::WriteAllLines((Join-Path $Workspace 'employees.txt'), [string[]]$employees, [Text.Encoding]::ASCII)
        return
    }

    $snapshot = Get-Content -LiteralPath (Join-Path $Workspace 'context.json') -Raw | ConvertFrom-Json
    $lines = [IO.File]::ReadAllLines((Join-Path $Workspace 'offsets.csv'))
    $plan = @(New-AttendancePlan $snapshot $lines)
    Write-Host "起始本機時間：$($snapshot.Start)；動作：$($snapshot.Action)"
    if ($Preview) {
        foreach ($entry in $plan) { Write-Host "$($entry.EmployeeNo) $($entry.Clock.ToString('o')) PREVIEW" }
        Write-Host "預覽完成，共 $($plan.Count) 位員工，沒有寫入資料庫。"
        return
    }
    $connection = Open-AttendanceConnection $EnvPath
    $transaction = $null
    try {
        Assert-AttendanceSchema $connection
        $transaction = $connection.BeginTransaction()
        $command = $connection.CreateCommand()
        $command.Transaction = $transaction
        $command.CommandTimeout = 30
        try {
            $command.CommandText = @'
DECLARE @Active INT;
SELECT @Active = IsActive FROM dbo.Employees WITH (UPDLOCK, HOLDLOCK)
WHERE EmployeeNo = @EmployeeNo;
IF ISNULL(@Active, 0) <> 1 OR @EmployeeNo IN (N'K002', N'K020')
    SELECT N'SKIP_INACTIVE';
ELSE IF EXISTS (SELECT 1 FROM dbo.AttendanceRecords
    WHERE EmployeeNo = @EmployeeNo AND WorkDate = @WorkDate AND AttendanceAction = @Action)
    SELECT N'SKIP_DUPLICATE';
ELSE IF @Action = N'CLOCK_OUT' AND NOT EXISTS (SELECT 1 FROM dbo.AttendanceRecords
    WHERE EmployeeNo = @EmployeeNo AND WorkDate = @WorkDate AND AttendanceAction = N'CLOCK_IN')
    SELECT N'SKIP_NO_CLOCK_IN';
ELSE IF EXISTS (SELECT 1 FROM dbo.AttendanceRecords
    WHERE EmployeeNo = @EmployeeNo AND WorkDate = @WorkDate AND ClockedAtUtc >= @Utc)
    SELECT N'SKIP_TIME_ORDER';
ELSE
BEGIN
    INSERT dbo.AttendanceRecords
        (EmployeeNo, AttendanceAction, ClockedAt, ClockedAtUtc, WorkDate, SourceIp, Remark)
    VALUES (@EmployeeNo, @Action, @Local, @Utc, @WorkDate, N'SIMULATOR',
            N'手動批次模擬：依執行當下本機時間累加 1 至 600 秒');
    SELECT N'INSERTED';
END;
'@
            $null = $command.Parameters.Add('@EmployeeNo', [Data.SqlDbType]::NVarChar, 50)
            $null = $command.Parameters.Add('@Action', [Data.SqlDbType]::NVarChar, 50)
            $null = $command.Parameters.Add('@Local', [Data.SqlDbType]::DateTime2)
            $null = $command.Parameters.Add('@Utc', [Data.SqlDbType]::DateTime2)
            $null = $command.Parameters.Add('@WorkDate', [Data.SqlDbType]::Date)
            $results = @()
            foreach ($entry in $plan) {
                $command.Parameters['@EmployeeNo'].Value = $entry.EmployeeNo
                $command.Parameters['@Action'].Value = $entry.Action
                $command.Parameters['@Local'].Value = $entry.Clock.DateTime
                $command.Parameters['@Utc'].Value = $entry.Clock.UtcDateTime
                $command.Parameters['@WorkDate'].Value = $entry.Clock.Date
                $status = [string]$command.ExecuteScalar()
                $results += "$($entry.EmployeeNo) $($entry.Clock.ToString('o')) $status"
            }
            $transaction.Commit()
            foreach ($result in $results) { Write-Host $result }
            Write-Host "完成，共處理 $($plan.Count) 位員工。"
        } finally { $command.Dispose() }
    } catch {
        if ($null -ne $transaction) {
            try { $transaction.Rollback() } catch { }
        }
        throw '整批操作失敗或提交結果未確認，請查詢出勤紀錄後再重試。'
    } finally {
        if ($null -ne $transaction) { $transaction.Dispose() }
        $connection.Dispose()
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    try { Invoke-AttendanceTool } catch {
        Write-Host $_.Exception.Message -ForegroundColor Red
        exit 1
    }
}
