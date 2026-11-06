// Command erp 是網站、Python gRPC 工作程序與 SQL Server 的唯一啟動入口。
package main

import (
	"context"
	"crypto/rand"
	"crypto/tls"
	"encoding/hex"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"runtime"
	"strconv"
	"syscall"
	"time"

	"erp-site/backend/internal/config"
	"erp-site/backend/internal/server"
	"erp-site/backend/rpc"
	"erp-site/database"

	"google.golang.org/grpc"
	"google.golang.org/grpc/status"
)

const (
	databaseCheckTimeout = 8 * time.Second
	workerStartTimeout   = 30 * time.Second
	maintenanceTimeout   = 10 * time.Minute
	shutdownTimeout      = server.DefaultWriteTimeout + 10*time.Second
	maxRPCMessageBytes   = 32 * 1024 * 1024
)

type operationMode string

const (
	modeServe      operationMode = "serve"
	modeCheck      operationMode = "check"
	modeInitialize operationMode = "initialize"
	modeSync       operationMode = "sync"
)

type options struct {
	root     string
	python   string
	address  string
	mode     operationMode
	skipSync bool
	tlsCert  string
	tlsKey   string
	tlsProxy bool
}

func defaultValue(name, value string) string {
	if actual := os.Getenv(name); actual != "" {
		return actual
	}
	return value
}

func parseOptions(args []string, output io.Writer) (options, error) {
	var result options
	flags := flag.NewFlagSet("erp", flag.ContinueOnError)
	flags.SetOutput(output)
	flags.StringVar(&result.root, "root", ".", "專案根目錄")
	host := flags.String("host", defaultValue("WEB_HOST", "127.0.0.1"), "HTTP 監聽位址")
	portText := flags.String("port", defaultValue("WEB_PORT", "80"), "HTTP 監聽埠")
	flags.StringVar(&result.python, "python", os.Getenv("ERP_PYTHON"), "Python 3.11 虛擬環境直譯器")
	check := flags.Bool("check", false, "檢查 Python 與套件，不連線資料庫")
	initDB := flags.Bool("init-db", false, "明確初始化相容資料表與業務基礎資料後結束")
	syncDocs := flags.Bool("sync-docs", false, "同步 SOP 文件後結束")
	flags.BoolVar(&result.skipSync, "skip-doc-sync", defaultValue("ERP_SKIP_DOC_SYNC", "0") == "1", "略過啟動後的 SOP 背景同步")
	flags.StringVar(&result.tlsCert, "tls-cert", os.Getenv("ERP_TLS_CERT"), "HTTPS 憑證檔案")
	flags.StringVar(&result.tlsKey, "tls-key", os.Getenv("ERP_TLS_KEY"), "HTTPS 私鑰檔案")
	flags.BoolVar(&result.tlsProxy, "tls-proxy", defaultValue("ERP_TLS_PROXY", "0") == "1", "由隔離網路內的反向代理提供 HTTPS")
	if err := flags.Parse(args); err != nil {
		return result, err
	}
	if flags.NArg() != 0 {
		return result, errors.New("不接受額外位置參數")
	}
	result.mode = modeServe
	modes := 0
	for _, item := range []struct {
		enabled bool
		mode    operationMode
	}{{*check, modeCheck}, {*initDB, modeInitialize}, {*syncDocs, modeSync}} {
		if item.enabled {
			modes++
			result.mode = item.mode
		}
	}
	if modes > 1 {
		return result, errors.New("--check、--init-db 與 --sync-docs 不可同時使用")
	}
	if result.mode == modeSync && result.skipSync {
		return result, errors.New("--sync-docs 不可與 --skip-doc-sync 或 ERP_SKIP_DOC_SYNC=1 同時使用")
	}
	var err error
	result.root, err = filepath.Abs(result.root)
	if err != nil {
		return result, fmt.Errorf("解析專案根目錄失敗：%w", err)
	}
	if result.python == "" {
		if runtime.GOOS == "windows" {
			result.python = filepath.Join(result.root, ".venv", "Scripts", "python.exe")
		} else {
			result.python = filepath.Join(result.root, ".venv", "bin", "python")
		}
	}
	result.python, err = filepath.Abs(result.python)
	if err != nil {
		return result, fmt.Errorf("解析 Python 路徑失敗：%w", err)
	}
	// 維護命令不啟動 HTTP，不依賴監聽或 TLS 設定。
	if result.mode != modeServe {
		return result, nil
	}
	port, err := strconv.Atoi(*portText)
	if err != nil || port < 1 || port > 65535 {
		return result, errors.New("HTTP 埠必須介於 1 與 65535")
	}
	result.address = net.JoinHostPort(*host, strconv.Itoa(port))
	if (result.tlsCert == "") != (result.tlsKey == "") {
		return result, errors.New("--tls-cert 與 --tls-key 必須同時設定")
	}
	if result.tlsCert == "" && !result.tlsProxy {
		ip := net.ParseIP(*host)
		if ip == nil || !ip.IsLoopback() {
			return result, errors.New("對外監聽必須設定 TLS 憑證，或以 --tls-proxy 明確使用隔離網路內的 HTTPS 反向代理")
		}
	}
	return result, nil
}

func main() {
	if err := run(); err != nil && !errors.Is(err, flag.ErrHelp) {
		log.Print(err)
		os.Exit(1)
	}
}

func run() error {
	settings, err := parseOptions(os.Args[1:], os.Stderr)
	if err != nil {
		return err
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	return runApplication(ctx, settings)
}

func checkEnvironment(ctx context.Context, settings options) error {
	checkCtx, cancel := context.WithTimeout(ctx, workerStartTimeout)
	defer cancel()
	command := exec.CommandContext(checkCtx, settings.python, "-c", "import sys; assert sys.version_info[:2] == (3, 11), '需要 Python 3.11'; import grpc, google.protobuf, docx, openpyxl, pypdf, xlrd, pymupdf, PIL, pytesseract; from backend.src.erp import worker")
	command.Dir = settings.root
	command.Stdout = os.Stdout
	command.Stderr = os.Stderr
	if err := command.Run(); err != nil {
		return fmt.Errorf("Python 3.11 與相依套件檢查失敗：%w", errors.Join(err, checkCtx.Err()))
	}
	log.Print("Go／Python gRPC 環境檢查通過；未連線資料庫或啟動網站")
	return nil
}

type schemaStore interface {
	Initialize(context.Context, string) error
	DetectSchema(context.Context) error
	SeedInitialData(context.Context, string) error
}

func prepareDatabase(ctx context.Context, store schemaStore, settings options) error {
	workCtx, cancel := context.WithTimeout(ctx, maintenanceTimeout)
	defer cancel()
	if settings.mode == modeInitialize {
		if err := store.Initialize(workCtx, settings.root); err != nil {
			return fmt.Errorf("初始化資料庫結構失敗：%w", err)
		}
	}
	checkCtx, cancelCheck := context.WithTimeout(workCtx, databaseCheckTimeout)
	err := store.DetectSchema(checkCtx)
	cancelCheck()
	if err != nil {
		return fmt.Errorf("辨識資料庫結構失敗：%w", err)
	}
	if settings.mode != modeSync {
		// Python 會依在職員工更新部門狀態，必須先備妥員工資料。
		if err := store.SeedInitialData(workCtx, settings.root); err != nil {
			return fmt.Errorf("準備應用初始資料失敗：%w", err)
		}
	}
	return nil
}

func listenHTTP(settings options) (net.Listener, error) {
	var tlsConfig *tls.Config
	if settings.tlsCert != "" {
		certificate, err := tls.LoadX509KeyPair(settings.tlsCert, settings.tlsKey)
		if err != nil {
			return nil, errors.New("無法載入 HTTPS 憑證與私鑰，請檢查檔案及配對")
		}
		tlsConfig = &tls.Config{MinVersion: tls.VersionTLS12, Certificates: []tls.Certificate{certificate}}
	}
	listener, err := net.Listen("tcp", settings.address)
	if err != nil {
		return nil, fmt.Errorf("HTTP 監聽失敗：%w", err)
	}
	if tlsConfig != nil {
		return tls.NewListener(listener, tlsConfig), nil
	}
	return listener, nil
}

func runApplication(ctx context.Context, settings options) error {
	if settings.mode == modeCheck {
		return checkEnvironment(ctx, settings)
	}
	var httpListener net.Listener
	if settings.mode == modeServe {
		var err error
		httpListener, err = listenHTTP(settings)
		if err != nil {
			return err
		}
		defer httpListener.Close()
	}
	values, err := config.Load(settings.root)
	if err != nil {
		return err
	}
	store, err := database.Open(values)
	if err != nil {
		return err
	}
	defer func() {
		if err := store.Close(); err != nil {
			log.Printf("資料庫連線池關閉失敗：%v", err)
		}
	}()
	if err := prepareDatabase(ctx, store, settings); err != nil {
		return err
	}
	secret := make([]byte, 32)
	if _, err := rand.Read(secret); err != nil {
		return err
	}
	token := hex.EncodeToString(secret)
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return err
	}
	defer listener.Close()
	grpcServer := grpc.NewServer(grpc.UnaryInterceptor(server.Authenticate(token)),
		grpc.MaxRecvMsgSize(maxRPCMessageBytes), grpc.MaxSendMsgSize(maxRPCMessageBytes))
	rpc.RegisterDatabaseServer(grpcServer, store)
	dbErrors := make(chan error, 1)
	go func() { dbErrors <- grpcServer.Serve(listener) }()
	defer grpcServer.Stop()
	startCtx, cancel := context.WithTimeout(ctx, workerStartTimeout)
	worker, err := server.StartWorker(startCtx, settings.root, settings.python, listener.Addr().String(), token)
	cancel()
	if err != nil {
		return err
	}
	defer func() {
		if err := worker.Close(); err != nil {
			log.Printf("Python 工作程序回收失敗：%v", err)
		}
	}()
	control := func(ctx context.Context, action string) error {
		workCtx, cancel := context.WithTimeout(ctx, maintenanceTimeout)
		defer cancel()
		return worker.Control(workCtx, store, action, action == "initialize")
	}
	if settings.mode != modeServe {
		if err := control(ctx, string(settings.mode)); err != nil {
			return err
		}
		log.Print("指定的資料庫工作已完成")
		return nil
	}
	gateway := server.NewGateway(settings.root, worker.Client, store, token)
	defer gateway.Shutdown()
	httpServer := &http.Server{
		Addr:              settings.address,
		Handler:           gateway,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       20 * time.Second,
		WriteTimeout:      server.DefaultWriteTimeout,
		IdleTimeout:       60 * time.Second,
		MaxHeaderBytes:    32 * 1024,
	}
	httpErrors := make(chan error, 1)
	go func() {
		scheme := "http"
		if settings.tlsCert != "" {
			scheme = "https"
		}
		log.Printf("銀盾共同體 Go 網站：%s://%s", scheme, httpListener.Addr())
		httpErrors <- httpServer.Serve(httpListener)
	}()
	syncCtx, cancelSync := context.WithCancel(ctx)
	syncDone := startDocumentSync(syncCtx, settings.skipSync, func(ctx context.Context) error {
		return control(ctx, "sync")
	})
	var runErr error
	select {
	case <-ctx.Done():
	case <-worker.Done:
		runErr = errors.New("Python 工作程序已停止，結束 Go 服務以供監控重新啟動")
	case err := <-dbErrors:
		runErr = fmt.Errorf("內部資料庫服務已停止：%w", err)
	case err := <-httpErrors:
		if !errors.Is(err, http.ErrServerClosed) {
			runErr = err
		}
	}
	cancelSync()
	gateway.Shutdown()
	shutdownCtx, cancelShutdown := context.WithTimeout(context.Background(), shutdownTimeout)
	defer cancelShutdown()
	if err := httpServer.Shutdown(shutdownCtx); err != nil {
		runErr = errors.Join(runErr, err, httpServer.Close())
	}
	select {
	case <-syncDone:
	case <-shutdownCtx.Done():
		runErr = errors.Join(runErr, errors.New("背景文件同步未在關閉期限內結束"))
	}
	return runErr
}

func startDocumentSync(ctx context.Context, skip bool, syncDocuments func(context.Context) error) <-chan struct{} {
	done := make(chan struct{})
	if skip {
		close(done)
		return done
	}
	go func() {
		defer close(done)
		started := time.Now()
		if err := syncDocuments(ctx); err != nil {
			if ctx.Err() != nil {
				log.Print("服務停止，已取消背景 SOP 同步")
				return
			}
			// 僅記錄狀態碼與類別，避免底層錯誤訊息洩漏憑證或業務資料。
			log.Printf("背景 SOP 同步失敗：階段=sync，狀態=%s，類別=%T，耗時=%s；可使用 --sync-docs 重試", status.Code(err), err, time.Since(started).Round(time.Millisecond))
			return
		}
		log.Printf("背景 SOP 同步完成，耗時=%s", time.Since(started).Round(time.Millisecond))
	}()
	return done
}
