from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.src.erp import api as app
from backend.src.erp import input as user_input
from backend.src.erp.rpc import backend_pb2


class QuestionImageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.content = b"\x89PNG\r\n\x1a\n" + b"x" * 128
        self.upload = {"data": "data:image/png;base64," + base64.b64encode(self.content).decode()}
        self.name = "Python題庫_" + "a" * 24 + ".png"
        self.payload = {
            "subject_id": 1, "chapter_id": 2, "question": "測試題目",
            "question_type": "single_choice", "status": "draft",
            "options": ["甲", "乙"], "answers": [0],
            "content_blocks": [{"type": "image", "content": self.name}],
        }

    def test_image_block_survives_question_validation(self) -> None:
        result = user_input.validate_compliance_question(self.payload)
        self.assertEqual(result["content_blocks"], self.payload["content_blocks"])

    def test_image_blocks_reject_paths_and_external_urls(self) -> None:
        for name in ("../" + self.name, "https://example.com/image.png", "C:\\image.png", "image.svg"):
            with self.subTest(name=name), self.assertRaises(user_input.InputError):
                user_input.validate_compliance_question({
                    **self.payload, "content_blocks": [{"type": "image", "content": name}],
                })

    def test_upload_checks_content_and_size(self) -> None:
        image = user_input.validate_question_image(self.upload)
        self.assertEqual(image, {"content": self.content, "extension": "png"})
        for upload in (
            {"data": self.upload["data"].replace("image/png", "image/jpeg")},
            {"data": "data:image/png;base64," + base64.b64encode(b"x" * 128).decode()},
        ):
            with self.subTest(upload=upload), self.assertRaises(user_input.InputError):
                user_input.validate_question_image(upload)
        with mock.patch.object(user_input, "MAX_STAFF_PHOTO_BYTES", 128), self.assertRaises(user_input.InputError):
            user_input.validate_question_image(self.upload)

    def test_bank_names_are_safe_and_replacements_preserve_existing_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(app, "QUESTION_IMAGE_ROOT", Path(directory)):
            image = user_input.validate_question_image(self.upload)
            first = app.save_question_image("../Python 題庫", image)
            second = app.save_question_image("../Python 題庫", image)
            self.assertEqual(first.parent, Path(directory).resolve())
            self.assertTrue(first.name.startswith("Python_題庫_"))
            self.assertEqual(user_input.validate_question_image_name(first.name), first.name)
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_bytes(), self.content)

    def test_image_route_requires_login_and_returns_binary(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(app, "QUESTION_IMAGE_ROOT", Path(directory)):
            (Path(directory) / self.name).write_bytes(self.content)
            handler = app.Handler(backend_pb2.HttpRequest(target="/api/training/image?name=" + self.name))
            handler.require_employee = mock.Mock(return_value=None)
            handler.do_GET()
            self.assertEqual(handler.wfile.getvalue(), b"")
            handler.require_employee.return_value = {"employee_id": "TEST"}
            handler.do_GET()
            self.assertEqual(handler.response.status, 200)
            self.assertEqual(handler.wfile.getvalue(), self.content)
            self.assertIn(("Content-Type", "image/png"), [(h.name, h.value) for h in handler.response.headers])

    def make_save_handler(self) -> app.Handler:
        handler = app.Handler(backend_pb2.HttpRequest(target="/api/admin/compliance/question"))
        handler.require_employee = mock.Mock(return_value={"employee_id": "TEST"})
        handler.require_admin = mock.Mock(return_value={"csrf": "token"})
        handler.require_csrf = mock.Mock(return_value=True)
        handler.read_json = mock.Mock(return_value={**self.payload, "image": self.upload})
        handler.send_json = mock.Mock()
        return handler

    def test_save_adds_image_and_cleans_new_file_if_database_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(app, "QUESTION_IMAGE_ROOT", Path(directory)), \
             mock.patch.object(app.data, "training_taxonomy_admin", return_value={"subjects": [{"id": 1, "name": "Python題庫"}]}), \
             mock.patch.object(app.data, "save_compliance_question", return_value={"id": 1}) as save:
            self.make_save_handler().do_POST()
            blocks = save.call_args.args[0]["content_blocks"]
            self.assertEqual(len(blocks), 1)
            saved = Path(directory) / blocks[0]["content"]
            self.assertEqual(saved.read_bytes(), self.content)
            save.side_effect = ValueError("儲存失敗")
            handler = self.make_save_handler()
            handler.do_POST()
            self.assertEqual(list(Path(directory).iterdir()), [saved])
            self.assertEqual(handler.send_json.call_args.args[1], 400)

    def test_save_uses_document_name_when_linked_to_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(app, "QUESTION_IMAGE_ROOT", Path(directory)), \
             mock.patch.object(app.data, "training_taxonomy_admin", return_value={"subjects": [{"id": 1, "name": "通用科目"}]}), \
             mock.patch.object(app.data, "operations_manuals_admin", return_value=[{"id": 3, "file_name": "Python題庫.pdf"}]), \
             mock.patch.object(app.data, "save_compliance_question", return_value={"id": 1}) as save:
            handler = self.make_save_handler()
            handler.read_json.return_value["document_id"] = 3
            handler.do_POST()
            name = save.call_args.args[0]["content_blocks"][0]["content"]
            self.assertTrue(name.startswith("Python題庫_"))

    def test_save_without_upload_preserves_or_removes_image_blocks(self) -> None:
        with mock.patch.object(app.data, "save_compliance_question", return_value={"id": 1}) as save, \
             mock.patch.object(app, "save_question_image") as write:
            for blocks in (self.payload["content_blocks"], [{"type": "text", "content": "測試題目"}]):
                handler = self.make_save_handler()
                handler.read_json.return_value = {**self.payload, "content_blocks": blocks}
                handler.do_POST()
                self.assertEqual(save.call_args.args[0]["content_blocks"], blocks)
            write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
