# 20261110實作內容
參照以下進行實作
# 1.JavaScript資源整理
所有從[/page/static/js/](/page/static/js/)引用的資源，全數依照ES6 module進行管理。詳細如下作法：
```html
<script type="module" src="./static/js/exam.js"></script>
```
重新檢查`HTML`內遷入位置JavaScript必須在上方import
```js
import { apiData, employeeLoginUrl, escapeHtml, jsonRequest } from './script.js';
```
每個`JavaScript`內部內必須遵循，物件導向寫法，並且使用函式來做分類、管理。舉例：
```js
async function loadWrong() {
    showAcademic(wrongView);
    const items = await request('/api/training/wrong');
    $('#wrongList').innerHTML = items.length ? items.map(item => `<article class="wrong-card" data-wrong-card="${item.id}"><div><span class="tag">${esc(item.subject)}｜${esc(item.chapter)}</span>${renderBlocks(item.content_blocks)}<p class="hint">正確答案：${esc((item.answers || []).map(value => typeof value === 'number' ? String.fromCharCode(65 + value) : value).join('、'))}</p><p>${esc(item.explanation || '此題尚無解析。')}</p></div><button class="btn second" data-remove-wrong="${item.id}">從錯題本移除</button></article>`).join('') : '<div class="empty">目前沒有待複習錯題。</div>'
}
```
---
為了日後能新增更多項是俄羅斯方塊這種小遊戲，在分頁中避免衝突。針對`JavaScript`檔案，必須得遵照以下調整，這張圖事後整理更詳細放到[History](/agents/history.md)中。分支到越細部必須越精簡，因為跟CSS一樣大部分變數和事件都共用，但針對各種不同的靜態資源再去加新的東西。
```text
page/static/
└── js/
    ├── script.js            # 【核心控制】唯一被 HTML 引入的模組，負責啟動並串接所有功能
    ├── theme.js             # 【狀態模組】管理深淺色切換，即時控制目前主題操作
    ├── panel.js             # 【狀態模組】管理後台分頁切換，控制後台分頁操作
    ├── index.js             # 【前台網頁】獨立管理前台想呈現的內容
    ├── home.js              # 【後台網頁】獨立管理後台想呈現的內容
    ├── sales.js
    ├── exam.js
    ├── workflow.html
    ├── game.js
    ├── staff.js
    ├── mis.js
    └── canvas/              # 【繪圖核心】集中管理所有Canvas相關邏輯，有用到Canvas的才要放進來
        ├── python.js        # 抓取 HTML 的 Canvas 空殼、設定解析度並匯出畫筆 (ctx)
        ├── python-worker.js
        ├── golang.js        # 抓取 HTML 的 Canvas 空殼、設定解析度並匯出畫筆 (ctx)
        ├── golang-worker.js
        └── teris.js         # 匯入 setup.js 的畫筆與 theme.js 的主題色來執行繪圖
```


## 2.製作SOP文件查閱頁面
目前有SOP文件同步，在[exam.html](/page/exam.html)新增一個頁面用來檢視，以讀取的文件章節。

## 4.題庫維護部份顯示調整
因為資料表`dbo.TrainingQuestions`中，已經有`id`作為主鍵。所以`QuestionNo`，但是從[question-bank.md](/backend/docs/question-bank.md)的設計來看，針對`id`、`QuestionNo`的編排並不理想，第14行說依照部門修正流水號編排，實際上也非照流水號編排，目前來說前端顯示的編號是`QuestionNo`，`id`維持隱藏是可以的，`QuestionNo`也維持隱藏，只針對原本的三個資料表串聯使用，表要顯示於前端的後台管理上。

先修復對於其他三個資料庫的關聯後，另外再針對前端的後台管理部分，目前分類檢視只有狀態，請再新增科目、章節分類，需要事先選科目再帶入章節。



## 5.DND角色卡設計，參考資料
加上分頁切換，參照[5etools 中文鏡像站](https://5etools.wayneh.tw/5etools.html)、[DnD Codex 創建角色指南](https://www.soeling-dnd.com/dnd/create-character/)、[ㄐㄍ的 DND5E 中文資料網](https://sites.google.com/view/dnd5e-2/)，以及巴哈撰寫的[創造角色](https://home.gamer.com.tw/artwork.php?sn=1851554)、[【心得】龍與地下城5E自動角色卡 強迫症細節美化Edition v4.8](https://forum.gamer.com.tw/C.php?bsn=60429&snA=1399)

來製作快速製作一名角色的模板資料，最後完成可選擇導出成具有結構化的`*.json`、`*.yaml`、`*.xml`、`*.csv`，或是`*.xlsx`試算表、`*.docx`文件、`*.pdf`，甚至是離線SQLite資料庫`*.db`。

範例資料內容用我復健提供的檔案，角色卡格式上遵照DND官方來做。

DND部分先提供規劃方案，暫時不用實作。
