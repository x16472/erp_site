"""Go 資料庫服務的型別化用戶端；本模組不載入任何 SQL Server 驅動。"""

from __future__ import annotations

import contextvars
import json
from datetime import date, datetime
from decimal import Decimal
from dataclasses import dataclass
from typing import Any

import grpc

from .rpc import backend_pb2, backend_pb2_grpc

request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
request_context: contextvars.ContextVar[Any] = contextvars.ContextVar("request_context", default=None)
_stub: backend_pb2_grpc.DatabaseStub | None = None
_token = ""


class Error(RuntimeError):
    """只攜帶 Go 提供的安全錯誤，不包含 SQL、帳密或連線字串。"""


class IntegrityError(Error):
    """唯一值或外鍵限制衝突。"""


@dataclass(frozen=True)
class Statement:
    """Go 查詢代碼與受控的查詢選項；不包含 SQL 本文。"""

    name: str
    options: tuple[Any, ...]


def statement(name: str, *options: Any) -> Statement:
    """指定需要 Go 白名單驗證及展開的動態查詢選項。"""
    return Statement(name, options)


def configure(channel: grpc.Channel, token: str) -> None:
    """由工作程序設定共用 gRPC 通道及每次啟動重新產生的權杖。"""
    global _stub, _token
    _stub = backend_pb2_grpc.DatabaseStub(channel)
    _token = token


def _encode(value: Any) -> dict[str, str]:
    """保留日期、小數及二進位參數型別，避免整數經浮點數遺失精度。"""
    if isinstance(value, datetime):
        return {"type": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"type": "date", "value": value.isoformat()}
    if isinstance(value, Decimal):
        return {"type": "decimal", "value": str(value)}
    if isinstance(value, bytes):
        return {"type": "bytes", "value": value.hex()}
    raise TypeError(f"不支援的資料庫參數型別：{type(value).__name__}")


def _decode(value: dict[str, Any]) -> Any:
    """將 Go 傳回的 SQL 型別還原為既有業務程式使用的 Python 型別。"""
    converters = {"datetime": datetime.fromisoformat, "date": date.fromisoformat,
                  "decimal": Decimal, "bytes": bytes.fromhex}
    converter = converters.get(value.get("type"))
    return converter(value["value"]) if converter else value


def _call(operation: str, **fields: Any) -> backend_pb2.DatabaseResponse:
    """執行具期限及驗證權杖的內部呼叫；禁止自動重試資料異動。"""
    if _stub is None or not request_id.get():
        raise Error("請透過 Go 主程式執行資料庫工作")
    context = request_context.get()
    remaining = context.time_remaining() if context is not None else None
    timeout = min(30.0, remaining) if remaining is not None else 30.0
    if timeout <= 0:
        raise Error("資料庫工作已逾時")
    try:
        result = _stub.Execute(
            backend_pb2.DatabaseRequest(operation=operation, request_id=request_id.get(), **fields),
            metadata=(("authorization", f"Bearer {_token}"),), timeout=timeout,
        )
    except grpc.RpcError as exc:
        raise Error("Go 資料庫服務無法回應或工作已逾時") from exc
    if result.error_code:
        exception = IntegrityError if result.error_code == "INTEGRITY_ERROR" else Error
        raise exception(result.error_message)
    return result


class Cursor:
    """將既有游標介面轉為 Go RPC；結果集在 Go 完整消耗後才傳回。"""

    def __init__(self, connection: Connection) -> None:
        """建立邏輯游標，不額外借用 SQL Server 連線。"""
        self.connection = connection
        self.description: list[tuple[str]] = []
        self.rowcount = -1
        self._rows: list[list[Any]] = []
        self._position = 0

    def execute(self, query: str | Statement, *parameters: Any) -> Cursor:
        """使用獨立參數送出固定 SQL，不在 Python 插入使用者輸入。"""
        if self.connection.closed:
            raise Error("資料庫連線已關閉")
        values = parameters[0] if len(parameters) == 1 and isinstance(parameters[0], (tuple, list)) else parameters
        query_name = query.name if isinstance(query, Statement) else query
        options = query.options if isinstance(query, Statement) else ()
        result = _call("query", session_id=self.connection.session_id, query=query_name,
                       options_json=json.dumps(options, ensure_ascii=False).encode("utf-8"),
                       parameters_json=json.dumps(values, default=_encode, ensure_ascii=False).encode("utf-8"))
        self.description = [(column,) for column in result.columns]
        self.rowcount = result.row_count
        self._rows = json.loads(result.rows_json or b"[]", object_hook=_decode)
        self._position = 0
        return self

    def executemany(self, query: str, parameters: Any) -> Cursor:
        """沿用同一 Go 交易批次執行，任何失敗交由呼叫端回復整個交易。"""
        total = 0
        for values in parameters:
            self.execute(query, values)
            total += max(0, self.rowcount)
        self.rowcount = total
        return self

    def fetchone(self) -> list[Any] | None:
        """傳回下一筆資料；結果耗盡時傳回 None。"""
        if self._position >= len(self._rows):
            return None
        value = self._rows[self._position]
        self._position += 1
        return value

    def fetchall(self) -> list[list[Any]]:
        """傳回尚未讀取的所有資料。"""
        values = self._rows[self._position:]
        self._position = len(self._rows)
        return values


class Connection:
    """保存 Go 核發的連線代碼；實體連線與交易均留在 Go。"""

    def __init__(self, read_only: bool, autocommit: bool) -> None:
        """於目前請求範圍中取得連線。"""
        self.session_id = _call("open", read_only=read_only, autocommit=autocommit).session_id
        self.closed = False

    def cursor(self) -> Cursor:
        """建立游標；拒絕重用已歸還的連線。"""
        if self.closed:
            raise Error("資料庫連線已關閉")
        return Cursor(self)

    def commit(self) -> None:
        """明確提交目前交易。"""
        _call("commit", session_id=self.session_id)

    def rollback(self) -> None:
        """回復目前交易。"""
        _call("rollback", session_id=self.session_id)

    def close(self) -> None:
        """歸還連線，Go 會先回復尚未提交的交易。"""
        if not self.closed:
            self.closed = True
            _call("close", session_id=self.session_id)

    def __enter__(self) -> Connection:
        """讓非 HTTP 工作也能使用明確的連線範圍。"""
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        """釋放連線；不隱含提交尚未完成的工作。"""
        self.close()


def connect(read_only: bool = True, autocommit: bool = True) -> Connection:
    """建立相容的邏輯連線。"""
    return Connection(read_only, autocommit)


def admin_credentials() -> tuple[str, str]:
    """僅在內部驗證流程向 Go 取得管理員憑證。"""
    result = json.loads(_call("credentials").rows_json)
    return result[0][0], result[0][1]
