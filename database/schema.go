package database

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
)

var batchSeparator = regexp.MustCompile(`(?im)^\s*GO\s*$`)

// SeedEmployees 將版本控管的員工初始資料寫入新結構，交易及執行標記避免覆寫後台修改。
func (s *Store) SeedEmployees(ctx context.Context, root string) error {
	if !s.normalized {
		return errors.New("員工初始化需要新版資料表結構")
	}
	body, err := os.ReadFile(filepath.Join(root, "database", "SeedEmployees.sql"))
	if err != nil {
		return errors.New("無法讀取員工初始資料腳本")
	}
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return errors.New("無法啟動員工初始化交易")
	}
	if _, err := tx.ExecContext(ctx, string(body)); err != nil {
		return errors.Join(errors.New("員工初始化失敗，資料已回復"), tx.Rollback())
	}
	if err := tx.Commit(); err != nil {
		return errors.New("員工初始化提交失敗")
	}
	return nil
}

// Initialize 執行版本控管的 SQL 腳本，整體成功才提交；平常啟動不會隱含執行。
func (s *Store) Initialize(ctx context.Context, root string) error {
	var legacy int
	if err := s.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM sys.tables WHERE name IN ('Company_Staff','Company_TrainingQuestion') AND schema_id=SCHEMA_ID('dbo')").Scan(&legacy); err != nil {
		return errors.New("無法確認既有資料庫結構")
	}
	if legacy > 0 {
		return errors.New("已有舊版資料表，無法使用全新資料庫初始化；初始化不會覆寫既有資料")
	}
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return errors.New("無法啟動資料庫初始化交易")
	}
	for _, name := range []string{"CreateTables.sql", "SeedData.sql"} {
		body, err := os.ReadFile(filepath.Join(root, "database", name))
		if err != nil {
			return errors.Join(err, tx.Rollback())
		}
		for index, batch := range batchSeparator.Split(string(body), -1) {
			if batch == "" {
				continue
			}
			if _, err := tx.ExecContext(ctx, batch); err != nil {
				rollbackErr := tx.Rollback()
				if rollbackErr != nil {
					return fmt.Errorf("%s 第 %d 批次失敗且無法回復交易", name, index+1)
				}
				return fmt.Errorf("%s 第 %d 批次失敗，初始化已回復", name, index+1)
			}
		}
	}
	if err := tx.Commit(); err != nil {
		return errors.New("資料庫初始化提交失敗")
	}
	return nil
}

// DetectSchema 在開始服務前辨識相容檢視表，切換新版明確預設值與編號產生查詢。
func (s *Store) DetectSchema(ctx context.Context) error {
	var normalized bool
	query := "SELECT CAST(CASE WHEN OBJECT_ID(N'dbo.Employees',N'U') IS NOT NULL AND OBJECT_ID(N'dbo.Company_Staff',N'V') IS NOT NULL THEN 1 ELSE 0 END AS BIT)"
	if err := s.db.QueryRowContext(ctx, query).Scan(&normalized); err != nil {
		return errors.New("無法辨識資料庫結構版本")
	}
	if normalized {
		var overrides map[string]queryDefinition
		if err := json.Unmarshal(normalizedCatalog, &overrides); err != nil {
			return err
		}
		for key, value := range overrides {
			s.queries[key] = value
		}
	}
	s.normalized = normalized
	return nil
}
