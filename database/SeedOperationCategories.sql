-- 日報必要類別；只補缺少的設定，不覆寫既有名稱或排序。
SET XACT_ABORT ON;
INSERT dbo.OperationCategories(CategoryNo,DisplayOrder)
SELECT source.CategoryNo,source.DisplayOrder
FROM (VALUES(N'出勤',1),(N'業務進度',2),(N'物流調度',3),(N'帳務',4),(N'設備',5),(N'餐飲服務',6),(N'其他',7)) source(CategoryNo,DisplayOrder)
WHERE NOT EXISTS(SELECT 1 FROM dbo.OperationCategories currentRow WHERE currentRow.CategoryNo=source.CategoryNo);
