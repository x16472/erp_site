// Package server 提供 Go HTTP 入口與 Python 工作程序管理。
package server

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"io"
	"log"
	"mime"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"erp-site/backend/rpc"
	"google.golang.org/grpc"
	"google.golang.org/grpc/metadata"
)

const maxBody = 7 * 1024 * 1024
const maxMessage = 32 * 1024 * 1024

// ScopeStore 註冊請求生命週期，確保取消或逾時時回復未提交的交易。
type ScopeStore interface {
	BeginScope(context.Context, string) func()
}

// Gateway 管理 HTTP 資源、大小上限、並行數及內部 RPC 的期限。
type Gateway struct {
	root     string
	client   rpc.PythonWorkerClient
	store    ScopeStore
	token    string
	requests chan struct{}
}

// NewGateway 建立共用的網站與 API 入口；root 是專案根目錄。
func NewGateway(root string, client rpc.PythonWorkerClient, store ScopeStore, token string) *Gateway {
	return &Gateway{root: root, client: client, store: store, token: token, requests: make(chan struct{}, 12)}
}

func requestID() (string, error) {
	value := make([]byte, 24)
	if _, err := rand.Read(value); err != nil {
		return "", err
	}
	return hex.EncodeToString(value), nil
}

func secureHeaders(w http.ResponseWriter) {
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("X-Frame-Options", "DENY")
	w.Header().Set("Referrer-Policy", "same-origin")
}

func writeError(w http.ResponseWriter, status int, message string) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(status)
	if _, err := io.WriteString(w, message); err != nil {
		log.Printf("HTTP 回應傳送失敗：%v", err)
	}
}

// ServeHTTP 將公開靜態內容留在 Go，業務 API 經驗證的 gRPC 通道執行。
func (g *Gateway) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	secureHeaders(w)
	if !strings.HasPrefix(r.URL.Path, "/api/") {
		g.static(w, r)
		return
	}
	if r.Method != http.MethodGet && r.Method != http.MethodPost && r.Method != http.MethodDelete {
		w.Header().Set("Allow", "GET, POST, DELETE")
		writeError(w, 405, `{"error":"不支援的請求方法","code":"METHOD_NOT_ALLOWED"}`)
		return
	}
	select {
	case g.requests <- struct{}{}:
		defer func() { <-g.requests }()
	default:
		writeError(w, 503, `{"error":"服務忙碌，請稍後再試","code":"SERVICE_UNAVAILABLE"}`)
		return
	}
	r.Body = http.MaxBytesReader(w, r.Body, maxBody)
	body, err := io.ReadAll(r.Body)
	if err != nil {
		var sizeError *http.MaxBytesError
		if errors.As(err, &sizeError) {
			writeError(w, 413, `{"error":"請求內容過大","code":"INVALID_REQUEST"}`)
		} else {
			writeError(w, 400, `{"error":"無法讀取請求內容","code":"INVALID_REQUEST"}`)
		}
		return
	}
	id, err := requestID()
	if err != nil {
		writeError(w, 500, `{"error":"無法建立工作範圍"}`)
		return
	}
	duration := 45 * time.Second
	if r.URL.Path == "/api/admin/manuals/sync" {
		duration = 10 * time.Minute
	}
	ctx, cancel := context.WithTimeout(r.Context(), duration)
	defer cancel()
	release := g.store.BeginScope(ctx, id)
	defer release()
	ctx = metadata.NewOutgoingContext(ctx, metadata.Pairs("authorization", "Bearer "+g.token))
	address, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		address = r.RemoteAddr
	}
	request := &rpc.HttpRequest{Method: r.Method, Target: r.URL.RequestURI(), Body: body, RemoteAddress: address, RequestId: id}
	for name, values := range r.Header {
		if strings.EqualFold(name, "Content-Length") {
			continue
		}
		for _, value := range values {
			request.Headers = append(request.Headers, &rpc.Header{Name: name, Value: value})
		}
	}
	request.Headers = append(request.Headers, &rpc.Header{Name: "Content-Length", Value: strconv.Itoa(len(body))})
	response, err := g.client.Handle(ctx, request, grpc.MaxCallRecvMsgSize(maxMessage), grpc.MaxCallSendMsgSize(maxMessage))
	if err != nil {
		status := 503
		if errors.Is(ctx.Err(), context.DeadlineExceeded) {
			status = 504
		}
		writeError(w, status, `{"error":"業務服務暫時無法回應","code":"SERVICE_UNAVAILABLE"}`)
		return
	}
	if response.Status < 200 || response.Status > 599 {
		writeError(w, 502, `{"error":"業務服務回應格式錯誤"}`)
		return
	}
	for _, header := range response.Headers {
		switch strings.ToLower(header.Name) {
		case "content-type", "set-cookie", "cache-control":
			w.Header().Add(header.Name, header.Value)
		}
	}
	w.Header().Set("Content-Length", strconv.Itoa(len(response.Body)))
	w.WriteHeader(int(response.Status))
	if _, err := w.Write(response.Body); err != nil {
		log.Printf("API 回應傳送失敗：%v", err)
	}
}

func (g *Gateway) static(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		w.Header().Set("Allow", "GET, HEAD")
		http.Error(w, "Method Not Allowed", 405)
		return
	}
	pages := map[string]string{"/": "index.html", "/index.html": "index.html", "/home.html": "home.html", "/sales.html": "sales.html", "/mis.html": "mis.html", "/exam.html": "exam.html", "/workflow.html": "workflow.html", "/game.html": "game.html", "/staff.html": "staff.html", "/employee-login.html": "employee-login.html", "/style.css": "static/style.css"}
	relative, ok := pages[r.URL.Path]
	if !ok {
		if !strings.HasPrefix(r.URL.Path, "/static/") || strings.ContainsAny(r.URL.Path, "\\:\x00") {
			http.NotFound(w, r)
			return
		}
		for _, part := range strings.Split(r.URL.Path, "/") {
			if strings.HasPrefix(part, ".") {
				http.NotFound(w, r)
				return
			}
		}
		relative = strings.TrimPrefix(r.URL.Path, "/")
	}
	root, err := filepath.EvalSymlinks(filepath.Join(g.root, "page"))
	if err != nil {
		http.NotFound(w, r)
		return
	}
	target, err := filepath.EvalSymlinks(filepath.Join(root, filepath.FromSlash(relative)))
	if err != nil {
		http.NotFound(w, r)
		return
	}
	boundary, err := filepath.Rel(root, target)
	if err != nil || boundary == ".." || strings.HasPrefix(boundary, ".."+string(filepath.Separator)) || filepath.IsAbs(boundary) {
		http.NotFound(w, r)
		return
	}
	file, err := os.Open(target)
	if err != nil {
		http.NotFound(w, r)
		return
	}
	defer func() {
		if err := file.Close(); err != nil {
			log.Printf("靜態檔案關閉失敗：%v", err)
		}
	}()
	stat, err := file.Stat()
	if err != nil || stat.IsDir() {
		http.NotFound(w, r)
		return
	}
	if contentType := mime.TypeByExtension(filepath.Ext(target)); contentType != "" {
		w.Header().Set("Content-Type", contentType)
	}
	http.ServeContent(w, r, stat.Name(), stat.ModTime(), file)
}
