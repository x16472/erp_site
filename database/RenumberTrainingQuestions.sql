-- 在 Company 資料庫執行；停止網站服務並完成備份後，才將 @Apply 改為 1。
-- 預覽與正式執行皆包含軟刪除題目，避免歷史作答失去關聯。
SET NOCOUNT ON;
SET XACT_ABORT ON;
DECLARE @Apply BIT = 0;

IF @@TRANCOUNT <> 0
    THROW 51000, N'請在沒有既有交易的查詢視窗執行。', 1;
IF OBJECT_ID(N'dbo.TrainingQuestions', N'U') IS NULL
    THROW 51000, N'此腳本只適用 TrainingQuestions 新版資料表。', 1;
IF COLUMNPROPERTY(OBJECT_ID(N'dbo.TrainingQuestions'), N'Id', 'IsIdentity') <> 1
    THROW 51000, N'題庫 Id 不是預期的 IDENTITY 欄位，請先確認結構。', 1;

DROP TABLE IF EXISTS #QuestionBackup;
DROP TABLE IF EXISTS #QuestionMap;

BEGIN TRY
    BEGIN TRANSACTION;
    DECLARE @LockedRows BIGINT;
    SELECT @LockedRows = COUNT_BIG(*) FROM dbo.TrainingQuestions WITH (TABLOCKX, HOLDLOCK);
    SELECT @LockedRows = COUNT_BIG(*) FROM dbo.TrainingAnswers WITH (TABLOCKX, HOLDLOCK);
    SELECT @LockedRows = COUNT_BIG(*) FROM dbo.TrainingSessionQuestions WITH (TABLOCKX, HOLDLOCK);
    SELECT @LockedRows = COUNT_BIG(*) FROM dbo.TrainingWrongQuestions WITH (TABLOCKX, HOLDLOCK);

    IF EXISTS (
        SELECT 1 FROM sys.foreign_keys AS fk
        WHERE fk.referenced_object_id = OBJECT_ID(N'dbo.TrainingQuestions')
          AND (fk.parent_object_id NOT IN (
                  OBJECT_ID(N'dbo.TrainingAnswers'),
                  OBJECT_ID(N'dbo.TrainingSessionQuestions'),
                  OBJECT_ID(N'dbo.TrainingWrongQuestions'))
               OR fk.is_disabled = 1 OR fk.is_not_trusted = 1
               OR (SELECT COUNT(*) FROM sys.foreign_key_columns AS fc
                   WHERE fc.constraint_object_id = fk.object_id) <> 1
               OR EXISTS (
                   SELECT 1 FROM sys.foreign_key_columns AS fc
                   JOIN sys.columns AS pc ON pc.object_id = fc.parent_object_id AND pc.column_id = fc.parent_column_id
                   JOIN sys.columns AS rc ON rc.object_id = fc.referenced_object_id AND rc.column_id = fc.referenced_column_id
                   WHERE fc.constraint_object_id = fk.object_id
                     AND (pc.name <> N'QuestionNo' OR rc.name <> N'QuestionNo')))
    )
        THROW 51000, N'發現額外或未驗證的題目外鍵，請先補齊關聯更新規則。', 1;

    IF EXISTS (
        SELECT 1 FROM sys.triggers
        WHERE parent_id IN (OBJECT_ID(N'dbo.TrainingQuestions'), OBJECT_ID(N'dbo.TrainingAnswers'),
                            OBJECT_ID(N'dbo.TrainingSessionQuestions'), OBJECT_ID(N'dbo.TrainingWrongQuestions'))
          AND is_disabled = 0
    )
        THROW 51000, N'題庫相關資料表有啟用中的觸發程序，請先確認重編影響。', 1;

    IF EXISTS (SELECT 1 FROM dbo.TrainingQuestions WHERE QuestionNo IS NULL OR LTRIM(RTRIM(QuestionNo)) = N'')
        THROW 51000, N'存在空白題目編號，無法安全建立對照。', 1;
    IF EXISTS (SELECT QuestionNo FROM dbo.TrainingQuestions GROUP BY QuestionNo HAVING COUNT(*) > 1)
        THROW 51000, N'存在重複題目編號，請先釐清資料。', 1;
    IF EXISTS (SELECT 1 FROM dbo.TrainingSessionQuestions WHERE ISJSON(SnapshotJson) <> 1 OR SnapshotJson IS NULL)
        THROW 51000, N'存在無法解析的作答快照，請先修復。', 1;

    SELECT * INTO #QuestionBackup FROM dbo.TrainingQuestions;
    DECLARE @TemporaryPrefix NVARCHAR(37) = CONVERT(NVARCHAR(36), NEWID()) + N'_';
    SELECT Id AS OldId, QuestionNo AS OldQuestionNo,
           CONVERT(INT, ROW_NUMBER() OVER (ORDER BY Id)) AS NewId,
           CONVERT(NVARCHAR(50), ROW_NUMBER() OVER (ORDER BY Id)) AS NewQuestionNo,
           CONVERT(NVARCHAR(50), @TemporaryPrefix + CONVERT(NVARCHAR(10), ROW_NUMBER() OVER (ORDER BY Id))) AS TemporaryQuestionNo
    INTO #QuestionMap
    FROM #QuestionBackup;

    IF EXISTS (SELECT 1 FROM #QuestionMap AS m JOIN #QuestionMap AS old ON old.OldQuestionNo = m.TemporaryQuestionNo)
        THROW 51000, N'暫存編號與既有編號衝突，請重新執行。', 1;

    SELECT OldId, OldQuestionNo, NewId, NewQuestionNo FROM #QuestionMap ORDER BY NewId;
    IF @Apply = 0
    BEGIN
        ROLLBACK TRANSACTION;
        PRINT N'僅預覽，未變更資料。核對後將 @Apply 改為 1 才會套用。';
        RETURN;
    END;

    DECLARE @DisableForeignKeys NVARCHAR(MAX), @EnableForeignKeys NVARCHAR(MAX);
    SELECT @DisableForeignKeys = STRING_AGG(CONVERT(NVARCHAR(MAX),
               N'ALTER TABLE ' + QUOTENAME(OBJECT_SCHEMA_NAME(parent_object_id)) + N'.' + QUOTENAME(OBJECT_NAME(parent_object_id))
               + N' NOCHECK CONSTRAINT ' + QUOTENAME(name) + N';'), NCHAR(10)),
           @EnableForeignKeys = STRING_AGG(CONVERT(NVARCHAR(MAX),
               N'ALTER TABLE ' + QUOTENAME(OBJECT_SCHEMA_NAME(parent_object_id)) + N'.' + QUOTENAME(OBJECT_NAME(parent_object_id))
               + N' WITH CHECK CHECK CONSTRAINT ' + QUOTENAME(name) + N';'), NCHAR(10))
    FROM sys.foreign_keys WHERE referenced_object_id = OBJECT_ID(N'dbo.TrainingQuestions');
    IF @DisableForeignKeys IS NOT NULL EXEC sys.sp_executesql @DisableForeignKeys;

    UPDATE sq SET SnapshotJson = JSON_MODIFY(sq.SnapshotJson, '$.id', m.NewId)
    FROM dbo.TrainingSessionQuestions AS sq JOIN #QuestionMap AS m ON m.OldQuestionNo = sq.QuestionNo;

    -- 先使用獨立暫存編號，避免錯題本唯一索引在新舊編號交錯時衝突。
    UPDATE a SET QuestionNo = m.TemporaryQuestionNo
    FROM dbo.TrainingAnswers AS a JOIN #QuestionMap AS m ON m.OldQuestionNo = a.QuestionNo;
    UPDATE sq SET QuestionNo = m.TemporaryQuestionNo
    FROM dbo.TrainingSessionQuestions AS sq JOIN #QuestionMap AS m ON m.OldQuestionNo = sq.QuestionNo;
    UPDATE w SET QuestionNo = m.TemporaryQuestionNo
    FROM dbo.TrainingWrongQuestions AS w JOIN #QuestionMap AS m ON m.OldQuestionNo = w.QuestionNo;

    DELETE FROM dbo.TrainingQuestions;
    DECLARE @Columns NVARCHAR(MAX), @Values NVARCHAR(MAX), @RestoreSql NVARCHAR(MAX);
    SELECT @Columns = STRING_AGG(CONVERT(NVARCHAR(MAX), QUOTENAME(name)), N',') WITHIN GROUP (ORDER BY column_id),
           @Values = STRING_AGG(CONVERT(NVARCHAR(MAX), CASE name
               WHEN N'Id' THEN N'm.NewId'
               WHEN N'QuestionNo' THEN N'm.NewQuestionNo'
               ELSE N'b.' + QUOTENAME(name) END), N',') WITHIN GROUP (ORDER BY column_id)
    FROM sys.columns WHERE object_id = OBJECT_ID(N'dbo.TrainingQuestions')
      AND is_computed = 0 AND generated_always_type = 0 AND system_type_id <> 189;
    SET @RestoreSql = N'INSERT dbo.TrainingQuestions (' + @Columns + N') SELECT ' + @Values
        + N' FROM #QuestionBackup AS b JOIN #QuestionMap AS m ON m.OldId=b.Id;';
    SET IDENTITY_INSERT dbo.TrainingQuestions ON;
    EXEC sys.sp_executesql @RestoreSql;
    SET IDENTITY_INSERT dbo.TrainingQuestions OFF;

    UPDATE a SET QuestionNo = m.NewQuestionNo
    FROM dbo.TrainingAnswers AS a JOIN #QuestionMap AS m ON m.TemporaryQuestionNo = a.QuestionNo;
    UPDATE sq SET QuestionNo = m.NewQuestionNo
    FROM dbo.TrainingSessionQuestions AS sq JOIN #QuestionMap AS m ON m.TemporaryQuestionNo = sq.QuestionNo;
    UPDATE w SET QuestionNo = m.NewQuestionNo
    FROM dbo.TrainingWrongQuestions AS w JOIN #QuestionMap AS m ON m.TemporaryQuestionNo = w.QuestionNo;

    IF @EnableForeignKeys IS NOT NULL EXEC sys.sp_executesql @EnableForeignKeys;
    IF (SELECT COUNT_BIG(*) FROM dbo.TrainingQuestions) <> (SELECT COUNT_BIG(*) FROM #QuestionBackup)
        THROW 51000, N'重編後題目筆數不一致，回復交易。', 1;
    IF EXISTS (SELECT 1 FROM dbo.TrainingQuestions WHERE QuestionNo <> CONVERT(NVARCHAR(50), Id))
        THROW 51000, N'重編後 Id 與 QuestionNo 不一致，回復交易。', 1;

    DECLARE @LastId INT = ISNULL((SELECT MAX(Id) FROM dbo.TrainingQuestions), 0);
    DECLARE @ReseedSql NVARCHAR(MAX) = N'DBCC CHECKIDENT (N''dbo.TrainingQuestions'', RESEED, '
        + CONVERT(NVARCHAR(10), @LastId) + N') WITH NO_INFOMSGS;';
    EXEC sys.sp_executesql @ReseedSql;
    -- 保持舊序列可供查閱；新版新增題目已改為在交易內同步分配兩個編號。
    IF OBJECT_ID(N'dbo.TrainingQuestionsNumbers', N'SO') IS NOT NULL
    BEGIN
        DECLARE @SequenceSql NVARCHAR(MAX) = N'ALTER SEQUENCE dbo.TrainingQuestionsNumbers RESTART WITH '
            + CONVERT(NVARCHAR(20), CONVERT(BIGINT, @LastId) + 1) + N' NO CACHE;';
        EXEC sys.sp_executesql @SequenceSql;
    END;
    COMMIT TRANSACTION;
    SELECT Id, QuestionNo, QuestionText FROM dbo.TrainingQuestions ORDER BY Id;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    BEGIN TRY
        SET IDENTITY_INSERT dbo.TrainingQuestions OFF;
    END TRY
    BEGIN CATCH
        PRINT N'請關閉此查詢連線，清除可能殘留的 IDENTITY_INSERT 設定。';
    END CATCH;
    THROW;
END CATCH;
