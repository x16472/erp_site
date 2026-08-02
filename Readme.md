# 福祿貝爾營運中心

福祿貝爾營運中心是一套前後端分離的幼稚園網站與園務入口。系統包含對外官方網站、全體員工入口、營運資料蒐集、教育訓練、休閒專區及受登入保護的 MIS 管理中心；後端透過 `pyodbc` 實際查詢 SQL Server，並依資料敏感度限制查閱範圍。

## 網站角色

| 頁面 | 對象與用途 |
| --- | --- |
| `index.html` | 對外官方網站，呈現教育理念、園區規模與參觀資訊 |
| `home.html` | 全體員工入口，提供園務摘要、公告、快速功能與知識搜尋 |
| `sales.html` | 員工營運蒐集，受理出勤、班級、接送、收費、設備及餐點紀錄 |
| `exam.html` | 員工教育訓練，題庫由後端提供 |
| `game.html` | 員工休閒專區 |
| `mis.html` | MIS 管理中心，登入後管理官網內容、唯讀查閱資料表與檢視待處理紀錄 |

所有頁面共用一致的導覽與視覺語言，圖檔只使用 `static` 資料夾內的資源。官方網站支援海洋、晨光與森林三種主題，管理員儲存後即可由資料庫設定套用。

## 實際資料來源

`data.py` 讀取既有 `.env` 連線資訊並連接 SQL Server，不會建立或修改 `.env`。園務摘要主要使用：

- `學籍資料`：幼兒學籍彙總。
- `班別名稱`：班級代號、名稱與園區。
- `ALLtable`：教職員整合主檔與部門彙總。
- `搭交通車況`：接送服務彙總。
- `分校資料`：園區代號與人力彙總。
- `繳費類別`、`繳費項目`、`繳費班別`、`繳費記錄`、`繳費明細`：托育收費流程。

MIS 管理中心可查閱其他使用者資料表。後端會先比對 SQL Server 中繼資料、限制每頁筆數，並遮罩兒少、聯絡、證件、銀行、薪資、保險及稅務等敏感資料。前端不能送入任意 SQL，也沒有任意資料表編輯功能。

## 管理端與寫入範圍

管理端帳號由 `.env` 的 `BackendWebAdminUser` 與 `BackendWebAdminPassword` 提供，密碼只在伺服器端比對，不會傳送到前端。登入工作階段有效時間為 8 小時，並具有 HttpOnly、SameSite Cookie、CSRF 驗證及登入失敗頻率限制。

資料寫入嚴格限制為兩類：

1. 官網版型與文字設定只會寫入專案專用的 `dbo.Frobel_WebSettings`。此資料表會在管理員第一次儲存設定時建立，其他既有資料表仍為唯讀。
2. 員工營運蒐集先寫入 `data/operation_submissions.json` 待 MIS 查核，不直接修改正式園務資料庫；檔案已加入 `.gitignore`，避免營運紀錄被提交到版本庫。

## 專案結構

| 檔案 | 用途 |
| --- | --- |
| `app.py` | HTTP 服務、路由、管理端工作階段與 JSON API |
| `data.py` | SQL Server 連線、唯讀查詢、資料遮罩與官網設定寫入 |
| `input.py` | 營運資料驗證與待處理佇列 |
| `style.css` | 官方網站、員工入口及管理中心共用樣式 |
| `database.md` | 資料庫連線、安全範圍與部署注意事項 |
| `site.md` | 頁面資訊架構、角色與操作流程 |

## 安裝與啟動

建議使用 Visual Studio Code 開啟專案，並確認電腦已安裝 Microsoft ODBC Driver 17 for SQL Server。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

啟動後開啟 `http://127.0.0.1:8000`。請勿直接以檔案模式開啟 HTML，否則頁面無法呼叫後端 API。

## API 摘要

| 路徑 | 權限 | 說明 |
| --- | --- | --- |
| `GET /api/public` | 公開 | 官網文字、主題與公開彙總 |
| `GET /api/dashboard` | 員工入口 | 園務彙總與班級摘要 |
| `GET /api/knowledge` | 員工入口 | 園務知識內容 |
| `GET /api/operations` | 員工入口 | 營運流程說明 |
| `POST /api/operations/submit` | 員工入口 | 新增待 MIS 查核的營運紀錄 |
| `POST /api/admin/login` | 公開 | 建立 MIS 管理工作階段 |
| `GET /api/admin/catalog` | 管理員 | 取得資料表目錄 |
| `GET /api/admin/table?name=...` | 管理員 | 取得遮罩後的分頁資料 |
| `GET/POST /api/admin/settings` | 管理員 | 讀取或儲存官網設定 |
| `GET /api/admin/submissions` | 管理員 | 檢視待查核營運紀錄 |

## 上線注意事項

- 正式環境應透過反向代理啟用 HTTPS，並將管理 Cookie 加上 Secure 屬性。
- 園務唯讀查詢與官網設定寫入最好使用不同的最小權限資料庫帳號。
- 目前登入工作階段存放在單一 Python 程序記憶體；多主機部署時應改用集中式工作階段儲存。
- 上線前應由園方依兒少資料政策覆核欄位遮罩規則、網路來源限制與存取稽核。

## 本次改版總結

本次改版將原有資料展示頁重整為符合幼稚園實務的分眾平台：對外官網強化教育品牌與招生入口，員工端聚焦日常園務，MIS 端加入實際登入、受控資料查閱與官網內容管理。後端保留 SQL Server 真實資料串接，同時以白名單寫入、敏感資料遮罩及待查核佇列降低誤改正式資料的風險。
