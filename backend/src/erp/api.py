"""官方網站、員工入口與受保護的 後台管理 API。"""

from __future__ import annotations

import hmac
import html
import json
import os
import re
import secrets
import threading
import time
from datetime import date
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from . import domain as data, media
from . import doc as operations_manuals
from . import input as user_input
from .rpc import backend_pb2
from email.message import Message
from io import BytesIO

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PAGE_ROOT = (PROJECT_ROOT / "page").resolve()
STATIC_ROOT = (PAGE_ROOT / "static").resolve()
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


class Handler:
    """保留業務 API 行為，輸入輸出皆為 protobuf，沒有 HTTP 監聽器。"""

    def __init__(self, request: backend_pb2.HttpRequest) -> None:
        """從 Go 的請求建立單次業務處理器與回應緩衝區。"""
        self.path = request.target
        self.client_address = (request.remote_address, 0)
        self.headers = Message()
        for header in request.headers:
            self.headers[header.name] = header.value
        self.rfile = BytesIO(request.body)
        self.wfile = BytesIO()
        self.response = backend_pb2.HttpResponse(status=200)

    def send_response(self, status: int, message: str = "") -> None:
        """設定回應狀態；HTTP 狀態列由 Go 產生。"""
        self.response.status = status

    def send_header(self, name: str, value: str) -> None:
        """保留重複標頭，例如多個 Set-Cookie。"""
        self.response.headers.add(name=name, value=value)

    def end_headers(self) -> None:
        """protobuf 以結構保存標頭，不需要 HTTP 分隔字元。"""

    def security_headers(self) -> None:
        """將共用安全標頭附加至目前 HTTP 回應。"""
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")

    def send_json(
        self,
        payload: Any,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        """將資料序列化為 UTF-8 JSON，設定狀態碼及額外標頭。"""
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
        """讀取有大小限制的請求本文，回傳 JSON 物件。"""
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

    def _active_session(self, cookie_name: str, sessions: dict[str, dict]) -> dict | None:
        """依 Cookie 名稱取回有效工作階段，必要時清除逾期紀錄。"""
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        token = cookie.get(cookie_name)
        if not token:
            return None
        now = time.time()
        with SESSION_LOCK:
            session = sessions.get(token.value)
            if not session or session["expires"] <= now:
                sessions.pop(token.value, None)
                return None
            session["expires"] = now + SESSION_TTL
            return session

    def session(self) -> dict | None:
        """回傳目前管理員工作階段，未登入時回傳空值。"""
        return self._active_session("silver_shield_admin", SESSIONS)

    def employee_session(self) -> dict | None:
        """回傳目前員工工作階段，未登入時回傳空值。"""
        return self._active_session("silver_shield_employee", EMPLOYEE_SESSIONS)

    def require_admin(self, employee_session: dict | None = None) -> dict | None:
        """驗證管理員與員工工作階段綁定，失敗時輸出拒絕回應。"""
        session = self.session()
        if not session or (employee_session and session.get("employee_id") != employee_session["employee_id"]):
            self.send_json({"error": "請先登入 後台管理區。", "code": "AUTH_REQUIRED"}, 401)
            return None
        return session

    def require_employee(self) -> dict | None:
        """重新確認有效員工及出勤條件，回傳已授權工作階段。"""
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
        """以固定時間比對驗證工作階段的 CSRF Token。"""
        supplied = self.headers.get("X-CSRF-Token", "")
        if not hmac.compare_digest(supplied, session["csrf"]):
            self.send_json({"error": "安全驗證失敗，請重新登入。", "code": "CSRF_FAILED"}, 403)
            return False
        return True

    def do_GET(self) -> None:
        """依既有 GET 路由驗證權限並輸出資料。"""
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

        if parsed.path == "/api/operations/mine":
            try:
                session = self.require_employee()
                if not session:
                    return
                return self.send_json({"data": data.employee_operation_submissions(session["employee_id"])})
            except data.DatabaseUnavailable as exc:
                return self.send_json({"error": str(exc), "code": "DATABASE_UNAVAILABLE"}, 503)

        if parsed.path.startswith("/api/training/"):
            try:
                session = self.require_employee()
                if not session:
                    return
                query = parse_qs(parsed.query)
                if parsed.path == "/api/training/catalog":
                    result = data.training_catalog(session["employee_id"])
                elif parsed.path == "/api/training/session":
                    result = data.training_session(query.get("id", [""])[0], session["employee_id"])
                elif parsed.path == "/api/training/wrong":
                    result = data.training_wrong_questions(session["employee_id"])
                elif parsed.path == "/api/training/practical":
                    result = data.practical_questions(session["employee_id"])
                else:
                    return self.send_not_found()
                return self.send_json({"data": result})
            except ValueError as exc:
                return self.send_json({"error": str(exc), "code": "INVALID_REQUEST"}, 400)
            except data.DatabaseUnavailable as exc:
                return self.send_json({"error": str(exc), "code": "DATABASE_UNAVAILABLE"}, 503)

        employee_routes = {
            "/api/dashboard": data.dashboard,
            "/api/knowledge": data.knowledge,
            "/api/operations": data.operations_process,
            "/api/departments": data.departments,
            "/api/branches": data.branches,
            "/api/compliance/questions": data.compliance_questions,
            "/api/staff/attendance-options": data.attendance_staff_options,
            "/api/manuals": data.operations_manual_catalog,
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

        if parsed.path == "/api/manuals/document":
            try:
                if not self.require_employee():
                    return
                document_id = int(parse_qs(parsed.query).get("id", ["0"])[0])
                return self.send_json({"data": data.operations_manual_document(document_id)})
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
                if parsed.path == "/api/admin/manuals/documents":
                    return self.send_json({"data": data.operations_manuals_admin()})
                if parsed.path == "/api/admin/compliance/questions":
                    return self.send_json({"data": data.compliance_questions_admin()})
                if parsed.path == "/api/admin/compliance/answers":
                    return self.send_json({"data": data.compliance_essay_answers_admin()})
                if parsed.path == "/api/admin/training/taxonomy":
                    return self.send_json({"data": data.training_taxonomy_admin()})
            except ValueError as exc:
                return self.send_json({"error": str(exc), "code": "INVALID_REQUEST"}, 400)
            except data.DatabaseUnavailable as exc:
                return self.send_json({"error": str(exc), "code": "DATABASE_UNAVAILABLE"}, 503)
            return self.send_not_found()

        self.send_not_found()

    def do_POST(self) -> None:
        """依既有 POST 路由驗證登入、CSRF 與輸入後執行業務。"""
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/employee/login":
                return self.employee_login()
            if parsed.path == "/api/employee/logout":
                return self.employee_logout()
            if parsed.path == "/api/youtube/resolve":
                session = self.require_employee()
                if not session or not self.require_csrf(session):
                    return
                item = user_input.validate_youtube(self.read_json())
                return self.send_json({"data": youtube_metadata(item)})
            if parsed.path == "/api/media/resolve":
                session = self.require_employee()
                if not session or not self.require_csrf(session):
                    return
                item = user_input.validate_media(self.read_json())
                return self.send_json({"data": media.video_metadata(item)})
            if parsed.path == "/api/operations/submit":
                session = self.require_employee()
                if not session or not self.require_csrf(session):
                    return
                item = user_input.validate_operation(self.read_json())
                return self.send_json({"data": data.add_operation(item, session["employee_id"])}, 201)
            if parsed.path == "/api/operations/reply":
                session = self.require_employee()
                if not session or not self.require_csrf(session):
                    return
                item = user_input.validate_operation_reply(self.read_json())
                return self.send_json({"data": data.reply_operation(item, session["employee_id"])})
            if parsed.path == "/api/compliance/answer":
                session = self.require_employee()
                if not session or not self.require_csrf(session):
                    return
                item = user_input.validate_compliance_answer(self.read_json())
                return self.send_json({"data": data.grade_compliance_answer(item, session["employee_id"])})
            if parsed.path == "/api/training/session/start":
                session = self.require_employee()
                if not session or not self.require_csrf(session):
                    return
                item = user_input.validate_training_start(self.read_json())
                return self.send_json({"data": data.start_training_session(item, session["employee_id"])}, 201)
            if parsed.path == "/api/training/session/answer":
                session = self.require_employee()
                if not session or not self.require_csrf(session):
                    return
                item = user_input.validate_training_answer(self.read_json())
                return self.send_json({"data": data.save_training_answer(item, session["employee_id"])})
            if parsed.path == "/api/training/session/submit":
                session = self.require_employee()
                if not session or not self.require_csrf(session):
                    return
                session_id = user_input.validate_training_session_action(self.read_json())
                return self.send_json({"data": data.submit_training_session(session_id, session["employee_id"])})
            if parsed.path == "/api/training/wrong/remove":
                session = self.require_employee()
                if not session or not self.require_csrf(session):
                    return
                question_id = user_input.validate_training_wrong_remove(self.read_json())
                return self.send_json({"data": data.remove_training_wrong(question_id, session["employee_id"])})
            if parsed.path == "/api/training/practical/answer":
                session = self.require_employee()
                if not session or not self.require_csrf(session):
                    return
                item = user_input.validate_compliance_answer(self.read_json())
                return self.send_json({"data": data.grade_compliance_answer(item, session["employee_id"])})
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
                if parsed.path == "/api/admin/manuals/sync":
                    report = operations_manuals.sync_training_sources(ensure_schema=False)
                    return self.send_json({"data": report})
                if parsed.path == "/api/admin/manuals/document":
                    item = user_input.validate_operations_manual_state(self.read_json())
                    return self.send_json({"data": data.set_operations_manual_state(item["id"], item["is_active"])})
                if parsed.path == "/api/admin/compliance/question":
                    item = user_input.validate_compliance_question(self.read_json())
                    return self.send_json({"data": data.save_compliance_question(item)})
                if parsed.path == "/api/admin/training/question/status":
                    item = user_input.validate_training_question_status(self.read_json())
                    return self.send_json({"data": data.set_training_question_status(item["id"], item["status"])})
                if parsed.path == "/api/admin/training/question/reimport":
                    question_id = user_input.validate_training_wrong_remove(self.read_json())
                    data.unlock_training_question_import(question_id)
                    report = operations_manuals.sync_training_sources(ensure_schema=False)
                    return self.send_json({"data": report})
                if parsed.path == "/api/admin/training/questions/bulk":
                    item = user_input.validate_training_question_bulk(self.read_json())
                    return self.send_json({"data": data.update_training_questions_bulk(item)})
                if parsed.path == "/api/admin/training/subject":
                    item = user_input.validate_training_subject(self.read_json())
                    return self.send_json({"data": data.save_training_subject(item)})
                if parsed.path == "/api/admin/training/chapter":
                    item = user_input.validate_training_chapter(self.read_json())
                    return self.send_json({"data": data.save_training_chapter(item)})
                if parsed.path == "/api/admin/compliance/answer/review":
                    item = user_input.validate_essay_review(self.read_json())
                    return self.send_json({"data": data.review_compliance_essay(item, session["employee_id"])})
                if parsed.path == "/api/admin/submission/review":
                    item = user_input.validate_operation_review(self.read_json())
                    return self.send_json({"data": data.review_operation(item, session["employee_id"])})
        except user_input.InputError as exc:
            return self.send_json({"error": str(exc), "code": "INVALID_INPUT"}, 400)
        except ValueError as exc:
            return self.send_json({"error": str(exc), "code": "INVALID_REQUEST"}, 400)
        except (data.DatabaseUnavailable, operations_manuals.DocumentImportError) as exc:
            return self.send_json({"error": str(exc), "code": "SERVICE_UNAVAILABLE"}, 503)
        except (ExternalServiceUnavailable, media.MetadataUnavailable) as exc:
            return self.send_json({"error": str(exc), "code": "EXTERNAL_SERVICE_UNAVAILABLE"}, 503)
        self.send_json({"error": "此路徑不接受寫入。"}, 405)

    def do_DELETE(self) -> None:
        """驗證管理員與 CSRF 後處理既有刪除路由。"""
        parsed = urlparse(self.path)
        allowed_paths = {"/api/admin/staff", "/api/admin/departments", "/api/admin/compliance/question"}
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
                question_id = user_input.validate_training_wrong_remove({"question_id": payload.get("id")})
                result = data.delete_compliance_question(question_id)
            return self.send_json({"data": result})
        except user_input.InputError as exc:
            return self.send_json({"error": str(exc), "code": "INVALID_INPUT"}, 400)
        except ValueError as exc:
            return self.send_json({"error": str(exc), "code": "INVALID_REQUEST"}, 400)
        except data.DatabaseUnavailable as exc:
            return self.send_json({"error": str(exc), "code": "DATABASE_UNAVAILABLE"}, 503)

    def admin_login(self, employee_session: dict) -> None:
        """驗證帳密及員工身分後建立管理員 Cookie。"""
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
        cookie = f"silver_shield_admin={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_TTL}"
        return self.send_json({"data": {"authenticated": True, "username": username, "csrf": csrf}}, headers={"Set-Cookie": cookie})

    def employee_login(self) -> None:
        """依員工編號與進入模式建立工作階段，必要時打卡。"""
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
        cookie = f"silver_shield_employee={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_TTL}"
        return self.send_json({"data": {"authenticated": True, "employee": employee, "attendance": attendance, "access_mode": item["mode"], "csrf": csrf}}, headers={"Set-Cookie": cookie})

    def employee_logout(self) -> None:
        """清除員工與其綁定的管理員工作階段。"""
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        token = cookie.get("silver_shield_employee")
        admin_token = cookie.get("silver_shield_admin")
        if token:
            with SESSION_LOCK:
                EMPLOYEE_SESSIONS.pop(token.value, None)
                if admin_token:
                    SESSIONS.pop(admin_token.value, None)
        return self.send_json({"data": {"authenticated": False}}, headers={"Set-Cookie": "silver_shield_employee=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"})

    def admin_logout(self) -> None:
        """清除管理員工作階段與 Cookie。"""
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        token = cookie.get("silver_shield_admin")
        if token:
            with SESSION_LOCK:
                SESSIONS.pop(token.value, None)
        return self.send_json({"data": {"authenticated": False}}, headers={"Set-Cookie": "silver_shield_admin=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"})

    def send_not_found(self) -> None:
        """輸出與既有 API 相容的找不到資源回應。"""
        body = ("<!doctype html><html lang=\"zh-TW\"><meta charset=\"utf-8\"><title>找不到頁面</title>"
                "<body><h1>404</h1><p>找不到指定的頁面。</p><a href=\"/\">返回銀盾共同體首頁</a></body></html>").encode()
        self.send_response(404, "Not Found")
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.security_headers()
        self.end_headers()
        self.wfile.write(body)


def youtube_metadata(item: dict[str, str]) -> dict[str, str]:
    """依影片識別碼取得 YouTube 的標題與播放網址。"""
    video_id = item["video_id"]
    with YOUTUBE_CACHE_LOCK:
        cached = YOUTUBE_CACHE.get(video_id)
    if cached:
        return cached
    query = urlencode({"url": item["watch_url"], "format": "json"})
    endpoint = "https://www.youtube.com/oembed?" + query
    request = Request(endpoint, headers={"User-Agent": "SilverShieldOperations/1.0"})
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
    """驗證上傳照片後依員工編號儲存，回傳可公開使用的檔名。"""
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
