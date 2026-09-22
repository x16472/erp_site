from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from backend import data
from backend import doc
from backend import input as user_input


class TrainingDocumentParserTests(unittest.TestCase):
    def test_choice_question_is_split_into_structured_fields(self) -> None:
        block = """01 (C) 下列哪一個函式可讀取使用者輸入？
A. print()
B. len()
C. input()
D. type()
解析：input 會從主控台讀取文字。"""
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
        block = """02 下列何者正確？
A. 第一項
B. 第二項"""
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
    def test_training_start_accepts_all_question_count(self) -> None:
        result = user_input.validate_training_start({
            "subject_id": 7,
            "mode": "practice",
            "question_count": 0,
            "chapter_ids": [2, 2],
            "source_ids": [],
            "question_types": ["single_choice", "matching"],
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


if __name__ == "__main__":
    unittest.main()
