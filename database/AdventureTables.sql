-- 冒險遊戲資料表結構；依據 DATABASE.md 與 RPG.md 規範設計。
SET XACT_ABORT ON;
GO

IF OBJECT_ID(N'dbo.AdventureWorlds', N'U') IS NULL
CREATE TABLE dbo.[AdventureWorlds] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [WorldNo] NVARCHAR(50) NOT NULL DEFAULT (SPACE(0)),
    [WorldName] NVARCHAR(50) NOT NULL DEFAULT (SPACE(0)),
    [Description] NVARCHAR(MAX) NOT NULL DEFAULT (SPACE(0)),
    [IsOpen] BIT NOT NULL DEFAULT (0),
    [CurrentVersionNo] NVARCHAR(50) NOT NULL DEFAULT (SPACE(0)),
    [Remark] NVARCHAR(250) NOT NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NOT NULL DEFAULT (GETDATE())
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_AdventureWorlds_WorldNo' AND object_id=OBJECT_ID(N'dbo.AdventureWorlds'))
CREATE UNIQUE INDEX UX_AdventureWorlds_WorldNo ON dbo.[AdventureWorlds](WorldNo);
GO

IF OBJECT_ID(N'dbo.AdventureDrafts', N'U') IS NULL
CREATE TABLE dbo.[AdventureDrafts] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [WorldNo] NVARCHAR(50) NOT NULL DEFAULT (SPACE(0)),
    [Revision] INT NOT NULL DEFAULT (1),
    [Content] NVARCHAR(MAX) NOT NULL DEFAULT (SPACE(0)),
    [UpdatedBy] NVARCHAR(50) NOT NULL DEFAULT (SPACE(0)),
    [Remark] NVARCHAR(250) NOT NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NOT NULL DEFAULT (GETDATE())
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_AdventureDrafts_WorldNo' AND object_id=OBJECT_ID(N'dbo.AdventureDrafts'))
CREATE UNIQUE INDEX UX_AdventureDrafts_WorldNo ON dbo.[AdventureDrafts](WorldNo);
GO

IF OBJECT_ID(N'dbo.AdventureVersions', N'U') IS NULL
CREATE TABLE dbo.[AdventureVersions] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [WorldNo] NVARCHAR(50) NOT NULL DEFAULT (SPACE(0)),
    [VersionNo] NVARCHAR(50) NOT NULL DEFAULT (SPACE(0)),
    [FormatVersion] INT NOT NULL DEFAULT (1),
    [Content] NVARCHAR(MAX) NOT NULL DEFAULT (SPACE(0)),
    [PublishedBy] NVARCHAR(50) NOT NULL DEFAULT (SPACE(0)),
    [Remark] NVARCHAR(250) NOT NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NOT NULL DEFAULT (GETDATE())
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_AdventureVersions_WorldNo_VersionNo' AND object_id=OBJECT_ID(N'dbo.AdventureVersions'))
CREATE UNIQUE INDEX UX_AdventureVersions_WorldNo_VersionNo ON dbo.[AdventureVersions](WorldNo, VersionNo);
GO

IF OBJECT_ID(N'dbo.AdventureSaves', N'U') IS NULL
CREATE TABLE dbo.[AdventureSaves] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [SaveNo] NVARCHAR(50) NOT NULL DEFAULT (SPACE(0)),
    [EmployeeNo] NVARCHAR(50) NOT NULL DEFAULT (SPACE(0)),
    [WorldNo] NVARCHAR(50) NOT NULL DEFAULT (SPACE(0)),
    [SlotIndex] INT NOT NULL DEFAULT (1),
    [VersionNo] NVARCHAR(50) NOT NULL DEFAULT (SPACE(0)),
    [Revision] INT NOT NULL DEFAULT (1),
    [CharacterSnapshot] NVARCHAR(MAX) NOT NULL DEFAULT (SPACE(0)),
    [StateJson] NVARCHAR(MAX) NOT NULL DEFAULT (SPACE(0)),
    [IsActive] BIT NOT NULL DEFAULT (1),
    [Remark] NVARCHAR(250) NOT NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NOT NULL DEFAULT (GETDATE())
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_AdventureSaves_Employee_World_Slot' AND object_id=OBJECT_ID(N'dbo.AdventureSaves'))
CREATE UNIQUE INDEX UX_AdventureSaves_Employee_World_Slot ON dbo.[AdventureSaves](EmployeeNo, WorldNo, SlotIndex);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_AdventureSaves_SaveNo' AND object_id=OBJECT_ID(N'dbo.AdventureSaves'))
CREATE UNIQUE INDEX UX_AdventureSaves_SaveNo ON dbo.[AdventureSaves](SaveNo);
GO

IF OBJECT_ID(N'dbo.AdventureTurns', N'U') IS NULL
CREATE TABLE dbo.[AdventureTurns] (
    [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [SaveNo] NVARCHAR(50) NOT NULL DEFAULT (SPACE(0)),
    [TurnIndex] INT NOT NULL DEFAULT (0),
    [RequestId] NVARCHAR(50) NOT NULL DEFAULT (SPACE(0)),
    [ExpectedRevision] INT NOT NULL DEFAULT (0),
    [ActionId] NVARCHAR(50) NOT NULL DEFAULT (SPACE(0)),
    [ActionInput] NVARCHAR(MAX) NOT NULL DEFAULT (SPACE(0)),
    [RollResult] NVARCHAR(MAX) NOT NULL DEFAULT (SPACE(0)),
    [StateDiff] NVARCHAR(MAX) NOT NULL DEFAULT (SPACE(0)),
    [ResponseJson] NVARCHAR(MAX) NOT NULL DEFAULT (SPACE(0)),
    [Remark] NVARCHAR(250) NOT NULL DEFAULT (SPACE(0)),
    [CreateTime] DATETIME2 NOT NULL DEFAULT (GETDATE())
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'UX_AdventureTurns_SaveNo_RequestId' AND object_id=OBJECT_ID(N'dbo.AdventureTurns'))
CREATE UNIQUE INDEX UX_AdventureTurns_SaveNo_RequestId ON dbo.[AdventureTurns](SaveNo, RequestId);
GO

-- 外鍵條件
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_AdventureDrafts_WorldNo')
ALTER TABLE dbo.[AdventureDrafts] WITH CHECK ADD CONSTRAINT [FK_AdventureDrafts_WorldNo] FOREIGN KEY ([WorldNo]) REFERENCES dbo.[AdventureWorlds] ([WorldNo]) ON DELETE CASCADE;
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_AdventureVersions_WorldNo')
ALTER TABLE dbo.[AdventureVersions] WITH CHECK ADD CONSTRAINT [FK_AdventureVersions_WorldNo] FOREIGN KEY ([WorldNo]) REFERENCES dbo.[AdventureWorlds] ([WorldNo]) ON DELETE CASCADE;
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_AdventureSaves_WorldNo')
ALTER TABLE dbo.[AdventureSaves] WITH CHECK ADD CONSTRAINT [FK_AdventureSaves_WorldNo] FOREIGN KEY ([WorldNo]) REFERENCES dbo.[AdventureWorlds] ([WorldNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_AdventureSaves_EmployeeNo')
ALTER TABLE dbo.[AdventureSaves] WITH CHECK ADD CONSTRAINT [FK_AdventureSaves_EmployeeNo] FOREIGN KEY ([EmployeeNo]) REFERENCES dbo.[Employees] ([EmployeeNo]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_AdventureTurns_SaveNo')
ALTER TABLE dbo.[AdventureTurns] WITH CHECK ADD CONSTRAINT [FK_AdventureTurns_SaveNo] FOREIGN KEY ([SaveNo]) REFERENCES dbo.[AdventureSaves] ([SaveNo]) ON DELETE CASCADE;
GO

-- 必要識別欄位拒絕空字串；RPG 欄位使用 NOT NULL 與既有預設值。
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = N'CK_AdventureWorlds_Text')
ALTER TABLE dbo.AdventureWorlds WITH CHECK ADD CONSTRAINT CK_AdventureWorlds_Text CHECK (
    (WorldNo IS NULL OR LEN(LTRIM(RTRIM(WorldNo))) > 0) AND
    (WorldName IS NULL OR LEN(LTRIM(RTRIM(WorldName))) > 0));
GO
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = N'CK_AdventureSaves_Identity')
ALTER TABLE dbo.AdventureSaves WITH CHECK ADD CONSTRAINT CK_AdventureSaves_Identity CHECK (
    (SaveNo IS NULL OR LEN(LTRIM(RTRIM(SaveNo))) > 0) AND
    (EmployeeNo IS NULL OR LEN(LTRIM(RTRIM(EmployeeNo))) > 0) AND
    (WorldNo IS NULL OR LEN(LTRIM(RTRIM(WorldNo))) > 0) AND
    (VersionNo IS NULL OR LEN(LTRIM(RTRIM(VersionNo))) > 0) AND
    (SlotIndex IS NULL OR SlotIndex BETWEEN 1 AND 3));
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = N'FK_AdventureSaves_Version')
ALTER TABLE dbo.AdventureSaves WITH CHECK ADD CONSTRAINT FK_AdventureSaves_Version
FOREIGN KEY (WorldNo, VersionNo) REFERENCES dbo.AdventureVersions (WorldNo, VersionNo);
GO
