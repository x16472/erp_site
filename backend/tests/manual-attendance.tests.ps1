$ErrorActionPreference = 'Stop'
$toolDirectory = Join-Path $PSScriptRoot '..\tools\manual-attendance'
$scriptPath = Join-Path $toolDirectory 'simulate-attendance.ps1'
. $scriptPath

function Assert-RejectedPlan {
    param($Snapshot, [string[]]$Lines)
    $rejected = $false
    try { $null = @(New-AttendancePlan $Snapshot $Lines) } catch { $rejected = $true }
    if (-not $rejected) { throw '不合法的計畫未被拒絕。' }
}

$snapshot = [pscustomobject]@{
    Start = '2026-11-07T08:00:00.0000000+08:00'
    Action = 'CLOCK_IN'
    Employees = @('K001', 'K003')
}
$plan = @(New-AttendancePlan $snapshot @('K001,1', 'K003,601'))
if ($plan.Count -ne 2 -or $plan[0].Clock.Second -ne 1 -or $plan[1].Clock.Minute -ne 10 -or $plan[0].Clock.UtcDateTime.Hour -ne 0) {
    throw '上午打卡、間隔邊界或 UTC 轉換錯誤。'
}
$snapshot.Start = '2026-11-07T17:00:00.0000000+08:00'
$snapshot.Action = 'CLOCK_OUT'
$plan = @(New-AttendancePlan $snapshot @('K001,600', 'K003,601'))
if ($plan[0].Action -ne 'CLOCK_OUT' -or $plan[0].Clock.Minute -ne 10) { throw '下班計畫錯誤。' }
foreach ($lines in @(
    @('K001,0', 'K003,1'),
    @('K001,601', 'K003,602'),
    @('K001,1', 'K003,1'),
    @('K001,1', 'K002,2'),
    @('K001,1', 'K020,2'),
    @('K001,1', 'K001,2'),
    @('K001,1', 'K003&echo,2')
)) { Assert-RejectedPlan $snapshot $lines }
Assert-RejectedPlan $snapshot @('K001,1')
$snapshot.Action = 'CLOCK_IN'
Assert-RejectedPlan $snapshot @('K001,1', 'K003,2')
$snapshot.Action = 'CLOCK_OUT'
$snapshot.Start = '2026-11-07T23:59:59.0000000+08:00'
Assert-RejectedPlan $snapshot @('K001,1', 'K003,2')
$snapshot.Start = '2026-11-07T12:00:00.0000000+08:00'
$null = @(New-AttendancePlan $snapshot @('K001,1', 'K003,2'))

$testWorkspace = Join-Path ([IO.Path]::GetTempPath()) ('erp-clock-test-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $testWorkspace
try {
    # 直接執行正式批次檔的亂數子程序，驗證 CMD 展開與呼叫行為。
    $batchSource = [IO.File]::ReadAllText((Join-Path $toolDirectory 'simulate-attendance.bat'))
    $subroutine = $batchSource.Substring($batchSource.IndexOf(":makeOffset`r`n"))
    $employees = @(1..22 | Where-Object { $_ -notin @(2, 20) } | ForEach-Object { 'K{0:000}' -f $_ })
    $driver = @('@echo off', 'setlocal DisableDelayedExpansion', ('set "SIM_WORK={0}"' -f $testWorkspace),
        'set /a SIM_OFFSET=0', 'type nul > "%SIM_WORK%\offsets.csv"')
    $driver += $employees | ForEach-Object { "call :makeOffset $_" }
    $driver += @('exit /b 0', $subroutine)
    $driverPath = Join-Path $testWorkspace 'random-test.bat'
    [IO.File]::WriteAllText($driverPath, ($driver -join "`r`n"), [Text.Encoding]::ASCII)
    & $env:ComSpec /d /c ('"' + $driverPath + '"')
    if ($LASTEXITCODE -ne 0) { throw '正式批次亂數子程序執行失敗。' }
    $snapshot.Start = '2026-11-07T08:00:00.0000000+08:00'
    $snapshot.Action = 'CLOCK_IN'
    $snapshot.Employees = $employees
    $snapshot | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $testWorkspace 'context.json') -Encoding UTF8
    $lines = [IO.File]::ReadAllLines((Join-Path $testWorkspace 'offsets.csv'))
    $plan = @(New-AttendancePlan $snapshot $lines)
    if ($plan.Count -ne 20) { throw '批次名單筆數錯誤。' }
    & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $scriptPath -Phase Apply -Workspace $testWorkspace -Preview
    if ($LASTEXITCODE -ne 0) { throw '離線預覽流程失敗。' }
} finally {
    foreach ($fileName in @('random-test.bat', 'offsets.csv', 'context.json')) {
        $path = Join-Path $testWorkspace $fileName
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path }
    }
    Remove-Item -LiteralPath $testWorkspace
}
Write-Output 'PASS: 時間、UTC、上午／下午界線、排除／錯誤資料、跨日、20 位員工批次亂數與離線預覽。'
