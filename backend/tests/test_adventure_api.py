from __future__ import annotations

import json
from datetime import datetime
import unittest
from unittest import mock

from backend.src.erp import api as app, domain as data, adventure
from backend.src.erp.rpc import backend_pb2


class AdventureApiTests(unittest.TestCase):
    """驗證冒險系統之 HTTP API 路由、權限驗證與狀態碼。"""

    def setUp(self) -> None:
        self.employee_session = {
            "employee_id": "EMP001",
            "full_name": "王小明",
            "role": "staff",
            "csrf": "test-csrf-token",
        }
        self.admin_session = {
            "employee_id": "EMP001",
            "username": "admin",
            "csrf": "admin-csrf-token",
        }

    def _make_handler(self, path: str, method: str = "GET") -> app.Handler:
        handler = object.__new__(app.Handler)
        handler.path = path
        handler.command = method
        handler.send_json = mock.Mock()
        handler.send_not_found = mock.Mock()
        handler.require_employee = mock.Mock(return_value=self.employee_session)
        handler.require_admin = mock.Mock(return_value=self.admin_session)
        handler.require_csrf = mock.Mock(return_value=True)
        return handler

    def test_get_adventure_worlds_requires_employee(self) -> None:
        handler = self._make_handler("/api/adventure/worlds")
        handler.require_employee.return_value = None

        handler.do_GET()

        handler.require_employee.assert_called_once()
        handler.send_json.assert_not_called()

    def test_get_adventure_worlds_success(self) -> None:
        handler = self._make_handler("/api/adventure/worlds")
        mock_worlds = [{"world_no": "DEMO_TOWN", "world_name": "穿越小鎮"}]

        with mock.patch.object(data, "adventure_worlds", return_value=mock_worlds) as get_worlds:
            handler.do_GET()

        get_worlds.assert_called_once()
        handler.send_json.assert_called_once_with({"data": mock_worlds})

    def test_get_adventure_saves_success(self) -> None:
        handler = self._make_handler("/api/adventure/saves?world_no=DEMO_TOWN")
        mock_saves = [{"save_no": "DEMO_TOWN-S1", "slot_index": 1}]

        with mock.patch.object(data, "adventure_saves", return_value=mock_saves) as get_saves:
            handler.do_GET()

        get_saves.assert_called_once_with("EMP001")
        handler.send_json.assert_called_once_with({"data": mock_saves})

    def test_create_save_requires_csrf(self) -> None:
        handler = self._make_handler("/api/adventure/saves/create", method="POST")
        handler.require_csrf.return_value = False
        handler.read_json = mock.Mock(return_value={"world_no": "DEMO_TOWN", "slot_index": 1})

        handler.do_POST()

        handler.require_csrf.assert_called_once_with(self.employee_session)
        handler.send_json.assert_not_called()

    def test_create_save_success(self) -> None:
        handler = self._make_handler("/api/adventure/saves/create", method="POST")
        handler.read_json = mock.Mock(return_value={"world_no": "DEMO_TOWN", "slot_index": 2, "trait_id": "scholar"})
        mock_result = {"save_no": "DEMO_TOWN-EMP001-S2", "slot_index": 2}

        with mock.patch.object(data, "adventure_create_save", return_value=mock_result) as create_save:
            handler.do_POST()

        create_save.assert_called_once_with("EMP001", "DEMO_TOWN", 2, "scholar")
        handler.send_json.assert_called_once_with({"data": mock_result}, 201)

    def test_adventure_action_success(self) -> None:
        handler = self._make_handler("/api/adventure/action", method="POST")
        handler.read_json = mock.Mock(return_value={
            "save_no": "DEMO_TOWN-S1",
            "request_id": "req-12345",
            "expected_revision": 1,
            "action": {"type": "rest"},
        })
        mock_response = {"save_no": "DEMO_TOWN-S1", "revision": 2, "new_logs": ["你休息了一會兒。"]}

        with mock.patch.object(data, "adventure_action", return_value=mock_response) as act:
            handler.do_POST()

        act.assert_called_once_with("EMP001", "DEMO_TOWN-S1", "req-12345", 1, {"type": "rest"})
        handler.send_json.assert_called_once_with({"data": mock_response})

    def test_adventure_action_conflict_returns_409(self) -> None:
        """當存檔修訂號衝突時，後端應捕捉 CONFLICT 前綴並回傳 409。"""
        handler = self._make_handler("/api/adventure/action", method="POST")
        handler.read_json = mock.Mock(return_value={
            "save_no": "DEMO_TOWN-S1",
            "request_id": "req-12345",
            "expected_revision": 1,
            "action": {"type": "rest"},
        })

        with mock.patch.object(
            data,
            "adventure_action",
            side_effect=ValueError("CONFLICT:存檔修訂號不符，已被其他操作更新，請重新整理取得最新狀態。"),
        ):
            handler.do_POST()

        handler.send_json.assert_called_once_with(
            {"error": "存檔修訂號不符，已被其他操作更新，請重新整理取得最新狀態。", "code": "CONFLICT"},
            409,
        )

    def test_adventure_action_missing_fields_returns_400(self) -> None:
        handler = self._make_handler("/api/adventure/action", method="POST")
        handler.read_json = mock.Mock(return_value={"save_no": "DEMO_TOWN-S1"})

        handler.do_POST()

        handler.send_json.assert_called_once_with(
            {"error": "缺少必要的 save_no, request_id 或 action 資料", "code": "INVALID_REQUEST"},
            400,
        )

    def test_admin_draft_routes_require_admin(self) -> None:
        handler = self._make_handler("/api/admin/adventure/draft?world_no=DEMO_TOWN")
        handler.require_admin.return_value = None

        handler.do_GET()

        handler.require_admin.assert_called_once()
        handler.send_json.assert_not_called()

    def test_admin_save_draft_success(self) -> None:
        handler = self._make_handler("/api/admin/adventure/draft/save", method="POST")
        handler.read_json = mock.Mock(return_value={
            "world_no": "DEMO_TOWN",
            "expected_revision": 1,
            "content": {"title": "更新後的草稿"},
        })
        mock_result = {"world_no": "DEMO_TOWN", "revision": 2}

        with mock.patch.object(data, "admin_save_draft", return_value=mock_result) as save_draft:
            handler.do_POST()

        save_draft.assert_called_once_with("DEMO_TOWN", 1, {"title": "更新後的草稿"}, "admin")
        handler.send_json.assert_called_once_with({"data": mock_result})

    def test_admin_validate_draft_success(self) -> None:
        handler = self._make_handler("/api/admin/adventure/validate", method="POST")
        handler.read_json = mock.Mock(return_value={"content": {"title": "待驗證草稿"}})
        mock_result = {"valid": True, "errors": [], "warnings": []}

        with mock.patch.object(data, "admin_validate_draft", return_value=mock_result) as val:
            handler.do_POST()

        val.assert_called_once_with({"title": "待驗證草稿"})
        handler.send_json.assert_called_once_with({"data": mock_result})

    def test_admin_test_run_success(self) -> None:
        handler = self._make_handler("/api/admin/adventure/test-run", method="POST")
        handler.read_json = mock.Mock(return_value={
            "content": {"title": "試跑草稿"},
            "initial_state": {"turn": 1},
            "action": {"type": "rest"},
            "rng_seed": 100,
        })
        mock_result = {"new_state": {"turn": 2}, "logs": ["試跑成功"]}

        with mock.patch.object(data, "admin_test_run", return_value=mock_result) as test_run:
            handler.do_POST()

        test_run.assert_called_once_with({"title": "試跑草稿"}, {"turn": 1}, {"type": "rest"}, 100)
        handler.send_json.assert_called_once_with({"data": mock_result})

    def test_admin_publish_draft_success(self) -> None:
        handler = self._make_handler("/api/admin/adventure/publish", method="POST")
        handler.read_json = mock.Mock(return_value={
            "world_no": "DEMO_TOWN",
            "expected_revision": 2,
        })
        mock_result = {"world_no": "DEMO_TOWN", "version_no": "V002"}

        with mock.patch.object(data, "admin_publish_draft", return_value=mock_result) as pub:
            handler.do_POST()

        pub.assert_called_once_with("DEMO_TOWN", 2, "admin")
        handler.send_json.assert_called_once_with({"data": mock_result})


class AdventureDomainLogicTests(unittest.TestCase):
    """驗證 Domain 層之冪等防重、修訂號樂觀鎖與欄位上限邏輯。"""

    def test_adventure_action_idempotency_returns_cached_response(self) -> None:
        """相同 request_id 與相同 action 應直接回傳快取回應，不重新執行。"""
        action_payload = {"type": "rest"}
        cached_result = {"save_no": "S1", "revision": 2, "new_logs": ["之前休息的紀錄"]}

        mock_db = mock.MagicMock()
        mock_cursor = mock_db.cursor.return_value

        # 1. 查詢存檔 (SaveNo, EmployeeId, WorldNo, SlotIndex, VersionNo, Revision, CurrentPhase, StateJson, IsCompleted)
        mock_cursor.fetchall.side_effect = [
            [(1, "EMP001", "DEMO_TOWN", 1, "V001", 1, "ACTIVE", "{}", 0)],  # save_rows
            [(1, "S1", 1, "req-101", json.dumps(action_payload), "{}", "{}", json.dumps(cached_result), "2026-11-06")],  # turn_rows
        ]

        with mock.patch.object(data, "connect") as mock_conn:
            mock_conn.return_value.__enter__.return_value = mock_db
            res = data.adventure_action("EMP001", "S1", "req-101", 1, action_payload)

        self.assertEqual(res, cached_result)
        mock_db.commit.assert_called_once()
        mock_db.rollback.assert_not_called()

    def test_adventure_action_same_request_id_different_action_rejected(self) -> None:
        """相同 request_id 但不同 action 時，應拒絕並 rollback。"""
        mock_db = mock.MagicMock()
        mock_cursor = mock_db.cursor.return_value

        mock_cursor.fetchall.side_effect = [
            [(1, "EMP001", "DEMO_TOWN", 1, "V001", 1, "ACTIVE", "{}", 0)],
            [(1, "S1", 1, "req-101", json.dumps({"type": "attack"}), "{}", "{}", "{}", "2026-11-06")],
        ]

        with mock.patch.object(data, "connect") as mock_conn:
            mock_conn.return_value.__enter__.return_value = mock_db
            with self.assertRaisesRegex(ValueError, "相同請求識別碼搭配不同行動內容"):
                data.adventure_action("EMP001", "S1", "req-101", 1, {"type": "defend"})

        mock_db.rollback.assert_called_once()

    def test_adventure_action_revision_conflict_raises_conflict(self) -> None:
        """當預期修訂號與資料庫不符時，拋出 CONFLICT 錯誤並 rollback。"""
        mock_db = mock.MagicMock()
        mock_cursor = mock_db.cursor.return_value

        mock_cursor.fetchall.side_effect = [
            [(1, "EMP001", "DEMO_TOWN", 1, "V001", 3, "ACTIVE", "{}", 0)],  # 實際是 3
            [],  # 沒有相同 request_id
        ]

        with mock.patch.object(data, "connect") as mock_conn:
            mock_conn.return_value.__enter__.return_value = mock_db
            with self.assertRaisesRegex(ValueError, "CONFLICT:存檔修訂號不符"):
                data.adventure_action("EMP001", "S1", "req-102", 2, {"type": "rest"})  # 預期是 2

        mock_db.rollback.assert_called_once()

    def test_adventure_create_save_slot_validation_and_duplicate(self) -> None:
        """存檔欄位超出 1~3 範圍或已佔用槽位時應阻擋。"""
        with self.assertRaisesRegex(ValueError, "存檔欄位必須為 1、2 或 3"):
            data.adventure_create_save("EMP001", "DEMO_TOWN", 4)

        mock_db = mock.MagicMock()
        with mock.patch.object(data, "_fetch", side_effect=[
            [{"IsOpen": True, "CurrentVersionNo": "V001"}],  # world_rows
            [{"Content": "{}"}],  # ver_rows
            [{"WorldNo": "DEMO_TOWN", "SlotIndex": 1, "SaveNo": "EXISTING"}],
        ]), mock.patch.object(data, "employee_identity", return_value={"employee_id": "EMP001", "display_name": "王小明", "department": "IT", "position": "工程師"}), \
             mock.patch.object(data, "adventure_state", return_value={"save_no": "EXISTING"}) as state_view, \
             mock.patch.object(data, "connect") as mock_conn:
            mock_conn.return_value.__enter__.return_value = mock_db
            result = data.adventure_create_save("EMP001", "DEMO_TOWN", 1)
            self.assertEqual(result["save_no"], "EXISTING")
            state_view.assert_called_once_with("EXISTING", "EMP001")


class AdventurePersistenceRegressionTests(unittest.TestCase):
    def setUp(self):
        self.script = adventure.create_demo_chapter()
        self.state = adventure.create_initial_state({"employee_id": "E1"}, self.script)
        self.save = {"SaveNo": "S1", "EmployeeNo": "E1", "WorldNo": "DEMO_TOWN", "SlotIndex": 1,
                     "VersionNo": "v1", "Revision": 1, "CharacterSnapshot": "{}",
                     "StateJson": json.dumps(self.state), "IsActive": True, "CreateTime": None, "WorldName": "小鎮",
                     "SaveDisplayId": 4, "VersionDisplayId": 2}

    def test_save_list_dates_can_be_sent_as_json(self):
        for timestamp, expected in (
            (datetime(2026, 11, 7, 12, 34, 56, 123456), "2026-11-07T12:34:56.123456"),
            ("2026-11-07T12:34:56", "2026-11-07T12:34:56"),
            (None, None),
        ):
            with self.subTest(timestamp=timestamp):
                self.save["CreateTime"] = timestamp
                handler = app.Handler(backend_pb2.HttpRequest(method="GET", target="/api/adventure/saves"))
                with mock.patch.object(data, "_fetch", return_value=[self.save]), mock.patch.object(
                    handler, "require_employee", return_value={"employee_id": "E1"}
                ):
                    handler.do_GET()
                self.assertEqual(handler.response.status, 200)
                result = json.loads(handler.wfile.getvalue())["data"][0]
                self.assertEqual(result["create_time"], expected)
                self.assertEqual(result["save_no"], "S1")
                self.assertEqual(result["save_display_no"], "SAVE_000004")

    def test_save_history_dates_can_be_sent_as_json(self):
        turn = {
            "Id": 1, "TurnIndex": 1, "RequestId": "R1", "ActionId": "rest",
            "ActionInput": "{}", "RollResult": "{}", "StateDiff": "{}", "ResponseJson": "{}",
            "CreateTime": datetime(2026, 11, 7, 12, 34, 56),
        }
        handler = app.Handler(backend_pb2.HttpRequest(method="GET", target="/api/adventure/history?save_no=S1"))
        with mock.patch.object(data, "_fetch", side_effect=[[self.save], [turn]]), mock.patch.object(
            handler, "require_employee", return_value={"employee_id": "E1"}
        ):
            handler.do_GET()
        self.assertEqual(handler.response.status, 200)
        self.assertEqual(json.loads(handler.wfile.getvalue())["data"][0]["create_time"], "2026-11-07T12:34:56")

    def test_view_hides_rules_and_undiscovered_characters(self):
        view = data.adventure_view(self.save, self.script, self.state)
        fountain = view["location"]["objects"][0]
        self.assertNotIn("effects", fountain)
        self.assertNotIn("condition", fountain)
        self.assertEqual(view["state"]["relationships"], [])
        self.assertTrue(all("flow_id" not in a and "next_node_id" not in a for a in view["available_actions"]))

    def test_commit_response_and_duplicate_have_same_complete_shape(self):
        db = mock.MagicMock()
        cursor = db.cursor.return_value
        cursor.rowcount = 1
        cursor.fetchall.side_effect = [list([list(self.save.values())]), [],
                                     [["DEMO_TOWN", "v1", 1, json.dumps(self.script)]]]
        with mock.patch.object(data, "connect") as connect, mock.patch.object(data, "adventure_state", side_effect=AssertionError("不得在 commit 後重讀")):
            connect.return_value.__enter__.return_value = db
            response = data.adventure_action("E1", "S1", "R1", 1, {"action": "move", "target_location_id": "cozy_inn"})
        stored = next(call for call in cursor.execute.call_args_list if call.args[0] == "domain.adventure_turns.2")
        self.assertEqual(json.loads(stored.args[-1]), response)
        self.assertIn("state", response)
        self.assertEqual(response["revision"], 2)
        self.assertEqual(response["save_display_no"], "SAVE_000004")
        self.assertEqual(response["version_display_no"], "V000002")
        self.assertEqual(response["state"]["location_id"], "cozy_inn")
        self.assertEqual(cursor.execute.call_args_list[0].args[0], "domain.adventure_saves.lock")

    def test_second_slot_uses_actual_sql_column_names(self):
        db = mock.MagicMock()
        with mock.patch.object(data, "_fetch", side_effect=[
            [{"IsOpen": True, "CurrentVersionNo": "v1"}], [{"Content": json.dumps(self.script)}],
            [{"WorldNo": "DEMO_TOWN", "SlotIndex": 1, "SaveNo": "S1"}],
        ]), mock.patch.object(data, "employee_identity", return_value={"employee_id":"E1", "display_name":"主角", "department":"部門", "position":"員工"}), \
             mock.patch.object(data, "connect") as connect, mock.patch.object(data, "adventure_state", return_value={"created": True}):
            connect.return_value.__enter__.return_value = db
            self.assertEqual(data.adventure_create_save("E1", "DEMO_TOWN", 2), {"created": True})
        self.assertEqual(db.cursor.return_value.execute.call_args.args[4], 2)
        db.commit.assert_called_once()

    def test_save_display_numbers_preserve_internal_identifiers(self):
        self.save["SaveNo"] = "SAVE_fa4a9fa669115054bd57913a2b650272"
        self.save["VersionNo"] = "v8.e6eb8950a38e"
        view = data.adventure_view(self.save, self.script, self.state)
        with mock.patch.object(data, "_fetch", return_value=[self.save]):
            listed = data.adventure_saves("E1")[0]
        for result in (view, listed):
            self.assertEqual(result["save_no"], self.save["SaveNo"])
            self.assertEqual(result["version_no"], self.save["VersionNo"])
            self.assertEqual(result["save_display_no"], "SAVE_000004")
            self.assertEqual(result["version_display_no"], "V000002")

    def test_publish_uses_uuid_and_returns_separate_display_number(self):
        db = mock.MagicMock()
        cursor = db.cursor.return_value
        cursor.fetchall.return_value = [["DEMO_TOWN", 5, json.dumps(self.script)]]
        cursor.fetchone.return_value = [12]
        with mock.patch.object(data, "connect") as connect:
            connect.return_value.__enter__.return_value = db
            result = data.admin_publish_draft("DEMO_TOWN", 5, "admin")
        self.assertRegex(result["version_no"], r"^VER_[0-9a-f]{32}$")
        self.assertEqual(result["version_display_no"], "V000012")
        insert = next(c for c in cursor.execute.call_args_list if c.args[0] == "domain.admin_adventure_publish.1")
        update = next(c for c in cursor.execute.call_args_list if c.args[0] == "domain.admin_adventure_publish.2")
        self.assertEqual(insert.args[2], result["version_no"])
        self.assertEqual(update.args[1], result["version_no"])

    def test_publish_without_inserted_id_rolls_back_with_clear_error(self):
        db = mock.MagicMock()
        cursor = db.cursor.return_value
        cursor.fetchall.return_value = [["DEMO_TOWN", 5, json.dumps(self.script)]]
        cursor.fetchone.return_value = None
        with mock.patch.object(data, "connect") as connect:
            connect.return_value.__enter__.return_value = db
            with self.assertRaisesRegex(data.DatabaseUnavailable, "重新編譯並重啟 Go"):
                data.admin_publish_draft("DEMO_TOWN", 5, "admin")
        db.rollback.assert_called_once()
        db.commit.assert_not_called()
        self.assertFalse(any(c.args[0] == "domain.admin_adventure_publish.2"
                             for c in cursor.execute.call_args_list))

    def test_stale_publish_checks_locked_revision(self):
        db = mock.MagicMock()
        db.cursor.return_value.fetchall.return_value = [["DEMO_TOWN", 5, json.dumps(self.script)]]
        with mock.patch.object(data, "connect") as connect:
            connect.return_value.__enter__.return_value = db
            with self.assertRaisesRegex(ValueError, "CONFLICT"):
                data.admin_publish_draft("DEMO_TOWN", 4, "admin")
        db.commit.assert_not_called()
        self.assertEqual(db.cursor.return_value.execute.call_args.args[0], "domain.admin_adventure_draft.lock")

    def test_published_employee_snapshot_is_loaded_on_server(self):
        db = mock.MagicMock()
        self.script["npcs"]["artisan"]["mapped_employee_id"] = "E2"
        self.script["npcs"]["artisan"]["mapped_employee_snapshot"] = {"display_name": "偽造資料"}
        db.cursor.return_value.fetchall.return_value = [["DEMO_TOWN", 5, json.dumps(self.script)]]
        with mock.patch.object(data, "connect") as connect, mock.patch.object(data, "employee_identity", return_value={"employee_id":"E2", "display_name":"資料庫姓名"}):
            connect.return_value.__enter__.return_value = db
            data.admin_publish_draft("DEMO_TOWN", 5, "admin")
        insert = next(c for c in db.cursor.return_value.execute.call_args_list if c.args[0] == "domain.admin_adventure_publish.1")
        snapshot = json.loads(insert.args[3])["npcs"]["artisan"]["mapped_employee_snapshot"]
        self.assertEqual(snapshot["display_name"], "資料庫姓名")


if __name__ == "__main__":
    unittest.main()
