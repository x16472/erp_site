# Golang 專案設計規範

## 主要開發技術棧
- Go 1.23+
- encoding/csv / excelize (Excel 讀寫)
- gonum (數值計算與矩陣)
- gonum/plot 或 go-echarts (圖表視覺化)
- Go Modules (go.mod / go.sum 相依管理)
- 可選：dataframe-go 或 gopher-csv 等資料處理函式庫

## 設計偏好
- 使用 `camelCase` 命名未匯出變數與函式，`PascalCase` 命名匯出識別符
- 套件名稱一律使用小寫、簡短且有意義的單字（避免底線）
- 優先使用明確的型別，善用介面（interface）與泛型（generics）
- 資料處理優先使用切片（slice）與映射（map）的慣用寫法，避免不必要的指標與複雜巢狀迴圈
- 讀寫大型資料集優先使用 parquet（parquet-go）或高效二進位格式，而非純文字 csv
- 每個匯出函式與套件都加上 godoc 風格註解，說明用途、參數與回傳值
- 錯誤處理一律使用 `if err != nil` 模式，禁止忽略錯誤；必要時使用 `errors.Is` / `errors.As` 或自訂錯誤型別

## 專案結構偏好
- 原始資料放 `data/raw/`，處理後資料放 `data/processed/`，兩者皆不進版控（加入 .gitignore）
- 後端入口放 `backend/cmd/<app>/main.go`，共用後端邏輯放 `backend/internal/`，gRPC 契約放 `backend/rpc/`；資料庫存取與 SQL 統一放 `database/`
- 相依套件統一由 `go.mod` 與 `go.sum` 管理，使用 `go mod tidy` 保持乾淨