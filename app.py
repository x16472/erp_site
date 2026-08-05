"""官方網站、員工入口與受保護的 MIS 管理 API。"""

from __future__ import annotations

import argparse
import html
import hmac
import json
import mimetypes
import os
import re
import secrets
import threading
import time
import socket
from datetime import date
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
from typing import Any

import data
import doc as training_documents
import input as user_input

ROOT = Path(__file__).parent.resolve()
STATIC_ROOT = (ROOT / "static").resolve()
PAGES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/home.html": "home.html",
    "/sales.html": "sales.html",
    "/mis.html": "mis.html",
    "/exam.html": "exam.html",
    "/game.html": "game.html",
    "/staff.html": "staff.html",
    "/style.css": "style.css",
    "/employee-login.html": "employee-login.html",
}
SESSION_TTL = 8 * 60 * 60
SESSIONS: dict[str, dict] = {}
EMPLOYEE_SESSIONS: dict[str, dict] = {}
LOGIN_ATTEMPTS: dict[str, list[float]] = {}
EMPLOYEE_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
SESSION_LOCK = threading.Lock()
YOUTUBE_CACHE: dict[str, dict[str, str]] = {}
YOUTUBE_CACHE_LOCK = threading.Lock()
MAX_STAFF_REQUEST_SIZE = 7 * 1024 * 1024


class ExternalServiceUnavailable(RuntimeError):
    """外部服務暫時無法回應。"""


def youtube_metadata(item: dict[str, str]) -> dict[str, str]:
    video_id = item["video_id"]
    with YOUTUBE_CACHE_LOCK:
        cached = YOUTUBE_CACHE.get(video_id)
    if cached:
        return cached
    query = urlencode({"url": item["watch_url"], "format": "json"})
    endpoint = "https://www.youtube.com/oembed?" + query
    request = Request(endpoint, headers={"User-Agent": "FrobelOperations/1.0"})
    try:
        with urlopen(request, timeout=6) as response:
            payload = json.loads(response.read(65536).decode("utf-8"))
    except HTTPError as exc:
        if exc.code in {400, 401, 403, 404}:
            raise user_input.InputError("找不到影片，或影片不允許嵌入播放") from exc
        raise ExternalServiceUnavailable("YouTube 目前無法回應，請稍後再試") from exc
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise ExternalServiceUnavailable("YouTube 連線逾時，請稍後再試") from exc
    title = html.unescape(str(payload.get("title", "")).strip())
    if not title:
        raise ExternalServiceUnavailable("YouTube 未回傳影片標題")
    result = {**item, "title": title}
    with YOUTUBE_CACHE_LOCK:
        YOUTUBE_CACHE[video_id] = result
    return result


def save_staff_photo(employee_id: str, photo: dict[str, Any]) -> str:
    staff_root = STATIC_ROOT / "staff"
    staff_root.mkdir(parents=True, exist_ok=True)
    file_name = f"{employee_id}.{photo['extension']}"
    target = (staff_root / file_name).resolve()
    if staff_root not in target.parents:
        raise user_input.InputError("員工照片路徑不正確")
    temporary = staff_root / f".{employee_id}.{secrets.token_hex(6)}.tmp"
    try:
        temporary.write_bytes(photo["content"])
        os.replace(temporary, target)
        for extension in ("jpg", "png", "webp"):
            old = staff_root / f"{employee_id}.{extension}"
            if old != target and old.is_file():
                old.unlink()
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise user_input.InputError("員工照片儲存失敗") from exc
    return file_name


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

    def read_json(self, maximum_size: int = 32768) -> dict:
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise user_input.InputError("請求內容大小不正確") from exc
        if size < 1 or size > maximum_size:
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

    def employee_session(self) -> dict | None:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        token = cookie.get("frobel_employee")
        if not token:
            return None
        now = time.time()
        with SESSION_LOCK:
            session = EMPLOYEE_SESSIONS.get(token.value)
            if not session or session["expires"] <= now:
                EMPLOYEE_SESSIONS.pop(token.value, None)
                return None
            session["expires"] = now + SESSION_TTL
            return session

    def require_admin(self, employee_session: dict | None = None) -> dict | None:
        session = self.session()
        if not session or (employee_session and session.get("employee_id") != employee_session["employee_id"]):
            self.send_json({"error": "請先登入 MIS 管理區。", "code": "AUTH_REQUIRED"}, 401)
            return None
        return session

    def require_employee(self) -> dict | None:
        session = self.employee_session()
        if not session:
            self.send_json({"error": "請先輸入有效的員工編號。", "code": "EMPLOYEE_AUTH_REQUIRED"}, 401)
            return None
        try:
            session["employee"] = data.employee_identity(session["employee_id"])
            session["attendance"] = data.attendance_status(session["employee_id"])
        except ValueError:
            with SESSION_LOCK:
                EMPLOYEE_SESSIONS.pop(session["token"], None)
            self.send_json({"error": "員工編號不存在或已停用，請重新登入。", "code": "EMPLOYEE_AUTH_REQUIRED"}, 401)
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
            "/api/time": data.server_time,
        }
        if parsed.path in public_routes:
            try:
                return self.send_json({"data": public_routes[parsed.path]()})
            except data.DatabaseUnavailable as exc:
                return self.send_json({"error": str(exc), "code": "DATABASE_UNAVAILABLE"}, 503)

        if parsed.path == "/api/staff/public":
            try:
                department = parse_qs(parsed.query).get("department", [""])[0].strip()
                if len(department) > 50:
                    raise ValueError("部門名稱過長")
                return self.send_json({"data": data.public_staff(department)})
            except ValueError as exc:
                return self.send_json({"error": str(exc), "code": "INVALID_REQUEST"}, 400)
            except data.DatabaseUnavailable as exc:
                return self.send_json({"error": str(exc), "code": "DATABASE_UNAVAILABLE"}, 503)

        if parsed.path == "/api/staff/departments":
            try:
                return self.send_json({"data": data.public_staff_departments()})
            except data.DatabaseUnavailable as exc:
                return self.send_json({"error": str(exc), "code": "DATABASE_UNAVAILABLE"}, 503)

        if parsed.path == "/api/employee/session":
            session = self.employee_session()
            if not session:
                return self.send_json({"data": {"authenticated": False, "employee": None, "csrf": None}})
            try:
                session["employee"] = data.employee_identity(session["employee_id"])
                session["attendance"] = data.attendance_status(session["employee_id"])
                return self.send_json({"data": {"authenticated": True, "employee": session["employee"], "attendance": session["attendance"], "access_mode": session.get("access_mode"), "csrf": session["csrf"]}})
            except ValueError:
                with SESSION_LOCK:
                    EMPLOYEE_SESSIONS.pop(session["token"], None)
                return self.send_json({"data": {"authenticated": False, "employee": None, "csrf": None}})
            except data.DatabaseUnavailable as exc:
                return self.send_json({"error": str(exc), "code": "DATABASE_UNAVAILABLE"}, 503)

        employee_routes = {
            "/api/dashboard": data.dashboard,
            "/api/knowledge": data.knowledge,
            "/api/operations": data.operations_process,
            "/api/departments": data.departments,
            "/api/branches": data.branches,
            "/api/roles": data.permission_profiles,
            "/api/questions": data.questions,
            "/api/staff/attendance-options": data.attendance_staff_options,
            "/api/training": data.training_catalog,
        }
        if parsed.path in employee_routes:
            try:
                if not self.require_employee():
                    return
                return self.send_json({"data": employee_routes[parsed.path]()})
            except ValueError as exc:
                return self.send_json({"error": str(exc), "code": "INVALID_REQUEST"}, 400)
            except data.DatabaseUnavailable as exc:
                return self.send_json({"error": str(exc), "code": "DATABASE_UNAVAILABLE"}, 503)

        if parsed.path == "/api/training/document":
            try:
                if not self.require_employee():
                    return
                document_id = int(parse_qs(parsed.query).get("id", ["0"])[0])
                return self.send_json({"data": data.training_document(document_id)})
            except ValueError as exc:
                return self.send_json({"error": str(exc), "code": "INVALID_REQUEST"}, 400)
            except data.DatabaseUnavailable as exc:
                return self.send_json({"error": str(exc), "code": "DATABASE_UNAVAILABLE"}, 503)

        if parsed.path == "/api/admin/session":
            try:
                employee_session = self.require_employee()
                if not employee_session:
                    return
                session = self.session()
                if session and session.get("employee_id") != employee_session["employee_id"]:
                    session = None
                return self.send_json({"data": {"authenticated": bool(session), "username": session["username"] if session else None, "csrf": session["csrf"] if session else None}})
            except data.DatabaseUnavailable as exc:
                return self.send_json({"error": str(exc), "code": "DATABASE_UNAVAILABLE"}, 503)

        if parsed.path.startswith("/api/admin/"):
            try:
                employee_session = self.require_employee()
                if not employee_session:
                    return
                session = self.require_admin(employee_session)
                if not session:
                    return
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
                if parsed.path == "/api/admin/departments":
                    return self.send_json({"data": data.admin_departments()})
                if parsed.path == "/api/admin/attendance":
                    day = query.get("date", [""])[0]
                    if day:
                        date.fromisoformat(day)
                    return self.send_json({"data": data.attendance_records(day, query.get("employee_id", [""])[0].upper())})
                if parsed.path == "/api/admin/training/documents":
                    return self.send_json({"data": data.training_documents_admin()})
                if parsed.path == "/api/admin/training/questions":
                    return self.send_json({"data": data.training_questions_admin()})
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
            if parsed.path == "/api/employee/login":
                return self.employee_login()
            if parsed.path == "/api/employee/logout":
                return self.employee_logout()
            if parsed.path == "/api/youtube/resolve":
                if not self.require_employee():
                    return
                item = user_input.validate_youtube(self.read_json())
                return self.send_json({"data": youtube_metadata(item)})
            if parsed.path == "/api/operations/submit":
                session = self.require_employee()
                if not session or not self.require_csrf(session):
                    return
                item = user_input.validate_operation(self.read_json())
                return self.send_json({"data": data.add_operation(item, session["employee_id"])}, 201)
            if parsed.path == "/api/attendance/clock":
                session = self.require_employee()
                if not session or not self.require_csrf(session):
                    return
                payload = self.read_json()
                payload["employee_id"] = session["employee_id"]
                item = user_input.validate_attendance(payload)
                attendance = data.clock_attendance(item, self.client_address[0])
                session["attendance"] = attendance
                return self.send_json({"data": attendance}, 201)
            if parsed.path == "/api/admin/login":
                employee_session = self.require_employee()
                if not employee_session:
                    return
                return self.admin_login(employee_session)
            if parsed.path == "/api/admin/logout":
                if not self.require_employee():
                    return
                return self.admin_logout()
            if parsed.path.startswith("/api/admin/"):
                employee_session = self.require_employee()
                if not employee_session:
                    return
                session = self.require_admin(employee_session)
                if not session or not self.require_csrf(session):
                    return
                if parsed.path == "/api/admin/settings":
                    settings = user_input.validate_site_settings(self.read_json())
                    return self.send_json({"data": data.save_site_settings(settings, session["username"])})
                if parsed.path == "/api/admin/staff":
                    payload = self.read_json(MAX_STAFF_REQUEST_SIZE)
                    staff = user_input.validate_staff(payload)
                    photo = user_input.validate_staff_photo(payload.get("photo"))
                    photo_file = save_staff_photo(staff["employee_id"], photo) if photo else None
                    return self.send_json({"data": data.save_staff(staff, session["username"], photo_file)})
                if parsed.path == "/api/admin/departments":
                    department = user_input.validate_department(self.read_json())
                    return self.send_json({"data": data.save_department(department, session["username"])})
                if parsed.path == "/api/admin/training/sync":
                    documents = training_documents.sync_training_library(ensure_schema=False)
                    return self.send_json({"data": {"documents": documents}})
                if parsed.path == "/api/admin/training/document":
                    item = user_input.validate_training_document_state(self.read_json())
                    return self.send_json({"data": data.set_training_document_state(item["id"], item["is_active"])})
                if parsed.path == "/api/admin/training/question":
                    item = user_input.validate_training_question(self.read_json())
                    return self.send_json({"data": data.save_training_question(item)})
        except user_input.InputError as exc:
            return self.send_json({"error": str(exc), "code": "INVALID_INPUT"}, 400)
        except ValueError as exc:
            return self.send_json({"error": str(exc), "code": "INVALID_REQUEST"}, 400)
        except (data.DatabaseUnavailable, training_documents.DocumentImportError) as exc:
            return self.send_json({"error": str(exc), "code": "SERVICE_UNAVAILABLE"}, 503)
        except ExternalServiceUnavailable as exc:
            return self.send_json({"error": str(exc), "code": "EXTERNAL_SERVICE_UNAVAILABLE"}, 503)
        self.send_json({"error": "此路徑不接受寫入。"}, 405)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        allowed_paths = {"/api/admin/staff", "/api/admin/departments", "/api/admin/training/question"}
        if parsed.path not in allowed_paths:
            return self.send_json({"error": "此路徑不接受刪除。"}, 405)
        try:
            employee_session = self.require_employee()
            if not employee_session:
                return
        except data.DatabaseUnavailable as exc:
            return self.send_json({"error": str(exc), "code": "DATABASE_UNAVAILABLE"}, 503)
        session = self.require_admin(employee_session)
        if not session or not self.require_csrf(session):
            return
        try:
            payload = self.read_json()
            if parsed.path == "/api/admin/staff":
                employee_id = str(payload.get("employee_id", "")).strip().upper()
                if not re.fullmatch(r"[A-Z0-9_-]{1,20}", employee_id):
                    raise user_input.InputError("員工編號格式不正確")
                result = data.deactivate_staff(employee_id, session["username"])
            elif parsed.path == "/api/admin/departments":
                try:
                    department_id = int(payload.get("id"))
                except (TypeError, ValueError) as exc:
                    raise user_input.InputError("部門編號不正確") from exc
                result = data.deactivate_department(department_id, session["username"])
            else:
                try:
                    question_id = int(payload.get("id"))
                except (TypeError, ValueError) as exc:
                    raise user_input.InputError("題目編號不正確") from exc
                result = data.deactivate_training_question(question_id)
            return self.send_json({"data": result})
        except user_input.InputError as exc:
            return self.send_json({"error": str(exc), "code": "INVALID_INPUT"}, 400)
        except ValueError as exc:
            return self.send_json({"error": str(exc), "code": "INVALID_REQUEST"}, 400)
        except data.DatabaseUnavailable as exc:
            return self.send_json({"error": str(exc), "code": "DATABASE_UNAVAILABLE"}, 503)

    def admin_login(self, employee_session: dict) -> None:
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
            SESSIONS[token] = {"username": username, "employee_id": employee_session["employee_id"], "csrf": csrf, "expires": now + SESSION_TTL}
        cookie = f"frobel_admin={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_TTL}"
        return self.send_json({"data": {"authenticated": True, "username": username, "csrf": csrf}}, headers={"Set-Cookie": cookie})

    def employee_login(self) -> None:
        now = time.time()
        client = self.client_address[0]
        with SESSION_LOCK:
            attempts = [stamp for stamp in EMPLOYEE_LOGIN_ATTEMPTS.get(client, []) if now - stamp < 300]
        if len(attempts) >= 10:
            return self.send_json({"error": "驗證失敗次數過多，請五分鐘後再試。", "code": "RATE_LIMITED"}, 429)
        payload = self.read_json()
        item = user_input.validate_employee_access(payload)
        try:
            employee = data.employee_identity(item["employee_id"])
        except ValueError:
            with SESSION_LOCK:
                attempts.append(now)
                EMPLOYEE_LOGIN_ATTEMPTS[client] = attempts
            return self.send_json({"error": "員工編號不存在或已停用。", "code": "INVALID_EMPLOYEE"}, 401)
        attendance = (
            data.clock_attendance({"employee_id": item["employee_id"], "action": "CLOCK_IN"}, self.client_address[0])
            if item["mode"] == "CLOCK_IN"
            else data.attendance_status(item["employee_id"])
        )
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        session = {
            "token": token,
            "employee_id": employee["employee_id"],
            "employee": employee,
            "attendance": attendance,
            "access_mode": item["mode"],
            "csrf": csrf,
            "expires": now + SESSION_TTL,
        }
        with SESSION_LOCK:
            EMPLOYEE_LOGIN_ATTEMPTS.pop(client, None)
            EMPLOYEE_SESSIONS[token] = session
        cookie = f"frobel_employee={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_TTL}"
        return self.send_json({"data": {"authenticated": True, "employee": employee, "attendance": attendance, "access_mode": item["mode"], "csrf": csrf}}, headers={"Set-Cookie": cookie})

    def employee_logout(self) -> None:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        token = cookie.get("frobel_employee")
        admin_token = cookie.get("frobel_admin")
        if token:
            with SESSION_LOCK:
                EMPLOYEE_SESSIONS.pop(token.value, None)
                if admin_token:
                    SESSIONS.pop(admin_token.value, None)
        return self.send_json({"data": {"authenticated": False}}, headers={"Set-Cookie": "frobel_employee=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"})

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
    parser.add_argument("--host", default=os.environ.get("FROBEL_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("FROBEL_PORT", "80")))
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
    if args.host == "0.0.0.0":
        try:
            addresses = sorted({item[4][0] for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)})
        except OSError:
            addresses = []
        for address in addresses:
            if not address.startswith("127."):
                print(f"內網存取：http://{address}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n伺服器已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
