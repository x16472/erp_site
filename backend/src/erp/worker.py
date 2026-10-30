"""由 Go 管理的 Python gRPC 工作程序，僅綁定 IPv4 回送位址。"""

from __future__ import annotations

import hmac
import logging
import os
import sys
import threading
from concurrent import futures

import grpc

from . import api, database_client, domain, doc
from .rpc import backend_pb2, backend_pb2_grpc

MAX_MESSAGE_SIZE = 32 * 1024 * 1024


class Worker(backend_pb2_grpc.PythonWorkerServicer):
    """處理已由 Go 限流與驗證來源的 API 及生命週期呼叫。"""

    def __init__(self, token: str, stop: threading.Event) -> None:
        """保留僅此程序有效的驗證權杖與停止事件。"""
        self.token = token
        self.stop = stop

    def _authenticate(self, context: grpc.ServicerContext) -> None:
        """拒絕未帶啟動權杖的本機呼叫。"""
        headers = dict(context.invocation_metadata())
        if not hmac.compare_digest(headers.get("authorization", ""), f"Bearer {self.token}"):
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "內部驗證失敗")

    def Handle(self, request: backend_pb2.HttpRequest, context: grpc.ServicerContext) -> backend_pb2.HttpResponse:
        """執行原有 API 契約並將 Cookie、狀態碼及內容原樣交回 Go。"""
        self._authenticate(context)
        scope_token = database_client.request_id.set(request.request_id)
        context_token = database_client.request_context.set(context)
        handler = api.Handler(request)
        try:
            with domain.connection_scope():
                if request.method == "GET":
                    handler.do_GET()
                elif request.method == "POST":
                    handler.do_POST()
                elif request.method == "DELETE":
                    handler.do_DELETE()
                else:
                    handler.send_json({"error": "不支援的請求方法"}, 405)
        except (database_client.Error, domain.DatabaseUnavailable):
            handler = api.Handler(request)
            handler.send_json({"error": "資料庫服務暫時無法使用", "code": "DATABASE_UNAVAILABLE"}, 503)
        except Exception as exc:
            # 只記錄類別；業務資料、SQL 與憑證不寫入記錄。
            logging.error("Python API 未預期錯誤：%s", type(exc).__name__)
            handler = api.Handler(request)
            handler.send_json({"error": "服務暫時無法處理請求", "code": "INTERNAL_ERROR"}, 500)
        finally:
            database_client.request_context.reset(context_token)
            database_client.request_id.reset(scope_token)
        handler.response.body = handler.wfile.getvalue()
        return handler.response

    def Control(self, request: backend_pb2.ControlRequest, context: grpc.ServicerContext) -> backend_pb2.ControlResponse:
        """提供就緒、初始化、同步及停止；操作名稱採固定白名單。"""
        self._authenticate(context)
        scope = dict(context.invocation_metadata()).get("x-request-id", "")
        scope_token = database_client.request_id.set(scope)
        context_token = database_client.request_context.set(context)
        try:
            if request.action == "ready":
                return backend_pb2.ControlResponse(status="ready")
            if request.action == "stop":
                self.stop.set()
                return backend_pb2.ControlResponse(status="stopping")
            with domain.connection_scope():
                if request.action == "initialize":
                    domain.initialize_business_data()
                elif request.action != "sync":
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, "不支援的控制操作")
                if not request.skip_doc_sync:
                    try:
                        doc.sync_operations_manuals(ensure_schema=False)
                    except (doc.DocumentImportError, domain.DatabaseUnavailable, database_client.Error) as exc:
                        logging.error("文件同步失敗：%s", type(exc).__name__)
                        if request.action == "sync":
                            context.abort(grpc.StatusCode.UNAVAILABLE, "文件同步失敗")
            return backend_pb2.ControlResponse(status="complete")
        except (domain.DatabaseUnavailable, database_client.Error):
            context.abort(grpc.StatusCode.UNAVAILABLE, "資料庫初始化失敗")
        finally:
            database_client.request_context.reset(context_token)
            database_client.request_id.reset(scope_token)


def main() -> None:
    """由 Go 注入回送端點與驗證權杖，啟動 gRPC 並監測父程序。"""
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError("需要 Python 3.11")
    token = os.environ.get("ERP_INTERNAL_TOKEN", "")
    address = os.environ.get("ERP_DATABASE_ADDRESS", "")
    if not token or not address.startswith("127.0.0.1:"):
        raise RuntimeError("請使用 Go 主程式啟動 Python 工作程序")
    options = [("grpc.max_receive_message_length", MAX_MESSAGE_SIZE),
               ("grpc.max_send_message_length", MAX_MESSAGE_SIZE)]
    channel = grpc.insecure_channel(address, options=options)
    database_client.configure(channel, token)
    stop = threading.Event()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=16), options=options,
                         maximum_concurrent_rpcs=16)
    backend_pb2_grpc.add_PythonWorkerServicer_to_server(Worker(token, stop), server)
    port = server.add_insecure_port("127.0.0.1:0")
    if not port:
        raise RuntimeError("無法啟動 Python gRPC 端點")
    server.start()
    print(f"ERP_WORKER_READY={port}", flush=True)
    try:
        while not stop.wait(1):
            # Go 保持 stdin 開啟；父程序終止後由獨立讀取執行緒通知停止。
            pass
    finally:
        server.stop(5).wait()
        channel.close()


if __name__ == "__main__":
    import sys

    # stdin EOF 可跨 Windows／Linux 偵測 Go 父程序已離開。
    def watch_parent() -> None:
        """父程序意外停止時終止工作程序，避免孤兒程序持有工作階段。"""
        # 不持有 BufferedReader 鎖，避免正常關閉時與直譯器清理互相卡住。
        try:
            while os.read(sys.stdin.fileno(), 4096):
                pass
        except OSError:
            return
        os._exit(0)

    threading.Thread(target=watch_parent, daemon=True).start()
    main()
