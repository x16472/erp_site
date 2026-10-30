# 資料庫共通規範
## 資料庫連接規範
- 資料庫工具 : Microsoft SQL Server Docker Image（mcr.microsoft.com/mssql/server:2025-latest）
- 資料庫伺器 : 10.10.0.4:1433
- 資料庫位置 : /srv/dev-disk-by-uuid-e508bb33-1bb6-4daa-ad93-08f1edae1580/Data/mssql_data
- 資料庫名稱 : Company
- 登入帳號 : sa
- 登入密碼 : ZZZaaa926473

## SQL 指令檔規範
- 資料表的 SQL 指令檔規範放在專案的 database 資料夾下方
- 資料表建置的檔案名稱為 CreateTables.sql
- 範例資料建置的檔案名稱為 SeedData.sql

## 資料表設計規範
- 表格名稱使用駝峰命名法（Camel Case）
- 表格名稱使用複數化命名規範，如客戶基本資料為 Customers

## 資料表欄位設計規範
### 欄位通用設計規範
- 所有資料表：主索引鍵固定為 Id INT IDENTITY(1,1) PRIMARY KEY。
- 最後第二個欄位固定為 Remark NVARCHAR(250) NULL
- 最後第一個欄位固定為 CreateTime Datetime2 NULL , 預設值為 getdate()
### 欄位命名設計規範
- 欄位名稱使用駝峰命名法（Camel Case）
- 主檔資料表(如公司、部門、職稱、員工、...) ，每個主檔均有全域唯一的 ...No NVARCHAR(50) 編號欄位 (如 EmployeeNo)。
- 表單資料表(如公加班單、請假單、採購單、...) ，表單主檔的單據編號固定為 SheetNo , 單據日期固定為 SheetDate
- 不要使用 SQL 的關鍵字來命名(如 Name 、 Date 、 ...) , 使用如 EmployeeName 、PurchaseDate、... 來命名
### 欄位 Null 值設計規範
- 主索鍵欄位一律不允許 Null
- 除了主索鍵欄位外其它欄位一律允許 Null , Null值問題由程式來控制
### 欄位關聯設計規範
- 交易檔關聯主檔時使用主檔編號欄位，並建立對應外鍵，不使用主檔 Id。
- 交易檔彼此關聯時可使用 Id；本系統的刷卡記錄以 WorkScheduleId 關聯排班 Id。
- 未來若增加請假單、加班單等表單：單據主檔以 Id 為主鍵，另設唯一單號。
- 單據明細以 {單據主檔名稱}Id 關聯單據主檔 Id。
- 單據主檔或明細關聯員工、公司等主檔時，仍使用主檔編號。
### 文字型別欄位設計規範
- 所有文字欄位只使用 NVARCHAR：預估長度不超過 50：NVARCHAR(50)。
- 超過 50、但不超過 250：NVARCHAR(250)。
- 超過 250 或無法合理預估：NVARCHAR(MAX)。
- 設定預設值為 space(0)
### 整數型別欄位設計規範
- 一律使用 INT
- 設定預設值為 0
### 小數型別欄位設計規範
- 除了特例外一律使用 DECIMAL(18,4)
- 經緯度欄位一律使用 DECIMAL(18,15)
- 設定預設值為 0
### 布林型別欄位設計規範
- 一律使用 BIT
- 命名規則為 Is 開頭 + 欄位功能 , 如:是否結案為 IsClose
- 設定預設值為 0
### 日期型別欄位設計規範
- 一律使用 DATE
- 如果需要記錄日期時間一律使用 DATETIME2
