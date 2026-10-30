# Golang Playground 維護說明

工作面板第二分頁原本的 F & Q 已改為 Golang Playground，沿用 Python 分頁的上方編輯器、下方命令列與共用 CSS。根元素為 `golang_canvas`，控制項使用 `golang-` 前綴。

## 操作

- 編輯上方 `main.go`，按「執行 main.go」或 Ctrl / Command + Enter 執行。
- 「格式化 gofmt」或命令列 `go fmt main.go` 使用 Go 的 `go/format` 格式化編輯內容。無法解析時保留原程式碼並顯示錯誤。
- 標準輸入須在執行前填妥，可透過 `fmt.Scan`、`bufio.Scanner` 或 `os.Stdin` 讀取；每次操作重新讀取，資料結束後為 EOF。
- 命令列支援 `go run main.go`、`go fmt main.go`、`gofmt main.go`、`go version`、`help`、`clear`、`reset`。
- 也能直接輸入 Go 運算式、宣告及 `import "fmt"` 等互動指令。多行區塊輸入到結束大括號後執行，方向鍵上下可選取歷史指令。
- 每次執行 `main.go` 都使用新的 Worker；程式結束後釋放背景 goroutine，重新建立獨立的互動環境。互動指令之間保留變數，執行檔案或重設後會清除。
- 「停止」可終止無窮迴圈，之後使用「重設環境」重新啟動。編輯內容與標準輸入仍保留。

## 執行環境與限制

使用 Yaegi 0.16.1 解譯 Go，執行環境由 Go 1.22.12 編譯成 WebAssembly。這是瀏覽器內的 Go 解譯環境，語法與函式庫相容性以 Yaegi 為準。沒有提供主機 Shell、`go get`、外部 Go modules、原生編譯或完整的主機檔案與程序操作。

部署使用已建置的靜態檔案，主要後端及 `requirements.txt` 不需修改，也無須在部署主機安裝 Go。程式碼與標準輸入不會送到外部編譯服務。

執行環境只在首次開啟第二分頁時載入。壓縮後的 `golang.wasm.gz` 約 8 MB，由瀏覽器 `DecompressionStream` 解壓縮，因此需使用支援此功能的現代瀏覽器。支援 Cache Storage 時會以 `golang-playground-` 前綴保存快取；其他情況使用正常下載與瀏覽器 HTTP 快取。不使用 Cookie 儲存執行檔或建立不存在的套件安裝清單。

## 檔案

- `page/static/golang.js`：介面、指令歷史、Worker 生命週期及格式化回填。
- `page/static/golang-worker.js`：載入 WASM、瀏覽器快取、輸出緩衝與每次輸出上限。
- `page/static/golang-runtime/`：壓縮 WASM、配對的官方 `wasm_exec.js` 與 Go／Yaegi 授權文件，部署時須一併包含。
- `page/static/python.css`：Python 與 Go 共用排版，以各自的根元素限定範圍，沿用 `style.css` 的元件與色彩。
- `page/tools/go-playground/`：僅用於建置前端 WASM 的原始碼、固定依賴與建置腳本；不提供伺服器功能。

## 重新建置

在專案根目錄執行 `powershell -NoProfile -File page/tools/go-playground/build.ps1`。需要本機 Go 啟動工具，以及首次下載固定工具鏈與 Yaegi 時的網路連線。建置快取放在已忽略的 `.deps/go-playground/`，環境變數在腳本結束後還原，不變更系統的 Go 設定。

腳本使用 Go 模組校驗碼驗證依賴，並檢查 `wasm_exec.js` 的固定 SHA-256。修改 WASM 原始碼並重新建置後，須同步更新 `golang-worker.js` 的 `GOLANG_BUILD`，避免沿用舊快取。

## 已驗證

以 Edge 實測範例程式、UTF-8 標準輸入、語法錯誤、panic、多行 REPL、格式化、即時輸出、goroutine／channel、輸出上限、瀏覽器快取、背景工作釋放、停止無窮迴圈及重啟、遊戲鍵盤隔離、390px 手機版面與深色模式；範例執行過程沒有外部編譯請求。

官方參考：[Yaegi v0.16.1 說明與限制](https://github.com/traefik/yaegi/tree/v0.16.1)、[配對的 Go 1.22.12 JavaScript 執行環境](https://github.com/golang/go/blob/go1.22.12/misc/wasm/wasm_exec.js)。
