"""模擬考以 SQL Server UTC 判定期限，避免裝置與主機時區造成提前交卷。"""
from datetime import UTC, datetime, timedelta
import unittest
from unittest import mock

from backend.src.erp import domain


class TrainingClockTests(unittest.TestCase):
    def test_active_session_uses_database_clock_and_explicit_utc(self) -> None:
        """即使應用主機已晚於歷史題組，仍以資料庫時間判定。"""
        now = datetime(2020, 1, 1, tzinfo=UTC)
        session = {"id": "S", "mode": "mock", "status": "in_progress", "subject_id": 1,
                   "started_at": "2020-01-01T00:00:00", "expires_at": "2020-01-01T00:45:00"}
        with mock.patch.object(domain, "_fetch", side_effect=[[session], []]), \
             mock.patch.object(domain, "_training_now", return_value=now), \
             mock.patch.object(domain, "submit_training_session") as submit:
            result = domain.training_session("S", "E")
        submit.assert_not_called()
        self.assertEqual(result["expires_at"], "2020-01-01T00:45:00+00:00")
        self.assertEqual(result["server_time"], now.isoformat())

    def test_expired_answer_is_rejected_by_database_clock(self) -> None:
        """SQL Server 已到期時，即使應用主機較慢仍拒絕繼續寫入。"""
        row = {"status": "in_progress", "expires_at": "2099-01-01T00:00:00"}
        with mock.patch.object(domain, "_fetch", return_value=[row]), \
             mock.patch.object(domain, "_training_now", return_value=datetime(2099, 1, 1, tzinfo=UTC)), \
             mock.patch.object(domain, "submit_training_session") as submit, \
             mock.patch.object(domain, "connect") as connect:
            with self.assertRaisesRegex(ValueError, "時間已到"):
                domain.save_training_answer({"session_id": "S", "order": 1}, "E")
        submit.assert_called_once_with("S", "E")
        connect.assert_not_called()

    def test_start_uses_same_sql_snapshot_for_start_and_expiry(self) -> None:
        """開始及結束時間出自同一個 SQL 時間快照。"""
        now = datetime(2030, 1, 1, 9, 0)
        subject = {"domain": "academic", "mock_question_count": 1, "mock_duration_minutes": 45, "mock_pass_score": 70}
        item = {"subject_id": 1, "mode": "mock", "question_count": 0, "chapter_ids": [], "source_ids": [], "question_types": []}
        connection = mock.MagicMock()
        connection.__enter__.return_value = connection
        with mock.patch.object(domain, "_fetch", return_value=[subject]), \
             mock.patch.object(domain, "_published_question_rows", return_value=[{"id": 1}]), \
             mock.patch.object(domain, "_question_snapshot", return_value={}), \
             mock.patch.object(domain, "connect", return_value=connection), \
             mock.patch.object(domain.time, "now", return_value={"utc_time": now}), \
             mock.patch.object(domain, "training_session", return_value={}):
            domain.start_training_session(item, "E")
        args = connection.cursor().execute.call_args_list[0].args
        self.assertEqual(args[-2:], (now, now + timedelta(minutes=45)))
        connection.commit.assert_called_once()

    def test_mock_requires_positive_duration(self) -> None:
        """沒有有效時限的模擬考回報設定問題，不建立無計時題組。"""
        subject = {"domain": "academic", "mock_question_count": 1, "mock_duration_minutes": 0}
        item = {"subject_id": 1, "mode": "mock", "chapter_ids": [], "source_ids": [], "question_types": []}
        with mock.patch.object(domain, "_fetch", return_value=[subject]), \
             mock.patch.object(domain, "_published_question_rows", return_value=[{"id": 1}]), \
             mock.patch.object(domain, "connect") as connect:
            with self.assertRaisesRegex(ValueError, "時間必須大於"):
                domain.start_training_session(item, "E")
        connect.assert_not_called()
