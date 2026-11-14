-- 只還原題庫缺少的 QuestionNo，保留三張作答表與快照中的既有編號。
SET NOCOUNT ON;
SET XACT_ABORT ON;
SET LOCK_TIMEOUT 10000;
DECLARE @Apply BIT = 0;

IF DB_NAME() <> N'Company'
    THROW 51000,N'請在 Company 資料庫執行。',1;
IF @@TRANCOUNT <> 0
    THROW 51000,N'請使用沒有既有交易的連線。',1;

BEGIN TRY
    BEGIN TRANSACTION;
    DECLARE @Rows BIGINT;
    SELECT @Rows=COUNT_BIG(*) FROM dbo.TrainingQuestions WITH(TABLOCKX,HOLDLOCK);
    SELECT @Rows=COUNT_BIG(*) FROM dbo.TrainingAnswers WITH(TABLOCKX,HOLDLOCK);
    SELECT @Rows=COUNT_BIG(*) FROM dbo.TrainingSessionQuestions WITH(TABLOCKX,HOLDLOCK);
    SELECT @Rows=COUNT_BIG(*) FROM dbo.TrainingWrongQuestions WITH(TABLOCKX,HOLDLOCK);

    IF OBJECT_ID(N'dbo.TR_TrainingQuestions_PermanentQuestionNo',N'TR') IS NOT NULL
       AND EXISTS (SELECT 1 FROM dbo.TrainingQuestions WHERE QuestionNo IS NULL OR QuestionNo=N'')
        THROW 51000,N'永久編號保護已安裝，不得藉修復腳本改號；請先人工確認遺失原因。',1;

    IF EXISTS(SELECT 1 FROM dbo.TrainingSessionQuestions WHERE ISJSON(SnapshotJson)<>1 OR SnapshotJson IS NULL)
        THROW 51000,N'歷史題目快照不是有效 JSON，停止修復。',1;
    IF EXISTS(SELECT 1 FROM dbo.TrainingQuestions WHERE ISJSON(OptionsJson)<>1 OR OptionsJson IS NULL)
        THROW 51000,N'題目選項不是有效 JSON，停止修復。',1;
    IF EXISTS(SELECT 1 FROM dbo.TrainingSessionQuestions WHERE QuestionNo<>JSON_VALUE(SnapshotJson,'$.id') OR JSON_VALUE(SnapshotJson,'$.id') IS NULL)
        THROW 51000,N'作答表與快照的題目編號不一致，停止修復。',1;

    SELECT QuestionNo INTO #ReferencedNumbers FROM (
        SELECT QuestionNo FROM dbo.TrainingAnswers
        UNION SELECT QuestionNo FROM dbo.TrainingSessionQuestions
        UNION SELECT QuestionNo FROM dbo.TrainingWrongQuestions
    ) n;
    IF EXISTS(SELECT 1 FROM #ReferencedNumbers WHERE TRY_CONVERT(INT,QuestionNo)<1 OR TRY_CONVERT(INT,QuestionNo) IS NULL)
        THROW 51000,N'三張作答表有無效的 QuestionNo，停止修復。',1;

    ;WITH snapshots AS (
        SELECT sq.QuestionNo,JSON_VALUE(sq.SnapshotJson,'$.question_type') AS QuestionType,
            JSON_VALUE(sq.SnapshotJson,'$.subject') AS SubjectName,
            JSON_QUERY(sq.SnapshotJson,'$.options') AS OptionsJson,
            REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(JSON_VALUE(sq.SnapshotJson,'$.question'),N'：',N':'),NCHAR(13),N''),NCHAR(10),N''),NCHAR(9),N''),N' ',N'') AS QuestionText
        FROM dbo.TrainingSessionQuestions sq
    ), questions AS (
        SELECT q.Id,q.QuestionType,q.OptionsJson,s.SubjectName,
            REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(q.QuestionText,N'：',N':'),NCHAR(13),N''),NCHAR(10),N''),NCHAR(9),N''),N' ',N'') AS QuestionText
        FROM dbo.TrainingQuestions q JOIN dbo.TrainingSubjects s ON s.SubjectNo=q.SubjectNo
    )
    SELECT DISTINCT history.QuestionNo,currentQuestion.Id AS QuestionId
    INTO #Candidates
    FROM snapshots history JOIN questions currentQuestion
        ON history.QuestionType=currentQuestion.QuestionType
        AND history.SubjectName=currentQuestion.SubjectName
        AND history.QuestionText COLLATE Latin1_General_100_BIN2=currentQuestion.QuestionText COLLATE Latin1_General_100_BIN2
    WHERE ISJSON(history.OptionsJson)=1 AND NOT EXISTS(
        SELECT 1 FROM OPENJSON(history.OptionsJson) oldOption
        FULL OUTER JOIN OPENJSON(currentQuestion.OptionsJson) newOption ON oldOption.[key]=newOption.[key]
        WHERE oldOption.[key] IS NULL OR newOption.[key] IS NULL
            OR oldOption.[type]<>newOption.[type]
            OR oldOption.[value] COLLATE Latin1_General_100_BIN2<>newOption.[value] COLLATE Latin1_General_100_BIN2
    );

    SELECT n.QuestionNo,MIN(c.QuestionId) AS QuestionId,COUNT(c.QuestionId) AS CandidateCount
    INTO #Mapping FROM #ReferencedNumbers n LEFT JOIN #Candidates c ON c.QuestionNo=n.QuestionNo GROUP BY n.QuestionNo;
    SELECT COUNT(*) AS ReferencedNumbers,SUM(CASE WHEN CandidateCount=1 THEN 1 ELSE 0 END) AS UniqueMatches,
        SUM(CASE WHEN CandidateCount=0 THEN 1 ELSE 0 END) AS MissingMatches,
        SUM(CASE WHEN CandidateCount>1 THEN 1 ELSE 0 END) AS AmbiguousMatches FROM #Mapping;
    IF EXISTS(SELECT 1 FROM #Mapping WHERE CandidateCount<>1)
        THROW 51000,N'有無法唯一確認的題目，未修改資料。',1;
    IF EXISTS(SELECT QuestionId FROM #Mapping GROUP BY QuestionId HAVING COUNT(*)>1)
        THROW 51000,N'多個歷史編號指向同一題目，未修改資料。',1;
    IF EXISTS(SELECT 1 FROM dbo.TrainingQuestions q LEFT JOIN #Mapping m ON m.QuestionId=q.Id WHERE m.QuestionId IS NULL AND (q.QuestionNo IS NULL OR LTRIM(RTRIM(q.QuestionNo))=N''))
        THROW 51000,N'存在無歷史對照的空白題號，不能推測編號。',1;
    IF EXISTS(SELECT 1 FROM dbo.TrainingQuestions q JOIN #Mapping m ON m.QuestionId=q.Id WHERE q.QuestionNo IS NOT NULL AND q.QuestionNo<>N'' AND q.QuestionNo<>m.QuestionNo)
        THROW 51000,N'現有題號與歷史證據不同，未覆寫既有值。',1;

    SELECT q.Id,q.QuestionNo AS BeforeQuestionNo,m.QuestionNo AS RestoredQuestionNo
    FROM dbo.TrainingQuestions q JOIN #Mapping m ON m.QuestionId=q.Id ORDER BY q.Id;
    IF @Apply=0
    BEGIN
        ROLLBACK TRANSACTION;
        SELECT N'PreviewOnly' AS Result;
        RETURN;
    END;

    UPDATE q SET QuestionNo=m.QuestionNo
    FROM dbo.TrainingQuestions q JOIN #Mapping m ON m.QuestionId=q.Id
    WHERE q.QuestionNo IS NULL OR q.QuestionNo=N'';
    DECLARE @RestoredRows INT=@@ROWCOUNT;

    -- BEGIN TrainingQuestionNoContract
    -- 建表與歷史修復須同步本區塊；只保護結構，不重編既有資料。
    DECLARE @QuestionContractRows BIGINT;
    SELECT @QuestionContractRows=COUNT_BIG(*) FROM dbo.TrainingQuestions WITH (TABLOCKX,HOLDLOCK);
    IF EXISTS (
        SELECT 1 FROM dbo.TrainingQuestions
        WHERE QuestionNo IS NULL OR TRY_CONVERT(INT,QuestionNo) IS NULL OR TRY_CONVERT(INT,QuestionNo)<1
           OR CONVERT(VARBINARY(100),QuestionNo)
              <> CONVERT(VARBINARY(100),CONVERT(NVARCHAR(50),TRY_CONVERT(INT,QuestionNo)))
    )
        THROW 51010, N'存在無效的 QuestionNo，請先核對歷史資料；建置不會自動改號。', 1;

    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_TrainingQuestions_1' AND object_id=OBJECT_ID(N'dbo.TrainingQuestions'))
        CREATE UNIQUE INDEX UX_TrainingQuestions_1 ON dbo.TrainingQuestions(QuestionNo);
    IF NOT EXISTS (
        SELECT 1 FROM sys.indexes i
        WHERE i.object_id=OBJECT_ID(N'dbo.TrainingQuestions') AND i.name=N'UX_TrainingQuestions_1'
          AND i.is_unique=1 AND i.is_disabled=0 AND i.has_filter=0 AND i.ignore_dup_key=0
          AND (SELECT COUNT(*) FROM sys.index_columns ic
               WHERE ic.object_id=i.object_id AND ic.index_id=i.index_id AND ic.key_ordinal>0)=1
          AND EXISTS (SELECT 1 FROM sys.index_columns ic JOIN sys.columns c
                      ON c.object_id=ic.object_id AND c.column_id=ic.column_id
                      WHERE ic.object_id=i.object_id AND ic.index_id=i.index_id AND ic.key_ordinal=1 AND c.name=N'QuestionNo')
    )
        THROW 51010, N'UX_TrainingQuestions_1 定義不符，請先確認索引；不會自動覆寫。', 1;

    IF OBJECT_ID(N'dbo.FK_TrainingAnswers_QuestionNo',N'F') IS NULL
        ALTER TABLE dbo.TrainingAnswers WITH CHECK ADD CONSTRAINT FK_TrainingAnswers_QuestionNo
            FOREIGN KEY(QuestionNo) REFERENCES dbo.TrainingQuestions(QuestionNo) ON UPDATE NO ACTION ON DELETE NO ACTION;
    IF NOT EXISTS (
        SELECT 1 FROM sys.foreign_keys fk
        WHERE fk.object_id=OBJECT_ID(N'dbo.FK_TrainingAnswers_QuestionNo',N'F')
          AND fk.parent_object_id=OBJECT_ID(N'dbo.TrainingAnswers')
          AND fk.referenced_object_id=OBJECT_ID(N'dbo.TrainingQuestions')
          AND fk.update_referential_action=0 AND fk.delete_referential_action=0
          AND (SELECT COUNT(*) FROM sys.foreign_key_columns fc WHERE fc.constraint_object_id=fk.object_id)=1
          AND EXISTS (SELECT 1 FROM sys.foreign_key_columns fc
                      JOIN sys.columns pc ON pc.object_id=fc.parent_object_id AND pc.column_id=fc.parent_column_id
                      JOIN sys.columns rc ON rc.object_id=fc.referenced_object_id AND rc.column_id=fc.referenced_column_id
                      WHERE fc.constraint_object_id=fk.object_id AND pc.name=N'QuestionNo' AND rc.name=N'QuestionNo')
    )
        THROW 51010, N'FK_TrainingAnswers_QuestionNo 定義不符，必須以 QuestionNo 關聯主檔。', 1;
    ALTER TABLE dbo.TrainingAnswers WITH CHECK CHECK CONSTRAINT FK_TrainingAnswers_QuestionNo;

    IF OBJECT_ID(N'dbo.FK_TrainingSessionQuestions_QuestionNo',N'F') IS NULL
        ALTER TABLE dbo.TrainingSessionQuestions WITH CHECK ADD CONSTRAINT FK_TrainingSessionQuestions_QuestionNo
            FOREIGN KEY(QuestionNo) REFERENCES dbo.TrainingQuestions(QuestionNo) ON UPDATE NO ACTION ON DELETE NO ACTION;
    IF NOT EXISTS (
        SELECT 1 FROM sys.foreign_keys fk
        WHERE fk.object_id=OBJECT_ID(N'dbo.FK_TrainingSessionQuestions_QuestionNo',N'F')
          AND fk.parent_object_id=OBJECT_ID(N'dbo.TrainingSessionQuestions')
          AND fk.referenced_object_id=OBJECT_ID(N'dbo.TrainingQuestions')
          AND fk.update_referential_action=0 AND fk.delete_referential_action=0
          AND (SELECT COUNT(*) FROM sys.foreign_key_columns fc WHERE fc.constraint_object_id=fk.object_id)=1
          AND EXISTS (SELECT 1 FROM sys.foreign_key_columns fc
                      JOIN sys.columns pc ON pc.object_id=fc.parent_object_id AND pc.column_id=fc.parent_column_id
                      JOIN sys.columns rc ON rc.object_id=fc.referenced_object_id AND rc.column_id=fc.referenced_column_id
                      WHERE fc.constraint_object_id=fk.object_id AND pc.name=N'QuestionNo' AND rc.name=N'QuestionNo')
    )
        THROW 51010, N'FK_TrainingSessionQuestions_QuestionNo 定義不符，必須以 QuestionNo 關聯主檔。', 1;
    ALTER TABLE dbo.TrainingSessionQuestions WITH CHECK CHECK CONSTRAINT FK_TrainingSessionQuestions_QuestionNo;

    IF OBJECT_ID(N'dbo.FK_TrainingWrongQuestions_QuestionNo',N'F') IS NULL
        ALTER TABLE dbo.TrainingWrongQuestions WITH CHECK ADD CONSTRAINT FK_TrainingWrongQuestions_QuestionNo
            FOREIGN KEY(QuestionNo) REFERENCES dbo.TrainingQuestions(QuestionNo) ON UPDATE NO ACTION ON DELETE NO ACTION;
    IF NOT EXISTS (
        SELECT 1 FROM sys.foreign_keys fk
        WHERE fk.object_id=OBJECT_ID(N'dbo.FK_TrainingWrongQuestions_QuestionNo',N'F')
          AND fk.parent_object_id=OBJECT_ID(N'dbo.TrainingWrongQuestions')
          AND fk.referenced_object_id=OBJECT_ID(N'dbo.TrainingQuestions')
          AND fk.update_referential_action=0 AND fk.delete_referential_action=0
          AND (SELECT COUNT(*) FROM sys.foreign_key_columns fc WHERE fc.constraint_object_id=fk.object_id)=1
          AND EXISTS (SELECT 1 FROM sys.foreign_key_columns fc
                      JOIN sys.columns pc ON pc.object_id=fc.parent_object_id AND pc.column_id=fc.parent_column_id
                      JOIN sys.columns rc ON rc.object_id=fc.referenced_object_id AND rc.column_id=fc.referenced_column_id
                      WHERE fc.constraint_object_id=fk.object_id AND pc.name=N'QuestionNo' AND rc.name=N'QuestionNo')
    )
        THROW 51010, N'FK_TrainingWrongQuestions_QuestionNo 定義不符，必須以 QuestionNo 關聯主檔。', 1;
    ALTER TABLE dbo.TrainingWrongQuestions WITH CHECK CHECK CONSTRAINT FK_TrainingWrongQuestions_QuestionNo;

    EXEC(N'CREATE OR ALTER TRIGGER dbo.TR_TrainingQuestions_PermanentQuestionNo
    ON dbo.TrainingQuestions
    AFTER INSERT, UPDATE, DELETE
    AS
    BEGIN
        SET NOCOUNT ON;
        IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted)
            RETURN;

        -- 保留停用與軟刪除資料，才能持續保留已發出的編號與歷史關聯。
        IF EXISTS (SELECT 1 FROM deleted d LEFT JOIN inserted i ON i.Id=d.Id WHERE i.Id IS NULL)
            THROW 51011, N''題目永久編號不得刪除；請使用停用或軟刪除。'', 1;
        IF EXISTS (
            SELECT 1 FROM inserted i JOIN deleted d ON d.Id=i.Id
            WHERE ISNULL(CONVERT(VARBINARY(100),i.QuestionNo),0x)
               <> ISNULL(CONVERT(VARBINARY(100),d.QuestionNo),0x)
        )
            THROW 51012, N''QuestionNo 是永久編號，建立後不得修改。'', 1;

        IF EXISTS (
            SELECT 1 FROM inserted
            WHERE QuestionNo IS NULL OR TRY_CONVERT(INT,QuestionNo) IS NULL OR TRY_CONVERT(INT,QuestionNo)<1
               OR CONVERT(VARBINARY(100),QuestionNo)
                  <> CONVERT(VARBINARY(100),CONVERT(NVARCHAR(50),TRY_CONVERT(INT,QuestionNo)))
        )
            THROW 51013, N''QuestionNo 必須是標準格式的正整數編號。'', 1;

        IF EXISTS (SELECT 1 FROM inserted i LEFT JOIN deleted d ON d.Id=i.Id WHERE d.Id IS NULL)
        BEGIN
            DECLARE @PreviousQuestionNo BIGINT;
            SELECT @PreviousQuestionNo=ISNULL(MAX(TRY_CONVERT(BIGINT,q.QuestionNo)),0)
            FROM dbo.TrainingQuestions q WITH (TABLOCKX,HOLDLOCK)
            WHERE NOT EXISTS (
                SELECT 1 FROM inserted i LEFT JOIN deleted d ON d.Id=i.Id
                WHERE d.Id IS NULL AND i.Id=q.Id
            );
            IF EXISTS (
                SELECT 1 FROM inserted i LEFT JOIN deleted d ON d.Id=i.Id
                WHERE d.Id IS NULL AND TRY_CONVERT(BIGINT,i.QuestionNo)<=@PreviousQuestionNo
            )
                THROW 51014, N''新增題目只能使用大於既有最大題號的新編號，不得補號或重用。'', 1;
        END;
    END;');
    ENABLE TRIGGER dbo.TR_TrainingQuestions_PermanentQuestionNo ON dbo.TrainingQuestions;
    -- END TrainingQuestionNoContract

    IF EXISTS(SELECT 1 FROM #ReferencedNumbers n LEFT JOIN dbo.TrainingQuestions q ON q.QuestionNo=n.QuestionNo WHERE q.Id IS NULL)
        THROW 51000,N'修復後仍有孤兒關聯，回復交易。',1;
    COMMIT TRANSACTION;
    SELECT N'Restored' AS Result,@RestoredRows AS RestoredQuestions;
END TRY
BEGIN CATCH
    IF XACT_STATE()<>0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
