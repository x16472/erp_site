# 前端版面與主題維護

所有頁面共用 `page/static/css/style.css`，並在樣式表之前載入 `page/static/js/theme.js`，避免載入時閃現錯誤的色彩模式。

## 靜態資源路徑

- 樣式表放在 `page/static/css/`；頁面腳本、共用模組及 Worker 放在 `page/static/js/`。
- HTML 使用 `./static/css/style.css` 與 `./static/js/theme.js` 等路徑；各頁模組同樣從 `./static/js/` 載入。
- 同目錄 JavaScript 模組使用 `./script.js` 等相對 import；Python 與 Go 的 Worker 也由腳本所在目錄解析。
- CSS 的圖片網址相對於 CSS 檔案位置，例如共用背景使用 `url("../appicon.png")`；HTML 或動態插入 HTML 的圖片網址則相對於頁面。
- Go Worker 使用 `../golang-runtime/` 載入 WASM 與配套 `wasm_exec.js`，執行資源保留在 `page/static/golang-runtime/`。
- Go 的 `/style.css` 相容路由對應 `page/static/css/style.css`；新增或修改引用時，檔名大小寫須與檔案一致，以支援 Linux 部署。

桌面與手機載入相同的基礎 CSS、主題腳本與頁面模組。驗收手機版時，除檢查 viewport 與響應式斷點，也應在瀏覽器網路面板確認這些資源、模組及圖片沒有 404，並分別檢查深淺色模式。

## 頁面結構

以 `workflow.html` 為基準：`portal-shell` 包含側欄 `portal-sidebar` 與主區 `portal-main`；主區依序放置 `portal-topbar`、`portal-content`。官網使用同一套框架的無側欄配置，員工登入頁使用相同的側欄與頂列。

多欄操作區以 `staff.html` 的員工管理配置為基準，加入 `workspace-layout` 共用外框、分隔線與面板。`portal-grid` 使用等寬雙欄；首欄為 `narrow` 時採左側工具欄與右側內容，首欄為 `wide` 時則反向排列。表單、清單、篩選與明細的既有 ID 保留。

## 色彩與共用參數

色彩、陰影、圓角、側欄寬度、內容與面板間距集中在 CSS 開頭的 `:root`。新增介面使用 `--surface`、`--surface-subtle`、`--ink`、`--muted`、`--line` 等語意變數；品牌區使用 `--brand-deep`、`--on-brand`，避免將固定白色直接用在一般介面。

深色模式透過根元素的 `data-color-mode="dark"` 覆寫參數。官網既有的 `body[data-theme]` 是品牌配色，與深淺色模式分開。首次使用依系統偏好，手動選擇後存入 `localStorage` 的 `erp-color-mode`，跨頁、重新載入與其他已開啟的分頁同步。儲存空間不可用時，仍可在目前頁面切換。

## 響應式配置

共用斷點集中在樣式表末端：

- 679px 以下：表單改為單欄、頂列分頁獨占一列、按鈕群組換行，員工名冊與資料表不撐開整頁。
- 680px~980px 以下：側欄轉上方橫向導覽，多欄工作區上下堆疊，保留表格容器內捲動。
- 超過 980px：沿用桌面側欄與多欄工作區。

新增寬表格應放在 `.table-scroll` 或 `.staff-table-scroll` 等可捲動容器內，不要隱藏整頁溢位以掩蓋內容裁切。工作面板的文字表格使用 `.workflow-table-scroll`，儲存格允許換行。
