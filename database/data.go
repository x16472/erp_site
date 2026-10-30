// Package database 是 SQL Server 的唯一連線、交易與查詢執行層。
package database

import (
	"bytes"
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"time"

	"erp-site/backend/rpc"
	mssql "github.com/microsoft/go-mssqldb"
)

type connection struct {
	mu         sync.Mutex
	conn       *sql.Conn
	tx         *sql.Tx
	owner      string
	autocommit bool
	readOnly   bool
	normalized bool
	closed     bool
}

// Store 管理連線池與請求範圍；Python 無法選擇連線字串或取得資料庫密碼。
type Store struct {
	rpc.UnimplementedDatabaseServer
	db            *sql.DB
	mu            sync.Mutex
	scopes        map[string]context.Context
	connections   map[string]*connection
	adminUser     string
	adminPassword string
	queries       map[string]queryDefinition
	normalized    bool
}

// DSN 以 URL 編碼組合 SQL Server 設定，支援帳密中的分號與括號。
func DSN(values map[string]string) (string, error) {
	for _, key := range []string{"DatabaseIP", "DatabaseName", "DatabaseUser", "DatabasePassword"} {
		if values[key] == "" {
			return "", fmt.Errorf("缺少資料庫設定：%s", key)
		}
	}
	host := values["DatabaseIP"]
	instance := ""
	if i := strings.IndexByte(host, '\\'); i >= 0 {
		host, instance = host[:i], strings.TrimLeft(host[i:], "\\")
	}
	if host == "." {
		host = "localhost"
	}
	if port := values["DatabasePort"]; port != "" {
		portNumber, err := strconv.Atoi(port)
		if err != nil || portNumber < 1 || portNumber > 65535 {
			return "", errors.New("DatabasePort 必須介於 1 與 65535")
		}
		host = net.JoinHostPort(host, port)
	}
	endpoint := &url.URL{Scheme: "sqlserver", User: url.UserPassword(values["DatabaseUser"], values["DatabasePassword"]), Host: host}
	if instance != "" {
		endpoint.Path = "/" + instance
	}
	// connection timeout 會限制每次 socket 讀寫；長查詢由各自 context 控制期限。
	query := url.Values{"database": {values["DatabaseName"]}, "encrypt": {"disable"}, "TrustServerCertificate": {"true"}, "dial timeout": {"5"}}
	endpoint.RawQuery = query.Encode()
	return endpoint.String(), nil
}

// Open 建立共用連線池，實際連線由 Ping 或第一個查詢驗證。
func Open(values map[string]string) (*Store, error) {
	queries, err := loadQueries()
	if err != nil {
		return nil, err
	}
	dsn, err := DSN(values)
	if err != nil {
		return nil, err
	}
	db, err := sql.Open("sqlserver", dsn)
	if err != nil {
		return nil, errors.New("無法建立 SQL Server 連線池")
	}
	db.SetMaxOpenConns(24)
	db.SetMaxIdleConns(8)
	db.SetConnMaxLifetime(30 * time.Minute)
	db.SetConnMaxIdleTime(5 * time.Minute)
	return &Store{db: db, scopes: make(map[string]context.Context), connections: make(map[string]*connection), queries: queries, adminUser: values["BackendWebAdminUser"], adminPassword: values["BackendWebAdminPassword"]}, nil
}

// Ping 以呼叫端期限驗證資料庫，對外只傳回不含機密的錯誤。
func (s *Store) Ping(ctx context.Context) error {
	if err := s.db.PingContext(ctx); err != nil {
		return errors.New("無法連線至 SQL Server，請檢查 .env、網路及資料庫服務")
	}
	return nil
}

// BeginScope 註冊 Go 核准的工作範圍；回傳函式會回復未提交交易並歸還連線。
func (s *Store) BeginScope(ctx context.Context, id string) func() {
	s.mu.Lock()
	s.scopes[id] = ctx
	s.mu.Unlock()
	return func() {
		s.mu.Lock()
		delete(s.scopes, id)
		var sessions []*connection
		for key, c := range s.connections {
			if c.owner == id {
				sessions = append(sessions, c)
				delete(s.connections, key)
			}
		}
		s.mu.Unlock()
		for _, c := range sessions {
			if err := closeConnection(c); err != nil {
				log.Printf("資料庫範圍清理失敗：%v", err)
			}
		}
	}
}

// Close 關閉資料庫連線池；必須先停止接受請求。
func (s *Store) Close() error { return s.db.Close() }

func closeConnection(c *connection) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.closed {
		return nil
	}
	c.closed = true
	var rollbackErr error
	if c.tx != nil {
		rollbackErr = c.tx.Rollback()
		if errors.Is(rollbackErr, sql.ErrTxDone) {
			rollbackErr = nil
		}
	}
	return errors.Join(rollbackErr, c.conn.Close())
}

// Execute 執行內部資料庫操作，連線與交易僅限所屬的 Go 請求範圍。
func (s *Store) Execute(ctx context.Context, req *rpc.DatabaseRequest) (*rpc.DatabaseResponse, error) {
	s.mu.Lock()
	scope, exists := s.scopes[req.RequestId]
	s.mu.Unlock()
	if !exists || scope.Err() != nil {
		return failure("DATABASE_UNAVAILABLE", "資料庫工作範圍已結束"), nil
	}
	ctx, cancel := context.WithCancel(ctx)
	stopCancel := context.AfterFunc(scope, cancel)
	defer func() { stopCancel(); cancel() }()
	if req.Operation == "credentials" {
		if s.adminUser == "" || s.adminPassword == "" {
			return failure("DATABASE_UNAVAILABLE", ".env 尚未設定管理員帳號密碼"), nil
		}
		body, err := json.Marshal([][]string{{s.adminUser, s.adminPassword}})
		if err != nil {
			return nil, err
		}
		return &rpc.DatabaseResponse{RowsJson: body}, nil
	}
	if req.Operation == "open" {
		conn, err := s.db.Conn(ctx)
		if err != nil {
			return databaseFailure(err), nil
		}
		c := &connection{conn: conn, owner: req.RequestId, autocommit: req.Autocommit, readOnly: req.ReadOnly, normalized: s.normalized}
		if !req.Autocommit {
			// 交易跟隨整個 HTTP／背景工作，不能綁在會立即結束的單次 RPC。
			c.tx, err = conn.BeginTx(scope, nil)
			if err != nil {
				return databaseFailure(errors.Join(err, conn.Close())), nil
			}
		}
		token := make([]byte, 32)
		if _, err = rand.Read(token); err != nil {
			return nil, errors.Join(err, closeConnection(c))
		}
		id := hex.EncodeToString(token)
		s.mu.Lock()
		if _, ok := s.scopes[req.RequestId]; !ok || scope.Err() != nil {
			s.mu.Unlock()
			return databaseFailure(errors.Join(scope.Err(), closeConnection(c))), nil
		}
		s.connections[id] = c
		s.mu.Unlock()
		return &rpc.DatabaseResponse{SessionId: id}, nil
	}
	s.mu.Lock()
	c, exists := s.connections[req.SessionId]
	s.mu.Unlock()
	if !exists || c.owner != req.RequestId {
		return failure("DATABASE_UNAVAILABLE", "資料庫連線已失效"), nil
	}
	if req.Operation == "close" {
		s.mu.Lock()
		delete(s.connections, req.SessionId)
		s.mu.Unlock()
		if err := closeConnection(c); err != nil {
			return databaseFailure(err), nil
		}
		return &rpc.DatabaseResponse{}, nil
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.closed {
		return failure("DATABASE_UNAVAILABLE", "資料庫連線已關閉"), nil
	}
	switch req.Operation {
	case "commit", "rollback":
		if c.tx == nil {
			return &rpc.DatabaseResponse{}, nil
		}
		var err error
		if req.Operation == "commit" {
			err = c.tx.Commit()
		} else {
			err = c.tx.Rollback()
		}
		c.tx = nil
		if err != nil {
			return databaseFailure(err), nil
		}
		return &rpc.DatabaseResponse{}, nil
	case "query":
		if !c.autocommit && c.tx == nil {
			var err error
			c.tx, err = c.conn.BeginTx(scope, nil)
			if err != nil {
				return databaseFailure(err), nil
			}
		}
		args, err := decodeParameters(req.ParametersJson)
		if err != nil {
			return failure("INVALID_REQUEST", err.Error()), nil
		}
		sqlText, err := resolveQuery(s.queries, req.Query, req.OptionsJson, c.readOnly)
		if err != nil {
			return failure("INVALID_REQUEST", err.Error()), nil
		}
		query, err := bindParameters(sqlText, len(args))
		if err != nil {
			return failure("INVALID_REQUEST", err.Error()), nil
		}
		result, err := executeQuery(ctx, c, query, args)
		if err != nil {
			return databaseFailure(err), nil
		}
		return result, nil
	default:
		return failure("INVALID_REQUEST", "不支援的資料庫操作"), nil
	}
}

func failure(code, message string) *rpc.DatabaseResponse {
	return &rpc.DatabaseResponse{ErrorCode: code, ErrorMessage: message}
}

func databaseFailure(err error) *rpc.DatabaseResponse {
	var sqlError mssql.Error
	if errors.As(err, &sqlError) {
		log.Printf("SQL Server 錯誤編號：%d", sqlError.Number)
		if sqlError.Number == 2601 || sqlError.Number == 2627 || sqlError.Number == 547 {
			return failure("INTEGRITY_ERROR", "資料重複或關聯條件不符")
		}
	}
	return failure("DATABASE_UNAVAILABLE", "SQL Server 操作失敗，請檢查資料庫連線與資料表結構")
}

func decodeParameters(body []byte) ([]any, error) {
	if len(body) == 0 {
		return nil, nil
	}
	decoder := json.NewDecoder(bytes.NewReader(body))
	decoder.UseNumber()
	var args []any
	if err := decoder.Decode(&args); err != nil {
		return nil, errors.New("SQL 參數格式錯誤")
	}
	for i, value := range args {
		switch v := value.(type) {
		case json.Number:
			if integer, err := v.Int64(); err == nil {
				args[i] = integer
			} else {
				number, err := v.Float64()
				if err != nil {
					return nil, err
				}
				args[i] = number
			}
		case map[string]any:
			text, ok := v["value"].(string)
			if !ok {
				return nil, errors.New("SQL 型別值錯誤")
			}
			switch v["type"] {
			case "datetime":
				parsed, err := time.Parse("2006-01-02T15:04:05.999999999", text)
				if err != nil {
					parsed, err = time.Parse(time.RFC3339Nano, text)
				}
				if err != nil {
					return nil, err
				}
				args[i] = parsed
			case "date":
				parsed, err := time.Parse("2006-01-02", text)
				if err != nil {
					return nil, err
				}
				args[i] = mssql.DateTime1(parsed)
			case "decimal":
				args[i] = text
			case "bytes":
				decoded, err := hex.DecodeString(text)
				if err != nil {
					return nil, err
				}
				args[i] = decoded
			default:
				return nil, errors.New("不支援的 SQL 參數型別")
			}
		case nil, string, bool:
		default:
			return nil, errors.New("不支援的 SQL 參數型別")
		}
	}
	return args, nil
}

func executeQuery(ctx context.Context, c *connection, query string, args []any) (*rpc.DatabaseResponse, error) {
	// 最後的結果集取回影響筆數，仍完整消耗 OUTPUT／SELECT 的前置結果集。
	query += "\n;SELECT @@ROWCOUNT AS [__erp_affected_rows__];"
	var rows *sql.Rows
	var err error
	if c.tx != nil {
		rows, err = c.tx.QueryContext(ctx, query, args...)
	} else {
		rows, err = c.conn.QueryContext(ctx, query, args...)
	}
	if err != nil {
		return nil, err
	}
	result := &rpc.DatabaseResponse{RowCount: -1}
	values := make([][]any, 0)
	for {
		columns, err := rows.Columns()
		if err != nil {
			return nil, errors.Join(err, rows.Close())
		}
		types, err := rows.ColumnTypes()
		if err != nil {
			return nil, errors.Join(err, rows.Close())
		}
		marker := len(columns) == 1 && columns[0] == "__erp_affected_rows__"
		capture := !marker && len(columns) > 0 && len(result.Columns) == 0
		if capture {
			result.Columns = columns
		}
		for rows.Next() {
			row := make([]any, len(columns))
			targets := make([]any, len(columns))
			for i := range row {
				targets[i] = &row[i]
			}
			if err := rows.Scan(targets...); err != nil {
				return nil, errors.Join(err, rows.Close())
			}
			if marker {
				if n, ok := row[0].(int64); ok {
					result.RowCount = n
				}
				continue
			}
			if capture {
				for i, v := range row {
					row[i] = encodeValue(v, types[i].DatabaseTypeName())
					if c.normalized {
						row[i] = legacyNumber(columns[i], row[i])
					}
				}
				values = append(values, row)
			}
		}
		if err := rows.Err(); err != nil {
			return nil, errors.Join(err, rows.Close())
		}
		if !rows.NextResultSet() {
			break
		}
	}
	if err := errors.Join(rows.Err(), rows.Close()); err != nil {
		return nil, err
	}
	result.RowsJson, err = json.Marshal(values)
	return result, err
}

func legacyNumber(column string, value any) any {
	switch column {
	case "id", "document_id", "subject_id", "chapter_id", "question_id":
		if text, ok := value.(string); ok {
			if number, err := strconv.ParseInt(text, 10, 32); err == nil {
				return number
			}
		}
	}
	return value
}

func encodeValue(value any, sqlType string) any {
	switch v := value.(type) {
	case time.Time:
		kind, layout := "datetime", "2006-01-02T15:04:05.999999999"
		if strings.EqualFold(sqlType, "DATE") {
			kind, layout = "date", "2006-01-02"
		}
		if strings.EqualFold(sqlType, "DATETIMEOFFSET") {
			layout = time.RFC3339Nano
		}
		return map[string]string{"type": kind, "value": v.Format(layout)}
	case []byte:
		if strings.EqualFold(sqlType, "DECIMAL") || strings.EqualFold(sqlType, "NUMERIC") {
			return map[string]string{"type": "decimal", "value": string(v)}
		}
		if strings.EqualFold(sqlType, "UNIQUEIDENTIFIER") && len(v) == 16 {
			return fmt.Sprintf("%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%x", v[3], v[2], v[1], v[0], v[5], v[4], v[7], v[6], v[8], v[9], v[10:])
		}
		return map[string]string{"type": "bytes", "value": hex.EncodeToString(v)}
	default:
		return value
	}
}
