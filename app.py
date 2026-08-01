"""福祿貝爾幼稚園營運中心後端與唯讀 JSON API。"""

from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import data


ROOT = Path(__file__).parent.resolve()
PAGES = {"/": "index.html", "/index.html": "index.html", "/home.html": "home.html", "/sales.html": "sales.html", "/mis.html": "mis.html", "/exam.html": "exam.html", "/game.html": "game.html", "/style.css": "style.css"}


class Handler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        routes = {
            "/api/health": data.health,
            "/api/dashboard": data.dashboard,
            "/api/knowledge": data.knowledge,
            "/api/operations": data.operations_process,
            "/api/departments": data.departments,
            "/api/branches": data.branches,
            "/api/roles": data.permission_profiles,
            "/api/questions": data.questions,
            "/api/catalog": data.table_catalog,
        }
        if parsed.path == "/api/table":
            query = parse_qs(parsed.query)
            table_name = query.get("name", [""])[0]
            try:
                page = int(query.get("page", ["1"])[0])
                page_size = int(query.get("page_size", ["20"])[0])
                return self.send_json({"data": data.table_data(table_name, page, page_size)})
            except ValueError as exc:
                return self.send_json({"error": str(exc), "code": "INVALID_REQUEST"}, 400)
            except data.DatabaseUnavailable as exc:
                return self.send_json({"error": str(exc), "code": "DATABASE_UNAVAILABLE"}, 503)
        if parsed.path in routes:
            try:
                return self.send_json({"data": routes[parsed.path]()})
            except data.DatabaseUnavailable as exc:
                return self.send_json({"error": str(exc), "code": "DATABASE_UNAVAILABLE"}, 503)
        if parsed.path in PAGES:
            return self.send_file(ROOT / PAGES[parsed.path])
        if parsed.path.startswith("/static/"):
            target = (ROOT / parsed.path.lstrip("/")).resolve()
            if ROOT in target.parents:
                return self.send_file(target)
        self.send_not_found()

    def do_POST(self):
        self.send_json({"error": "此版本使用唯讀資料庫連線，未開放寫入 API。"}, 405)

    def send_file(self, path: Path):
        if not path.is_file():
            return self.send_not_found()
        body = path.read_bytes()
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if mime.startswith("text/") or mime in {"application/javascript", "application/json"}:
            mime += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_not_found(self):
        """回傳 UTF-8 的 404 頁面，避免中文 HTTP reason 觸發 Latin-1 錯誤。"""
        body = (
            "<!doctype html><html lang=\"zh-TW\"><meta charset=\"utf-8\">"
            "<title>找不到頁面</title><body><h1>404</h1>"
            "<p>找不到指定的頁面。</p><a href=\"/\">返回營運總覽</a></body></html>"
        ).encode("utf-8")
        self.send_response(404, "Not Found")
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print("福祿貝爾營運中心：http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n伺服器已停止")
