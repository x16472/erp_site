# 手動模擬上下班打卡

這是獨立工具，不啟動網站、不呼叫網站 API，也不併入主程式。需要 Windows PowerShell 5.1 與可連線的 SQL Server；不需 Go、Python 或 sqlcmd。

點兩下 `simulate-attendance.bat` 即可執行，結果視窗會保留。連線讀取專案根目錄既有 `.env`，不另外儲存帳密。兩個工具檔案須放在同一目錄；若搬離專案，請修改 PowerShell 的 `EnvPath` 預設路徑。

- 寫入 `dbo.AttendanceRecords`，員工來自 `dbo.Employees` 的在職名單，排除 K002、K020。
- 以按下執行時的本機時間為起點，12:00 前為 CLOCK_IN，12:00 起為 CLOCK_OUT。因此早上 8 點執行為上班，下午 5 點執行為下班；不另設 9 點或 17 點基準。
- 批次檔迴圈為第一位員工及其後每位員工累加 1～600 秒；立即整批寫入產生的時間，不等待實際時刻。若有 20 人，整批最晚可能延伸 200 分鐘；1～600 秒是相鄰員工的間隔。
- ClockedAt 使用本機日期時間，ClockedAtUtc 依本機時區轉換，WorkDate 使用當日本機日期。網站以台灣工作日呈現，執行電腦請使用台灣時區並校準時間。
- 已有當日同動作會略過；沒有當日上班紀錄時略過下班打卡；時間順序不符或員工已停用亦略過。每次最多補一組當日上下班，不模擬多次進出。
- SourceIp 寫入 SIMULATOR，Remark 註明模擬來源，CreateTime 沿用資料表預設值。
- 寫入前檢查目標欄位，使用參數與單一交易；SQL 執行失敗時回復整批。產生時間跨日則整批停止。連線中斷恰逢提交時須先查詢結果，重跑會略過已存在的動作。
- 不建立排程；需要上、下班資料時各手動執行一次。

若要先查看時間而不寫入，在此資料夾開啟命令提示字元執行：

```bat
simulate-attendance.bat --preview
```

預覽會連線讀取欄位與員工名單，但不寫入任何資料。正式執行會重新取當下時間及亂數，因此時間不會與預覽完全相同。

結果代碼：INSERTED 為已寫入；SKIP_DUPLICATE 為同日同動作已存在；SKIP_NO_CLOCK_IN 為尚未上班；SKIP_TIME_ORDER 為時間順序不符；SKIP_INACTIVE 為不適用員工。

離線回歸檢查可於專案根目錄執行，不連線資料庫：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File backend/tests/manual-attendance.tests.ps1
```
