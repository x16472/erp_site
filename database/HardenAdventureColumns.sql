-- 既有 RPG 表的 NOT NULL 修正；預設只預覽，不會由網站啟動執行。
-- 確認資料、備份及維護時段後，人工將 @Apply 改為 1。
-- 發現 NULL 時停止，不猜測內容、不清空玩家進度。
SET NOCOUNT ON;
SET XACT_ABORT ON;
DECLARE @Apply BIT = 0;
DECLARE @Columns TABLE (TableName SYSNAME, ColumnName SYSNAME, ColumnType NVARCHAR(50));
INSERT INTO @Columns
SELECT t.name, c.name,
       CASE TYPE_NAME(c.user_type_id)
           WHEN N'nvarchar' THEN N'NVARCHAR(' + CASE WHEN c.max_length = -1 THEN N'MAX' ELSE CONVERT(NVARCHAR(10), c.max_length / 2) END + N')'
           WHEN N'datetime2' THEN N'DATETIME2(' + CONVERT(NVARCHAR(10), c.scale) + N')'
           WHEN N'int' THEN N'INT'
           WHEN N'bit' THEN N'BIT'
       END
FROM sys.tables t
JOIN sys.columns c ON c.object_id = t.object_id
WHERE t.schema_id = SCHEMA_ID(N'dbo')
  AND t.name IN (N'AdventureWorlds', N'AdventureDrafts', N'AdventureVersions', N'AdventureSaves', N'AdventureTurns')
  AND c.is_nullable = 1;

SELECT TableName, ColumnName, ColumnType FROM @Columns ORDER BY TableName, ColumnName;
IF @Apply = 0 RETURN;
IF EXISTS (SELECT 1 FROM @Columns WHERE ColumnType IS NULL)
    THROW 50001, N'發現非預期型別，請先人工確認結構。', 1;

BEGIN TRY
    BEGIN TRANSACTION;
    DECLARE @Table SYSNAME, @Column SYSNAME, @Type NVARCHAR(50), @Sql NVARCHAR(MAX), @NullCount INT;
    DECLARE columns_cursor CURSOR LOCAL FAST_FORWARD FOR
        SELECT TableName, ColumnName, ColumnType FROM @Columns;
    OPEN columns_cursor;
    FETCH NEXT FROM columns_cursor INTO @Table, @Column, @Type;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @Sql = N'SELECT @Count = COUNT(*) FROM dbo.' + QUOTENAME(@Table)
                 + N' WITH (TABLOCKX, HOLDLOCK) WHERE ' + QUOTENAME(@Column) + N' IS NULL';
        EXEC sys.sp_executesql @Sql, N'@Count INT OUTPUT', @Count = @NullCount OUTPUT;
        IF @NullCount > 0
            THROW 50002, N'既有 RPG 資料含 NULL，請先確認正確值；本次交易已停止。', 1;
        SET @Sql = N'ALTER TABLE dbo.' + QUOTENAME(@Table) + N' ALTER COLUMN '
                 + QUOTENAME(@Column) + N' ' + @Type + N' NOT NULL';
        EXEC sys.sp_executesql @Sql;
        FETCH NEXT FROM columns_cursor INTO @Table, @Column, @Type;
    END;
    CLOSE columns_cursor;
    DEALLOCATE columns_cursor;
    COMMIT;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK;
    THROW;
END CATCH;
