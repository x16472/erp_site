"""內部 gRPC 契約、型別與取消／錯誤行為的回歸測試。"""

from __future__ import annotations

import json
import threading
import unittest
from concurrent import futures
from datetime import date, datetime
from decimal import Decimal
from unittest import mock

import grpc

from backend.src.erp import database_client as database
from backend.src.erp import domain
from backend.src.erp.rpc import backend_pb2, backend_pb2_grpc
from backend.src.erp.worker import Worker


class DatabaseContractTests(unittest.TestCase):
    """測試跨語言 SQL 值及資料庫錯誤的相容性。"""

    def test_typed_values_round_trip(self) -> None:
        """日期、整數及精確小數不能因 JSON 往返而遺失型別或精度。"""
        values = [date(2026, 10, 30), datetime(2026, 10, 30, 1, 2, 3),
                  Decimal("12345678901234.5678"), b"\x00\xff", 1793314439123456789, None]
        body = json.dumps(values, default=database._encode)
        self.assertEqual(json.loads(body, object_hook=database._decode), values)

    def test_connection_failure_is_safe(self) -> None:
        """業務層不向前端揭露底層連線資訊。"""
        with mock.patch.object(database, "connect", side_effect=database.Error("internal details")):
            with self.assertRaises(domain.DatabaseUnavailable) as result:
                domain._new_connection(True, True)
        self.assertNotIn("internal details", str(result.exception))

    def test_cursor_transmits_query_id_and_typed_parameters(self) -> None:
        """SQL 本文留在 Go，用戶端只傳送查詢代碼與獨立的參數。"""
        connection = mock.Mock(session_id="connection", closed=False)
        result = backend_pb2.DatabaseResponse(columns=["Id"], rows_json=b"[[7]]", row_count=1)
        with mock.patch.object(database, "_call", return_value=result) as call:
            cursor = database.Cursor(connection).execute("domain.health.1", (1793314439123456789,))
        self.assertEqual(call.call_args.kwargs["query"], "domain.health.1")
        self.assertEqual(json.loads(call.call_args.kwargs["parameters_json"]), [1793314439123456789])
        self.assertEqual(cursor.fetchone(), [7])
        self.assertIsNone(cursor.fetchone())


class WorkerContractTests(unittest.TestCase):
    """使用真正的 protobuf／gRPC 通道測試內部 API 契約。"""

    def setUp(self) -> None:
        """啟動不連接 SQL Server 的回送工作服務。"""
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        backend_pb2_grpc.add_PythonWorkerServicer_to_server(Worker("test-token", threading.Event()), self.server)
        port = self.server.add_insecure_port("127.0.0.1:0")
        self.server.start()
        self.channel = grpc.insecure_channel(f"127.0.0.1:{port}")
        self.stub = backend_pb2_grpc.PythonWorkerStub(self.channel)

    def tearDown(self) -> None:
        """釋放通道及測試程序的工作執行緒。"""
        self.channel.close()
        self.server.stop(0).wait()

    def test_unauthenticated_rpc_is_rejected(self) -> None:
        """本機呼叫也必須攜帶 Go 啟動權杖。"""
        with self.assertRaises(grpc.RpcError) as result:
            self.stub.Handle(backend_pb2.HttpRequest(method="GET", target="/api/employee/session"), timeout=3)
        self.assertEqual(result.exception.code(), grpc.StatusCode.UNAUTHENTICATED)

    def test_employee_session_contract(self) -> None:
        """保留前端既有的未登入 JSON 格式與安全標頭。"""
        response = self.stub.Handle(
            backend_pb2.HttpRequest(method="GET", target="/api/employee/session", request_id="test"),
            metadata=(("authorization", "Bearer test-token"),), timeout=3,
        )
        self.assertEqual(response.status, 200)
        self.assertFalse(json.loads(response.body)["data"]["authenticated"])
        self.assertIn("no-store", [header.value for header in response.headers])

    def test_delete_still_requires_employee(self) -> None:
        """Go 轉送 DELETE 後仍需通過既有員工、管理員與 CSRF 檢查。"""
        response = self.stub.Handle(
            backend_pb2.HttpRequest(method="DELETE", target="/api/admin/compliance/question", request_id="test"),
            metadata=(("authorization", "Bearer test-token"),), timeout=3,
        )
        self.assertEqual(response.status, 401)
        self.assertEqual(json.loads(response.body)["code"], "EMPLOYEE_AUTH_REQUIRED")


if __name__ == "__main__":
    unittest.main()
