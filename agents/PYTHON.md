# Python 專案設計規範

## 主要開發技術棧
- Python 3.11
- pandas
- NumPy
- openpyxl / ClosedXML(Excel 讀寫)
- Matplotlib / Plotly(圖表視覺化)
- Jupyter Notebook(探索性分析)
- .venv(虛擬環境管理)

## 設計偏好
- 使用 `snake_case` 命名變數與函式
- 使用 `PascalCase` 命名類別
- 函式與參數優先加上型別註記(Type Hints)
- 資料處理流程優先使用 pandas 的向量化操作,避免逐列 for 迴圈
- 讀寫大型資料集優先使用 parquet,而非 csv
- 每個函式前加上簡短 docstring 說明用途、參數與回傳值
- 錯誤處理避免裸露的 except:,一律指定明確的例外類型

## 專案結構偏好
- 原始資料放 `data/raw/`,處理後資料放 `data/processed/`,兩者皆不進版控
- 可重用後端模組放 `backend/src/`，後端測試與工具分別放 `backend/tests/`、`backend/tools/`，不在根目錄另設程式資料夾
- 相依套件統一記錄於 `requirements.txt` 或 `pyproject.toml`