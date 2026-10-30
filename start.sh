#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$PROJECT_ROOT"
ERP_PYTHON="${ERP_PYTHON:-$PROJECT_ROOT/.venv/bin/python}"
ERP_BINARY="$PROJECT_ROOT/bin/erp-site"

if [[ ! -x "$ERP_BINARY" ]]; then
    printf '%s\n' '找不到 Go 主程式，請先執行 go build -o bin/erp-site ./backend/cmd/erp。' >&2
    exit 1
fi

# OMV 管理介面通常使用 80 埠，網站預設使用 8080。
export WEB_HOST="${WEB_HOST:-0.0.0.0}"
export WEB_PORT="${WEB_PORT:-8080}"
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONIOENCODING=utf-8

# 讓 systemd 直接追蹤 Go；Go 負責管理 Python gRPC 子程序。
exec "$ERP_BINARY" --root "$PROJECT_ROOT" --python "$ERP_PYTHON" "$@"
