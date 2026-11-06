package server

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"erp-site/backend/rpc"
	"google.golang.org/grpc"
	"google.golang.org/grpc/metadata"
)

type fakeStore struct{ active int }

func (s *fakeStore) BeginScope(_ context.Context, _ string) func() {
	s.active++
	return func() { s.active-- }
}

type fakeClient struct {
	rpc.PythonWorkerClient
	request *rpc.HttpRequest
	auth    string
}

func (c *fakeClient) Handle(ctx context.Context, r *rpc.HttpRequest, _ ...grpc.CallOption) (*rpc.HttpResponse, error) {
	c.request = r
	meta, _ := metadata.FromOutgoingContext(ctx)
	c.auth = meta.Get("authorization")[0]
	return &rpc.HttpResponse{Status: 200, Headers: []*rpc.Header{{Name: "Content-Type", Value: "application/json"}, {Name: "Set-Cookie", Value: "a=1; HttpOnly"}, {Name: "Set-Cookie", Value: "b=2; HttpOnly"}}, Body: []byte(`{"data":true}`)}, nil
}

func TestDeleteBodyCookiesAndRequestCleanup(t *testing.T) {
	client, store := &fakeClient{}, &fakeStore{}
	gateway := NewGateway(t.TempDir(), client, store, "secret")
	request := httptest.NewRequest(http.MethodDelete, "/api/admin/compliance/question", strings.NewReader(`{"id":7}`))
	request.Header.Set("X-CSRF-Token", "csrf")
	request.Header.Set("Cookie", "session=x")
	response := httptest.NewRecorder()
	gateway.ServeHTTP(response, request)
	if response.Code != 200 || client.request.Method != "DELETE" || string(client.request.Body) != `{"id":7}` {
		t.Fatal("DELETE 契約未保留")
	}
	if len(response.Header().Values("Set-Cookie")) != 2 || store.active != 0 || client.auth != "Bearer secret" {
		t.Fatal("Cookie、驗證或範圍清理不正確")
	}
	for _, cookie := range response.Result().Cookies() {
		if !cookie.Secure || !cookie.HttpOnly {
			t.Fatal("工作階段 Cookie 應保留 HttpOnly 並強制 Secure")
		}
	}
}

func TestLANCookiesAndPublicRequests(t *testing.T) {
	for _, address := range []string{"10.10.0.20:1234", "192.168.1.20:1234", "127.0.0.1:1234", "[::1]:1234"} {
		gateway := NewGateway(t.TempDir(), &fakeClient{}, &fakeStore{}, "secret", true)
		request := httptest.NewRequest(http.MethodPost, "/api/employee/login", strings.NewReader(`{}`))
		request.RemoteAddr = address
		response := httptest.NewRecorder()
		gateway.ServeHTTP(response, request)
		if response.Code != 200 {
			t.Fatalf("內網請求遭拒絕：%s", address)
		}
		for _, cookie := range response.Result().Cookies() {
			if cookie.Secure || !cookie.HttpOnly {
				t.Fatal("內網 HTTP Cookie 必須能儲存且保留 HttpOnly")
			}
		}
	}
	client := &fakeClient{}
	gateway := NewGateway(t.TempDir(), client, &fakeStore{}, "secret", true)
	request := httptest.NewRequest(http.MethodGet, "/api/employee/session", nil)
	request.RemoteAddr = "203.0.113.1:1234"
	request.Header.Set("X-Forwarded-For", "10.10.0.1")
	response := httptest.NewRecorder()
	gateway.ServeHTTP(response, request)
	if response.Code != http.StatusForbidden || client.request != nil {
		t.Fatal("內網 HTTP 不得信任偽造的轉送標頭")
	}
}

type deadlineRecorder struct {
	*httptest.ResponseRecorder
	deadlines []time.Time
}

func (w *deadlineRecorder) SetWriteDeadline(deadline time.Time) error {
	w.deadlines = append(w.deadlines, deadline)
	return nil
}

type blockingClient struct {
	rpc.PythonWorkerClient
	handle func(context.Context) (*rpc.HttpResponse, error)
}

func (c *blockingClient) Handle(ctx context.Context, _ *rpc.HttpRequest, _ ...grpc.CallOption) (*rpc.HttpResponse, error) {
	return c.handle(ctx)
}

func TestShutdownCancelsOnlyLongRequests(t *testing.T) {
	for _, path := range []string{"/api/admin/manuals/sync", "/api/public"} {
		t.Run(path, func(t *testing.T) {
			longRequest := path == "/api/admin/manuals/sync"
			started := make(chan time.Duration, 1)
			release := make(chan struct{})
			client := &blockingClient{handle: func(ctx context.Context) (*rpc.HttpResponse, error) {
				deadline, _ := ctx.Deadline()
				started <- time.Until(deadline)
				select {
				case <-ctx.Done():
					return nil, ctx.Err()
				case <-release:
					return &rpc.HttpResponse{Status: 200, Body: []byte("ok")}, nil
				}
			}}
			gateway := NewGateway(t.TempDir(), client, &fakeStore{}, "secret")
			defer gateway.Shutdown()
			recorder := &deadlineRecorder{ResponseRecorder: httptest.NewRecorder()}
			done := make(chan struct{})
			go func() {
				defer close(done)
				gateway.ServeHTTP(recorder, httptest.NewRequest("POST", path, nil))
			}()
			var duration time.Duration
			select {
			case duration = <-started:
			case <-time.After(time.Second):
				t.Fatal("RPC 未開始")
			}
			wantDuration := requestTimeout
			if longRequest {
				wantDuration = documentSyncTimeout
			}
			if duration < wantDuration-time.Second || duration > wantDuration {
				t.Fatalf("RPC 期限不正確：%s", duration)
			}
			gateway.Shutdown()
			if !longRequest {
				select {
				case <-done:
					t.Fatal("一般 API 應等待完成，不應因開始關閉而取消")
				default:
				}
				close(release)
			}
			select {
			case <-done:
			case <-time.After(time.Second):
				if longRequest {
					close(release)
				}
				t.Fatal("請求未完成關閉")
			}
			wantStatus := 200
			if longRequest {
				wantStatus = 503
			}
			if recorder.Code != wantStatus {
				t.Fatalf("關閉時的狀態碼不正確：%d", recorder.Code)
			}
			if len(recorder.deadlines) < 2 {
				t.Fatal("RPC 完成後應重新設定傳送期限")
			}
			remaining := time.Until(recorder.deadlines[len(recorder.deadlines)-1])
			if remaining < responseWriteTimeout-time.Second || remaining > responseWriteTimeout {
				t.Fatalf("回應傳送期限不正確：%s", remaining)
			}
		})
	}
}

func TestOversizedBodyNeverReachesWorker(t *testing.T) {
	client := &fakeClient{}
	gateway := NewGateway(t.TempDir(), client, &fakeStore{}, "secret")
	response := httptest.NewRecorder()
	gateway.ServeHTTP(response, httptest.NewRequest("POST", "/api/admin/staff", strings.NewReader(strings.Repeat("x", maxBody+1))))
	if response.Code != 413 || client.request != nil {
		t.Fatal("過大內容未被 Go 擋下")
	}
}

func TestStaticAllowlistAndTraversal(t *testing.T) {
	root := t.TempDir()
	if err := os.MkdirAll(filepath.Join(root, "page", "static"), 0700); err != nil {
		t.Fatal(err)
	}
	for path, body := range map[string]string{"page/index.html": "<h1>首頁</h1>", "page/static/app.js": "let x=1;", ".env": "secret", "page/static/.private": "private"} {
		if err := os.WriteFile(filepath.Join(root, filepath.FromSlash(path)), []byte(body), 0600); err != nil {
			t.Fatal(err)
		}
	}
	gateway := NewGateway(root, &fakeClient{}, &fakeStore{}, "secret")
	for path, want := range map[string]int{"/": 200, "/index.html": 200, "/static/app.js": 200, "/.env": 404, "/static/../index.html": 404, "/static/.private": 404, "/static/%2e%2e/.env": 404, "/static/..%5c..%5c.env": 404, "/static/": 404} {
		recorder := httptest.NewRecorder()
		gateway.ServeHTTP(recorder, httptest.NewRequest("GET", path, nil))
		if recorder.Code != want {
			t.Errorf("%s: %d != %d", path, recorder.Code, want)
		}
	}
}

func TestInternalAuthentication(t *testing.T) {
	called := false
	handler := func(context.Context, any) (any, error) { called = true; return nil, nil }
	_, err := Authenticate("secret")(context.Background(), nil, &grpc.UnaryServerInfo{}, handler)
	if err == nil || called {
		t.Fatal("內部 gRPC 接受未驗證呼叫")
	}
	ctx := metadata.NewIncomingContext(context.Background(), metadata.Pairs("authorization", "Bearer secret"))
	if _, err := Authenticate("secret")(ctx, nil, &grpc.UnaryServerInfo{}, handler); err != nil || !called {
		t.Fatal("合法內部呼叫遭拒絕")
	}
}
