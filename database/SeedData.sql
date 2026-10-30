-- 僅供全新資料庫初始化，既有資料遷移請勿先執行此檔。
SET XACT_ABORT ON;
GO
INSERT dbo.OperationCategories(CategoryNo,DisplayOrder)
SELECT source.CategoryNo,source.DisplayOrder
FROM (VALUES(N'出勤',1),(N'業務進度',2),(N'物流調度',3),(N'帳務',4),(N'設備',5),(N'餐飲服務',6),(N'其他',7)) source(CategoryNo,DisplayOrder)
WHERE NOT EXISTS(SELECT 1 FROM dbo.OperationCategories currentRow WHERE currentRow.CategoryNo=source.CategoryNo);
GO
INSERT dbo.Departments(DepartmentNo,IsActive,UpdatedBy)
SELECT source.DepartmentNo,1,N'initialization'
FROM (VALUES(N'營運部'),(N'製造部'),(N'財務部'),(N'資訊部'),(N'福利部'),(N'後勤部')) source(DepartmentNo)
WHERE NOT EXISTS(SELECT 1 FROM dbo.Departments currentRow WHERE currentRow.DepartmentNo=source.DepartmentNo);
GO
IF NOT EXISTS(SELECT 1 FROM dbo.TrainingSubjects WHERE TrainingDomain=N'academic' AND SubjectName=N'通用知識')
INSERT dbo.TrainingSubjects(SubjectNo,TrainingDomain,SubjectName,MockQuestionCount,MockDurationMinutes,MockPassScore,IsActive)
VALUES(CONVERT(NVARCHAR(50),NEXT VALUE FOR dbo.TrainingSubjectsNumbers),N'academic',N'通用知識',40,45,70,1);
GO
IF NOT EXISTS(SELECT 1 FROM dbo.TrainingSubjects WHERE TrainingDomain=N'practical' AND SubjectName=N'術科申論')
INSERT dbo.TrainingSubjects(SubjectNo,TrainingDomain,SubjectName,MockQuestionCount,MockDurationMinutes,MockPassScore,IsActive)
VALUES(CONVERT(NVARCHAR(50),NEXT VALUE FOR dbo.TrainingSubjectsNumbers),N'practical',N'術科申論',0,0,0,1);
GO
