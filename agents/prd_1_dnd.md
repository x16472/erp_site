# 20261110實作內容
參照以下進行實作
# JavaScript資源整理
所以從[/page/static/js/](/page/static/js/)引用的資源，依照ES6 module進行管理。詳細如下作法：
```html
<script type="module" src="./static/js/exam.js"></script>
```
重新檢查`HTML`內遷入位置JavaScript必須


## SOP文件查閱
[exam.html](/page/exam.html)

## DND角色卡設計，參考資料
加上分頁切換，參照[5etools 中文鏡像站](https://5etools.wayneh.tw/5etools.html)、[DnD Codex 創建角色指南](https://www.soeling-dnd.com/dnd/create-character/)、[ㄐㄍ的 DND5E 中文資料網](https://sites.google.com/view/dnd5e-2/)，以及巴哈撰寫的[創造角色](https://home.gamer.com.tw/artwork.php?sn=1851554)、[【心得】龍與地下城5E自動角色卡 強迫症細節美化Edition v4.8](https://forum.gamer.com.tw/C.php?bsn=60429&snA=1399)

來製作快速製作一名角色的模板資料，最後完成可選擇導出成具有結構化的`*.json`、`*.yaml`、`*.xml`、`*.csv`，或是`*.xlsx`試算表、`*.docx`文件、`*.pdf`，甚至是離線SQLite資料庫`*.db`。

範例資料內容用我復健提供的檔案，角色卡格式上遵照DND官方來做。