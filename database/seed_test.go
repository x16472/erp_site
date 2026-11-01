package database

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"github.com/DATA-DOG/go-sqlmock"
)

func TestInitialDataCommitsCategoriesAndEmployeesTogether(t *testing.T) {
	store, mock := testStore(t)
	store.normalized = true
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, "database"), 0700); err != nil {
		t.Fatal(err)
	}
	for name, body := range map[string]string{"SeedOperationCategories.sql": "SELECT 11", "SeedEmployees.sql": "SELECT 22"} {
		if err := os.WriteFile(filepath.Join(root, "database", name), []byte(body), 0600); err != nil {
			t.Fatal(err)
		}
	}
	mock.ExpectBegin()
	mock.ExpectExec("SELECT 11").WillReturnResult(sqlmock.NewResult(0, 7))
	mock.ExpectExec("SELECT 22").WillReturnResult(sqlmock.NewResult(0, 0))
	mock.ExpectCommit()
	if err := store.SeedInitialData(context.Background(), root); err != nil {
		t.Fatal(err)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatal(err)
	}
}

func TestInitialDataRollsBackIfEmployeeScriptMissing(t *testing.T) {
	store, mock := testStore(t)
	store.normalized = true
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, "database"), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "database", "SeedOperationCategories.sql"), []byte("SELECT 11"), 0600); err != nil {
		t.Fatal(err)
	}
	mock.ExpectBegin()
	mock.ExpectExec("SELECT 11").WillReturnResult(sqlmock.NewResult(0, 7))
	mock.ExpectRollback()
	if err := store.SeedInitialData(context.Background(), root); err == nil {
		t.Fatal("缺少必要腳本應回復類別寫入")
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatal(err)
	}
}
