"""冒險引擎單元測試：驗證規則運算、時段、條件判斷、戰鬥、迴圈保護與示範章節。"""

import copy
import unittest
from backend.src.erp import adventure


class AdventureEngineTests(unittest.TestCase):
    def setUp(self):
        self.script = adventure.create_demo_chapter()
        self.employee = {
            "employee_id": "K001",
            "display_name": "王大明",
            "department": "營運部",
            "position": "專員",
            "photo_file": "K001.png",
        }
        self.initial_state = adventure.create_initial_state(self.employee, self.script, initial_trait_id="athletic")

    def test_initial_state_and_trait(self):
        """驗證初始狀態與特長加成。"""
        char = self.initial_state["character"]
        self.assertEqual(char["employee_id"], "K001")
        self.assertEqual(char["display_name"], "王大明")
        self.assertEqual(char["trait_id"], "athletic")
        # athletic 增加 20 ep 與 3 agility
        self.assertEqual(char["max_ep"], 120)
        self.assertEqual(char["ep"], 120)
        self.assertEqual(char["attributes"]["agility"], 13)
        self.assertEqual(self.initial_state["location_id"], "town_square")
        self.assertEqual(self.initial_state["turn"], 1)
        self.assertEqual(self.initial_state["time_of_day"], "morning")

    def test_npc_staff_collision_uses_fallback(self):
        """當 NPC 角色槽之映射員工與玩家本人相同，應自動使用虛構替代角色避免自己撞到自己。"""
        # K001 映射在 guard_captain (守衛長)
        effective_guard = adventure.get_effective_npc("guard_captain", self.script, self.initial_state)
        self.assertTrue(effective_guard.get("is_fallback"))
        self.assertEqual(effective_guard["name"], "杜恩")

        # 旅店老闆娘映射 K002，與玩家 K001 不同，若無快照則使用替代角色或名稱
        effective_inn = adventure.get_effective_npc("innkeeper", self.script, self.initial_state)
        self.assertTrue(effective_inn["name"] in ("瑪莎", "旅店老闆"))

    def test_time_advances_on_movement(self):
        """移動地點消耗精力並推進回合與時段。"""
        action = {"action": "move", "target_location_id": "cozy_inn"}
        new_state, logs, actions, _ = adventure.advance(self.script, self.initial_state, action)
        self.assertEqual(new_state["location_id"], "cozy_inn")
        self.assertEqual(new_state["turn"], 2)
        self.assertEqual(new_state["time_of_day"], "noon")
        self.assertEqual(new_state["character"]["ep"], 115)  # 120 - 5
        self.assertTrue(any("抵達了【溫暖旅店】" in log["text"] for log in logs))

    def test_leisure_activities(self):
        """生活休閒活動：工坊打工消耗精力賺取金幣；客棧休息恢復 HP/EP。"""
        # 先前往工坊
        state = self.initial_state
        state["location_id"] = "suburb_workshop"
        work_action = {"action": "activity", "activity_id": "work_workshop"}
        state, logs, actions, _ = adventure.advance(self.script, state, work_action)
        self.assertEqual(state["character"]["gold"], 80)  # 50 + 30
        self.assertEqual(state["character"]["ep"], 100)  # 120 - 20
        self.assertEqual(state["turn"], 2)

        # 旅店休息
        state["location_id"] = "cozy_inn"
        state["character"]["hp"] = 50
        state["character"]["ep"] = 20
        rest_action = {"action": "activity", "activity_id": "rest_inn"}
        state, logs, actions, _ = adventure.advance(self.script, state, rest_action)
        self.assertEqual(state["character"]["hp"], state["character"]["max_hp"])
        self.assertEqual(state["character"]["ep"], state["character"]["max_ep"])
        self.assertEqual(state["character"]["gold"], 70)  # 80 - 10

    def test_condition_evaluation(self):
        """條件白名單：數值、物品、旗標、關係與邏輯組合。"""
        state = copy.deepcopy(self.initial_state)
        state["character"]["gold"] = 100
        state["flags"]["quest_started"] = True
        state["relationships"]["guard_captain"] = 25

        self.assertTrue(adventure.evaluate_condition({"field": "gold", "op": ">=", "value": 80}, state))
        self.assertFalse(adventure.evaluate_condition({"field": "gold", "op": "<", "value": 50}, state))
        self.assertTrue(adventure.evaluate_condition({"field": "flag.quest_started", "op": "==", "value": True}, state))
        self.assertTrue(adventure.evaluate_condition({"field": "affinity.guard_captain", "op": ">", "value": 20}, state))

        compound = {
            "all": [
                {"field": "gold", "op": ">=", "value": 80},
                {"field": "location", "op": "==", "value": "town_square"},
            ]
        }
        self.assertTrue(adventure.evaluate_condition(compound, state))

    def test_three_solutions_for_main_gate(self):
        """示範章節可驗收行為：同一個主線目標（通行關卡）具備三種不同解法。"""
        # 解法 1：繳交 80 金幣規費
        state1 = copy.deepcopy(self.initial_state)
        state1["location_id"] = "guard_post"
        state1["character"]["gold"] = 80
        # 觸發對話
        state1, logs, actions, _ = adventure.advance(self.script, state1, {"action": "talk", "npc_id": "guard_captain"})
        self.assertTrue(any(a.get("choice_id") == "pay_toll" for a in actions))
        # 選擇付費
        state1, logs, actions, _ = adventure.advance(self.script, state1, {
            "action": "flow_choice",
            "flow_id": "flow_guard_captain",
            "choice_id": "pay_toll",
            "next_node_id": "toll_success",
            "cost": {"gold": 80},
        })
        self.assertEqual(state1["character"]["gold"], 0)
        self.assertTrue(state1["flags"].get("gate_passed"))
        self.assertEqual(state1["quests"]["pass_the_gate"]["method_used"], "toll_fee")

        # 解法 2：協助旅店老闆娘取得介紹信後通關
        state2 = copy.deepcopy(self.initial_state)
        state2["location_id"] = "cozy_inn"
        state2["flags"]["inn_help_accepted"] = True
        state2["inventory"].append({"item_id": "wild_herb", "count": 2, "equipped": False})
        # 旅店提交草藥
        state2, logs, actions, _ = adventure.advance(self.script, state2, {"action": "talk", "npc_id": "innkeeper"})
        self.assertTrue(any(a.get("choice_id") == "submit_herb" for a in actions))
        state2, logs, actions, _ = adventure.advance(self.script, state2, {
            "action": "flow_choice",
            "flow_id": "flow_innkeeper",
            "choice_id": "submit_herb",
            "next_node_id": "inn_submit_herb",
        })
        # 取得介紹信
        self.assertTrue(any(i["item_id"] == "mayor_letter" for i in state2["inventory"]))
        # 前往關卡出示信件
        state2["location_id"] = "guard_post"
        state2, logs, actions, _ = adventure.advance(self.script, state2, {"action": "talk", "npc_id": "guard_captain"})
        state2, logs, actions, _ = adventure.advance(self.script, state2, {
            "action": "flow_choice",
            "flow_id": "flow_guard_captain",
            "choice_id": "show_letter",
            "next_node_id": "letter_success",
        })
        self.assertTrue(state2["flags"].get("gate_passed"))
        self.assertEqual(state2["quests"]["pass_the_gate"]["method_used"], "recommendation")

        # 解法 3：後山秘密小徑調查通關
        state3 = copy.deepcopy(self.initial_state)
        state3["location_id"] = "suburb_workshop"
        # 調查後山山徑
        state3, logs, actions, _ = adventure.advance(self.script, state3, {
            "action": "interact_object",
            "object_id": "workshop_secret_trail",
        })
        self.assertTrue(any(a.get("choice_id") == "check_trail_agility" for a in actions))
        # 固定高隨機數確保檢定通過
        state3, logs, actions, _ = adventure.advance(
            self.script,
            state3,
            {
                "action": "flow_choice",
                "flow_id": "flow_secret_trail",
                "choice_id": "check_trail_agility",
                "next_node_id": "check_trail_agi",
            },
            random_source=lambda: 0.1,  # 擲出 10%
        )
        self.assertTrue(state3["flags"].get("gate_passed"))
        self.assertEqual(state3["quests"]["pass_the_gate"]["method_used"], "secret_trail")
        self.assertTrue(any(i["item_id"] == "unknown_fragment" for i in state3["inventory"]))

    def test_flowchart_100_step_limit(self):
        """流程圖防止死循環：無等待點之自動循環推進超過 100 步時應主動拋出例外。"""
        infinite_script = copy.deepcopy(self.script)
        infinite_script["flowcharts"]["infinite_loop"] = {
            "id": "infinite_loop",
            "name": "死循環測試",
            "nodes": {
                "start": {"type": "start", "next_node_id": "loop_a"},
                "loop_a": {"type": "narrative", "text": "環節 A", "next_node_id": "loop_b"},
                "loop_b": {"type": "narrative", "text": "環節 B", "next_node_id": "loop_a"},
            },
        }
        with self.assertRaises(adventure.FlowchartLimitExceeded):
            adventure.step_flowchart(infinite_script, self.initial_state, "infinite_loop", "start", random_fn=lambda: 0.5)

    def test_combat_flow_and_no_death_deletion(self):
        """戰鬥系統：支援攻擊、生命歸零安全送回旅店恢復，不刪除存檔。"""
        state = copy.deepcopy(self.initial_state)
        state["combat"] = {
            "enemy_id": "test_monster",
            "enemy_name": "測試怪獸",
            "enemy_hp": 10,
            "enemy_max_hp": 10,
            "enemy_atk": 100,  # 極高攻擊力使玩家倒下
            "enemy_def": 0,
            "enemy_agility": 5,
            "round": 1,
            "win_node_id": "",
            "lose_node_id": "",
            "escape_node_id": "",
            "flow_id": "",
        }
        state["character"]["hp"] = 10
        state["character"]["gold"] = 25

        # 玩家防禦，敵方回合玩家倒下
        new_state, logs, actions, _ = adventure.advance(self.script, state, {
            "action": "combat_action",
            "subaction": "defend",
        })
        self.assertIsNone(new_state["combat"])
        # 安全送到旅店，生命與精力恢復至 30，金幣扣除 10 醫藥費
        self.assertEqual(new_state["location_id"], "cozy_inn")
        self.assertEqual(new_state["character"]["hp"], 30)
        self.assertEqual(new_state["character"]["ep"], 30)
        self.assertEqual(new_state["character"]["gold"], 15)

    def test_draft_validation(self):
        """劇本靜態驗證器：缺少出口、無效節點或缺少 NPC 替代角色應回傳明確錯誤。"""
        # 正確示範章節應無錯誤
        errors = adventure.validate_draft(self.script)
        self.assertEqual(len(errors), 0)

        # 破壞劇本：刪除 NPC fallback
        bad_script = copy.deepcopy(self.script)
        bad_script["npcs"]["guard_captain"]["fallback_character"] = None
        errors = adventure.validate_draft(bad_script)
        self.assertTrue(any("缺少虛構替代角色" in e for e in errors))

        # 破壞劇本：懸空出口
        bad_script2 = copy.deepcopy(self.script)
        bad_script2["flowcharts"]["flow_guard_captain"]["nodes"]["start"]["next_node_id"] = "non_existent_node"
        errors2 = adventure.validate_draft(bad_script2)
        self.assertTrue(any("指向不存在的節點" in e for e in errors2))


class AdventureRegressionTests(unittest.TestCase):
    def setUp(self):
        self.script = adventure.create_demo_chapter()
        self.state = adventure.create_initial_state({"employee_id": "PLAYER"}, self.script)

    def test_forged_flow_and_negative_cost_cannot_unlock_gate(self):
        original = copy.deepcopy(self.state)
        with self.assertRaises(adventure.InvalidActionError):
            adventure.advance(self.script, self.state, {
                "action": "flow_choice", "flow_id": "flow_guard_captain",
                "next_node_id": "toll_success", "cost": {"gold": -1000},
            })
        self.assertEqual(self.state, original)

    def test_cost_comes_from_current_choice_not_request(self):
        self.state["location_id"] = "guard_post"
        self.state["character"]["gold"] = 80
        state, _, _, _ = adventure.advance(self.script, self.state, {"action": "talk", "npc_id": "guard_captain"})
        state, _, _, _ = adventure.advance(self.script, state, {
            "action": "flow_choice", "choice_id": "pay_toll", "cost": {"gold": -1000},
        })
        self.assertEqual(state["character"]["gold"], 0)
        self.assertTrue(state["flags"]["gate_passed"])

    def test_remote_npc_and_hidden_activity_rejected(self):
        with self.assertRaises(adventure.InvalidActionError):
            adventure.advance(self.script, self.state, {"action": "talk", "npc_id": "guard_captain"})
        self.script["locations"]["town_square"]["activities"] = [{
            "id": "locked", "condition": {"field": "gold", "op": ">", "value": 9999},
            "effects": [{"type": "modify_stat", "stat": "gold", "value": 100}],
        }]
        with self.assertRaises(adventure.InvalidActionError):
            adventure.advance(self.script, self.state, {"action": "activity", "activity_id": "locked"})

    def test_dialogue_prevents_movement_and_equipped_gifts(self):
        self.state["location_id"] = "cozy_inn"
        state, _, _, _ = adventure.advance(self.script, self.state, {"action": "talk", "npc_id": "innkeeper"})
        with self.assertRaises(adventure.InvalidActionError):
            adventure.advance(self.script, state, {"action": "move", "target_location_id": "town_square"})
        self.state["location_id"] = "suburb_workshop"
        state, _, _, _ = adventure.advance(self.script, self.state, {"action": "equip_item", "item_id": "worn_dagger"})
        with self.assertRaises(adventure.InvalidActionError):
            adventure.advance(self.script, state, {"action": "gift_item", "npc_id": "artisan", "item_id": "worn_dagger"})

    def test_validator_rejects_bad_graphs_and_costs(self):
        for node in ({"type": "unsupported"}, {"type": "narrative"}, {"type": "start", "next_node_id": "start"}):
            with self.subTest(node=node):
                script = copy.deepcopy(self.script)
                script["flowcharts"] = {"bad": {"nodes": {"start": node}}}
                self.assertTrue(adventure.validate_draft(script))
        self.script["locations"]["cozy_inn"]["activities"][0]["cost"]["gold"] = -1
        self.assertTrue(adventure.validate_draft(self.script))

    def test_unknown_trait_rejected_and_logs_bounded(self):
        with self.assertRaises(adventure.InvalidActionError):
            adventure.create_initial_state({}, self.script, "forged")
        self.state["recent_logs"] = [{"text": "old"}] * 1000
        state, _, _, _ = adventure.advance(self.script, self.state, {"action": "move", "target_location_id": "cozy_inn"})
        self.assertLessEqual(len(state["recent_logs"]), 50)

    def test_zero_percent_check_never_succeeds(self):
        self.script["flowcharts"] = {"test": {"nodes": {
            "start": {"type": "check", "base_chance": 0, "stat_coeff": 0, "success_node_id": "yes", "fail_node_id": "no"},
            "yes": {"type": "end"}, "no": {"type": "end"},
        }}}
        logs, _ = adventure.step_flowchart(self.script, self.state, "test", "start", lambda: 0)
        self.assertFalse(logs[0]["success"])

    def test_test_runner_preserves_state_and_random_progress(self):
        first = adventure.simulate_test_run(self.script, None, {"action": "move", "target_location_id": "cozy_inn"})
        second = adventure.simulate_test_run(self.script, first["new_state"], {"action": "move", "target_location_id": "town_square"})
        self.assertEqual(second["new_state"]["turn"], 3)
        self.assertEqual(second["new_state"]["location_id"], "town_square")


if __name__ == "__main__":
    unittest.main()
