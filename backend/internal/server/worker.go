package server

import (
	"bufio"
	"context"
	"crypto/subtle"
	"errors"
	"fmt"
	"io"
	"log"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"time"

	"erp-site/backend/rpc"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
)

// Authenticate 驗證 Go 資料庫 gRPC 端點的每次呼叫。
func Authenticate(token string) grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req any, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (any, error) {
		values, ok := metadata.FromIncomingContext(ctx)
		if !ok || len(values.Get("authorization")) != 1 || subtle.ConstantTimeCompare([]byte(values.Get("authorization")[0]), []byte("Bearer "+token)) != 1 {
			return nil, status.Error(codes.Unauthenticated, "內部驗證失敗")
		}
		return handler(ctx, req)
	}
}

// Worker 包含由 Go 啟動的 Python 程序與 gRPC 用戶端。
type Worker struct {
	Client  rpc.PythonWorkerClient
	Done    chan struct{}
	command *exec.Cmd
	pipe    io.WriteCloser
	channel *grpc.ClientConn
	token   string
	err     error
}

// StartWorker 啟動回送 gRPC 子程序；端點由 Python 動態配置以避免埠號衝突。
func StartWorker(ctx context.Context, root, python, address, token string) (*Worker, error) {
	command := exec.Command(python, "-m", "backend.src.erp.worker")
	command.Dir = root
	command.Env = append(os.Environ(), "ERP_INTERNAL_TOKEN="+token, "ERP_DATABASE_ADDRESS="+address, "PYTHONUNBUFFERED=1", "PYTHONIOENCODING=utf-8", "PYTHONDONTWRITEBYTECODE=1")
	stdout, err := command.StdoutPipe()
	if err != nil {
		return nil, err
	}
	pipe, err := command.StdinPipe()
	if err != nil {
		return nil, err
	}
	command.Stderr = os.Stderr
	if err := command.Start(); err != nil {
		return nil, errors.Join(err, pipe.Close(), stdout.Close())
	}
	worker := &Worker{command: command, pipe: pipe, Done: make(chan struct{}), token: token}
	ready := make(chan string, 1)
	go func() {
		scanner := bufio.NewScanner(stdout)
		for scanner.Scan() {
			line := scanner.Text()
			if strings.HasPrefix(line, "ERP_WORKER_READY=") {
				select {
				case ready <- strings.TrimPrefix(line, "ERP_WORKER_READY="):
				default:
				}
			} else {
				log.Print(line)
			}
		}
		if err := scanner.Err(); err != nil {
			log.Printf("Python 記錄讀取失敗：%v", err)
		}
		worker.err = command.Wait()
		close(worker.Done)
	}()
	select {
	case port := <-ready:
		portNumber, err := strconv.Atoi(port)
		if err != nil || portNumber < 1 || portNumber > 65535 {
			return nil, errors.Join(errors.New("Python 端點格式錯誤"), worker.Close())
		}
		channel, err := grpc.NewClient("127.0.0.1:"+port, grpc.WithTransportCredentials(insecure.NewCredentials()), grpc.WithDefaultCallOptions(grpc.MaxCallRecvMsgSize(maxMessage), grpc.MaxCallSendMsgSize(maxMessage)))
		if err != nil {
			return nil, errors.Join(err, worker.Close())
		}
		worker.channel = channel
		worker.Client = rpc.NewPythonWorkerClient(channel)
		return worker, nil
	case <-worker.Done:
		return nil, fmt.Errorf("Python 啟動失敗：%w", worker.err)
	case <-ctx.Done():
		return nil, errors.Join(ctx.Err(), worker.Close())
	}
}

// Control 呼叫 Python 生命週期工作，沿用 Go 建立的資料庫範圍。
func (w *Worker) Control(ctx context.Context, store ScopeStore, action string, skipSync bool) error {
	id, err := requestID()
	if err != nil {
		return err
	}
	release := store.BeginScope(ctx, id)
	defer release()
	ctx = metadata.NewOutgoingContext(ctx, metadata.Pairs("authorization", "Bearer "+w.token, "x-request-id", id))
	_, err = w.Client.Control(ctx, &rpc.ControlRequest{Action: action, SkipDocSync: skipSync})
	return err
}

// Close 停止工作程序與 RPC 通道；逾時後確實回收子程序。
func (w *Worker) Close() error {
	var result error
	if w.Client != nil {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		ctx = metadata.NewOutgoingContext(ctx, metadata.Pairs("authorization", "Bearer "+w.token))
		_, err := w.Client.Control(ctx, &rpc.ControlRequest{Action: "stop"})
		cancel()
		if err != nil {
			log.Print("Python 停止通知未完成，改由父程序回收")
		}
	}
	select {
	case <-w.Done:
	case <-time.After(6 * time.Second):
		if err := w.command.Process.Kill(); err != nil && !errors.Is(err, os.ErrProcessDone) {
			result = errors.Join(result, err)
		}
		<-w.Done
	}
	if err := w.pipe.Close(); err != nil && !errors.Is(err, os.ErrClosed) {
		result = errors.Join(result, err)
	}
	if w.channel != nil {
		result = errors.Join(result, w.channel.Close())
	}
	return result
}
