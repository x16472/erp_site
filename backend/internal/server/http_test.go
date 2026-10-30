package server

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

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
