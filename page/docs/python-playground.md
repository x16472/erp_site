# Python Playground 維護說明

工作面板第三分頁使用 Pyodide 0.25.1，內含 CPython 3.11.3。程式在獨立 Web Worker 執行，無須安裝伺服器套件或修改主要後端。首次切到此分頁時才載入執行環境。

## 操作

- 上方編輯 `main.py`，使用執行按鈕或 Ctrl / Command + Enter 執行。Tab 插入四個空格，Enter 延續縮排。
- 下方可輸入 Python 指令，與 `main.py` 共用變數。多行區塊使用空白行結束，方向鍵上下可選取歷史指令。
- `input()` 與 `sys.stdin` 讀取「標準輸入」區域，須在執行前填妥。每次執行都重新讀取這份輸入，讀完後為 EOF。
- `python main.py` 執行編輯區；`clear` 清除輸出；`reset` 重設執行環境。
- 停止會終止整個 Worker，因此也能停止無窮迴圈。使用「重設環境」重新啟動，程式碼與標準輸入仍保留。
- 命令列提供 Python 操作，不提供主機的作業系統 Shell。檔案位於瀏覽器內的暫存檔案系統。

## pip 與瀏覽器儲存

`pip install 套件名稱` 透過 micropip 安裝到瀏覽器內的 Python，可指定多個套件及 `套件名稱==版本`。僅支援 Pyodide 提供或可在 WebAssembly 使用的 wheel，無法使用一般主機的原生套件或編譯工具。

成功安裝後，以 `python_playground_packages` Cookie 保存使用者指定的套件清單，期限 30 天，路徑限定目前工作面板頁面。重新整理或重設時會依清單重新建立環境。Cookie 僅存名稱及版本，最多約 3 KB；超出容量或 Cookie 遭停用時會在命令列提示，當次安裝仍可使用。

支援 Cache Storage 的瀏覽器會將公開的 Pyodide 資產與 PyPI wheel 存入 `python-playground-pyodide-0.25.1` 快取。不支援或儲存空間不足時，改由正常網路下載與瀏覽器 HTTP 快取處理。瀏覽器可能清除快取，套件索引查詢也可能需要網路，因此還原仍須具備網路連線。

這些操作不會執行伺服器的 pip、不會寫入 `requirements.txt`，也不會呼叫網站後端 API。若需移除安裝紀錄，可在瀏覽器開發工具刪除上述 Cookie 與快取，再重設環境。

## 檔案與隔離

- `page/workflow.html`：保留原有外殼與分頁，僅填入第三分頁及調整遊戲相關 ID、資源引用。
- `page/static/python.js`：`python_canvas` 介面、Worker 生命週期、命令歷史與 Cookie。
- `page/static/python-worker.js`：Python 執行、套件安裝、標準輸入、輸出上限與公開資產快取。
- `page/static/python.css`：限定 `python_canvas` 的少量排版，沿用共用色彩與元件。
- `page/static/teris.js` 與 `teris.css`：畫布為 `teris_canvas`，其他 ID 使用 `teris-` 前綴；JavaScript 使用區域作用域，CSS 限定第四分頁。離開遊戲會暫停，鍵盤事件只作用於遊戲分頁。

## 已驗證

以 Edge 實測 Python 3.11.3、程式執行、Python 例外、UTF-8 標準輸入、多行 REPL、`pip install pyfiglet==1.0.2`、Cookie、wheel 快取、重新整理還原、停止無窮迴圈與重啟、遊戲鍵盤隔離，以及 390px 手機寬度。

官方參考：[Worker 整合](https://pyodide.org/en/0.25.1/usage/webworker.html)、[標準輸入與輸出](https://pyodide.org/en/0.25.1/usage/streams.html)。
