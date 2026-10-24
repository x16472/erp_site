# 全域專案資安與效能複查驗證報告 (Security & Performance Verification Report)

> **審查日期**：2026-10-02  
> **系統名稱**：銀盾共同體 ERP 系統 (Silver Shield ERP Site)  
> **參照基準**：[`security_performance_audit.md`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/.agents/security_performance_audit.md)  
> **執行狀態**：全項通過 (All Passed)

---

## 一、 審查背景與目標

本報告針對 [`.agents/security_performance_audit.md`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/.agents/security_performance_audit.md) 記載之各項資安風險（SQL Injection、XSS、CSRF、權限控制、Path Traversal）及效能瓶頸（連線建立、磁碟 IO、Regex 編譯、SQL 批次寫入、冗餘程式碼），對專案程式碼進行全域檢驗與實測驗證。

---

## 二、 資安漏洞檢測與防禦現狀 (Security Audit)

### 1. SQL 注入攻擊 (SQL Injection) ── 【安全無漏洞】
* **檢驗標的**：
  * [`backend/data.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/data.py) - `_fetch()`、CRUD 操作、動態查詢
  * [`backend/input.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/input.py) - 參數過濾與型別檢查
* **防禦現狀**：
  * **參數化查詢**：所有資料庫讀寫函式（如 `_fetch()`、`add_operation()`、`save_staff()` 等）均採用標準的參數綁定（`?` 佔位符），徹底隔絕 SQL 注入。
  * **動態表名與排序**：`APPLICATION_TABLES` 白名單檢驗與 `_quote_identifier()` 轉義保護；員工排序使用 `_staff_order()` 白名單過濾。
  * **動態 `IN` 佔位符**：[`_published_question_rows()`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/data.py#L1369-L1397) 與 [`update_training_questions_bulk()`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/data.py#L2202-L2224) 中的 `IN (?, ?, ?)` 佔位符由內部固定欄位名稱生成，傳入參數在 [`backend/input.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/input.py#L335-L346) 經 `_positive_int_list` 強制轉型為 `int`，杜絕注入風險。

---

### 2. XSS 跨站腳本攻擊 (Cross-Site Scripting) ── 【安全 / 防護完整】
* **檢驗標的**：
  * [`page/static/script.js`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/page/static/script.js) - `escapeHtml()` / `esc()`
  * [`page/static/mis.js`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/page/static/mis.js)、[`page/static/exam.js`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/page/static/exam.js)、[`page/static/sales.js`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/page/static/sales.js)
* **防禦現狀**：
  * 前端所有動態文字渲染與換行轉換（`replace(/\n/g, '<br>')`）皆預先經過 `esc()` 進行 HTML 實體轉義。
  * 題幹內容採用後端結構化 JSON (`stem_blocks` / `content_blocks`) 區分程式碼區塊與文字區塊，由前端分別建立節點渲染，避免產生未轉義的任意 HTML 標籤。

---

### 3. CSRF 跨站請求偽造與身份驗證控管 ── 【安全 / 控管嚴格】
* **檢驗標的**：
  * [`backend/app.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/app.py) - `require_csrf()`、`require_admin()`、`require_employee()`、API 端點
* **防禦現狀**：
  * **防時序攻擊**：[`require_csrf()`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/app.py#L160-L165) 使用 `hmac.compare_digest` 進行常數時間比對。
  * **CSRF 檢查全面覆蓋**：所有狀態變更 API（包括 `POST /api/youtube/resolve`、日報送審、打卡、題庫編輯等）均已調用 `require_csrf()`。
  * **權限與 Session**：管理員 API 嚴格檢驗 `session.get("employee_id") == employee_session["employee_id"]`，防止跨帳號越權；Cookie 設定 `HttpOnly; SameSite=Strict`。

---

### 4. 目錄穿越與檔案存取 (Path Traversal) ── 【安全無漏洞】
* **檢驗標的**：
  * [`backend/app.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/app.py) - 靜態檔案分發與員工照片儲存
* **防禦現狀**：
  * 靜態資源路由解析時皆使用 `.resolve()`，並嚴格確認 `STATIC_ROOT in target.parents`，防止利用 `../` 突破靜態目錄存取系統檔案。

---

## 三、 效能瓶頸優化與代碼整潔度複查 (Performance & Code Quality)

### 1. 資料庫連線複用 (Connection Reuse) ── 【已優化】
* **實作位置**：[`backend/data.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/data.py#L86-L117) 與 [`backend/app.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/app.py#L76-L79)
* **優化成效**：
  * 實作 `connection_scope()` 上下文管理器與 `_REQUEST_CONNECTIONS` 執行緒局部變數儲存。
  * 在 HTTP Handler `handle_one_request()` 中自動建立 Scope，使單一請求內多次查詢（如 `training_catalog`）共用相同連線，請求結束後集中關閉，大幅消除 TCP/ODBC 連線握手延遲。

---

### 2. 員工 CSV 同步機制快取 (CSV Sync Optimization) ── 【已優化】
* **實作位置**：[`backend/data.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/data.py#L879-L907)
* **優化成效**：
  * 引入 `STAFF_SYNC_INTERVAL_SECONDS = 30` 秒時間快取與雙重檢查鎖定（Double-Checked Locking）。
  * 避免高頻率呼叫公開 API（如 `public_staff`、`public_staff_departments`）時重複進行 `stat()` 磁碟讀取與資料庫比對。

---

### 3. Regex 預先編譯與 SQL 批次寫入 (Batching & Pre-compilation) ── 【已優化】
* **實作位置**：
  * [`backend/doc.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/doc.py#L46-L50) - `QUESTION_CODE_PATTERN` 提升至模組頂層編譯。
  * [`backend/data.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/data.py#L1867-L1885) - `import_training_question_drafts` 改用 `cursor.executemany()`。
  * [`backend/data.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/data.py#L1670-L1675) - `submit_training_session` 交卷與錯題記錄改用批次 `executemany()`。
* **優化成效**：
  * 消除迴圈重複編譯正規表達式之開銷。
  * 大幅減少批次題目匯入與測驗交卷時的 SQL 網路往返（Round-trip）次數。

---

### 4. 冗餘程式碼清理 (Dead Code Removal) ── 【已優化】
* **實作位置**：
  * [`backend/data.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/data.py#L407-L409) - 清理 `_default_questions()` 舊版註解殘留代碼。
  * [`backend/app.py`](file:///E:/0.Data_Doc/0.Doc/Github/erp_site/backend/app.py#L118-L136) - 提煉 `_active_session()` 通用函式，消除重複的 Cookie 檢驗與過期刷新邏輯。

---

## 四、 測試驗證結果 (Automated Testing)

執行專案自動化單元測試套件：
* **測試指令**：`.venv\Scripts\python.exe -m unittest discover -s test -p "*.py"`
* **測試項目**：
  1. `test_choice_question_is_split_into_structured_fields`
  2. `test_question_without_answer_stays_reviewable_draft`
  3. `test_missing_ocr_is_reported_as_source_failure`
  4. `test_multiline_question_is_merged`
  5. `test_academic_and_practical_split`
  6. `test_exam_scoring_and_wrong_recording`
  7. `test_input_validation_boundary`
  8. `test_csrf_token_timing_safe_compare`
  9. `test_connection_scope_lifecycle`
* **執行結果**：
  ```text
  .........
  ----------------------------------------------------------------------
  Ran 9 tests in 0.005s

  OK
  ```

---

## 五、 結論與建議

1. **資安狀態**：系統各防禦環節均已落實，未發現高/中度資安漏洞。
2. **效能狀態**：已建立資料庫連線複用、IO 快取與批次 SQL 處理，大幅提升系統回應效能。
3. **後續維護建議**：
   * 持續維護 `test/` 單元測試覆蓋率。
   * 新增 API 時遵循既有的 `require_employee` / `require_csrf` 模式。
