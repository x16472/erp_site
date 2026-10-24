# SQL Server 串接與資料治理
## 連線設定
`data.py` 只讀取專案既有 `.env`，不由程式建立、覆寫或輸出其中內容。目前 `DatabaseName` 已配合 PRD 更新為 `Company_New`。一般營運查詢使用唯讀連線意圖；只有 Company 應用資料表的維護功能會建立可寫入連線。

## 資料範圍
公開官網只取得專業成員、六個營運部門、營運SOP數量等彙總，以及經白名單篩選的員工基本介紹。員工入口提供營運摘要、營運SOP、合規題庫及打卡。完整資料表目錄、員工維護、出缺勤與待審紀錄只開放給已登入的 MIS 管理員。

管理端資料查閱只允許 10 張 `dbo.Company_*` 白名單資料表，會先比對 SQL Server 中繼資料、限制分頁筆數，並遮罩聯絡、證件、銀行、薪資、保險及稅務欄位。前端無法提交任意 SQL。

## 網站專用正規化資料表

| 資料表 | 用途與關聯 |
| --- | --- |
| `dbo.Company_WebSettings` | 官網主題、標題、副標題與公告 |
| `dbo.Company_Department` | 部門主檔；提供員工表單下拉選單、啟用狀態與部門維護 |
| `dbo.Company_Staff` | 員工主檔；員工編號為主鍵 |
| `dbo.Company_Attendance` | 上下班打卡；保存 UTC 時間、台灣工作日，並以員工編號外鍵連接員工主檔 |
| `dbo.Company_OperationCategory` | 營運資料分類主檔 |
| `dbo.Company_OperationSubmission` | 營運待審紀錄；以分類代碼連接分類主檔，並以 `submitted_by` 連接建立事項的員工 |
| `dbo.Company_OperationActivity` | 營運日報的送出、補件、回覆、核准及退回歷程 |
| `dbo.Company_TrainingDocument` | 營運SOP文件主檔、來源檔名與匯入狀態 |
| `dbo.Company_TrainingSection` | 營運SOP文件段落；以文件編號外鍵連接文件主檔 |
| `dbo.Company_TrainingQuestion` | 單選、多選、閱讀測驗與申論題庫，可選擇連接來源文件 |
| `dbo.Company_TrainingAnswer` | 申論題文字答案、人工審核狀態及管理員回饋 |
| `dbo.Company_ImportState` | 記錄 `staff.csv` 的修改時間、大小與匯入筆數，避免未變更時重複覆寫員工主檔 |

## 資料排序

所有資料表由 `data.ensure_application_schema()` 以個別 SQL 敘述建立，並設有主鍵、外鍵、唯一限制及必要的數值檢查。應用資料表初始化後才接受前端輸入。

員工管理主檔固定由 `data.py` 依員工編號排序，避免中文部門名稱受到定序規則影響。公開官網的專業團隊另由 `data.py` 提供部門清單與參數化篩選，部門選單只影響公開名單，不改變後台員工主檔順序。

## 輸入流程

```text
HTML 表單
  → app.py 接收 JSON
  → input.py 清理與驗證
  → data.py 使用參數化 SQL
  → dbo.Company_* 應用資料表
  → app.py 回傳必要結果
```

- 打卡只接受有效且啟用中的員工編號，以及 `CLOCK_IN`、`CLOCK_OUT` 兩種動作。
- 每個台灣工作日的第一筆必須是上班打卡，之後上、下班必須交替；後端以交易鎖定同一員工的請求，拒絕連續兩次相同類型的打卡，換日後則重新開始判定。
- 員工端只收到本次打卡動作與伺服器時間，不會取得個人出勤歷史。
- 員工入口提供「上班打卡並進入」與「不打卡進入系統」；兩者都必須通過 SQL Server 在職驗證。「不打卡進入」不新增出勤紀錄，只查詢當日最後一筆打卡並建立 HttpOnly 工作階段。
- 工作台會顯示當日打卡時間；未打卡時提供補打卡，打卡下班仍遵循上下班交替與防重複交易規則，離開系統則不異動出勤資料。
- `time_sync.py` 的 `time.now()` 以 SQL Server UTC 時間轉換為 `Taipei Standard Time`，同時產生 UTC、台灣工作日及 ISO 時間；打卡寫入與回傳使用同一時間快照。
- 登入頁與工作台透過 `/api/time` 計算網路往返時間，每 60 秒重新校正本機顯示時鐘；員工與管理頁面切換時也會重新查詢資料庫當日最後打卡。
- 員工資料新增、更新與停用必須通過 MIS 工作階段及 CSRF 驗證。
- 員工姓名、性別、年齡、部門及職位均為後端必填；性別採固定選項、年齡限制 16 至 100，部門必須存在於啟用中的部門主檔。
- 部門名稱由前後端共同限制為最多 5 個字；目前使用營運部、製造部、財務部、資訊部、福利部與後勤部。
- 員工文字資料經 `input.py` 驗證後寫入 `dbo.Company_Staff`；照片只接受 JPEG、PNG、WebP 且上限 5 MB，存於 `static/staff` 並以不可變更的員工編號命名。
- 員工停用採狀態更新，既有打卡紀錄仍保留。
- 營運輸入只接受既定分類、有效日期、營運據點代碼及限制範圍內的彙總數量。

### 檢閱*.csv
既然目前已做到正規化，那麼在每次更新時務必掃描[staff.csv](/data/staff.csv)是否有更新，除了手動輸入的手段之外，`*.csv`也是一個重要的輸入手段。

`data.py` 會在員工查閱、驗證與維護前檢查 CSV 的修改時間與檔案大小；有異動才以參數化 `MERGE` 合併資料。CSV 未列出的資料不會自動停用，管理員上傳的既有照片也不會被 CSV 覆寫。

## 營運SOP文件匯入
`doc.py` 掃描 `data/exam`：
1. 舊 `.doc` 優先由 LibreOffice 無介面轉成 `.docx` 快取；沒有 LibreOffice 時才使用 Microsoft Word COM 備援。
2. `python-docx` 讀取段落及表格，依標題與內容長度整理成查閱區塊。
3. 文件主檔、段落及題庫分開寫入正規化資料表。
4. 原始 `.doc` 不會被覆寫；轉換快取位於 `data/exam/.converted` 並由 Git 排除。
5. MIS 可重新同步、啟用或停用營運SOP文件，並可新增、更新及停用 `Company_TrainingQuestion` 題目。

## 正式環境建議

1. 將既有營運唯讀查詢與 `dbo.Company_*` 寫入拆分為不同的最小權限帳號。
2. 限制資料庫可連線的主機與來源 IP。
3. 以 HTTPS 反向代理服務網站，並設定 Secure Cookie。
4. 將工作階段與操作稽核移至可持久化的集中服務。
5. 定期依共同體員工、客戶與合作夥伴資料政策覆核公開欄位、遮罩與權限白名單。
