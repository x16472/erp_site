# 前端版面與主題維護

所有頁面共用 `page/static/css/style.css`，HTML 唯一 JavaScript 入口為 `page/static/js/script.js`，使用 type="module"。入口先初始化 Theme 與分頁，再依 body 的 data-page 載入頁面控制器。ES Modules 在文件解析後執行，主題不再以獨立傳統 script 提前執行。

## 靜態資源路徑

- 樣式表放在 `page/static/css/`；頁面與共用模組放在 `page/static/js/`，Canvas 功能與 Worker 放在 `page/static/js/canvas/`。
- HTML 使用 `./static/css/style.css` 與唯一模組入口 `./static/js/script.js`；頁面不直接載入 theme.js 或功能模組。
- 共用 API 與 HTML 跳脫等函式從 `./api.js` 匯入，分頁從 `./panel.js` 匯入；功能模組不反向匯入啟動入口，避免循環。頁面控制器以物件 init 管理私有狀態與函式，重複 init 不會再綁事件。
- CSS 的圖片網址相對於 CSS 檔案位置，例如共用背景使用 `url("../appicon.png")`；HTML 或動態插入 HTML 的圖片網址則相對於頁面。
- Worker 使用 `new URL(..., import.meta.url)` 與 `type: module`；Python 載入固定版 pyodide.mjs，Go Worker 使用 `../../golang-runtime/` 載入 WASM 與配套 wasm_exec.js，執行資源仍在 `page/static/golang-runtime/`。
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

## 工作面板的穿越冒險

穿越冒險位於 `page/workflow.html` 的第五分頁 `section#pl5`，由 `panel.js` 與其他工作面板分頁共同控制顯示；`workflow.js` 組合 SD 工具、Canvas 及冒險控制器；`adventure.js` 以 ES Module 載入，首次切入才取得員工、世界與存檔資料。`game.html` 保留五個影音分頁，不載入冒險或俄羅斯方塊腳本。

存檔選擇區使用 `style.css` 的 `workflow-panel`；進入存檔後使用題庫維護及員工管理的 `staff-manager-workspace workspace-layout`，側欄沿用 `organization-pane`，主區沿用 `staff-master-detail`、`staff-directory-pane` 與 `staff-detail-pane`，分別顯示角色資訊、場景操作與敘事歷程。卡片、按鈕、表單與分頁沿用 `portal-card`、`card-head`、`btn`、`form-grid` 與 `admin-tabs`，不再引用 `adventure.css`。共用樣式表只補充 `pl5` 的排列、進度條、原生建立角色對話框及手機內容切換。MIS 的流程畫布仍使用 `adventure-editor.css`，維持原有縮放、節點與連線樣式。

## 教育訓練與 SOP

`exam.js` 管理學科、術科及 SOP 三個互斥分頁，切換後同步調整考試浮動工具。`manuals.js` 的 ManualReader 管理文件目錄、分類搜尋、章節與讀取狀態，文件內容以跳脫後的純文字呈現。快速切換文件或返回目錄時丟棄過期回應，失敗可按重新讀取重試。

MIS 題庫的檢視篩選與批次分類操作分開。先選科目才啟用章節，切換科目會清除章節與不再可見的批次勾選。題目 Id／QuestionNo 不顯示於清單、編輯提示或題庫資料表查閱；API 與 hidden／data 屬性保留操作識別，不能從畫面隱藏推論為權限控制。

新增 Canvas 遊戲可沿用 `canvas/setup.js` 的 CanvasSurface 取得畫筆，並由 Theme.colors() 讀取主題色；鍵盤事件須限制在自己的啟用分頁，切走時暫停，不在全域建立遊戲狀態。Python 與 Go Playground 只在對應分頁啟用後載入執行環境。

## 影音與工作面板的載入行為

`panel.js` 完成顯示切換後發出 panelchange，影音與工作面板依目標分頁更新。workflow.js 只載入目前開啟的工具模組，各分頁初始化失敗互不阻擋；Go／Python 的實際執行環境狀態顯示於各自面板。穿越冒險的頭像為選用元素，缺少圖片區域時仍可呈現角色與存檔。

影音頁五個平台使用相同的請求與播放器生命週期。首次開啟分頁會載入保存或表單預填的網址；切換時卸載隱藏播放器，避免背景聲音。新的解析請求取消舊請求，失敗時清除舊播放器及影片資訊；縮圖工具保留獨立操作。PNG 參數讀取會驗證完整檔頭與區塊邊界，切換檔案捨棄過期結果，預覽網址於替換或離開頁面時釋放。

Go 對 HTML、JavaScript、CSS 回傳 Cache-Control: no-cache，讓瀏覽器重新驗證未帶版本號的模組，避免新 HTML 搭配舊 JS。套用此後端設定需重建及重啟 Go；首次切換既有舊快取時可使用強制重新整理。
