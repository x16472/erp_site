"""福祿貝爾官方網站、員工入口與受保護的 MIS 管理 API。"""

from __future__ import annotations

import hmac
import json
import mimetypes
import secrets
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import data
import input as user_input

ROOT = Path(__file__).parent.resolve()
STATIC_ROOT = (ROOT / "static").resolve()
PAGES = {
    "/": "index.html", "/index.html": "index.html", "/home.html": "home.html",
    "/sales.html": "sales.html", "/mis.html": "mis.html", "/exam.html": "exam.html",
    "/game.html": "game.html", "/style.css": "style.css",
}

SESSION_TTL = 8 * 60 * 60
SESSIONS: dict[str, dict] = {}
LOGIN_ATTEMPTS: dict[str, list[float]] = {}
SESSION_LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200, headers: dict[str, str] | None = None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise user_input.InputError("請求內容大小不正確") from exc
        if size < 1 or size > 32768:
            raise user_input.InputError("請求內容大小不正確")
        try:
            payload = json.loads(self.rfile.read(size))
        except json.JSONDecodeError as exc:
            raise user_input.InputError("JSON 格式不正確") from exc
        if not isinstance(payload, dict):
            raise user_input.InputError("請求內容必須是物件")
        return payload

    def session(self) -> dict | None:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        token = cookie.get("frobel_admin")
        if not token:
            return None
        now = time.time()
        with SESSION_LOCK:
            session = SESSIONS.get(token.value)
            if not session or session["expires"] <= now:
                SESSIONS.pop(token.value, None)
                return None
            session["expires"] = now + SESSION_TTL
            return session

    def require_admin(self) -> dict | None:
        session = self.session()
        if not session:
            self.send_json({"error": "請先登入 MIS 管理區。", "code": "AUTH_REQUIRED"}, 401)
            return None
        return session

    def require_csrf(self, session: dict) -> bool:
        supplied = self.headers.get("X-CSRF-Token", "")
        if not hmac.compare_digest(supplied, session["csrf"]):
            self.send_json({"error": "安全驗證失敗，請重新登入。", "code": "CSRF_FAILED"}, 403)
            return False
        return True

    def do_GET(self):
        parsed = urlparse(self.path)
        public_routes = {
            "/api/health": data.health,
            "/api/public": data.public_overview,
            "/api/dashboard": data.dashboard,
            "/api/knowledge": data.knowledge,
            "/api/operations": data.operations_process,
            "/api/departments": data.departments,
            "/api/branches": data.branches,
            "/api/roles": data.permission_profiles,
            "/api/questions": data.questions,
        }
        if parsed.path in public_routes:
            try:
                return self.send_json({"data": public_routes[parsed.path]()})
            except data.DatabaseUnavailable as exc:
                return self.send_json({"error": str(exc), "code": "DATABASE_UNAVAILABLE"}, 503)

        if parsed.path == "/api/admin/session":
            session = self.session()
            return self.send_json({"data": {"authenticated": bool(session), "username": session["username"] if session else None, "csrf": session["csrf"] if session else None}})

        if parsed.path.startswith("/api/admin/"):
            session = self.require_admin()
            if not session:
                return
            try:
                if parsed.path == "/api/admin/catalog":
                    return self.send_json({"data": data.table_catalog()})
                if parsed.path == "/api/admin/table":
                    query = parse_qs(parsed.query)
                    result = data.table_data(query.get("name", [""])[0], int(query.get("page", ["1"])[0]), int(query.get("page_size", ["20"])[0]))
                    return self.send_json({"data": result})
                if parsed.path == "/api/admin/settings":
                    return self.send_json({"data": data.site_settings()})
                if parsed.path == "/api/admin/submissions":
                    return self.send_json({"data": user_input.list_operations()})
            except ValueError as exc:
                return self.send_json({"error": str(exc), "code": "INVALID_REQUEST"}, 400)
            except data.DatabaseUnavailable as exc:
                return self.send_json({"error": str(exc), "code": "DATABASE_UNAVAILABLE"}, 503)
            return self.send_not_found()

        if parsed.path in PAGES:
            return self.send_file(ROOT / PAGES[parsed.path])
        if parsed.path.startswith("/static/"):
            target = (ROOT / parsed.path.lstrip("/")).resolve()
            if STATIC_ROOT in target.parents:
                return self.send_file(target)
        self.send_not_found()

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/operations/submit":
                return self.send_json({"data": user_input.add_operation(self.read_json())}, 201)
            if parsed.path == "/api/admin/login":
                return self.admin_login()
            if parsed.path == "/api/admin/logout":
                return self.admin_logout()
            if parsed.path == "/api/admin/settings":
                session = self.require_admin()
                if not session or not self.require_csrf(session):
                    return
                settings = user_input.validate_site_settings(self.read_json())
                return self.send_json({"data": data.save_site_settings(settings, session["username"])})
        except user_input.InputError as exc:
            return self.send_json({"error": str(exc), "code": "INVALID_INPUT"}, 400)
        except data.DatabaseUnavailable as exc:
            return self.send_json({"error": str(exc), "code": "DATABASE_UNAVAILABLE"}, 503)
        self.send_json({"error": "此路徑不接受寫入。"}, 405)

    def admin_login(self):
        now = time.time()
        client = self.client_address[0]
        attempts = [stamp for stamp in LOGIN_ATTEMPTS.get(client, []) if now - stamp < 300]
        if len(attempts) >= 5:
            return self.send_json({"error": "登入失敗次數過多，請五分鐘後再試。", "code": "RATE_LIMITED"}, 429)
        payload = self.read_json()
        expected_user, expected_password = data.admin_credentials()
        username = str(payload.get("username", ""))
        password = str(payload.get("password", ""))
        if not (hmac.compare_digest(username, expected_user) and hmac.compare_digest(password, expected_password)):
            attempts.append(now)
            LOGIN_ATTEMPTS[client] = attempts
            return self.send_json({"error": "帳號或密碼不正確。", "code": "INVALID_CREDENTIALS"}, 401)
        LOGIN_ATTEMPTS.pop(client, None)
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        with SESSION_LOCK:
            SESSIONS[token] = {"username": username, "csrf": csrf, "expires": now + SESSION_TTL}
        cookie = f"frobel_admin={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_TTL}"
        return self.send_json({"data": {"authenticated": True, "username": username, "csrf": csrf}}, headers={"Set-Cookie": cookie})

    def admin_logout(self):
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        token = cookie.get("frobel_admin")
        if token:
            with SESSION_LOCK:
                SESSIONS.pop(token.value, None)
        return self.send_json({"data": {"authenticated": False}}, headers={"Set-Cookie": "frobel_admin=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"})

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
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.end_headers()
        self.wfile.write(body)

    def send_not_found(self):
        body = ("<!doctype html><html lang=\"zh-TW\"><meta charset=\"utf-8\"><title>找不到頁面</title>"
                "<body><h1>404</h1><p>找不到指定的頁面。</p><a href=\"/\">返回福祿貝爾首頁</a></body></html>").encode("utf-8")
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
