// Command erp 是網站、Python gRPC 工作程序與 SQL Server 的唯一啟動入口。
package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"flag"
	"fmt"
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
	"erp-site/database"
	"erp-site/backend/rpc"
	"erp-site/backend/internal/server"

	"google.golang.org/grpc"
)

func defaultValue(name, value string) string {
	if actual := os.Getenv(name); actual != "" {
		return actual
	}
	return value
}

func main() {
	if err := run(); err != nil {
		log.Print(err)
		os.Exit(1)
	}
}

func run() error {
	rootFlag := flag.String("root", ".", "專案根目錄")
	host := flag.String("host", defaultValue("WEB_HOST", "0.0.0.0"), "HTTP 監聽位址")
	portText := flag.String("port", defaultValue("WEB_PORT", "80"), "HTTP 監聽埠")
	pythonFlag := flag.String("python", os.Getenv("ERP_PYTHON"), "Python 3.11 虛擬環境直譯器")
	check := flag.Bool("check", false, "檢查 Python 與套件，不連線資料庫")
	initDB := flag.Bool("init-db", false, "明確初始化相容資料表與業務基礎資料後結束")
	syncDocs := flag.Bool("sync-docs", false, "同步 SOP 文件後結束")
	skipSync := flag.Bool("skip-doc-sync", defaultValue("ERP_SKIP_DOC_SYNC", "0") == "1", "略過啟動時 SOP 同步，預設自動同步")
	flag.Parse()
	if flag.NArg() != 0 {
		return errors.New("不接受額外位置參數")
	}
	root, err := filepath.Abs(*rootFlag)
	if err != nil {
		return err
	}
	python := *pythonFlag
	if python == "" {
		if runtime.GOOS == "windows" {
			python = filepath.Join(root, ".venv", "Scripts", "python.exe")
		} else {
			python = filepath.Join(root, ".venv", "bin", "python")
		}
	}
	python, err = filepath.Abs(python)
	if err != nil {
		return err
	}
	if *check {
		command := exec.Command(python, "-c", "import sys; assert sys.version_info[:2] == (3, 11), '需要 Python 3.11'; import grpc, google.protobuf, docx, openpyxl, pypdf, xlrd, pymupdf, PIL, pytesseract; from backend.src.erp import worker")
		command.Dir = root
		command.Stdout = os.Stdout
		command.Stderr = os.Stderr
		if err := command.Run(); err != nil {
			return fmt.Errorf("Python 3.11 與相依套件檢查失敗：%w", err)
		}
		log.Print("Go／Python gRPC 環境檢查通過；未連線資料庫或啟動網站")
		return nil
	}
	port, err := strconv.Atoi(*portText)
	if err != nil || port < 1 || port > 65535 {
		return errors.New("HTTP 埠必須介於 1 與 65535")
	}
	settings, err := config.Load(root)
	if err != nil {
		return err
	}
	store, err := database.Open(settings)
	if err != nil {
		return err
	}
	defer func() {
		if err := store.Close(); err != nil {
			log.Printf("資料庫連線池關閉失敗：%v", err)
		}
	}()
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	if *initDB || *syncDocs {
		pingCtx, cancel := context.WithTimeout(ctx, 8*time.Second)
		err = store.Ping(pingCtx)
		cancel()
		if err != nil {
			return err
		}
	}
	if !*initDB {
		checkCtx, cancel := context.WithTimeout(ctx, 8*time.Second)
		err = store.DetectSchema(checkCtx)
		cancel()
		if err != nil {
			return err
		}
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
	grpcServer := grpc.NewServer(grpc.UnaryInterceptor(server.Authenticate(token)),
		grpc.MaxRecvMsgSize(32*1024*1024),
		grpc.MaxSendMsgSize(32*1024*1024))
	rpc.RegisterDatabaseServer(grpcServer, store)
	dbErrors := make(chan error, 1)
	go func() { dbErrors <- grpcServer.Serve(listener) }()
	defer grpcServer.Stop()
	startCtx, cancel := context.WithTimeout(ctx, 30*time.Second)
	worker, err := server.StartWorker(startCtx, root, python, listener.Addr().String(), token)
	cancel()
	if err != nil {
		return err
	}
	defer func() {
		if err := worker.Close(); err != nil {
			log.Printf("Python 工作程序回收失敗：%v", err)
		}
	}()
	workCtx, cancel := context.WithTimeout(ctx, 10*time.Minute)
	if *initDB {
		err = store.Initialize(workCtx, root)
		if err == nil {
			err = store.DetectSchema(workCtx)
		}
		if err == nil {
			err = worker.Control(workCtx, store, "initialize", true)
		}
	}
	if err == nil && !*syncDocs {
		err = store.SeedEmployees(workCtx, root)
		if err != nil {
			cancel()
			return err
		}
	}
	if err == nil && !*initDB && (*syncDocs || !*skipSync) {
		err = worker.Control(workCtx, store, "sync", false)
	}
	cancel()
	if err != nil {
		if *initDB || *syncDocs {
			return err
		}
		log.Print("啟動時 SOP 同步未完成，網站仍可啟動；請確認資料庫後使用 --sync-docs 重試")
	}
	if *initDB || *syncDocs {
		log.Print("指定的資料庫工作已完成")
		return nil
	}
	httpServer := &http.Server{Addr: net.JoinHostPort(*host, strconv.Itoa(port)), Handler: server.NewGateway(root, worker.Client, store, token), ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 20 * time.Second, WriteTimeout: 11 * time.Minute, IdleTimeout: 60 * time.Second, MaxHeaderBytes: 32 * 1024}
	httpErrors := make(chan error, 1)
	go func() {
		log.Printf("銀盾共同體 Go 網站：http://%s", httpServer.Addr)
		httpErrors <- httpServer.ListenAndServe()
	}()
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
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	if err := httpServer.Shutdown(shutdownCtx); err != nil {
		runErr = errors.Join(runErr, err, httpServer.Close())
	}
	return runErr
}
