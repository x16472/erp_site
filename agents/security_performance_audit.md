# 全域專案資安漏洞與效能審查報告

本文件紀錄專案（銀盾共同體 ERP 系統）針對資安漏洞（SQL 注入、XSS、CSRF、權限控管、檔案存取）以及程式碼效能與冗詞贅字語法的全域審查結果與優化建議。

---

# 一、 資安漏洞檢測報告 (Security Audit)

## 1. SQL 注入攻擊 (SQL Injection) ── 【低風險 / 安全控制良好】
* **防禦現狀**：
  * 後端在 [`backend/data.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/data.py#L91-L98) 的 `_fetch()` 及大多數資料庫操作中，均採用標準的**參數化查詢（Parameter Binding `?`）**，能有效防範 SQL 注入。
  * 對於無法使用參數綁定的動態表名與排序（如 [`table_data`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/data.py#L192) 及 `_staff_order`），系統使用了嚴格的白名單 `APPLICATION_TABLES` 校驗與 `_quote_identifier()` 中括號轉義保護，阻止了表名注入。
* **改進建議**：
  * 在 [`backend/data.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/data.py#L1335-L1342) 的 `_published_question_rows()` 與 `update_training_questions_bulk()` 中，採用了動態拼接 `IN (?, ?, ?)` 佔位符。雖然傳入的參數均已經過 [`backend/input.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/input.py#L335) `_positive_int_list` 的 `int` 型態強制轉型，仍建議保持此嚴格型別過濾。

---

## 2. XSS 跨站腳本攻擊 (Cross-Site Scripting) ── 【中低風險 / 已有基本防護】
* **防禦現狀**：
  * 前端工具庫 [`page/static/script.js`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/page/static/script.js#L5-L9) 提供了 `escapeHtml()` 轉義函式。
  * 在 [`page/static/mis.js`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/page/static/mis.js#L464) 與 [`page/static/exam.js`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/page/static/exam.js#L36) 等處處理換行 `replace(/\n/g, '<br>')` 時，均先執行了 `esc(text)` HTML 轉義，防止了插入 `<script>` 或惡意 HTML 標籤。
* **改進建議**：
  * 前端多處（如 `index.js`、`sales.js`）大量使用 `innerHTML` 模板字串拼接。雖然動態變數皆已包裹 `esc()`，長遠維護建議逐步改用 DOM API（如 `textContent` 或 `element.replaceChildren()`），從根本上杜絕 DOM-based XSS 的可能性。

---

## 3. CSRF 與身份驗證控管 ── 【安全控制良好】
* **防禦現狀**：
  * [`backend/app.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/app.py#L163-L168) 的 `require_csrf()` 使用 `hmac.compare_digest` 比對 CSRF Token，防止了時序攻擊（Timing Attacks）。
  * 所有狀態變更（POST / DELETE）端點皆有強制檢查 CSRF Token，且 Cookie 設置了 `HttpOnly; SameSite=Strict`。
  * 管理員權限在 [`backend/app.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/app.py#L141-L146) 中嚴格綁定當前登入之員工 Session (`session.get("employee_id") == employee_session["employee_id"]`)，防止越權操作。
* **小細節提醒**：
  * `POST /api/youtube/resolve` 未調用 `require_csrf()`。雖然該 API 在 [`backend/input.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/input.py#L554) 中已鎖定 11 位字元英數符號的 YouTube ID（不會引發任意 SSRF），但仍建議補上 CSRF 驗證。

---

## 4. 路徑穿越與檔案存取 (Path Traversal) ── 【低風險 / 已妥善防禦】
* **防禦現狀**：
  * 靜態檔案與員工照片讀取/儲存（如 [`backend/app.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/app.py#L655-L661) `save_staff_photo` 及 `send_file`）均使用了 `.resolve()` 並檢查 `STATIC_ROOT in target.parents`，能有效防止利用 `../` 讀取系統敏感檔案。

---

# 二、效能瓶頸與冗詞贅字語法審查 (Performance & Code Cleanliness)

## 1.資料庫連線頻繁建立與釋放 ── 【主要效能瓶頸】
* **問題**：在 [`backend/data.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/data.py#L94) 的 `_fetch()` 及多數查詢函式中，每次執行查詢都會調用 `connect()` 重新與 SQL Server 建立 TCP + ODBC 連線。
* **影響**：以 `training_catalog()` 視圖為例，一次 HTTP 請求會連續開啟與關閉 **6 次**資料庫連線，帶來極大的網路往返延遲（RTT Latency）及 Socket 連線數耗盡風險。
* **優化建議**：建議採用資料庫連線池（Connection Pool）或在單一 HTTP 請求的上下文中複用同一個連線物件。

---

## 2.每次 API 請求皆重複進行 Disk IO 與 CSV 同步 ── 【重複計算浪費】
* **問題**：`public_staff()`、`public_staff_departments()`、`attendance_staff_options()`、`staff_records()`、`employee_identity()` 等多個 API，每次被觸發時都會呼叫 `sync_staff_csv()`。
* **影響**：每次呼叫都會對 `data/staff.csv` 進行 `stat()` 檔案狀態檢查與資料庫比對，造成昂貴的磁碟 IO 與線程鎖爭用（`STAFF_SYNC_LOCK`）。
* **優化建議**：對 CSV 狀態加上定時快取（例如 30 秒內僅檢查一次），減少頻繁的檔案與資料庫比對。

---

## 3.迴圈內重複編譯 Regex 與逐筆 SQL 執行 ── 【計算浪費與迴圈效能低落】
* **問題 A（Regex 重複編譯）**：在 [`backend/doc.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/doc.py#L509-L513) 的 `_question_content_blocks()` 函式內部，每次被呼叫時都會執行 `code_pattern = re.compile(...)` 重新編譯正規表示式。
  * **優化**：將 `code_pattern` 提升至模組頂層（Module Level Constant），僅編譯一次。
* **問題 B（迴圈逐筆 SQL 寫入）**：在 [`backend/doc.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/doc.py#L696) `import_training_question_drafts` 與 [`backend/data.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/data.py#L1611-L1622) `submit_training_session` 中，針對陣列資料採用 `for` 迴圈逐筆執行 `cursor.execute(...)`。
  * **優化**：改用 `cursor.executemany()` 或批次 SQL 語法，可提升數倍寫入效能。

---

## 4.冗餘程式碼與死碼 (Dead Code & Redundancy)
* **註解死碼**：[`backend/data.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/data.py#L369-L384) 中的 `_default_questions()` 包含大量已被註解說明的死碼，建議清理以保持程式碼整潔。
* **重複邏輯**：[`backend/app.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/app.py#L113-L139) 中的 `session()` 與 `employee_session()` 存在高度相同的 Cookie 解析與 Session 過期檢查邏輯，可抽離成通用的 Helper 函式。

---

# 三、優化行動總結 (Action Items)

1. **引入資料庫連線複用/連線池**（解決 API 回應延遲的主要因素）。
2. **優化 CSV 檔案同步的頻率與快取**（降低磁碟與鎖的爭用）。
3. **將迴圈內的 Regex 編譯提升至全域**，並將逐筆 SQL 執行改為批次寫入。

# 四、彙整摘要

1. 資安防護：系統在 SQL 參數化查詢、XSS HTML 轉義、CSRF Token 校驗與防路徑穿越方面均具備良好的防禦基礎。
2. 效能優化：提出了資料庫連線池、降低 CSV 檔案同步存取頻率、提升迴圈內 Regex 編譯至全域以及批次 SQL 寫入等優化方針。

# 五、補充

本節補足前述審查尚未涵蓋的稽核基準、安全面向、效能量測與驗收追蹤要求。後續每次重新審查時，應連同本節一併執行，避免報告只保留單次檢查結論而無法重現或驗收。

## 1. 稽核基本資料與可追溯性

每次審查應記錄下列資料：

- 審查日期、審查人員與使用的檢查工具。
- Git commit、分支、Python／ODBC／SQL Server 版本及部署環境。
- 納入與排除審查的目錄、端點、資料表及外部服務。
- 測試資料量、並行請求數、網路條件與硬體規格。
- 每項發現的證據、影響範圍、修正狀態與重新驗證日期。

原有的 `file:///E:/...` 絕對路徑及固定行號只適用於單一工作環境，後續應優先以專案相對路徑與函式名稱識別程式位置。若保留行號，重新審查時必須一併更新。

## 2. 風險分級標準

- 嚴重：可在未授權情況下執行任意程式、取得大量敏感資料、接管管理員權限，或造成服務全面中斷。
- 高：可跨使用者存取或修改資料、繞過主要驗證、持續消耗關鍵資源，或洩漏重要機密。
- 中：需要特定前置條件才能利用，影響範圍有限，或已有部分緩解措施但仍可能造成資料與服務風險。
- 低：目前難以直接利用，主要屬於強化、防禦縱深、維護性或有限度效能問題。

每項風險應同時記錄利用條件、可能影響、現有控制、殘餘風險及處理優先順序，不能只以「安全控制良好」作為結論。

## 3. 身分驗證、Session 與 Cookie

- 建立公開、員工及管理員 API 權限矩陣，逐一測試未登入、一般員工、其他員工與管理員身分，防止 IDOR 或水平越權。
- 檢查登入前後是否重新產生 Session Token、登出後伺服器端 Session 是否失效，以及過期 Session 是否會定期清除。
- 分別檢查登入、員工登出、管理員登出及其他狀態變更端點的 CSRF 防護；不可概括宣稱所有 POST／DELETE 都已驗證。
- Cookie 除 `HttpOnly` 與 `SameSite=Strict` 外，正式 HTTPS 環境應設定 `Secure`。若 TLS 在反向代理終止，應確認應用程式仍能正確套用安全 Cookie。
- 登入限流應驗證反向代理後的用戶端 IP 判定、紀錄過期清理、多人共用 IP 的誤封鎖，以及攻擊者建立大量不同鍵值造成記憶體耗盡的可能性。

## 4. HTTP、瀏覽器與輸出安全

- 檢查 Content Security Policy、Strict-Transport-Security、Permissions-Policy、Referrer-Policy、X-Content-Type-Options 與防點擊劫持設定。
- 盤點所有 `innerHTML`、URL、HTML 屬性與樣式插入點，記錄資料來源及對應編碼方式；不能只抽樣後推定所有動態內容皆已轉義。
- 逐項測試 HTML、JavaScript、URL、事件屬性、SVG 與換行轉換等 XSS 載荷，並優先以 `textContent`、`replaceChildren()` 或安全 DOM API 取代字串模板。
- 檢查錯誤回應及伺服器日誌不會洩漏 SQL、檔案路徑、帳密、Session Token、CSRF Token 或個人資料。
- 確認 CORS、Host Header、Content-Type、Content-Length、請求逾時與最大請求大小均有明確限制。

## 5. 外部連線、SSRF 與檔案處理

- YouTube 解析的主要 SSRF 防線是伺服器只對固定的 YouTube oEmbed 端點發出請求，影片 ID 格式驗證屬於額外限制；仍應檢查重新導向、DNS 解析、回應大小及連線逾時。
- `send_file()` 本身只負責回傳檔案，路徑根目錄限制位於呼叫端；新增呼叫點時必須驗證解析後路徑仍位於允許的根目錄。
- 員工照片除副檔名與檔頭外，應測試畸形圖片、超大尺寸、解碼炸彈、重複上傳及同時寫入；暫存檔在失敗時必須清除。
- Word、Excel、PDF、OCR 與文件轉換應限制檔案大小、頁數、解壓後容量、執行時間及同時處理數，避免壓縮炸彈與 CPU／記憶體耗盡。
- 外部程式呼叫應持續使用固定參數陣列、逾時與受控工作目錄，不得拼接未驗證的 Shell 指令。

## 6. 機密資料、相依套件與資料庫權限

- 確認 `.env`、資料庫備份、匯入檔、日誌與暫存檔不會被 Git、靜態檔案服務或錯誤訊息公開。
- 資料庫帳號應採最小權限，將一般查詢、應用程式寫入與結構遷移權限分離；正式環境不得長期使用可任意建表或修改結構的帳號。
- 定期執行 Python 相依套件漏洞掃描，記錄 CVE、受影響版本、修正版本與例外接受原因。
- 應保存相依套件清單或 SBOM，並建立版本更新、退版與重大漏洞緊急更新流程。

## 7. 記憶體、快取與並行安全

- `SESSIONS`、`EMPLOYEE_SESSIONS`、登入失敗紀錄及 `YOUTUBE_CACHE` 等記憶體容器必須設定容量上限、TTL 或定期清理機制，並測試長時間執行後的記憶體使用量。
- 檢查多執行緒下的鎖定範圍、競態條件與鎖等待時間，避免在執行磁碟 IO、資料庫查詢或外部網路請求期間持有全域鎖。
- CSV 的 30 秒檢查快取應驗證首次啟動、檔案異動、讀取失敗、強制同步及多執行緒同時觸發情境；錯誤結果不得被當成成功狀態快取。
- 若未來改為多行程或多主機部署，需重新評估記憶體 Session、限流及快取的一致性，必要時改用具 TTL 的共享儲存。

## 8. 效能量測與資料庫檢查

效能問題必須提供改善前後的可重現數據，不應只以「可能提升數倍」作為驗收依據。至少記錄：

- 主要 API 的 p50、p95、p99 回應時間、錯誤率及每秒請求數。
- 每個請求建立的資料庫連線數、SQL 執行次數、交易時間與連線池等待時間。
- SQL Server 實際執行計畫、索引命中情形、掃描筆數、鎖等待及逾時紀錄。
- 不同員工、題目、文件與出勤資料量下的記憶體、CPU、磁碟與網路使用量。
- 文件匯入、OCR、題庫匯入及批次交卷在小量、一般量與上限資料量下的完成時間。

資料庫連線複用必須保持唯讀與寫入連線分離、交易提交與回復正確，並在請求完成或例外發生後釋放連線。批次 SQL 則需驗證空集合、部分失敗、重複資料及整批回復行為。

## 9. 現況校正與後續追蹤

截至 2026-10-02，本報告前述項目需補充下列狀態：

- `POST /api/youtube/resolve` 已加入員工 Session 與 CSRF 驗證，前端亦會送出 CSRF Token。
- 資料庫已加入單一 HTTP 請求範圍的連線複用與請求結束清理。
- 員工 CSV 已加入 30 秒成功檢查快取及鎖內再次檢查。
- 題目內容 Regex 已移至模組層級，交卷評分、錯題紀錄及題庫草稿寫入已改為批次處理。
- `session()` 與 `employee_session()` 的共用邏輯已抽離，`_default_questions()` 的註解死碼已清除。
- `import_training_question_drafts()` 實際位於 `backend/data.py`，不是 `backend/doc.py`。
- 目前 Session Cookie 尚未設定 `Secure`；員工及管理員登出端點也尚未個別執行 CSRF 驗證，應列為待評估項目。

## 10. 問題追蹤與驗收格式

後續每一項發現至少應記錄：

1. 問題編號、標題、風險等級與狀態。
2. 受影響的相對路徑、函式、API 或資料表。
3. 可重現步驟、輸入資料及實際結果。
4. 安全或效能影響與利用前置條件。
5. 修正方式、負責人及預定完成日期。
6. 單元測試、整合測試、負載測試或人工驗證證據。
7. 修正後結果、重新驗證日期及仍接受的殘餘風險。

問題只有在修正已部署至目標環境、相關測試通過，且未引入權限、交易、快取或效能回歸後，才能標記為完成。
