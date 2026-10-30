"""從共用契約產生 Go 與 Python gRPC 程式碼。"""

from pathlib import Path
import subprocess
import sys


def main() -> None:
    """使用目前 Python 的 grpcio-tools 及 PATH 中的 Go protobuf 外掛。"""
    root = Path(__file__).resolve().parents[2]
    subprocess.run([
        sys.executable, "-m", "grpc_tools.protoc", "-I", "backend/proto",
        "--python_out=backend/src/erp/rpc", "--grpc_python_out=backend/src/erp/rpc",
        "--go_out=.", "--go_opt=module=erp-site",
        "--go-grpc_out=.", "--go-grpc_opt=module=erp-site", "backend/proto/backend.proto",
    ], cwd=root, check=True)
    stub = root / "backend/src/erp/rpc/backend_pb2_grpc.py"
    source = stub.read_text(encoding="utf-8")
    stub.write_text(source.replace("import backend_pb2 as", "from . import backend_pb2 as"), encoding="utf-8")


if __name__ == "__main__":
    main()
