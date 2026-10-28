# 前端版面與主題維護

所有頁面共用 `page/static/style.css`，並在樣式表之前載入 `page/static/theme.js`，避免載入時閃現錯誤的色彩模式。

## 頁面結構

以 `workflow.html` 為基準：`portal-shell` 包含側欄 `portal-sidebar` 與主區 `portal-main`；主區依序放置 `portal-topbar`、`portal-content`。官網使用同一套框架的無側欄配置，員工登入頁使用相同的側欄與頂列。

多欄操作區以 `staff.html` 的員工管理配置為基準，加入 `workspace-layout` 共用外框、分隔線與面板。`portal-grid` 使用等寬雙欄；首欄為 `narrow` 時採左側工具欄與右側內容，首欄為 `wide` 時則反向排列。表單、清單、篩選與明細的既有 ID 保留。

## 色彩與共用參數

色彩、陰影、圓角、側欄寬度、內容與面板間距集中在 CSS 開頭的 `:root`。新增介面使用 `--surface`、`--surface-subtle`、`--ink`、`--muted`、`--line` 等語意變數；品牌區使用 `--brand-deep`、`--on-brand`，避免將固定白色直接用在一般介面。

深色模式透過根元素的 `data-color-mode="dark"` 覆寫參數。官網既有的 `body[data-theme]` 是品牌配色，與深淺色模式分開。首次使用依系統偏好，手動選擇後存入 `localStorage` 的 `erp-color-mode`，跨頁、重新載入與其他已開啟的分頁同步。儲存空間不可用時，仍可在目前頁面切換。

## 響應式配置

共用斷點集中在樣式表末端：

- 980px 以下：側欄轉上方橫向導覽，多欄工作區上下堆疊，保留表格容器內捲動。
- 680px 以下：表單改為單欄、頂列分頁獨占一列、按鈕群組換行，員工名冊與資料表不撐開整頁。
- 超過 980px：沿用桌面側欄與多欄工作區。

新增寬表格應放在 `.table-scroll` 或 `.staff-table-scroll` 等可捲動容器內，不要隱藏整頁溢位以掩蓋內容裁切。工作面板的文字表格使用 `.workflow-table-scroll`，儲存格允許換行。
