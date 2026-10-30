-- 全新資料庫結構；不會搬移或覆寫既有資料。
SET XACT_ABORT ON;
GO
IF OBJECT_ID(N'dbo.TrainingDocumentsNumbers', N'SO') IS NULL
CREATE SEQUENCE dbo.[TrainingDocumentsNumbers] AS INT START WITH 1 INCREMENT BY 1;
GO
IF OBJECT_ID(N'dbo.TrainingSubjectsNumbers', N'SO') IS NULL
CREATE SEQUENCE dbo.[TrainingSubjectsNumbers] AS INT START WITH 1 INCREMENT BY 1;
GO
IF OBJECT_ID(N'dbo.TrainingChaptersNumbers', N'SO') IS NULL
CREATE SEQUENCE dbo.[TrainingChaptersNumbers] AS INT START WITH 1 INCREMENT BY 1;
GO
IF OBJECT_ID(N'dbo.TrainingQuestionsNumbers', N'SO') IS NULL
CREATE SEQUENCE dbo.[TrainingQuestionsNumbers] AS INT START WITH 1 INCREMENT BY 1;
GO
IF OBJECT_ID(N'dbo.WebSettings', N'U') IS NULL
CREATE TABLE dbo.[WebSettings] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [WebSettingNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [ThemeCode] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [HeroTitle] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [HeroSubtitle] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [Announcement] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [UpdatedBy] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [UpdatedAt] DATETIME2 NULL DEFAULT (SYSDATETIME()),
    [Remark] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NULL DEFAULT (GETDATE())
);
GO
IF OBJECT_ID(N'dbo.Departments', N'U') IS NULL
CREATE TABLE dbo.[Departments] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [DepartmentNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [IsActive] BIT NULL DEFAULT (0),
    [UpdatedBy] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [UpdatedAt] DATETIME2 NULL DEFAULT (SYSDATETIME()),
    [Remark] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NULL DEFAULT (GETDATE())
);
GO
IF OBJECT_ID(N'dbo.Employees', N'U') IS NULL
CREATE TABLE dbo.[Employees] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [EmployeeNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [EmployeeName] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [Gender] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [Age] INT NULL DEFAULT (0),
    [DepartmentNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [PositionName] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [Traits] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [Biography] NVARCHAR(MAX) NULL DEFAULT (SPACE(0)),
    [PhotoFile] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [IsActive] BIT NULL DEFAULT (0),
    [UpdatedBy] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [UpdatedAt] DATETIME2 NULL DEFAULT (SYSDATETIME()),
    [Remark] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NULL DEFAULT (GETDATE())
);
GO
IF OBJECT_ID(N'dbo.OperationCategories', N'U') IS NULL
CREATE TABLE dbo.[OperationCategories] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [CategoryNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [DisplayOrder] INT NULL DEFAULT (0),
    [Remark] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NULL DEFAULT (GETDATE())
);
GO
IF OBJECT_ID(N'dbo.AttendanceRecords', N'U') IS NULL
CREATE TABLE dbo.[AttendanceRecords] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [EmployeeNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [AttendanceAction] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [ClockedAt] DATETIME2 NULL DEFAULT (SYSDATETIME()),
    [ClockedAtUtc] DATETIME2 NULL,
    [WorkDate] DATE NULL,
    [SourceIp] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [Remark] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NULL DEFAULT (GETDATE())
);
GO
IF OBJECT_ID(N'dbo.OperationSubmissions', N'U') IS NULL
CREATE TABLE dbo.[OperationSubmissions] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [SheetNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [SheetDate] DATE NULL,
    [CampusCode] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [CategoryNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [Quantity] INT NULL DEFAULT (0),
    [SubmissionNote] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [EmployeeNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [ReviewStatus] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [SubmittedAt] DATETIME2 NULL DEFAULT (SYSDATETIME()),
    [Remark] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NULL DEFAULT (GETDATE())
);
GO
IF OBJECT_ID(N'dbo.OperationActivities', N'U') IS NULL
CREATE TABLE dbo.[OperationActivities] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [SheetNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [ActivityAction] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [ActivityMessage] NVARCHAR(MAX) NULL DEFAULT (SPACE(0)),
    [EmployeeNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [ActorRole] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [ActivityTime] DATETIME2 NULL DEFAULT (SYSDATETIME()),
    [Remark] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NULL DEFAULT (GETDATE())
);
GO
IF OBJECT_ID(N'dbo.TrainingDocuments', N'U') IS NULL
CREATE TABLE dbo.[TrainingDocuments] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [DocumentNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [FileName] NVARCHAR(MAX) NULL DEFAULT (SPACE(0)),
    [DocumentTitle] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [RoleCategory] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [SourceSize] INT NULL DEFAULT (0),
    [SourceModified] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [IsActive] BIT NULL DEFAULT (0),
    [ImportedAt] DATETIME2 NULL DEFAULT (SYSDATETIME()),
    [SourceKind] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [ParseStatus] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [ParseMessage] NVARCHAR(MAX) NULL DEFAULT (SPACE(0)),
    [FileNameDigest] AS CONVERT(VARBINARY(32),HASHBYTES('SHA2_256',[FileName])) PERSISTED,
    [Remark] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NULL DEFAULT (GETDATE())
);
GO
IF OBJECT_ID(N'dbo.TrainingSections', N'U') IS NULL
CREATE TABLE dbo.[TrainingSections] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [DocumentNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [SectionOrder] INT NULL DEFAULT (0),
    [Heading] NVARCHAR(MAX) NULL DEFAULT (SPACE(0)),
    [SectionContent] NVARCHAR(MAX) NULL DEFAULT (SPACE(0)),
    [Remark] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NULL DEFAULT (GETDATE())
);
GO
IF OBJECT_ID(N'dbo.TrainingSubjects', N'U') IS NULL
CREATE TABLE dbo.[TrainingSubjects] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [SubjectNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [TrainingDomain] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [SubjectName] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [MockQuestionCount] INT NULL DEFAULT (0),
    [MockDurationMinutes] INT NULL DEFAULT (0),
    [MockPassScore] INT NULL DEFAULT (0),
    [IsActive] BIT NULL DEFAULT (0),
    [Remark] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NULL DEFAULT (GETDATE())
);
GO
IF OBJECT_ID(N'dbo.TrainingChapters', N'U') IS NULL
CREATE TABLE dbo.[TrainingChapters] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [ChapterNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [SubjectNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [ChapterCode] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [ChapterName] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [DisplayOrder] INT NULL DEFAULT (0),
    [IsActive] BIT NULL DEFAULT (0),
    [Remark] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NULL DEFAULT (GETDATE())
);
GO
IF OBJECT_ID(N'dbo.TrainingQuestions', N'U') IS NULL
CREATE TABLE dbo.[TrainingQuestions] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [QuestionNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [DocumentNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [CategoryName] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [QuestionText] NVARCHAR(MAX) NULL DEFAULT (SPACE(0)),
    [OptionsJson] NVARCHAR(MAX) NULL DEFAULT (SPACE(0)),
    [CorrectIndex] INT NULL DEFAULT (0),
    [Explanation] NVARCHAR(MAX) NULL DEFAULT (SPACE(0)),
    [QuestionType] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [AnswerJson] NVARCHAR(MAX) NULL DEFAULT (SPACE(0)),
    [Passage] NVARCHAR(MAX) NULL DEFAULT (SPACE(0)),
    [IsActive] BIT NULL DEFAULT (0),
    [TrainingDomain] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [SubjectNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [ChapterNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [ContentJson] NVARCHAR(MAX) NULL DEFAULT (SPACE(0)),
    [StructureJson] NVARCHAR(MAX) NULL DEFAULT (SPACE(0)),
    [SourceLocator] NVARCHAR(MAX) NULL DEFAULT (SPACE(0)),
    [SourceQuestionKey] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [SourceFingerprint] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [ParseConfidence] DECIMAL(18,4) NULL DEFAULT (0),
    [ParseWarningsJson] NVARCHAR(MAX) NULL DEFAULT (SPACE(0)),
    [QuestionStatus] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [IsAdminLocked] BIT NULL DEFAULT (0),
    [UpdatedAt] DATETIME2 NULL DEFAULT (SYSDATETIME()),
    [DeletedAt] DATETIME2 NULL,
    [Remark] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NULL DEFAULT (GETDATE())
);
GO
IF OBJECT_ID(N'dbo.TrainingAnswers', N'U') IS NULL
CREATE TABLE dbo.[TrainingAnswers] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [QuestionNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [EmployeeNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [AnswerText] NVARCHAR(MAX) NULL DEFAULT (SPACE(0)),
    [ReviewStatus] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [Feedback] NVARCHAR(MAX) NULL DEFAULT (SPACE(0)),
    [SubmittedAt] DATETIME2 NULL DEFAULT (SYSDATETIME()),
    [ReviewerNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [ReviewedAt] DATETIME2 NULL,
    [Remark] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NULL DEFAULT (GETDATE())
);
GO
IF OBJECT_ID(N'dbo.TrainingSessions', N'U') IS NULL
CREATE TABLE dbo.[TrainingSessions] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [SessionNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [EmployeeNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [SubjectNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [TrainingMode] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [SessionStatus] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [ConfigJson] NVARCHAR(MAX) NULL DEFAULT (SPACE(0)),
    [StartedAt] DATETIME2 NULL DEFAULT (SYSUTCDATETIME()),
    [ExpiresAt] DATETIME2 NULL,
    [SubmittedAt] DATETIME2 NULL,
    [Score] DECIMAL(18,4) NULL DEFAULT (0),
    [Remark] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NULL DEFAULT (GETDATE())
);
GO
IF OBJECT_ID(N'dbo.TrainingSessionQuestions', N'U') IS NULL
CREATE TABLE dbo.[TrainingSessionQuestions] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [SessionNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [QuestionNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [QuestionOrder] INT NULL DEFAULT (0),
    [SnapshotJson] NVARCHAR(MAX) NULL DEFAULT (SPACE(0)),
    [ResponseJson] NVARCHAR(MAX) NULL DEFAULT (SPACE(0)),
    [IsFlagged] BIT NULL DEFAULT (0),
    [IsCorrect] BIT NULL DEFAULT (0),
    [AnsweredAt] DATETIME2 NULL,
    [Remark] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NULL DEFAULT (GETDATE())
);
GO
IF OBJECT_ID(N'dbo.TrainingWrongQuestions', N'U') IS NULL
CREATE TABLE dbo.[TrainingWrongQuestions] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [EmployeeNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [QuestionNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [AddedAt] DATETIME2 NULL DEFAULT (SYSUTCDATETIME()),
    [RemovedAt] DATETIME2 NULL,
    [Remark] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NULL DEFAULT (GETDATE())
);
GO
IF OBJECT_ID(N'dbo.ImportStates', N'U') IS NULL
CREATE TABLE dbo.[ImportStates] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [ImportSourceNo] NVARCHAR(50) NULL DEFAULT (SPACE(0)),
    [SourceModifiedAt] DATETIME2 NULL,
    [SourceSize] INT NULL DEFAULT (0),
    [ImportedRows] INT NULL DEFAULT (0),
    [ImportedAt] DATETIME2 NULL DEFAULT (SYSDATETIME()),
    [Remark] NVARCHAR(250) NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NULL DEFAULT (GETDATE())
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_WebSettings_1' AND object_id=OBJECT_ID(N'dbo.WebSettings'))
CREATE UNIQUE INDEX [UX_WebSettings_1] ON dbo.[WebSettings] ([WebSettingNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_Departments_1' AND object_id=OBJECT_ID(N'dbo.Departments'))
CREATE UNIQUE INDEX [UX_Departments_1] ON dbo.[Departments] ([DepartmentNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_Employees_1' AND object_id=OBJECT_ID(N'dbo.Employees'))
CREATE UNIQUE INDEX [UX_Employees_1] ON dbo.[Employees] ([EmployeeNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_OperationCategories_1' AND object_id=OBJECT_ID(N'dbo.OperationCategories'))
CREATE UNIQUE INDEX [UX_OperationCategories_1] ON dbo.[OperationCategories] ([CategoryNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_OperationCategories_2' AND object_id=OBJECT_ID(N'dbo.OperationCategories'))
CREATE UNIQUE INDEX [UX_OperationCategories_2] ON dbo.[OperationCategories] ([DisplayOrder]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_OperationSubmissions_1' AND object_id=OBJECT_ID(N'dbo.OperationSubmissions'))
CREATE UNIQUE INDEX [UX_OperationSubmissions_1] ON dbo.[OperationSubmissions] ([SheetNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_TrainingDocuments_1' AND object_id=OBJECT_ID(N'dbo.TrainingDocuments'))
CREATE UNIQUE INDEX [UX_TrainingDocuments_1] ON dbo.[TrainingDocuments] ([DocumentNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_TrainingSections_1' AND object_id=OBJECT_ID(N'dbo.TrainingSections'))
CREATE UNIQUE INDEX [UX_TrainingSections_1] ON dbo.[TrainingSections] ([DocumentNo],[SectionOrder]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_TrainingSubjects_1' AND object_id=OBJECT_ID(N'dbo.TrainingSubjects'))
CREATE UNIQUE INDEX [UX_TrainingSubjects_1] ON dbo.[TrainingSubjects] ([SubjectNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_TrainingSubjects_2' AND object_id=OBJECT_ID(N'dbo.TrainingSubjects'))
CREATE UNIQUE INDEX [UX_TrainingSubjects_2] ON dbo.[TrainingSubjects] ([TrainingDomain],[SubjectName]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_TrainingChapters_1' AND object_id=OBJECT_ID(N'dbo.TrainingChapters'))
CREATE UNIQUE INDEX [UX_TrainingChapters_1] ON dbo.[TrainingChapters] ([ChapterNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_TrainingChapters_2' AND object_id=OBJECT_ID(N'dbo.TrainingChapters'))
CREATE UNIQUE INDEX [UX_TrainingChapters_2] ON dbo.[TrainingChapters] ([SubjectNo],[ChapterCode]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_TrainingQuestions_1' AND object_id=OBJECT_ID(N'dbo.TrainingQuestions'))
CREATE UNIQUE INDEX [UX_TrainingQuestions_1] ON dbo.[TrainingQuestions] ([QuestionNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_TrainingSessions_1' AND object_id=OBJECT_ID(N'dbo.TrainingSessions'))
CREATE UNIQUE INDEX [UX_TrainingSessions_1] ON dbo.[TrainingSessions] ([SessionNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_TrainingSessionQuestions_1' AND object_id=OBJECT_ID(N'dbo.TrainingSessionQuestions'))
CREATE UNIQUE INDEX [UX_TrainingSessionQuestions_1] ON dbo.[TrainingSessionQuestions] ([SessionNo],[QuestionOrder]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_TrainingWrongQuestions_1' AND object_id=OBJECT_ID(N'dbo.TrainingWrongQuestions'))
CREATE UNIQUE INDEX [UX_TrainingWrongQuestions_1] ON dbo.[TrainingWrongQuestions] ([EmployeeNo],[QuestionNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_ImportStates_1' AND object_id=OBJECT_ID(N'dbo.ImportStates'))
CREATE UNIQUE INDEX [UX_ImportStates_1] ON dbo.[ImportStates] ([ImportSourceNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_Employees_DepartmentNo')
ALTER TABLE dbo.[Employees] WITH CHECK ADD CONSTRAINT [FK_Employees_DepartmentNo] FOREIGN KEY ([DepartmentNo]) REFERENCES dbo.[Departments] ([DepartmentNo]) ON UPDATE CASCADE;
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_AttendanceRecords_EmployeeNo')
ALTER TABLE dbo.[AttendanceRecords] WITH CHECK ADD CONSTRAINT [FK_AttendanceRecords_EmployeeNo] FOREIGN KEY ([EmployeeNo]) REFERENCES dbo.[Employees] ([EmployeeNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_OperationSubmissions_CategoryNo')
ALTER TABLE dbo.[OperationSubmissions] WITH CHECK ADD CONSTRAINT [FK_OperationSubmissions_CategoryNo] FOREIGN KEY ([CategoryNo]) REFERENCES dbo.[OperationCategories] ([CategoryNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_OperationSubmissions_EmployeeNo')
ALTER TABLE dbo.[OperationSubmissions] WITH CHECK ADD CONSTRAINT [FK_OperationSubmissions_EmployeeNo] FOREIGN KEY ([EmployeeNo]) REFERENCES dbo.[Employees] ([EmployeeNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_OperationActivities_SheetNo')
ALTER TABLE dbo.[OperationActivities] WITH CHECK ADD CONSTRAINT [FK_OperationActivities_SheetNo] FOREIGN KEY ([SheetNo]) REFERENCES dbo.[OperationSubmissions] ([SheetNo]) ON DELETE CASCADE;
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_OperationActivities_EmployeeNo')
ALTER TABLE dbo.[OperationActivities] WITH CHECK ADD CONSTRAINT [FK_OperationActivities_EmployeeNo] FOREIGN KEY ([EmployeeNo]) REFERENCES dbo.[Employees] ([EmployeeNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_TrainingSections_DocumentNo')
ALTER TABLE dbo.[TrainingSections] WITH CHECK ADD CONSTRAINT [FK_TrainingSections_DocumentNo] FOREIGN KEY ([DocumentNo]) REFERENCES dbo.[TrainingDocuments] ([DocumentNo]) ON DELETE CASCADE;
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_TrainingChapters_SubjectNo')
ALTER TABLE dbo.[TrainingChapters] WITH CHECK ADD CONSTRAINT [FK_TrainingChapters_SubjectNo] FOREIGN KEY ([SubjectNo]) REFERENCES dbo.[TrainingSubjects] ([SubjectNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_TrainingQuestions_DocumentNo')
ALTER TABLE dbo.[TrainingQuestions] WITH CHECK ADD CONSTRAINT [FK_TrainingQuestions_DocumentNo] FOREIGN KEY ([DocumentNo]) REFERENCES dbo.[TrainingDocuments] ([DocumentNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_TrainingQuestions_SubjectNo')
ALTER TABLE dbo.[TrainingQuestions] WITH CHECK ADD CONSTRAINT [FK_TrainingQuestions_SubjectNo] FOREIGN KEY ([SubjectNo]) REFERENCES dbo.[TrainingSubjects] ([SubjectNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_TrainingQuestions_ChapterNo')
ALTER TABLE dbo.[TrainingQuestions] WITH CHECK ADD CONSTRAINT [FK_TrainingQuestions_ChapterNo] FOREIGN KEY ([ChapterNo]) REFERENCES dbo.[TrainingChapters] ([ChapterNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_TrainingAnswers_QuestionNo')
ALTER TABLE dbo.[TrainingAnswers] WITH CHECK ADD CONSTRAINT [FK_TrainingAnswers_QuestionNo] FOREIGN KEY ([QuestionNo]) REFERENCES dbo.[TrainingQuestions] ([QuestionNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_TrainingAnswers_EmployeeNo')
ALTER TABLE dbo.[TrainingAnswers] WITH CHECK ADD CONSTRAINT [FK_TrainingAnswers_EmployeeNo] FOREIGN KEY ([EmployeeNo]) REFERENCES dbo.[Employees] ([EmployeeNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_TrainingAnswers_ReviewerNo')
ALTER TABLE dbo.[TrainingAnswers] WITH CHECK ADD CONSTRAINT [FK_TrainingAnswers_ReviewerNo] FOREIGN KEY ([ReviewerNo]) REFERENCES dbo.[Employees] ([EmployeeNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_TrainingSessions_EmployeeNo')
ALTER TABLE dbo.[TrainingSessions] WITH CHECK ADD CONSTRAINT [FK_TrainingSessions_EmployeeNo] FOREIGN KEY ([EmployeeNo]) REFERENCES dbo.[Employees] ([EmployeeNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_TrainingSessions_SubjectNo')
ALTER TABLE dbo.[TrainingSessions] WITH CHECK ADD CONSTRAINT [FK_TrainingSessions_SubjectNo] FOREIGN KEY ([SubjectNo]) REFERENCES dbo.[TrainingSubjects] ([SubjectNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_TrainingSessionQuestions_SessionNo')
ALTER TABLE dbo.[TrainingSessionQuestions] WITH CHECK ADD CONSTRAINT [FK_TrainingSessionQuestions_SessionNo] FOREIGN KEY ([SessionNo]) REFERENCES dbo.[TrainingSessions] ([SessionNo]) ON DELETE CASCADE;
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_TrainingSessionQuestions_QuestionNo')
ALTER TABLE dbo.[TrainingSessionQuestions] WITH CHECK ADD CONSTRAINT [FK_TrainingSessionQuestions_QuestionNo] FOREIGN KEY ([QuestionNo]) REFERENCES dbo.[TrainingQuestions] ([QuestionNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_TrainingWrongQuestions_EmployeeNo')
ALTER TABLE dbo.[TrainingWrongQuestions] WITH CHECK ADD CONSTRAINT [FK_TrainingWrongQuestions_EmployeeNo] FOREIGN KEY ([EmployeeNo]) REFERENCES dbo.[Employees] ([EmployeeNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_TrainingWrongQuestions_QuestionNo')
ALTER TABLE dbo.[TrainingWrongQuestions] WITH CHECK ADD CONSTRAINT [FK_TrainingWrongQuestions_QuestionNo] FOREIGN KEY ([QuestionNo]) REFERENCES dbo.[TrainingQuestions] ([QuestionNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_TrainingQuestions_Fingerprint' AND object_id=OBJECT_ID(N'dbo.TrainingQuestions'))
CREATE UNIQUE INDEX UX_TrainingQuestions_Fingerprint ON dbo.TrainingQuestions(SourceFingerprint) WHERE SourceFingerprint IS NOT NULL AND SourceFingerprint<>N'';
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_TrainingDocuments_FileName' AND object_id=OBJECT_ID(N'dbo.TrainingDocuments'))
CREATE UNIQUE INDEX UX_TrainingDocuments_FileName ON dbo.TrainingDocuments(FileNameDigest);
GO
IF OBJECT_ID(N'dbo.CK_Employees_Business',N'C') IS NULL
ALTER TABLE dbo.[Employees] WITH CHECK ADD CONSTRAINT [CK_Employees_Business] CHECK (Age IS NULL OR Age BETWEEN 16 AND 100);
GO
IF OBJECT_ID(N'dbo.CK_AttendanceRecords_Business',N'C') IS NULL
ALTER TABLE dbo.[AttendanceRecords] WITH CHECK ADD CONSTRAINT [CK_AttendanceRecords_Business] CHECK (AttendanceAction IN (N'CLOCK_IN',N'CLOCK_OUT'));
GO
IF OBJECT_ID(N'dbo.CK_OperationSubmissions_Business',N'C') IS NULL
ALTER TABLE dbo.[OperationSubmissions] WITH CHECK ADD CONSTRAINT [CK_OperationSubmissions_Business] CHECK (Quantity BETWEEN 0 AND 9999);
GO
IF OBJECT_ID(N'dbo.CK_TrainingQuestions_Business',N'C') IS NULL
ALTER TABLE dbo.[TrainingQuestions] WITH CHECK ADD CONSTRAINT [CK_TrainingQuestions_Business] CHECK (CorrectIndex BETWEEN 0 AND 9);
GO
IF OBJECT_ID(N'dbo.Company_WebSettings',N'U') IS NULL
EXEC(N'CREATE OR ALTER VIEW dbo.[Company_WebSettings] AS SELECT [WebSettingNo] AS [id], [ThemeCode] AS [theme], [HeroTitle] AS [hero_title], [HeroSubtitle] AS [hero_subtitle], [Announcement] AS [announcement], [UpdatedBy] AS [updated_by], [UpdatedAt] AS [updated_at] FROM dbo.[WebSettings];');
GO
IF OBJECT_ID(N'dbo.Company_Department',N'U') IS NULL
EXEC(N'CREATE OR ALTER VIEW dbo.[Company_Department] AS SELECT [Id] AS [department_id], [DepartmentNo] AS [department_name], [IsActive] AS [is_active], [UpdatedBy] AS [updated_by], [UpdatedAt] AS [updated_at] FROM dbo.[Departments];');
GO
IF OBJECT_ID(N'dbo.Company_Staff',N'U') IS NULL
EXEC(N'CREATE OR ALTER VIEW dbo.[Company_Staff] AS SELECT [EmployeeNo] AS [employee_id], [EmployeeName] AS [display_name], [Gender] AS [gender], [Age] AS [age], [DepartmentNo] AS [department], [PositionName] AS [position], [Traits] AS [traits], [Biography] AS [biography], [PhotoFile] AS [photo_file], [IsActive] AS [is_active], [UpdatedBy] AS [updated_by], [UpdatedAt] AS [updated_at] FROM dbo.[Employees];');
GO
IF OBJECT_ID(N'dbo.Company_OperationCategory',N'U') IS NULL
EXEC(N'CREATE OR ALTER VIEW dbo.[Company_OperationCategory] AS SELECT [CategoryNo] AS [category_code], [DisplayOrder] AS [display_order] FROM dbo.[OperationCategories];');
GO
IF OBJECT_ID(N'dbo.Company_Attendance',N'U') IS NULL
EXEC(N'CREATE OR ALTER VIEW dbo.[Company_Attendance] AS SELECT [Id] AS [attendance_id], [EmployeeNo] AS [employee_id], [AttendanceAction] AS [action], [ClockedAt] AS [clocked_at], [ClockedAtUtc] AS [clocked_at_utc], [WorkDate] AS [work_date], [SourceIp] AS [source_ip] FROM dbo.[AttendanceRecords];');
GO
IF OBJECT_ID(N'dbo.Company_OperationSubmission',N'U') IS NULL
EXEC(N'CREATE OR ALTER VIEW dbo.[Company_OperationSubmission] AS SELECT [SheetNo] AS [submission_id], [SheetDate] AS [operation_date], [CampusCode] AS [campus_code], [CategoryNo] AS [category_code], [Quantity] AS [quantity], [SubmissionNote] AS [note], [EmployeeNo] AS [submitted_by], [ReviewStatus] AS [status], [SubmittedAt] AS [submitted_at] FROM dbo.[OperationSubmissions];');
GO
IF OBJECT_ID(N'dbo.Company_OperationActivity',N'U') IS NULL
EXEC(N'CREATE OR ALTER VIEW dbo.[Company_OperationActivity] AS SELECT [Id] AS [activity_id], [SheetNo] AS [submission_id], [ActivityAction] AS [action_type], [ActivityMessage] AS [message], [EmployeeNo] AS [actor_employee_id], [ActorRole] AS [actor_role], [ActivityTime] AS [created_at] FROM dbo.[OperationActivities];');
GO
IF OBJECT_ID(N'dbo.Company_TrainingDocument',N'U') IS NULL
EXEC(N'CREATE OR ALTER VIEW dbo.[Company_TrainingDocument] AS SELECT [DocumentNo] AS [document_id], [FileName] AS [file_name], [DocumentTitle] AS [title], [RoleCategory] AS [role_category], [SourceSize] AS [source_size], [SourceModified] AS [source_modified], [IsActive] AS [is_active], [ImportedAt] AS [imported_at], [SourceKind] AS [source_kind], [ParseStatus] AS [parse_status], [ParseMessage] AS [parse_message] FROM dbo.[TrainingDocuments];');
GO
IF OBJECT_ID(N'dbo.Company_TrainingSection',N'U') IS NULL
EXEC(N'CREATE OR ALTER VIEW dbo.[Company_TrainingSection] AS SELECT [Id] AS [section_id], [DocumentNo] AS [document_id], [SectionOrder] AS [section_order], [Heading] AS [heading], [SectionContent] AS [content] FROM dbo.[TrainingSections];');
GO
IF OBJECT_ID(N'dbo.Company_TrainingSubject',N'U') IS NULL
EXEC(N'CREATE OR ALTER VIEW dbo.[Company_TrainingSubject] AS SELECT [SubjectNo] AS [subject_id], [TrainingDomain] AS [domain], [SubjectName] AS [subject_name], [MockQuestionCount] AS [mock_question_count], [MockDurationMinutes] AS [mock_duration_minutes], [MockPassScore] AS [mock_pass_score], [IsActive] AS [is_active] FROM dbo.[TrainingSubjects];');
GO
IF OBJECT_ID(N'dbo.Company_TrainingChapter',N'U') IS NULL
EXEC(N'CREATE OR ALTER VIEW dbo.[Company_TrainingChapter] AS SELECT [ChapterNo] AS [chapter_id], [SubjectNo] AS [subject_id], [ChapterCode] AS [chapter_code], [ChapterName] AS [chapter_name], [DisplayOrder] AS [display_order], [IsActive] AS [is_active] FROM dbo.[TrainingChapters];');
GO
IF OBJECT_ID(N'dbo.Company_TrainingQuestion',N'U') IS NULL
EXEC(N'CREATE OR ALTER VIEW dbo.[Company_TrainingQuestion] AS SELECT [QuestionNo] AS [question_id], [DocumentNo] AS [document_id], [CategoryName] AS [category], [QuestionText] AS [question], [OptionsJson] AS [options_json], [CorrectIndex] AS [correct_index], [Explanation] AS [explanation], [QuestionType] AS [question_type], [AnswerJson] AS [answer_json], [Passage] AS [passage], [IsActive] AS [is_active], [TrainingDomain] AS [domain], [SubjectNo] AS [subject_id], [ChapterNo] AS [chapter_id], [ContentJson] AS [content_json], [StructureJson] AS [structure_json], [SourceLocator] AS [source_locator], [SourceQuestionKey] AS [source_question_key], [SourceFingerprint] AS [source_fingerprint], [ParseConfidence] AS [parse_confidence], [ParseWarningsJson] AS [parse_warnings_json], [QuestionStatus] AS [status], [IsAdminLocked] AS [admin_locked], [UpdatedAt] AS [updated_at], [DeletedAt] AS [deleted_at] FROM dbo.[TrainingQuestions];');
GO
IF OBJECT_ID(N'dbo.Company_TrainingAnswer',N'U') IS NULL
EXEC(N'CREATE OR ALTER VIEW dbo.[Company_TrainingAnswer] AS SELECT [Id] AS [answer_id], [QuestionNo] AS [question_id], [EmployeeNo] AS [employee_id], [AnswerText] AS [answer_text], [ReviewStatus] AS [status], [Feedback] AS [feedback], [SubmittedAt] AS [submitted_at], [ReviewerNo] AS [reviewed_by], [ReviewedAt] AS [reviewed_at] FROM dbo.[TrainingAnswers];');
GO
IF OBJECT_ID(N'dbo.Company_TrainingSession',N'U') IS NULL
EXEC(N'CREATE OR ALTER VIEW dbo.[Company_TrainingSession] AS SELECT [SessionNo] AS [session_id], [EmployeeNo] AS [employee_id], [SubjectNo] AS [subject_id], [TrainingMode] AS [mode], [SessionStatus] AS [status], [ConfigJson] AS [config_json], [StartedAt] AS [started_at], [ExpiresAt] AS [expires_at], [SubmittedAt] AS [submitted_at], [Score] AS [score] FROM dbo.[TrainingSessions];');
GO
IF OBJECT_ID(N'dbo.Company_TrainingSessionQuestion',N'U') IS NULL
EXEC(N'CREATE OR ALTER VIEW dbo.[Company_TrainingSessionQuestion] AS SELECT [Id] AS [session_question_id], [SessionNo] AS [session_id], [QuestionNo] AS [question_id], [QuestionOrder] AS [question_order], [SnapshotJson] AS [snapshot_json], [ResponseJson] AS [response_json], [IsFlagged] AS [is_flagged], [IsCorrect] AS [is_correct], [AnsweredAt] AS [answered_at] FROM dbo.[TrainingSessionQuestions];');
GO
IF OBJECT_ID(N'dbo.Company_TrainingWrongQuestion',N'U') IS NULL
EXEC(N'CREATE OR ALTER VIEW dbo.[Company_TrainingWrongQuestion] AS SELECT [EmployeeNo] AS [employee_id], [QuestionNo] AS [question_id], [AddedAt] AS [added_at], [RemovedAt] AS [removed_at] FROM dbo.[TrainingWrongQuestions];');
GO
IF OBJECT_ID(N'dbo.Company_ImportState',N'U') IS NULL
EXEC(N'CREATE OR ALTER VIEW dbo.[Company_ImportState] AS SELECT [ImportSourceNo] AS [source_key], [SourceModifiedAt] AS [source_modified], [SourceSize] AS [source_size], [ImportedRows] AS [imported_rows], [ImportedAt] AS [imported_at] FROM dbo.[ImportStates];');
GO
