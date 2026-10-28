from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from backend import app, data, doc
from backend import input as user_input

"""用於辨識答案專區"""

class TrainingDocumentParserTests(unittest.TestCase):
    def test_matching_question_is_not_imported_as_choice(self) -> None:
        result = doc._parse_question_block(
            "01 (A) 請將資料類型移至右側完成配對。\nA. int\nB. str",
            number="01", answer_marker="A", source=Path("questions.pdf"),
            page_number=1, chapter_code="CH01", chapter_name="資料型態",
        )
        self.assertIsNone(result)

    def test_choice_question_is_split_into_structured_fields(self) -> None:
        block = """
01 (C) 下列哪一個函式可讀取使用者輸入？
A. print()
B. len()
C. input()
D. type()
解析：input 會從主控台讀取文字。
"""
        result = doc._parse_question_block(
            block,
            number="01",
            answer_marker="C",
            source=Path("ITS_Python.pdf"),
            page_number=1,
            chapter_code="CH01",
            chapter_name="資料型態",
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["question_type"], "single_choice")
        self.assertEqual(result["answers"], [2])
        self.assertEqual(len(result["options"]), 4)
        self.assertEqual(result["explanation"], "input 會從主控台讀取文字。")

    def test_question_without_answer_stays_reviewable_draft(self) -> None:
        block ="""
02 下列何者正確？
A. 第一項
B. 第二項
"""
        result = doc._parse_question_block(
            block,
            number="02",
            answer_marker="",
            source=Path("questions.pdf"),
            page_number=3,
            chapter_code="",
            chapter_name="",
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["status"], "draft")
        self.assertIn("未可靠辨識正確答案", result["parse_warnings"])

    def test_missing_ocr_is_reported_as_source_failure(self) -> None:
        def source_files(suffix: str) -> list[Path]:
            return [Path("scan.pdf")] if suffix == ".pdf" else []

        with mock.patch.object(doc, "_source_files", side_effect=source_files), \
             mock.patch.object(
                 doc,
                 "_pdf_pages_for_questions",
                 return_value=([], ["第 1 頁：找不到 Tesseract OCR"]),
             ):
            result = doc.read_training_question_drafts()

        self.assertEqual([], result["warnings"])
        self.assertEqual("scan.pdf", result["failures"][0]["source"])


class TrainingInputTests(unittest.TestCase):
    def test_matching_type_cannot_be_selected_or_saved(self) -> None:
        with self.assertRaises(user_input.InputError):
            user_input.validate_training_start({
                "subject_id": 1, "question_types": ["matching"],
            })
        with self.assertRaises(user_input.InputError):
            user_input.validate_compliance_question({
                "subject_id": 1, "chapter_id": 1, "question_type": "matching",
                "question": "測試題目", "options": [], "answers": [],
            })

    def test_removed_fill_blank_type_is_rejected(self) -> None:
        with self.assertRaises(user_input.InputError):
            user_input.validate_training_start({
                "subject_id": 1, "question_types": ["fill_blank"],
            })

    def test_training_start_accepts_all_question_count(self) -> None:
        result = user_input.validate_training_start({
            "subject_id": 7,
            "mode": "practice",
            "question_count": 0,
            "chapter_ids": [2, 2],
            "source_ids": [],
            "question_types": ["single_choice", "multiple_choice"],
        })
        self.assertEqual(result["question_count"], 0)
        self.assertEqual(result["chapter_ids"], [2])

    def test_practical_must_use_essay(self) -> None:
        with self.assertRaises(user_input.InputError):
            user_input.validate_compliance_question({
                "subject_id": 1,
                "chapter_id": 1,
                "domain": "practical",
                "question_type": "single_choice",
                "status": "draft",
                "question": "題目",
                "options": [],
                "answers": [],
            })


class TrainingResponseTests(unittest.TestCase):
    def test_active_mock_session_does_not_expose_answers(self) -> None:
        session = {
            "id": "session-id",
            "mode": "mock",
            "status": "in_progress",
            "subject_id": 1,
            "started_at": "2026-01-01T00:00:00",
            "expires_at": "2026-01-01T00:45:00",
            "submitted_at": None,
            "score": None,
            "config_json": "{}",
        }
        rows = [{
            "question_order": 1,
            "snapshot_json": '{"id":1,"question":"Q","answers":[2],"explanation":"secret"}',
            "response_json": None,
            "is_flagged": False,
            "is_correct": None,
        }]
        payload = data._public_session_payload(session, rows)
        self.assertNotIn("answers", payload["questions"][0])
        self.assertNotIn("explanation", payload["questions"][0])


class TrainingQuestionDeletionTests(unittest.TestCase):
    def test_matching_question_cannot_be_published(self) -> None:
        with mock.patch.object(data, "_fetch", return_value=[{"question_type": "matching"}]), \
             mock.patch.object(data, "connect") as connect, \
             self.assertRaisesRegex(ValueError, "此題型已不支援"):
            data.set_training_question_status(7, "published")
        connect.assert_not_called()

    def make_handler(self) -> app.Handler:
        handler = object.__new__(app.Handler)
        handler.path = "/api/admin/compliance/question"
        handler.require_employee = mock.Mock(return_value={"employee_id": "TEST"})
        handler.require_admin = mock.Mock(return_value={"csrf": "token"})
        handler.require_csrf = mock.Mock(return_value=True)
        handler.read_json = mock.Mock(return_value={"id": 7})
        handler.send_json = mock.Mock()
        return handler

    def test_delete_requires_admin_and_csrf(self) -> None:
        for admin, csrf in [(None, True), ({"csrf": "token"}, False)]:
            with self.subTest(admin=admin, csrf=csrf):
                handler = self.make_handler()
                handler.require_admin.return_value = admin
                handler.require_csrf.return_value = csrf
                with mock.patch.object(data, "delete_compliance_question") as delete:
                    handler.do_DELETE()
                delete.assert_not_called()
                handler.read_json.assert_not_called()

    def test_delete_route_removes_question_instead_of_disabling(self) -> None:
        handler = self.make_handler()
        result = {"id": 7, "deleted": True}
        with mock.patch.object(data, "delete_compliance_question", return_value=result) as delete:
            handler.do_DELETE()
        delete.assert_called_once_with(7)
        handler.send_json.assert_called_once_with({"data": result})

    def test_delete_rejects_invalid_id(self) -> None:
        handler = self.make_handler()
        handler.read_json.return_value = {"id": -1}
        with mock.patch.object(data, "delete_compliance_question") as delete:
            handler.do_DELETE()
        delete.assert_not_called()
        self.assertEqual(handler.send_json.call_args.args[1], 400)

    def test_missing_or_deleted_question_is_not_reported_as_deleted(self) -> None:
        connection = mock.MagicMock()
        connection.__enter__.return_value = connection
        connection.cursor.return_value.rowcount = 0
        with mock.patch.object(data, "connect", return_value=connection), \
             self.assertRaises(ValueError):
            data.delete_compliance_question(7)

    def test_deleted_source_question_is_not_reimported(self) -> None:
        connection = mock.MagicMock()
        connection.__enter__.return_value = connection
        cursor = connection.cursor.return_value
        cursor.execute.return_value.fetchall.return_value = []
        cursor.execute.return_value.fetchone.return_value = (7, False, "2026-10-28")
        with mock.patch.object(data, "connect", return_value=connection), \
             mock.patch.object(data, "_ensure_training_classification", return_value=(1, 2)):
            result = data.import_training_question_drafts([{
                "source_document": "questions.pdf", "source_fingerprint": "fingerprint",
            }])
        self.assertEqual(result["locked"], 1)
        self.assertEqual(result["created"], 0)
        self.assertEqual(result["updated"], 0)

    def test_deleted_question_cannot_be_republished(self) -> None:
        with mock.patch.object(data, "_fetch", return_value=[]), \
             mock.patch.object(data, "connect") as connect, \
             self.assertRaises(ValueError):
            data.set_training_question_status(7, "published")
        connect.assert_not_called()


class DatabaseConnectionTests(unittest.TestCase):
    def test_connection_string_includes_escaped_password(self) -> None:
        config = {
            "DatabaseIP": "db.example",
            "DatabasePort": "1433",
            "DatabaseName": "company;prod",
            "DatabaseUser": "service}user",
            "DatabasePassword": "p;ass}word",
        }
        with mock.patch.object(data, "_load_env", return_value=config), \
             mock.patch.object(data.mssql_python, "connect") as connect:
            data._new_connection(read_only=False, autocommit=False)

        connect.assert_called_once_with(
            "Server={db.example,1433};"
            "Database={company;prod};"
            "UID={service}}user};"
            "PWD={p;ass}}word};"
            "Encrypt=no;TrustServerCertificate=yes;",
            autocommit=False,
            timeout=5,
        )

    def test_read_only_connection_sets_application_intent(self) -> None:
        config = {
            "DatabaseIP": "db.example",
            "DatabasePort": "1433",
            "DatabaseName": "company",
            "DatabaseUser": "service",
            "DatabasePassword": "secret",
        }
        with mock.patch.object(data, "_load_env", return_value=config), \
             mock.patch.object(data.mssql_python, "connect") as connect:
            data._new_connection(read_only=True, autocommit=True)

        connection_string = connect.call_args.args[0]
        self.assertIn("ApplicationIntent=ReadOnly;", connection_string)
        self.assertTrue(connect.call_args.kwargs["autocommit"])
        self.assertEqual(connect.call_args.kwargs["timeout"], 5)


class SecurityAndPerformanceTests(unittest.TestCase):
    def test_request_scope_reuses_and_closes_connection(self) -> None:
        connection = mock.MagicMock()
        with mock.patch.object(data, "_new_connection", return_value=connection) as create, \
             data.connection_scope():
            with data.connect() as first:
                pass
            with data.connect() as second:
                pass
            connection.close.assert_not_called()
            connection.__exit__.assert_not_called()

        self.assertIs(first, second)
        create.assert_called_once_with(True, True)
        connection.close.assert_called_once_with()

    def test_failed_borrow_discards_request_connection(self) -> None:
        first_connection = mock.MagicMock()
        second_connection = mock.MagicMock()
        with mock.patch.object(data, "_new_connection", side_effect=[first_connection, second_connection]) as create:  # noqa: SIM117
            with data.connection_scope():
                with self.assertRaises(ValueError), data.connect():
                    raise ValueError("查詢失敗")
                with data.connect() as replacement:
                    self.assertIs(replacement, second_connection)

        self.assertEqual(create.call_count, 2)
        first_connection.close.assert_called_once_with()
        second_connection.close.assert_called_once_with()

    def test_connection_outside_request_uses_driver_context_manager(self) -> None:
        connection = mock.MagicMock()
        connection.__enter__.return_value = connection
        with mock.patch.object(data, "_new_connection", return_value=connection), data.connect() as borrowed:
            self.assertIs(borrowed, connection)

        connection.__exit__.assert_called_once()

    def test_staff_csv_check_is_throttled(self) -> None:
        connection = mock.MagicMock()
        connection.__enter__.return_value = connection
        original_checked_at = data._staff_sync_checked_at
        self.addCleanup(setattr, data, "_staff_sync_checked_at", original_checked_at)
        data._staff_sync_checked_at = None
        with mock.patch.object(data, "monotonic", side_effect=[100.0, 100.0, 110.0]), \
             mock.patch.object(data, "connect", return_value=connection) as connect, \
             mock.patch.object(data, "_sync_staff_csv_cursor", return_value=0) as sync:
            data.sync_staff_csv()
            data.sync_staff_csv()

        connect.assert_called_once_with(read_only=False, autocommit=False)
        sync.assert_called_once_with(connection.cursor())

    def test_youtube_resolver_requires_csrf(self) -> None:
        handler = object.__new__(app.Handler)
        handler.path = "/api/youtube/resolve"
        handler.require_employee = mock.Mock(return_value={"csrf": "token"})
        handler.require_csrf = mock.Mock(return_value=False)
        handler.read_json = mock.Mock()

        handler.do_POST()

        handler.require_csrf.assert_called_once_with({"csrf": "token"})
        handler.read_json.assert_not_called()

    def test_media_resolver_requires_employee_and_csrf(self) -> None:
        for session, csrf in [(None, True), ({"csrf": "token"}, False)]:
            with self.subTest(session=session):
                handler = object.__new__(app.Handler)
                handler.path = "/api/media/resolve"
                handler.require_employee = mock.Mock(return_value=session)
                handler.require_csrf = mock.Mock(return_value=csrf)
                handler.read_json = mock.Mock()
                handler.do_POST()
                handler.read_json.assert_not_called()

    def test_media_resolver_returns_actual_metadata(self) -> None:
        handler = object.__new__(app.Handler)
        handler.path = "/api/media/resolve"
        handler.require_employee = mock.Mock(return_value={"csrf": "token"})
        handler.require_csrf = mock.Mock(return_value=True)
        handler.read_json = mock.Mock(return_value={
            "platform": "bilibili", "url": "https://www.bilibili.com/video/BV1VRpw69E6V",
        })
        handler.send_json = mock.Mock()
        metadata = {"title": "實際影片標題", "title_status": "available"}
        with mock.patch.object(app.media, "video_metadata", return_value=metadata) as resolve:
            handler.do_POST()
        self.assertEqual(resolve.call_args.args[0]["video_id"], "BV1VRpw69E6V")
        handler.send_json.assert_called_once_with({"data": metadata})

    def test_media_metadata_failures_return_service_error(self) -> None:
        handler = object.__new__(app.Handler)
        handler.path = "/api/media/resolve"
        handler.require_employee = mock.Mock(return_value={"csrf": "token"})
        handler.require_csrf = mock.Mock(return_value=True)
        handler.read_json = mock.Mock(return_value={
            "platform": "bilibili", "url": "https://www.bilibili.com/video/BV1VRpw69E6V",
        })
        handler.send_json = mock.Mock()
        with mock.patch.object(app.media, "video_metadata", side_effect=app.media.MetadataUnavailable("來源無法回應")):
            handler.do_POST()
        handler.send_json.assert_called_once_with({
            "error": "來源無法回應", "code": "EXTERNAL_SERVICE_UNAVAILABLE",
        }, 503)


if __name__ == "__main__":
    unittest.main()
