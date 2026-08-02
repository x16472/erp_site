"""福祿貝爾官方網站、員工入口與受保護的 MIS 管理 API。"""

from __future__ import annotations

import argparse
import hmac
import json
import mimetypes
import os
import re
import secrets
import threading
import time
from datetime import date
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from typing import Any

import data
import doc as training_documents
import input as user_input

ROOT = Path(__file__).parent.resolve()
STATIC_ROOT = (ROOT / "static").resolve()
PAGES = {
    "/": "index.html", "/index.html": "index.html", "/home.html": "home.html",
    "/sales.html": "sales.html", "/mis.html": "mis.html", "/exam.html": "exam.html",
    "/game.html": "game.html", "/staff.html": "staff.html", "/style.css": "style.css",
}
SESSION_TTL = 8 * 60 * 60
SESSIONS: dict[str, dict] = {}
LOGIN_ATTEMPTS: dict[str, list[float]] = {}
SESSION_LOCK = threading.Lock()


class ApplicationServer(ThreadingHTTPServer):
    """讓各請求獨立處理，結束服務時不等待閒置中的連線執行緒。"""

    daemon_threads = True
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    server_version = "FrobelOperations/1.0"

    def security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")

    def send_json(
        self,
        payload: Any,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.security_headers()
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
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
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

    def do_GET(self) -> None:
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
            "/api/staff/public": data.public_staff,
            "/api/staff/attendance-options": data.attendance_staff_options,
            "/api/training": data.training_catalog,
        }
        if parsed.path in public_routes:
            try:
                return self.send_json({"data": public_routes[parsed.path]()})
            except data.DatabaseUnavailable as exc:
                return self.send_json({"error": str(exc), "code": "DATABASE_UNAVAILABLE"}, 503)

        if parsed.path == "/api/training/document":
            try:
                document_id = int(parse_qs(parsed.query).get("id", ["0"])[0])
                return self.send_json({"data": data.training_document(document_id)})
            except ValueError as exc:
                return self.send_json({"error": str(exc), "code": "INVALID_REQUEST"}, 400)
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
                query = parse_qs(parsed.query)
                if parsed.path == "/api/admin/catalog":
                    return self.send_json({"data": data.table_catalog()})
                if parsed.path == "/api/admin/table":
                    result = data.table_data(query.get("name", [""])[0], int(query.get("page", ["1"])[0]), int(query.get("page_size", ["20"])[0]))
                    return self.send_json({"data": result})
                if parsed.path == "/api/admin/settings":
                    return self.send_json({"data": data.site_settings()})
                if parsed.path == "/api/admin/submissions":
                    return self.send_json({"data": data.operation_submissions()})
                if parsed.path == "/api/admin/staff":
                    return self.send_json({"data": data.staff_records()})
                if parsed.path == "/api/admin/attendance":
                    day = query.get("date", [""])[0]
                    if day:
                        date.fromisoformat(day)
                    return self.send_json({"data": data.attendance_records(day, query.get("employee_id", [""])[0].upper())})
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

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/operations/submit":
                item = user_input.validate_operation(self.read_json())
                return self.send_json({"data": data.add_operation(item)}, 201)
            if parsed.path == "/api/attendance/clock":
                item = user_input.validate_attendance(self.read_json())
                return self.send_json({"data": data.clock_attendance(item, self.client_address[0])}, 201)
            if parsed.path == "/api/admin/login":
                return self.admin_login()
            if parsed.path == "/api/admin/logout":
                return self.admin_logout()
            if parsed.path.startswith("/api/admin/"):
                session = self.require_admin()
                if not session or not self.require_csrf(session):
                    return
                if parsed.path == "/api/admin/settings":
                    settings = user_input.validate_site_settings(self.read_json())
                    return self.send_json({"data": data.save_site_settings(settings, session["username"])})
                if parsed.path == "/api/admin/staff":
                    staff = user_input.validate_staff(self.read_json())
                    return self.send_json({"data": data.save_staff(staff, session["username"])})
                if parsed.path == "/api/admin/training/sync":
                    documents = training_documents.sync_training_library(ensure_schema=False)
                    return self.send_json({"data": {"documents": documents}})
        except user_input.InputError as exc:
            return self.send_json({"error": str(exc), "code": "INVALID_INPUT"}, 400)
        except ValueError as exc:
            return self.send_json({"error": str(exc), "code": "INVALID_REQUEST"}, 400)
        except (data.DatabaseUnavailable, training_documents.DocumentImportError) as exc:
            return self.send_json({"error": str(exc), "code": "SERVICE_UNAVAILABLE"}, 503)
        self.send_json({"error": "此路徑不接受寫入。"}, 405)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/admin/staff":
            return self.send_json({"error": "此路徑不接受刪除。"}, 405)
        session = self.require_admin()
        if not session or not self.require_csrf(session):
            return
        try:
            payload = self.read_json()
            employee_id = str(payload.get("employee_id", "")).strip().upper()
            if not re.fullmatch(r"[A-Z0-9_-]{1,20}", employee_id):
                raise user_input.InputError("員工編號格式不正確")
            return self.send_json({"data": data.deactivate_staff(employee_id, session["username"])})
        except user_input.InputError as exc:
            return self.send_json({"error": str(exc), "code": "INVALID_INPUT"}, 400)
        except ValueError as exc:
            return self.send_json({"error": str(exc), "code": "INVALID_REQUEST"}, 400)
        except data.DatabaseUnavailable as exc:
            return self.send_json({"error": str(exc), "code": "DATABASE_UNAVAILABLE"}, 503)

    def admin_login(self) -> None:
        now = time.time()
        client = self.client_address[0]
        with SESSION_LOCK:
            attempts = [stamp for stamp in LOGIN_ATTEMPTS.get(client, []) if now - stamp < 300]
        if len(attempts) >= 5:
            return self.send_json({"error": "登入失敗次數過多，請五分鐘後再試。", "code": "RATE_LIMITED"}, 429)
        payload = self.read_json()
        expected_user, expected_password = data.admin_credentials()
        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", ""))
        if not (hmac.compare_digest(username, expected_user) and hmac.compare_digest(password, expected_password)):
            with SESSION_LOCK:
                attempts.append(now)
                LOGIN_ATTEMPTS[client] = attempts
            return self.send_json({"error": "帳號或密碼不正確。", "code": "INVALID_CREDENTIALS"}, 401)
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        with SESSION_LOCK:
            LOGIN_ATTEMPTS.pop(client, None)
            SESSIONS[token] = {"username": username, "csrf": csrf, "expires": now + SESSION_TTL}
        cookie = f"frobel_admin={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_TTL}"
        return self.send_json({"data": {"authenticated": True, "username": username, "csrf": csrf}}, headers={"Set-Cookie": cookie})

    def admin_logout(self) -> None:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        token = cookie.get("frobel_admin")
        if token:
            with SESSION_LOCK:
                SESSIONS.pop(token.value, None)
        return self.send_json({"data": {"authenticated": False}}, headers={"Set-Cookie": "frobel_admin=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"})

    def send_file(self, path: Path) -> None:
        if not path.is_file():
            return self.send_not_found()
        body = path.read_bytes()
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if mime.startswith("text/") or mime in {"application/javascript", "application/json"}:
            mime += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.security_headers()
        self.end_headers()
        self.wfile.write(body)

    def send_not_found(self) -> None:
        body = ("<!doctype html><html lang=\"zh-TW\"><meta charset=\"utf-8\"><title>找不到頁面</title>"
                "<body><h1>404</h1><p>找不到指定的頁面。</p><a href=\"/\">返回福祿貝爾首頁</a></body></html>").encode("utf-8")
        self.send_response(404, "Not Found")
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.security_headers()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="啟動福祿貝爾營運中心")
    parser.add_argument("--host", default=os.environ.get("FROBEL_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("FROBEL_PORT", "8000")))
    parser.add_argument("--skip-doc-sync", action="store_true", help="略過啟動時的教育文件同步")
    args = parser.parse_args()
    data.ensure_application_schema()
    if not args.skip_doc_sync:
        try:
            count = training_documents.sync_training_library(ensure_schema=False)
            print(f"教育訓練資料：已同步 {count} 份文件")
        except (training_documents.DocumentImportError, data.DatabaseUnavailable) as exc:
            print(f"教育訓練文件暫時無法同步：{exc}")
    server = ApplicationServer((args.host, args.port), Handler)
    print(f"福祿貝爾營運中心：http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n伺服器已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
