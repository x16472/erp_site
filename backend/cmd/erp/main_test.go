package main

import (
	"bytes"
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/pem"
	"errors"
	"io"
	"log"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func cleanEnvironment(t *testing.T) {
	t.Helper()
	for _, name := range []string{"WEB_HOST", "WEB_PORT", "ERP_SKIP_DOC_SYNC", "ERP_TLS_CERT", "ERP_TLS_KEY", "ERP_TLS_PROXY", "ERP_LAN_HTTP", "ERP_PYTHON"} {
		t.Setenv(name, "")
	}
}

func TestRejectConflictingModes(t *testing.T) {
	cleanEnvironment(t)
	for _, args := range [][]string{
		{"--check", "--init-db"},
		{"--check", "--sync-docs"},
		{"--init-db", "--sync-docs"},
		{"--sync-docs", "--skip-doc-sync"},
	} {
		t.Run(strings.Join(args, " "), func(t *testing.T) {
			if _, err := parseOptions(args, io.Discard); err == nil {
				t.Fatal("互斥工作不可被接受")
			}
		})
	}
	t.Setenv("ERP_SKIP_DOC_SYNC", "1")
	if _, err := parseOptions([]string{"--sync-docs"}, io.Discard); err == nil {
		t.Fatal("環境變數的略過設定應一併驗證")
	}
	if _, err := parseOptions([]string{"--sync-docs", "--skip-doc-sync=false"}, io.Discard); err != nil {
		t.Fatalf("應允許命令列覆寫環境設定：%v", err)
	}
}

func TestRequireTLSForPublicListener(t *testing.T) {
	cleanEnvironment(t)
	tests := []struct {
		args  []string
		valid bool
	}{
		{nil, true},
		{[]string{"--host", "::1"}, true},
		{[]string{"--host", "0.0.0.0"}, false},
		{[]string{"--host", ""}, false},
		{[]string{"--host", "192.0.2.1"}, false},
		{[]string{"--host", "0.0.0.0", "--tls-proxy"}, true},
		{[]string{"--host", "0.0.0.0", "--allow-lan-http"}, true},
		{[]string{"--host", "10.10.0.2", "--allow-lan-http"}, true},
		{[]string{"--host", "203.0.113.1", "--allow-lan-http"}, false},
		{[]string{"--host", "0.0.0.0", "--tls-cert", "cert.pem", "--tls-key", "key.pem"}, true},
		{[]string{"--tls-cert", "cert.pem"}, false},
		{[]string{"--tls-key", "key.pem"}, false},
		{[]string{"--port", "0"}, false},
		{[]string{"--port", "65536"}, false},
		{[]string{"--check", "--host", "0.0.0.0", "--port", "invalid"}, true},
	}
	for _, test := range tests {
		t.Run(strings.Join(test.args, " "), func(t *testing.T) {
			settings, err := parseOptions(test.args, io.Discard)
			if (err == nil) != test.valid {
				t.Fatalf("valid=%v, error=%v", test.valid, err)
			}
			if len(test.args) == 0 && settings.address != "127.0.0.1:80" {
				t.Fatalf("預設不可對外監聽：%s", settings.address)
			}
		})
	}
}

type fakeSchemaStore struct {
	events []string
	failAt string
}

func (s *fakeSchemaStore) record(name string) error {
	s.events = append(s.events, name)
	if s.failAt == name {
		return errors.New("測試資料庫錯誤")
	}
	return nil
}

func (s *fakeSchemaStore) Initialize(context.Context, string) error { return s.record("schema") }
func (s *fakeSchemaStore) DetectSchema(context.Context) error       { return s.record("detect") }
func (s *fakeSchemaStore) SeedInitialData(context.Context, string) error {
	return s.record("employees")
}

func TestDatabasePreparation(t *testing.T) {
	tests := []struct {
		mode   operationMode
		failAt string
		want   []string
	}{
		{modeInitialize, "", []string{"schema", "detect", "employees"}},
		{modeServe, "", []string{"detect", "employees"}},
		{modeSync, "", []string{"detect"}},
		{modeInitialize, "schema", []string{"schema"}},
		{modeInitialize, "detect", []string{"schema", "detect"}},
		{modeInitialize, "employees", []string{"schema", "detect", "employees"}},
	}
	for _, test := range tests {
		t.Run(string(test.mode)+"/"+test.failAt, func(t *testing.T) {
			store := &fakeSchemaStore{failAt: test.failAt}
			err := prepareDatabase(context.Background(), store, options{mode: test.mode, root: "project"})
			if (err != nil) != (test.failAt != "") || !reflect.DeepEqual(store.events, test.want) {
				t.Fatalf("events=%v, error=%v", store.events, err)
			}
		})
	}
}

func TestDocumentSyncDoesNotBlockStartupAndCancels(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	started := make(chan struct{})
	done := startDocumentSync(ctx, false, func(ctx context.Context) error {
		close(started)
		<-ctx.Done()
		return ctx.Err()
	})
	select {
	case <-started:
	case <-time.After(time.Second):
		t.Fatal("背景同步未啟動")
	}
	select {
	case <-done:
		t.Fatal("同步應持續執行，且不可阻塞啟動呼叫")
	default:
	}
	cancel()
	select {
	case <-done:
	case <-time.After(time.Second):
		t.Fatal("服務停止後同步未結束")
	}
	called := false
	<-startDocumentSync(context.Background(), true, func(context.Context) error { called = true; return nil })
	if called {
		t.Fatal("略過同步時不應執行工作")
	}
}

func TestDocumentSyncLogsStatusWithoutSensitiveMessage(t *testing.T) {
	var output bytes.Buffer
	previous := log.Writer()
	log.SetOutput(&output)
	defer log.SetOutput(previous)
	<-startDocumentSync(context.Background(), false, func(context.Context) error {
		return status.Error(codes.Unavailable, "password=secret")
	})
	if !strings.Contains(output.String(), "Unavailable") || strings.Contains(output.String(), "password=secret") {
		t.Fatalf("同步記錄未保留安全的錯誤狀態：%s", output.String())
	}
}

func TestOccupiedPortFailsBeforeDatabaseAccess(t *testing.T) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer listener.Close()
	err = runApplication(context.Background(), options{mode: modeServe, address: listener.Addr().String(), root: t.TempDir()})
	if err == nil || !strings.Contains(err.Error(), "HTTP 監聽失敗") {
		t.Fatalf("監聽衝突應在讀取資料庫設定前失敗：%v", err)
	}
}

func TestHTTPSListener(t *testing.T) {
	certificateSource := httptest.NewTLSServer(http.NotFoundHandler())
	certificate := certificateSource.TLS.Certificates[0]
	certificateSource.Close()
	privateKey, err := x509.MarshalPKCS8PrivateKey(certificate.PrivateKey)
	if err != nil {
		t.Fatal(err)
	}
	root := t.TempDir()
	certPath, keyPath := filepath.Join(root, "cert.pem"), filepath.Join(root, "key.pem")
	if err := os.WriteFile(certPath, pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: certificate.Certificate[0]}), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(keyPath, pem.EncodeToMemory(&pem.Block{Type: "PRIVATE KEY", Bytes: privateKey}), 0600); err != nil {
		t.Fatal(err)
	}
	listener, err := listenHTTP(options{address: "127.0.0.1:0", tlsCert: certPath, tlsKey: keyPath})
	if err != nil {
		t.Fatal(err)
	}
	server := &http.Server{Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.TLS == nil {
			t.Error("請求未透過 TLS")
		}
		w.WriteHeader(http.StatusNoContent)
	})}
	defer server.Close()
	go server.Serve(listener)
	pool := x509.NewCertPool()
	pool.AddCert(certificateSource.Certificate())
	transport := &http.Transport{TLSClientConfig: &tls.Config{RootCAs: pool, MinVersion: tls.VersionTLS12}}
	defer transport.CloseIdleConnections()
	client := &http.Client{Transport: transport, Timeout: 3 * time.Second}
	response, err := client.Get("https://" + listener.Addr().String())
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusNoContent || response.TLS == nil {
		t.Fatalf("HTTPS 回應不正確：%v", response.Status)
	}
}
