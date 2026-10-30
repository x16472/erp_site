package database

import (
	"context"
	"encoding/json"
	"net/url"
	"strings"
	"testing"
	"time"

	"erp-site/backend/rpc"
	"github.com/DATA-DOG/go-sqlmock"
)

func TestDSNPreservesCredentials(t *testing.T) {
	value, err := DSN(map[string]string{"DatabaseIP": "db.example", "DatabasePort": "1433", "DatabaseName": "company;prod", "DatabaseUser": "service}user", "DatabasePassword": "p;ass}word@/#"})
	if err != nil {
		t.Fatal(err)
	}
	parsed, err := url.Parse(value)
	if err != nil {
		t.Fatal(err)
	}
	if parsed.Query().Get("connection timeout") != "" || parsed.Query().Get("dial timeout") != "5" {
		t.Fatal("連線撥號期限不可變成長查詢的 socket 期限")
	}
	password, ok := parsed.User.Password()
	if !ok || password != "p;ass}word@/#" || parsed.User.Username() != "service}user" || parsed.Query().Get("database") != "company;prod" {
		t.Fatal("連線字串未保留特殊字元")
	}
}

func TestBindParametersIgnoresLiteralsAndComments(t *testing.T) {
	query := "SELECT N'why?''?', [question?], \"quoted?\", ? -- ?\n/* ? /* ? */ ? */ WHERE x=?"
	result, err := bindParameters(query, 2)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(result, "@p1 -- ?") || !strings.HasSuffix(result, "WHERE x=@p2") {
		t.Fatal(result)
	}
	if _, err := bindParameters("SELECT ?", 0); err == nil {
		t.Fatal("應拒絕錯誤的參數數量")
	}
}

func TestCatalogRejectsSQLInjectionAndReadOnlyWrites(t *testing.T) {
	catalog, err := loadQueries()
	if err != nil {
		t.Fatal(err)
	}
	for _, test := range []struct {
		name, options string
		readOnly      bool
	}{
		{"SELECT 1", `[]`, true},
		{"domain.table_data.2", `["[employee_id]; DROP TABLE dbo.Company_Staff--","[dbo].[Company_Staff]"]`, true},
		{"domain.table_data.3", `["[dbo].[Passwords]"]`, true},
		{"domain.attendance_staff_options.1", `["employee_id; DROP TABLE x"]`, true},
		{"domain.deactivate_staff.1", `[]`, true},
	} {
		if _, err := resolveQuery(catalog, test.name, []byte(test.options), test.readOnly); err == nil {
			t.Fatalf("接受不合法的查詢：%s", test.name)
		}
	}
	if _, err := resolveQuery(catalog, "domain.table_data.2", []byte(`["[employee_id], [display_name]","[dbo].[Company_Staff]"]`), true); err != nil {
		t.Fatal(err)
	}
}

func testStore(t *testing.T) (*Store, sqlmock.Sqlmock) {
	t.Helper()
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatal(err)
	}
	catalog, err := loadQueries()
	if err != nil {
		t.Fatal(err)
	}
	store := &Store{db: db, scopes: make(map[string]context.Context), connections: make(map[string]*connection), queries: catalog}
	t.Cleanup(func() {
		mock.ExpectClose()
		if err := store.Close(); err != nil {
			t.Error(err)
		}
		if err := mock.ExpectationsWereMet(); err != nil {
			t.Error(err)
		}
	})
	return store, mock
}

func execute(t *testing.T, store *Store, req *rpc.DatabaseRequest) *rpc.DatabaseResponse {
	t.Helper()
	result, err := store.Execute(context.Background(), req)
	if err != nil {
		t.Fatal(err)
	}
	if result.ErrorCode != "" {
		t.Fatalf("%s: %s", result.ErrorCode, result.ErrorMessage)
	}
	return result
}

func TestRequestOwnsTransactionAndCleanupRollsBack(t *testing.T) {
	store, mock := testStore(t)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	release := store.BeginScope(ctx, "request-a")
	mock.ExpectBegin()
	opened := execute(t, store, &rpc.DatabaseRequest{Operation: "open", RequestId: "request-a"})
	other := store.BeginScope(ctx, "request-b")
	defer other()
	denied, err := store.Execute(ctx, &rpc.DatabaseRequest{Operation: "commit", RequestId: "request-b", SessionId: opened.SessionId})
	if err != nil || denied.ErrorCode == "" {
		t.Fatal("另一個請求不應控制此交易")
	}
	mock.ExpectRollback()
	release()
	if len(store.connections) != 0 || len(store.scopes) != 1 {
		t.Fatal("請求結束後仍殘留連線")
	}
}

func TestCommitAndReuseConnectionForNextTransaction(t *testing.T) {
	store, mock := testStore(t)
	release := store.BeginScope(context.Background(), "request")
	defer release()
	mock.ExpectBegin()
	id := execute(t, store, &rpc.DatabaseRequest{Operation: "open", RequestId: "request"}).SessionId
	mock.ExpectCommit()
	execute(t, store, &rpc.DatabaseRequest{Operation: "commit", SessionId: id, RequestId: "request"})
	mock.ExpectBegin()
	mock.ExpectQuery("SELECT DB_NAME").WillReturnRows(sqlmock.NewRows([]string{"資料庫"}).AddRow("erp_test"), sqlmock.NewRows([]string{"__erp_affected_rows__"}).AddRow(1))
	result := execute(t, store, &rpc.DatabaseRequest{Operation: "query", SessionId: id, RequestId: "request", Query: "domain.health.1", ParametersJson: []byte(`[]`)})
	if result.RowCount != 1 || string(result.RowsJson) != `[["erp_test"]]` {
		t.Fatalf("不正確的結果集：%s", result.RowsJson)
	}
	mock.ExpectRollback()
	execute(t, store, &rpc.DatabaseRequest{Operation: "close", SessionId: id, RequestId: "request"})
}

func TestCancellationStopsQuery(t *testing.T) {
	store, mock := testStore(t)
	ctx, cancel := context.WithCancel(context.Background())
	release := store.BeginScope(ctx, "request")
	defer release()
	id := execute(t, store, &rpc.DatabaseRequest{Operation: "open", RequestId: "request", Autocommit: true, ReadOnly: true}).SessionId
	mock.ExpectQuery("SELECT DB_NAME").WillDelayFor(time.Second).WillReturnRows(sqlmock.NewRows([]string{"資料庫"}).AddRow("erp_test"))
	done := make(chan *rpc.DatabaseResponse, 1)
	go func() {
		result, err := store.Execute(context.Background(), &rpc.DatabaseRequest{Operation: "query", SessionId: id, RequestId: "request", Query: "domain.health.1"})
		if err != nil {
			t.Error(err)
		}
		done <- result
	}()
	time.Sleep(25 * time.Millisecond)
	cancel()
	select {
	case result := <-done:
		if result.ErrorCode == "" {
			t.Error("取消後不應成功")
		}
	case <-time.After(500 * time.Millisecond):
		t.Fatal("未傳遞請求取消")
	}
}

func TestSQLTypesAndIntegerPrecision(t *testing.T) {
	args, err := decodeParameters([]byte(`[1793314439123456789,{"type":"date","value":"2026-10-30"},{"type":"decimal","value":"12.3456"},null,true]`))
	if err != nil {
		t.Fatal(err)
	}
	if args[0] != int64(1793314439123456789) {
		t.Fatal("整數精度遺失")
	}
	value := encodeValue(time.Date(2026, 10, 30, 0, 0, 0, 0, time.UTC), "DATE")
	encoded, err := json.Marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(encoded), `"type":"date"`) {
		t.Fatal(string(encoded))
	}
	if encodeValue(nil, "NVARCHAR") != nil {
		t.Fatal("NULL 必須保留")
	}
}
