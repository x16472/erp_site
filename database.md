# SQL Server 串接與資料治理

## 連線設定

`data.py` 只讀取專案既有 `.env`，不會建立、覆寫或輸出其中的內容。使用的鍵值如下：

- `DatabaseIP`
- `DatabasePort`
- `DatabaseName`
- `DatabaseUser`
- `DatabasePassword`
- `DatabaseDriver`，未設定時使用 `ODBC Driver 17 for SQL Server`
- `BackendWebAdminUser`
- `BackendWebAdminPassword`

一般查詢連線帶有 `ApplicationIntent=ReadOnly`。只有管理員儲存官網設定時，才會建立可寫入連線。

## 查閱模式

公開官網只取得班級、園區與接送服務等彙總數量，不回傳個人明細。員工入口顯示園務摘要、班級與知識內容。完整資料表目錄及分頁查閱僅提供給已登入的 MIS 管理員。

管理端查閱流程：

1. 從 `INFORMATION_SCHEMA` 取得實際資料表與欄位。
2. 前端指定的資料表名稱必須與中繼資料完全一致。
3. 後端自行組合識別字，不接受任意 SQL。
4. 每次最多回傳 50 筆並進行敏感欄位遮罩。

證件、地址、電話、銀行、薪資、托育費用、津貼、保險、稅務，以及幼兒、家長、緊急聯絡人與接送人員等資料均受限制。薪資、銀行、健保、勞保、其他收入與異動金額相關資料表採整表限制。

## 寫入邊界

管理端不允許編輯既有園務資料表。唯一 SQL Server 寫入目標是 `dbo.Frobel_WebSettings`，其欄位為官網主題、主標、副標、公告及異動人員；資料表於管理員第一次儲存時建立。

員工從 `sales.html` 送出的營運紀錄，經 `input.py` 驗證後寫入本機 `data/operation_submissions.json`，供 MIS 頁面查閱。紀錄不會自動同步或回寫 SQL Server。

## 正式環境建議

1. 為查閱及官網設定分別建立最小權限帳號。
2. 限制資料庫可連線的主機與來源 IP。
3. 以 HTTPS 反向代理服務網站，並設定 Secure Cookie。
4. 將工作階段與操作稽核移至可持久化的集中服務。
5. 定期依園方兒少資料政策覆核遮罩與存取白名單。
