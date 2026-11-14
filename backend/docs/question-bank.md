# 題庫關聯、維護與附圖

## 主鍵與內部關聯

`dbo.TrainingQuestions.Id` 是資料列主鍵，由 SQL Server IDENTITY 自動產生。`QuestionNo` 是不可變動的永久主檔編號，由 `UX_TrainingQuestions_1` 唯一索引保證不重複。兩者用途不同，允許不同數值及跳號，不依部門編排，也不在刪除後重排。

相容檢視表 `dbo.Company_TrainingQuestion.question_id` 對應 `TrainingQuestions.QuestionNo`。API 為相容既有客戶端，仍以 `id`／`question_id` 傳遞此關聯編號；它不是實體表的 Id。表單 hidden 欄位、DOM data 屬性與 API 識別欄位保留，MIS 題庫清單、編輯提示及題庫資料表查閱不顯示 Id 或 QuestionNo。

| 關聯資料表 | 外鍵欄位 | 參照 |
| --- | --- | --- |
| TrainingAnswers | QuestionNo | TrainingQuestions.QuestionNo |
| TrainingSessionQuestions | QuestionNo | TrainingQuestions.QuestionNo |
| TrainingWrongQuestions | QuestionNo | TrainingQuestions.QuestionNo |

作答快照 `SnapshotJson.id` 同樣使用 QuestionNo；題目更新、申論審核、錯題本及續作沿用同一編號。既有外鍵與資料均保留，不將它們改指向實體 Id。例：Id=1002、QuestionNo=51 時，三張表及快照仍使用 51。

人工新增、來源匯入與必要初始題目新增都使用同一取號方式：在交易中以 TABLOCKX／HOLDLOCK 鎖定題庫，從全部題目（包含停用、草稿及軟刪除）的數字 QuestionNo 最大值加一，另由 IDENTITY 產生 Id。新增回應必須回傳 QuestionNo，後續才能正確作答與編輯。現有 API 接受正整數編號，取號超過 INT 範圍時會拒絕新增。鎖定會序列化題目新增；不需要開啟 IDENTITY_INSERT 或為此授予 ALTER 權限。舊的 TrainingQuestionsNumbers 序列保留相容性，已不參與題庫取號，不得以重設序列或 Id 重編題號。

資料庫觸發程序 `TR_TrainingQuestions_PermanentQuestionNo` 對單筆、批次及直接 SQL 操作套用相同規則：建立後禁止改號，即使尚未作答也一樣；禁止實體 DELETE，刪題須保留原列並設定 DeletedAt／IsActive；新增編號必須大於既有最大值，不得補歷史缺號、重用編號或使用非標準正整數。允許正常修改題文與停用、軟刪除。三個外鍵均為 NO ACTION，不能透過級聯更新改號或刪除歷史關聯。欄位仍依 DATABASE.md 保持 NVARCHAR(50) NULL 定義，正常新增由應用程式及觸發程序驗證必要編號。

`database/CreateTables.sql` 與 `database/RepairTrainingQuestionRelations.sql` 使用相同的唯一索引、三個外鍵及觸發程序定義，維護時須同步兩份定義。重跑會驗證索引及外鍵實際參照欄位，並重新 CHECK 外鍵、啟用觸發程序；發現錯誤定義或無效既有題號會停止，不自動改寫歷史資料。建表腳本的 `TrainingQuestionNoContract` 區塊以交易保護，可單獨套用既有且資料正確的題庫；整份 CreateTables.sql 用於完整建置，不應為本次升級在正式環境重跑無關結構或種子資料。正常網站啟動不會執行這項結構更新。

已掃描 database 下全部九份 SQL：CreateTables.sql、RepairTrainingQuestionRelations.sql 同步新規則；RenumberTrainingQuestions.sql 已移除重編實作，執行會直接拒絕；SeedData.sql、SeedEmployees.sql、SeedOperationCategories.sql、SeedAdventure.sql、AdventureTables.sql、HardenAdventureColumns.sql 沒有題庫寫入或題號外鍵，不需為此修改。若日後新增題庫種子資料，須使用上述交易取號流程，不能固定填入舊題號。

若既有資料庫已發生孤兒關聯，須另外核對實際資料與備份，不能從 Id 猜測並覆寫 QuestionNo；本輪實際修復情形如下。

## MIS 分類檢視

題庫維護可同時依科目、章節、狀態與關鍵字篩選。先選科目，章節選單才啟用並只列該科目的章節；切換或清除科目會清除原章節。這組篩選與左側批次分類變更互相獨立，篩選本身不修改題目。

切換篩選時只保留仍可見的勾選題目，避免批次修改隱藏題目。題目依內部關聯編號的數值排序；畫面不另外顯示此編號。既有題目發布、退回草稿、停用、軟刪除與管理員保護行為保留。

## 題目附圖

選取附圖後可預覽，按「儲存題目」才會上傳。支援 JPEG、PNG、WebP，檔案大小介於 128 Bytes 至 5 MB。更換與移除附圖也須儲存才生效；編輯其他欄位時會保留既有附圖與程式碼區塊。

圖片存放於 `data/exam/images/`，第一次上傳時建立目錄。檔名使用關聯文件的主檔名；未指定文件時使用科目名稱，另加隨機識別碼及圖片副檔名，避免互相覆寫。名稱中的空白與檔案系統不適用字元轉為底線。

附圖檔名透過題目內容 JSON 儲存，不增加資料庫欄位。作答、成績回顧、錯題本與術科均顯示附圖，讀取須先登入員工入口。更換或移除附圖不刪除舊圖片，讓既有作答快照仍可顯示原圖。

部署時須重新建置 Go 以更新內嵌查詢目錄，同步更新 Python 及整個前端靜態資源目錄。服務帳號需有 `data/exam/images/` 的讀寫權限，備份也需包含此目錄。

## 2026-11-14 實際關聯修復

依 Phoenix 指示連線 Company 後，發現 178 題的 QuestionNo 全為 NULL，題庫只剩主鍵及來源指紋索引，三張作答表缺少指向題庫的外鍵。原有 TrainingAnswers 1 筆、TrainingSessionQuestions 1,436 筆、TrainingWrongQuestions 106 筆均保留既有 QuestionNo，但已無法連到題庫。

使用 `database/RepairTrainingQuestionRelations.sql`，以作答快照的題文、題型、科目及完整選項建立對照。題文僅正規化空白、換行及全半形冒號；不是依 Id 或題目排列猜測。預覽確認全部 178 個原編號都有唯一對照，才在同一交易還原題庫 QuestionNo，補回唯一索引與三個 WITH CHECK 外鍵。例 Id=1003 還原 QuestionNo=52，Id=1058 還原 QuestionNo=107。

修復沒有修改三張作答表、SnapshotJson 或題目 Id。三張表修復前後的筆數與完整資料 SHA-256 雜湊一致；修復後三個外鍵均啟用且受信任，孤兒關聯均為 0。證據存於未納入版控的 `data/processed/training-relations/`。

腳本預設 @Apply=0，只預覽後回復交易；任何缺少、重複或不一致的對照都會停止。它只用於還原這種遺失的 QuestionNo，不應作為一般題號重新編排工具，也不由網站啟動自動執行。永久編號保護已安裝後若再發現空白題號，腳本會停止，不能藉修復繞過保護。已修復的資料庫不需再次套用。

## 2026-11-14 永久編號保護驗證

已將建表腳本中的題號保護區塊實際套用 Company；唯一索引定義正確，三個外鍵仍啟用、受信任且無級聯更新／刪除，永久編號觸發程序已啟用。正規化 SQL Server 儲存的 CREATE 標頭與換行後，觸發程序定義與建表腳本相同。當時最大 QuestionNo 為 1169，下一次正常新增取號為 1170。

在獨立測試結構及回復交易內完成 24 項 SQL Server 行為驗證，涵蓋未作答及已作答題目改號／刪除、重複編號、補號、無效格式、批次寫入、軟刪除後取號、三張表孤兒外鍵、重跑恢復 CHECK／觸發程序及錯誤結構拒絕。全新建置與初始化連續重跑兩次，並執行三條實際新增查詢，均通過；測試結構已隨交易回復，未留下測試題目。

178 筆題目、1 筆申論作答及 106 筆錯題的完整資料雜湊在套用前後一致。期間實際系統另新增 10 筆考卷題目，原有 1436 筆 TrainingSessionQuestions 雜湊仍相同；沒有刪除或覆寫新紀錄，三張表孤兒關聯皆為 0。相關證據存於 `data/processed/training-relations/permanent-number-*-20261114.jsonl`。Go 全部測試、vet 與 Python 107 項測試通過。
