-- 此舊入口已停用：QuestionNo 是永久主檔編號，不得重編 Id、題號或歷史快照。
-- 新庫請執行 CreateTables.sql；缺少歷史題號時先人工核對 RepairTrainingQuestionRelations.sql。
THROW 51015, N'題號重編功能已停用。QuestionNo 建立後不得修改或重用，請使用最新版建表腳本。', 1;
