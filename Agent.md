# Agent
## 總體要求
1. 前端是動態網頁（串接後端 API 與資料庫），搭配後端（app.py）處理資料。
2. 頁面間的導覽連結與樣式架構保持一致，將[CSS UI](e:/資料、文檔/0.文件/Github/erp_site/style.css)建立起來，使用`static\`資料夾內涵的圖片進行發揮。
3. 移除所有原本的內嵌資料，但仍有實際的前端互動功能，改成空架構顯示、或是接入資料庫測試探測資料。
4. 資料庫密碼已經放在.env裡面，至於細節基於下方已經建好的架構進行補足。
```text
erp_site/
├── static/     #圖片素材庫
├── templates/  #專案資料夾
│       └── cookiecutter.json
├── data/       #存放較大的檔案資料夾
├── .env        #存放機密性資料用的
├── .gitignore  #Github排除檔案專用
├── app.py      #後端：網頁後端的核心控制
├── data.py     #後端：主要處理資料庫的串接
├── input.py    #後端：接收來自前端的輸入，彙整後將需要的資料餵給app.py
├── doc.py      #後端：接收來自data/exam的資料，彙整後將需要的資料餵給app.py
├── database.md #針對資料庫設定的說明
├── site.md     #針對網頁設定的說明
├── agent.md    #主要大方向（這個檔案）
├── style.css   #網頁CSS布局設定
├── script.js   #javascript控制項
├── index.html  #前端：前台官方網頁
│       ├── home.html   #前端：後台首頁，主要為員工入口網站，所有人都能看到
│       ├── sales.html  #前端：後台蒐集營運資料的分頁
│       ├── mis.html    #前端：後台管理所有設定的區域，必須使用帳號密碼登入獲得較高的權限
│       ├── exam.html   #前端：後台用來給予員工教育訓練的區域，資料會存放於上層data資料夾
│       └── game.html   #前端：後台給予員工放鬆的遊戲區域，並非要貼近網站內容，更多的是基於休閒性質
└── Readme.md   # 專案說明
```
## 管理員帳號密碼
設定在`.env`裡面，帳號：`BackendWebAdminUser`、密碼：`BackendWebAdminPassword`，進入[mis.html](/mis.html)必須輸入密碼登錄，且只有這個區塊在前端有較高的權限，可以控管網頁版面，及寫入資料表。

【程式碼品質規範】
- 程式碼必須乾淨且包含適當註解。
- 所有 JavaScript 請直接內嵌在各自 HTML 檔案的 <script> 標籤中，保持單一檔案可直接用瀏覽器開啟（Standalone）。

## 已修正問題
- 404 狀態列改用標準英文 `Not Found`，中文說明放在 UTF-8 回應本文，已排除 `UnicodeEncodeError`。
- 資料庫改為讀取專案 `.env`，透過 `pyodbc` 實際唯讀連線 SQL Server。
- 專案定位已調整為「福祿貝爾營運中心」，整合幼兒學籍、班級、收費、接送與園務人事。
## 與 Phoenix 的協作紀錄
- Phoenix 已確認專案名稱為「福祿貝爾營運中心」，不是「東泰」。
- 資料庫必須使用既有 `.env` 的實際連線設定，不建立 `.env.example`，也不得修改或公開 `.env` 的內容。
- 網站以提供的 SQL Server 資料表規劃為基礎；MIS 可查閱其他資料表，但既有園務資料表不得由網站編輯。
- 專案資料夾內除 `.env` 外可依需求優化，所有網站圖檔必須使用 `static` 資料夾內的素材。
- 前台需大幅翻修為符合幼稚園實際營運的網站，並允許配合需求微調後端程式。
- 對外首頁、員工工作台、營運蒐集、教育訓練、休閒專區及 MIS 管理中心應維持清楚的角色分流。
- MIS 登入使用 `.env` 內的管理帳密；帳密只在後端比對，不得回傳前端或寫入公開文件。
- 管理端與員工輸入只允許寫入網站專用的 `dbo.Frobel_*` 應用資料表，其他 SQL Server 園務資料維持唯讀。
- 員工營運輸入寫入正規化的 `dbo.Frobel_OperationSubmission` 待查核，不直接回寫既有園務資料表。
- 已以實際資料庫完成唯讀驗證：可讀取 43 張資料表，管理端未登入會被拒絕，登入後可查閱遮罩資料。
- 驗證過程不執行官網設定寫入，也不建立測試營運紀錄，以避免測試資料進入正式環境。
- 公開的 `Readme.md` 只保留專案用途、功能、安裝方式及安全設計；協作要求與內部決策集中記錄於本節。
## 維護功能
- 目前使用app.py執行，然後以8000 Port開啟，改為兩種開啟方式，一種是在`Windows`環境下用`*.bat`執行，以80 Port運作，另一種是用Vscode的`LiveServer`插件，開啟5500 Port運行，皆需要再[app.py](/app.py)內進行調整。
- 修正用.env內含的MIS帳號、密碼錯誤無法登入的問題。
- 所有需要輸入的功能，先建立好資料表，並遵循正規化原則，詳細依照[database.md](/database.md)就好。輸入的時候以[input.py](/input.py)來處理，最後回傳給[app.py](/app.py)再去做其他輸出。
## 新增功能
- `data/exam`內有`*.doc`的非結構化資料，需要用`python-docx`插件來做處理，主要為後台網頁[教育訓練](/exam.html)請求專用的資料，為求方便可以在資料庫建立相對應資料表。讓[doc.py](/doc.py)方便進行讀取，然後把內容回傳到[教育訓練](/exam.html)上，網頁的改動不只有題庫建立（伴隨資料庫），還需要作出容易查閱的資料
- 另外我已建立幼稚園員工的[員工資料](/data/staff.csv)，圖片放在這個[資料夾](/static/staff)，圖片檔名就是員工編號，根據目前設定的職掌，只有MIS才能做維護，[前台網頁](/index.html)只要呈現出員工的基本資料，[後台網頁](/home.html)要建置簡易的打卡功能（先建立起資料庫，後續用`inpuy.py`操作輸入），要有員工的打卡板塊，員工只能看到當下打卡時間，打卡狀況要用[員工出缺勤](/staff.html)檢視，同時需要用`.env`的`BackendWebAdminUser`、`BackendWebAdminPassword`進行登入

## 第 73 行起需求的實作紀錄
- 已加入 `start_windows_80.bat`，由 Python 後端直接以 Port 80 提供網站與 API。
- 專案只保留 `start_windows_80.bat` 啟動網站與 API；Port 5500 與即時重載由 Ritwick Dey 的 VS Code Live Server 擴充功能負責。
- `.vscode/settings.json` 使用 `liveServer.settings.proxy` 將 `/api` 轉送到 `http://localhost:80`；前端維持同來源請求，MIS 登入 Cookie 不需依賴跨來源 CORS。
- 已建立 8 張 `dbo.Frobel_*` 網站應用資料表；既有園務資料表仍維持唯讀。
- `input.py` 只負責驗證員工、打卡、營運及官網設定輸入，通過後由 `app.py` 交由 `data.py` 寫入 SQL Server。
- `doc.py` 優先使用 LibreOffice 無介面轉換舊 `.doc`，再用 `python-docx` 讀取；Microsoft Word COM 僅作為備援。
- 已匯入 23 份教育文件與 565 個整理後的查閱段落，題庫共 4 題並存放於資料庫。
- 已從 `data/staff.csv` 初始化 7 位員工，官網只公開姓名、部門、職位與特質；年齡、性別與背景僅供 MIS 維護。
- 員工工作台只回傳本次上班或下班打卡的伺服器時間；完整出缺勤明細需在 `staff.html` 使用 MIS 帳密登入後查閱。
- 已驗證 Live Server Proxy 設定、MIS 登入、員工名冊、教育文件、出缺勤權限及 `.env` 靜態路徑封鎖。
- 已修正 `app.py` 的請求型別、服務執行緒、教育同步例外處理及重複建表流程；教育同步失敗不再阻止其他網站功能啟動。
- 已修正 `doc.py` 的轉檔程式偵測、逾時與損壞文件處理、標題切段、長內容分段、UTC 修改時間及同步鎖定。
- 官網員工名冊改為獨立載入，不再受其他首頁 API 失敗連帶影響；員工工作台的打卡人員選單直接讀取 `dbo.Frobel_Staff` 啟用資料。
- 已依 Phoenix 指示刪除 `start_api_8000.bat`，只保留 `start_windows_80.bat`；啟動前會檢查專案 `.venv`、`pyodbc` 與 `python-docx`，並支援 `--check` 自我檢查。
- 已重建原先指向不存在 Python 3.10 的 `.venv`，改用 Python 3.12 並安裝 `requirements.txt`；VS Code 固定使用專案直譯器與工作區模組路徑，修正 `app.py` 匯入 `doc.py` 及 `doc.py` 匯入 `python-docx` 的解析問題。
- 員工打卡改為第一筆必須上班、後續上下班交替，並以資料庫交易鎖避免同一員工同時送出造成連續打卡。
- `game.html` 已改為 YouTube 直播休息站，只接受可辨識的 YouTube 網址並轉換為嵌入播放器。

## 依現況迫切需要修復的功能
-   在[game.html](/game.html)中，Youtube影片撥放必須加以優化，容易卡讀取到最後失敗，要加到[input.py](/input.py)去處理，實現前後端分離，但下方顯示不該是網址後方的`YoutubeCode`，而是實際擷取到的影片標題。
-   [staff.html](/staff.html)的內容，雖然可以利用[staff.csv](/data/staff.csv)更新去做到，目前前提是要能夠精準的對上[該資料夾](/static/staff/)的圖片檔名的員工編號。但實務上必須是[staff.html](/staff.html)輸入，透過[input.py](/input.py)處理，讓[app.py](/app.py)與資料庫對接。文字型態遵循正規化存入資料庫中，圖片則存放於[該資料夾](/static/staff/)，檔名跟隨員工編號（預設為主鍵，新增後不能再變更，後台網站輸入框需要特別用顏色標記），個人圖片需要做到可上傳，上傳後檔名自動變換成員工編號。
-   目前是使用`127.0.0.1`，要改成方便內網IP就能存取，這樣我後面會比較好處理

## 第 83 行起需求的實作紀錄
- `game.html` 改由 `input.py` 驗證 YouTube 網址，`app.py` 透過固定的 YouTube oEmbed 端點取得真實影片標題後才回傳嵌入網址；前端不再顯示影片代碼，並設有十秒逾時。
- `staff.html` 已整合 MIS 員工主檔維護、照片預覽及上傳；文字寫入 `dbo.Frobel_Staff`，圖片限制為 JPEG、PNG、WebP 與 5 MB，檔名由不可變更的員工編號自動產生。
- 員工編號進入編輯狀態後會鎖定並以警示色標記；後端沒有變更既有主鍵的操作。
- `app.py` 與 `start_windows_80.bat` 改為監聽 `0.0.0.0`，啟動時列出可供同一內網使用的 IPv4 位址；Live Server 亦改用內網模式。
