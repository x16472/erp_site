"""穿越冒險與休閒 RPG 規則引擎與劇本驗證器。

純邏輯模組，不直接存取資料庫或網路。
規則運算、事件推進、戰鬥、試跑與劇本驗證共用同一核心。
"""

from __future__ import annotations

import copy
import math
import random
import re
from typing import Any, Callable

TIME_PHASES = ["morning", "noon", "dusk", "night"]
TIME_PHASE_NAMES = {
    "morning": "清晨",
    "noon": "正午",
    "dusk": "傍晚",
    "night": "深夜",
}


class AdventureError(ValueError):
    """冒險引擎一般錯誤。"""


class FlowchartLimitExceeded(AdventureError):
    """流程自動推進超過單次上限（防止死循環）。"""


class InvalidActionError(AdventureError):
    """非法或不合法的玩家行動。"""


class ValidationError(AdventureError):
    """劇本草稿驗證失敗。"""


def get_time_of_day(turn: int) -> str:
    """依回合數計算時段（每回合推進一時段，4 回合為一日）。"""
    return TIME_PHASES[(max(1, turn) - 1) % len(TIME_PHASES)]


def create_initial_state(
    employee_snapshot: dict[str, Any],
    script: dict[str, Any],
    initial_trait_id: str = "",
) -> dict[str, Any]:
    """建立存檔的初始狀態。"""
    base_hp = 100
    base_ep = 100
    base_gold = 50
    base_atk = 10
    base_def = 5
    attributes = {"strength": 10, "agility": 10, "intellect": 10, "charisma": 10}

    # 套用特長修正
    traits_list = script.get("traits", [])
    selected_trait = next((t for t in traits_list if t.get("id") == initial_trait_id), None)
    if initial_trait_id and selected_trait is None:
        raise InvalidActionError("此版本沒有指定的初始特長。")
    trait_name = ""
    if selected_trait:
        trait_name = selected_trait.get("name", "")
        modifiers = selected_trait.get("modifiers", {})
        base_hp += modifiers.get("hp", 0)
        base_ep += modifiers.get("ep", 0)
        base_gold += modifiers.get("gold", 0)
        base_atk += modifiers.get("atk", 0)
        base_def += modifiers.get("def", 0)
        for stat, delta in modifiers.get("attributes", {}).items():
            attributes[stat] = attributes.get(stat, 10) + delta

    start_location = script.get("start_location_id", "town_square")
    initial_inventory = copy.deepcopy(script.get("initial_inventory", []))

    state = {
        "turn": 1,
        "time_of_day": "morning",
        "location_id": start_location,
        "character": {
            "employee_id": employee_snapshot.get("employee_id", ""),
            "display_name": employee_snapshot.get("display_name", "冒險者"),
            "department": employee_snapshot.get("department", "未指定"),
            "position": employee_snapshot.get("position", "員工"),
            "photo_file": employee_snapshot.get("photo_file", ""),
            "trait_id": initial_trait_id,
            "trait_name": trait_name,
            "hp": base_hp,
            "max_hp": base_hp,
            "ep": base_ep,
            "max_ep": base_ep,
            "gold": base_gold,
            "atk": base_atk,
            "def": base_def,
            "attributes": attributes,
        },
        "inventory": initial_inventory,  # list of {"item_id": str, "count": int, "equipped": bool}
        "equipment": {"weapon": "", "armor": "", "accessory": ""},
        "relationships": {},  # npc_id -> affinity int
        "quests": {
            # quest_id -> {"stage": int, "completed": bool, "method_used": str}
        },
        "flags": {},  # flag_key -> bool/int/str
        "clues": [],  # list of clue_id
        "discovered_locations": [start_location],
        "interaction": None,  # None or {"flow_id": str, "node_id": str, "speaker": str}
        "combat": None,  # None or combat state dict
        "recent_logs": [
            {
                "turn": 1,
                "text": f"你穿越到了未知的世界，環顧四周，抵達了【{script.get('locations', {}).get(start_location, {}).get('name', '此地')}】。",
                "type": "narrative",
            }
        ],
    }

    # 初始化 NPC 初始好感度
    for npc_id, npc_data in script.get("npcs", {}).items():
        state["relationships"][npc_id] = int(npc_data.get("initial_affinity", 0))

    # 初始化起始任務
    for quest_id, quest_data in script.get("quests", {}).items():
        if quest_data.get("auto_start", False):
            state["quests"][quest_id] = {"stage": 1, "completed": False, "method_used": ""}

    return state


def get_effective_npc(npc_id: str, script: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """取得 NPC 當前有效資料（若映射員工與玩家本人相同，自動替換為虛構替代角色）。"""
    npc_data = script.get("npcs", {}).get(npc_id, {})
    if not npc_data:
        return {"id": npc_id, "name": "神秘旅人", "title": "路人", "bio": "一位神秘的過客。"}

    player_emp_id = state.get("character", {}).get("employee_id", "")
    mapped_emp_id = npc_data.get("mapped_employee_id", "")

    # 若員工編號與玩家相同，使用替代角色避免本人與自己重複出現
    if mapped_emp_id and mapped_emp_id == player_emp_id:
        fallback = npc_data.get("fallback_character", {})
        return {
            "id": npc_id,
            "name": fallback.get("name", npc_data.get("slot_name", "替代角色")),
            "title": fallback.get("title", "地方居民"),
            "bio": fallback.get("bio", "故事中的居民。"),
            "photo_file": fallback.get("photo_file", ""),
            "is_fallback": True,
            "dialogue_flow_id": npc_data.get("dialogue_flow_id", ""),
        }

    # 若有映射員工且非本人，且腳本帶有映射員工快照
    staff_snapshot = npc_data.get("mapped_employee_snapshot")
    if staff_snapshot:
        return {
            "id": npc_id,
            "name": staff_snapshot.get("display_name", npc_data.get("slot_name", "同事")),
            "title": npc_data.get("slot_name", staff_snapshot.get("position", "同事")),
            "bio": npc_data.get("bio", f"在故事世界中擔任{npc_data.get('slot_name', '要職')}。"),
            "photo_file": staff_snapshot.get("photo_file", ""),
            "is_fallback": False,
            "dialogue_flow_id": npc_data.get("dialogue_flow_id", ""),
        }

    # 預設使用作者配置的 NPC 內容
    fallback = npc_data.get("fallback_character", {})
    return {
        "id": npc_id,
        "name": fallback.get("name", npc_data.get("slot_name", "人物")),
        "title": fallback.get("title", npc_data.get("slot_name", "居民")),
        "bio": fallback.get("bio", npc_data.get("bio", "")),
        "photo_file": fallback.get("photo_file", ""),
        "is_fallback": True,
        "dialogue_flow_id": npc_data.get("dialogue_flow_id", ""),
    }


def evaluate_single_condition(cond: dict[str, Any], state: dict[str, Any]) -> bool:
    """計算單一白名單條件。"""
    field = cond.get("field", "")
    op = cond.get("op", "==")
    expected = cond.get("value")

    # 取得實際值
    actual = None
    char = state.get("character", {})
    if field in ("hp", "max_hp", "ep", "max_ep", "gold", "atk", "def"):
        actual = char.get(field, 0)
    elif field.startswith("stat."):
        stat_name = field.split(".", 1)[1]
        actual = char.get("attributes", {}).get(stat_name, 0)
    elif field.startswith("item."):
        item_id = field.split(".", 1)[1]
        actual = sum(
            entry.get("count", 0) for entry in state.get("inventory", []) if entry.get("item_id") == item_id
        )
    elif field.startswith("flag."):
        flag_key = field.split(".", 1)[1]
        actual = state.get("flags", {}).get(flag_key, False)
    elif field.startswith("quest."):
        parts = field.split(".")
        quest_id = parts[1]
        prop = parts[2] if len(parts) > 2 else "stage"
        q_data = state.get("quests", {}).get(quest_id, {})
        actual = q_data.get(prop, 0 if prop == "stage" else False)
    elif field.startswith("affinity."):
        npc_id = field.split(".", 1)[1]
        actual = state.get("relationships", {}).get(npc_id, 0)
    elif field == "location":
        actual = state.get("location_id", "")
    elif field == "time_of_day":
        actual = state.get("time_of_day", "")
    elif field == "turn":
        actual = state.get("turn", 1)
    else:
        return False

    # 執行運算子比較
    try:
        if op == "==":
            return actual == expected
        elif op == "!=":
            return actual != expected
        elif op == ">":
            return float(actual) > float(expected)
        elif op == ">=":
            return float(actual) >= float(expected)
        elif op == "<":
            return float(actual) < float(expected)
        elif op == "<=":
            return float(actual) <= float(expected)
        elif op == "in":
            return actual in expected
        elif op == "contains":
            return expected in actual
    except (TypeError, ValueError):
        return False

    return False


def evaluate_condition(cond: dict[str, Any] | None, state: dict[str, Any]) -> bool:
    """計算條件結構（支援 all/any/none 與單條件）。"""
    if not cond:
        return True

    if "all" in cond:
        return all(evaluate_condition(c, state) for c in cond["all"])
    if "any" in cond:
        return any(evaluate_condition(c, state) for c in cond["any"])
    if "none" in cond:
        return not any(evaluate_condition(c, state) for c in cond["none"])

    return evaluate_single_condition(cond, state)


def render_narrative_template(template: str, script: dict[str, Any], state: dict[str, Any], context: dict[str, Any] | None = None) -> str:
    """敘事文字安全變數替換。"""
    ctx = context or {}
    char = state.get("character", {})
    loc_id = state.get("location_id", "")
    loc_name = script.get("locations", {}).get(loc_id, {}).get("name", "目前地點")

    speaker_name = ctx.get("speaker_name", "")
    if not speaker_name and "npc_id" in ctx:
        effective_npc = get_effective_npc(ctx["npc_id"], script, state)
        speaker_name = effective_npc.get("name", "人物")

    replacements = {
        "{player_name}": char.get("display_name", "冒險者"),
        "{player_department}": char.get("department", ""),
        "{player_position}": char.get("position", ""),
        "{location_name}": loc_name,
        "{time_of_day}": TIME_PHASE_NAMES.get(state.get("time_of_day", ""), "白天"),
        "{speaker_name}": speaker_name,
        "{turn}": str(state.get("turn", 1)),
        "{gold}": str(char.get("gold", 0)),
    }

    text = template
    for key, val in replacements.items():
        text = text.replace(key, str(val))
    return text


def apply_effect(effect: dict[str, Any], script: dict[str, Any], state: dict[str, Any]) -> str:
    """執行白名單效果，回傳文字紀錄。"""
    effect_type = effect.get("type", "")
    char = state["character"]
    msg = ""

    if effect_type == "modify_stat":
        stat = effect.get("stat", "")
        value = int(effect.get("value", 0))
        if stat == "hp":
            char["hp"] = max(0, min(char["max_hp"], char["hp"] + value))
            msg = f"生命 {'+' if value >= 0 else ''}{value}（目前 {char['hp']}/{char['max_hp']}）"
        elif stat == "ep":
            char["ep"] = max(0, min(char["max_ep"], char["ep"] + value))
            msg = f"精力 {'+' if value >= 0 else ''}{value}（目前 {char['ep']}/{char['max_ep']}）"
        elif stat == "gold":
            char["gold"] = max(0, char["gold"] + value)
            msg = f"金幣 {'+' if value >= 0 else ''}{value}（目前 {char['gold']} 金幣）"
        elif stat in ("atk", "def"):
            char[stat] = max(0, char[stat] + value)
            msg = f"{'攻擊力' if stat == 'atk' else '防禦力'} {'+' if value >= 0 else ''}{value}"
        elif stat in ("strength", "agility", "intellect", "charisma"):
            attrs = char.setdefault("attributes", {})
            attrs[stat] = max(1, attrs.get(stat, 10) + value)
            stat_names = {"strength": "力量", "agility": "敏捷", "intellect": "智力", "charisma": "魅力"}
            msg = f"屬性【{stat_names.get(stat, stat)}】{'+' if value >= 0 else ''}{value}"

    elif effect_type == "add_item":
        item_id = effect.get("item_id", "")
        count = int(effect.get("count", 1))
        item_def = script.get("items", {}).get(item_id, {})
        item_name = item_def.get("name", item_id)
        # 尋找是否已有該物品
        existing = next((i for i in state["inventory"] if i["item_id"] == item_id), None)
        if existing:
            existing["count"] += count
        else:
            state["inventory"].append({"item_id": item_id, "count": count, "equipped": False})
        msg = f"獲得物品：【{item_name}】x{count}"

    elif effect_type == "remove_item":
        item_id = effect.get("item_id", "")
        count = int(effect.get("count", 1))
        item_def = script.get("items", {}).get(item_id, {})
        item_name = item_def.get("name", item_id)
        existing = next((i for i in state["inventory"] if i["item_id"] == item_id), None)
        if existing:
            existing["count"] = max(0, existing["count"] - count)
            if existing["count"] == 0:
                if existing.get("equipped"):
                    slot = item_def.get("type")
                    if state.get("equipment", {}).get(slot) == item_id:
                        state["equipment"][slot] = ""
                        for stat in ("atk", "def"):
                            char[stat] = max(0, char[stat] - item_def.get("modifiers", {}).get(stat, 0))
                state["inventory"] = [i for i in state["inventory"] if i["item_id"] != item_id]
        msg = f"失去物品：【{item_name}】x{count}"

    elif effect_type == "change_affinity":
        npc_id = effect.get("npc_id", "")
        value = int(effect.get("value", 0))
        effective_npc = get_effective_npc(npc_id, script, state)
        npc_name = effective_npc.get("name", npc_id)
        current = state["relationships"].get(npc_id, 0)
        state["relationships"][npc_id] = current + value
        msg = f"與【{npc_name}】的好感度 {'+' if value >= 0 else ''}{value}"

    elif effect_type == "set_flag":
        flag = effect.get("flag", "")
        val = effect.get("value", True)
        state.setdefault("flags", {})[flag] = val

    elif effect_type == "set_quest_stage":
        quest_id = effect.get("quest_id", "")
        stage = int(effect.get("stage", 1))
        quest_def = script.get("quests", {}).get(quest_id, {})
        q_name = quest_def.get("name", quest_id)
        q = state.setdefault("quests", {}).setdefault(quest_id, {"stage": 1, "completed": False, "method_used": ""})
        q["stage"] = stage
        msg = f"任務進展：【{q_name}】進入第 {stage} 階段"

    elif effect_type == "complete_quest":
        quest_id = effect.get("quest_id", "")
        method_used = effect.get("method_used", "")
        quest_def = script.get("quests", {}).get(quest_id, {})
        q_name = quest_def.get("name", quest_id)
        q = state.setdefault("quests", {}).setdefault(quest_id, {"stage": 1, "completed": False, "method_used": ""})
        q["completed"] = True
        q["method_used"] = method_used
        msg = f"★ 達成任務：【{q_name}】！"

    elif effect_type == "move_location":
        loc_id = effect.get("location_id", "")
        loc_def = script.get("locations", {}).get(loc_id, {})
        loc_name = loc_def.get("name", loc_id)
        state["location_id"] = loc_id
        if loc_id not in state["discovered_locations"]:
            state["discovered_locations"].append(loc_id)
        msg = f"前往地點：【{loc_name}】"

    elif effect_type == "add_clue":
        clue_id = effect.get("clue_id", "")
        if clue_id and clue_id not in state["clues"]:
            state["clues"].append(clue_id)
            clue_title = effect.get("title", clue_id)
            msg = f"發現重要線索：【{clue_title}】"

    elif effect_type == "end_interaction":
        state["interaction"] = None

    return msg


def step_flowchart(
    script: dict[str, Any],
    state: dict[str, Any],
    flow_id: str,
    node_id: str,
    random_fn: Callable[[], float],
    step_budget: int = 100,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """遍歷流程圖的自動節點，直到遇到 choice、combat 或 end 停止。

    回傳：(產生的日誌列表, 當前停頓的節點資料或 None)
    """
    flow = script.get("flowcharts", {}).get(flow_id, {})
    nodes = flow.get("nodes", {})
    logs: list[dict[str, Any]] = []
    current_node_id = node_id
    steps = 0

    while current_node_id and steps < step_budget:
        steps += 1
        node = nodes.get(current_node_id)
        if not node:
            raise ValidationError(f"流程 {flow_id} 引用不存在的節點 {current_node_id}。")

        node_type = node.get("type")

        if node_type == "start":
            current_node_id = node.get("next_node_id", "")

        elif node_type == "narrative":
            text = render_narrative_template(node.get("text", ""), script, state, {"speaker_name": node.get("speaker", "")})
            logs.append({"turn": state["turn"], "text": text, "type": "dialogue", "speaker": node.get("speaker", "")})
            # 如果是自動流程節點，繼續下一節點；如果有明確設定 wait_click 則停在該節點（首版預設自動串接或轉為 choice）
            if node.get("wait_input", False):
                state["interaction"] = {"flow_id": flow_id, "node_id": current_node_id}
                return logs, node
            current_node_id = node.get("next_node_id", "")

        elif node_type == "choice":
            # 等待玩家選擇，停在此節點
            state["interaction"] = {"flow_id": flow_id, "node_id": current_node_id}
            return logs, node

        elif node_type == "condition":
            cond = node.get("condition")
            passed = evaluate_condition(cond, state)
            current_node_id = node.get("next_node_true") if passed else node.get("next_node_false")

        elif node_type == "check":
            # 屬性判定節點
            stat_name = node.get("stat", "agility")
            char_stat = state["character"].get("attributes", {}).get(stat_name, 10)
            base_chance = float(node.get("base_chance", 50))  # 基礎機率百分比
            stat_coeff = float(node.get("stat_coeff", 2.0))  # 每點屬性增加機率
            situational_mod = float(node.get("situational_mod", 0.0))  # 情境修正

            total_chance = max(0.0, min(100.0, base_chance + (char_stat - 10) * stat_coeff + situational_mod))
            roll = random_fn() * 100.0
            success = roll < total_chance

            stat_labels = {"strength": "力量", "agility": "敏捷", "intellect": "智力", "charisma": "魅力"}
            check_name = stat_labels.get(stat_name, stat_name)
            logs.append({
                "turn": state["turn"],
                "text": f"進行【{check_name}】檢定（成功率 {total_chance:.0f}%，擲出 {roll:.0f}）：{'★ 成功！' if success else '✗ 失敗…'}",
                "type": "check",
                "success": success,
            })
            current_node_id = node.get("success_node_id") if success else node.get("fail_node_id")

        elif node_type == "random":
            # 隨機分支
            branches = node.get("branches", [])
            total_weight = sum(b.get("weight", 1) for b in branches)
            if total_weight <= 0:
                current_node_id = node.get("next_node_id", "")
            else:
                target_weight = random_fn() * total_weight
                accum = 0.0
                selected_next = ""
                for b in branches:
                    accum += b.get("weight", 1)
                    if accum >= target_weight:
                        selected_next = b.get("next_node_id", "")
                        break
                current_node_id = selected_next or node.get("next_node_id", "")

        elif node_type == "effect":
            effects = node.get("effects", [])
            for eff in effects:
                eff_msg = apply_effect(eff, script, state)
                if eff_msg:
                    logs.append({"turn": state["turn"], "text": eff_msg, "type": "effect"})
            current_node_id = node.get("next_node_id", "")

        elif node_type == "combat":
            # 啟動戰鬥
            enemy_id = node.get("enemy_id", "")
            enemy_def = script.get("enemies", {}).get(enemy_id, {})
            state["combat"] = {
                "enemy_id": enemy_id,
                "enemy_name": enemy_def.get("name", "敵人"),
                "enemy_hp": enemy_def.get("hp", 50),
                "enemy_max_hp": enemy_def.get("hp", 50),
                "enemy_atk": enemy_def.get("atk", 10),
                "enemy_def": enemy_def.get("def", 2),
                "enemy_agility": enemy_def.get("agility", 8),
                "round": 1,
                "win_node_id": node.get("win_node_id", ""),
                "lose_node_id": node.get("lose_node_id", ""),
                "escape_node_id": node.get("escape_node_id", ""),
                "flow_id": flow_id,
            }
            state["interaction"] = None
            logs.append({
                "turn": state["turn"],
                "text": f"遭遇戰鬥！對手是【{state['combat']['enemy_name']}】！",
                "type": "combat",
            })
            return logs, node

        elif node_type == "end":
            end_type = node.get("end_type", "return_to_exploration")
            if end_type == "game_ending":
                ending_id = node.get("ending_id", "default")
                state["flags"]["game_ended"] = True
                state["flags"]["ending_id"] = ending_id
                logs.append({
                    "turn": state["turn"],
                    "text": f"=== 冒險章節達成結局：{node.get('ending_title', '章節終幕')} ===",
                    "type": "ending",
                })
            state["interaction"] = None
            return logs, node

        else:
            raise ValidationError(f"未知節點型別：{node_type}")

    if current_node_id and steps >= step_budget:
        raise FlowchartLimitExceeded(f"流程【{flow_id}】自節點【{node_id}】推進超過單次上限 ({step_budget} 步)，請檢查是否有無等待點的死循環。")

    return logs, None


def get_available_actions(script: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    """計算並回傳當下合法的玩家操作。"""
    actions: list[dict[str, Any]] = []
    if state.get("flags", {}).get("game_ended"):
        return actions

    # 1. 若處於戰鬥狀態，只能執行戰鬥行動
    if state.get("combat"):
        combat = state["combat"]
        actions.append({"id": "combat_attack", "action": "combat_action", "subaction": "attack", "label": "普通攻擊", "desc": "以武器直接攻擊敵人"})
        # 技能
        if state["character"]["ep"] >= 15:
            actions.append({"id": "combat_skill_strike", "action": "combat_action", "subaction": "skill", "skill_id": "heavy_strike", "label": "重擊（耗 15 精力）", "desc": "造成 1.5 倍傷害"})
        if state["character"]["ep"] >= 20:
            actions.append({"id": "combat_skill_heal", "action": "combat_action", "subaction": "skill", "skill_id": "first_aid", "label": "急救包紮（耗 20 精力）", "desc": "恢復 25 點生命"})
        # 戰鬥可用物品（藥草等）
        for item in state.get("inventory", []):
            item_def = script.get("items", {}).get(item["item_id"], {})
            if item_def.get("type") == "consumable" and item.get("count", 0) > 0:
                actions.append({
                    "id": f"combat_item_{item['item_id']}",
                    "action": "combat_action",
                    "subaction": "item",
                    "item_id": item["item_id"],
                    "label": f"使用【{item_def.get('name')}】(剩餘 {item['count']})",
                })
        actions.append({"id": "combat_defend", "action": "combat_action", "subaction": "defend", "label": "專注防禦", "desc": "暫時提升防禦並恢復 10 精力"})
        actions.append({"id": "combat_escape", "action": "combat_action", "subaction": "escape", "label": "嘗試逃跑", "desc": "依敏捷判定是否成功脫離戰鬥"})
        return actions

    # 2. 若處於局部流程圖或對話互動
    if state.get("interaction"):
        interaction = state["interaction"]
        flow_id = interaction.get("flow_id", "")
        node_id = interaction.get("node_id", "")
        flow = script.get("flowcharts", {}).get(flow_id, {})
        node = flow.get("nodes", {}).get(node_id, {})

        if node.get("type") == "choice":
            choices = node.get("choices", [])
            for c in choices:
                # 檢查選項條件
                c_cond = c.get("condition")
                if c_cond and not evaluate_condition(c_cond, state):
                    continue
                actions.append({
                    "id": f"choice_{c.get('id', c.get('next_node_id'))}",
                    "action": "flow_choice",
                    "flow_id": flow_id,
                    "choice_id": c.get("id"),
                    "next_node_id": c.get("next_node_id"),
                    "label": render_narrative_template(c.get("label", "繼續"), script, state),
                    "cost": c.get("cost", {}),
                })
            # 如果選項都不可行或作者未提供，提供安全返回選項
            if not actions:
                actions.append({
                    "id": "choice_exit",
                    "action": "flow_choice",
                    "flow_id": flow_id,
                    "next_node_id": "",
                    "label": "結束對話返回探索",
                })
            return actions

        if node.get("type") == "narrative" and node.get("wait_input"):
            return [{"id": "continue", "action": "flow_choice", "flow_id": flow_id,
                     "next_node_id": node.get("next_node_id", ""), "label": "繼續"}]
        return []

    # 3. 一般自由探索狀態
    current_loc_id = state.get("location_id", "")
    current_loc = script.get("locations", {}).get(current_loc_id, {})
    current_time = state.get("time_of_day", "morning")

    # 3.1 移動地點
    exits = current_loc.get("exits", [])
    for exit_id in exits:
        exit_loc = script.get("locations", {}).get(exit_id, {})
        actions.append({
            "id": f"move_{exit_id}",
            "action": "move",
            "target_location_id": exit_id,
            "label": f"前往【{exit_loc.get('name', exit_id)}】",
            "desc": exit_loc.get("description", ""),
            "cost": {"turn": 1, "ep": 5},
        })

    # 3.2 與目前地點的 NPC 互動
    for npc_id, npc_data in script.get("npcs", {}).items():
        schedule = npc_data.get("schedule", {})
        npc_loc = schedule.get(current_time, schedule.get("default", ""))
        if npc_loc == current_loc_id:
            effective_npc = get_effective_npc(npc_id, script, state)
            actions.append({
                "id": f"talk_{npc_id}",
                "action": "talk",
                "npc_id": npc_id,
                "label": f"與【{effective_npc.get('name')}】交談",
                "desc": f"{effective_npc.get('title')} - {effective_npc.get('bio')}",
            })
            # 送禮選項（如果背包有物品）
            for item in state.get("inventory", []):
                if item.get("count", 0) > 0 and not item.get("equipped", False):
                    item_def = script.get("items", {}).get(item["item_id"], {})
                    actions.append({
                        "id": f"gift_{npc_id}_{item['item_id']}",
                        "action": "gift_item",
                        "npc_id": npc_id,
                        "item_id": item["item_id"],
                        "label": f"贈送【{item_def.get('name')}】給 {effective_npc.get('name')}",
                    })

    # 3.3 地點可調查物件
    for obj in current_loc.get("objects", []):
        cond = obj.get("condition")
        if cond and not evaluate_condition(cond, state):
            continue
        actions.append({
            "id": f"object_{obj.get('id')}",
            "action": "interact_object",
            "object_id": obj.get("id"),
            "label": f"調查【{obj.get('name')}】",
            "desc": obj.get("description", ""),
        })

    # 3.4 生活休閒活動
    for act in current_loc.get("activities", []):
        cond = act.get("condition")
        if cond and not evaluate_condition(cond, state):
            continue
        actions.append({
            "id": f"act_{act.get('id')}",
            "action": "activity",
            "activity_id": act.get("id"),
            "label": act.get("name", "活動"),
            "desc": act.get("description", ""),
            "cost": act.get("cost", {}),
        })

    # 3.5 背包物品使用與裝備
    for item in state.get("inventory", []):
        if item.get("count", 0) <= 0:
            continue
        item_def = script.get("items", {}).get(item["item_id"], {})
        item_type = item_def.get("type", "misc")
        if item_type == "consumable":
            actions.append({
                "id": f"use_{item['item_id']}",
                "action": "use_item",
                "item_id": item["item_id"],
                "label": f"使用【{item_def.get('name')}】",
                "desc": item_def.get("description", ""),
            })
        elif item_type in ("weapon", "armor", "accessory"):
            is_equipped = item.get("equipped", False)
            actions.append({
                "id": f"{'unequip' if is_equipped else 'equip'}_{item['item_id']}",
                "action": "equip_item",
                "item_id": item["item_id"],
                "slot": item_type,
                "label": f"{'卸下' if is_equipped else '裝備'}【{item_def.get('name')}】",
                "desc": item_def.get("description", ""),
            })

    return actions


def advance(
    script_snapshot: dict[str, Any],
    save_state: dict[str, Any],
    player_action: dict[str, Any],
    random_source: Callable[[], float] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """從伺服器可用行動解析規則，禁止客戶端指定成本與流程出口。"""
    if not isinstance(player_action, dict):
        raise InvalidActionError("行動格式錯誤。")
    keys = ("action", "subaction", "skill_id", "item_id", "npc_id",
            "target_location_id", "object_id", "activity_id", "choice_id")
    candidates = get_available_actions(script_snapshot, save_state)
    chosen = None
    for candidate in candidates:
        if player_action.get("id") and candidate.get("id") != player_action["id"]:
            continue
        if any(player_action.get(k) != candidate.get(k) for k in keys):
            continue
        if player_action.get("flow_id") not in (None, candidate.get("flow_id")):
            continue
        if player_action.get("next_node_id") not in (None, candidate.get("next_node_id")):
            continue
        chosen = candidate
        break
    if chosen is None:
        raise InvalidActionError("此行動目前不可用，請重新讀取場景。")
    draws = []
    source = random_source or random.random
    def draw():
        value = source()
        draws.append(value)
        return value
    state, logs, actions, rolls = _advance(script_snapshot, save_state, chosen, draw)
    state["recent_logs"] = state.get("recent_logs", [])[-50:]
    met = set(state.get("met_npcs", []))
    if chosen.get("npc_id"):
        met.add(chosen["npc_id"])
    state["met_npcs"] = sorted(met)
    rolls["draws"] = draws
    return state, logs, actions, rolls


def _advance(
    script_snapshot: dict[str, Any],
    save_state: dict[str, Any],
    player_action: dict[str, Any],
    random_source: Callable[[], float] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """核心介面：推展一回合冒險。

    回傳：(new_state, new_logs, available_actions, roll_result)
    """
    random_fn = random_source if random_source is not None else random.random
    state = copy.deepcopy(save_state)
    new_logs: list[dict[str, Any]] = []
    roll_result: dict[str, Any] = {}

    action_type = player_action.get("action", "")

    # ==========================================
    # 戰鬥行動處理
    # ==========================================
    if state.get("combat"):
        if action_type != "combat_action":
            raise InvalidActionError("處於戰鬥狀態中，僅允許戰鬥行動。")

        subaction = player_action.get("subaction", "")
        combat = state["combat"]
        char = state["character"]
        enemy_name = combat.get("enemy_name", "敵人")

        # 玩家回合
        player_damage = 0
        defend_active = False

        if subaction == "attack":
            player_atk = char["atk"]
            enemy_def = combat["enemy_def"]
            # 武器攻擊加成
            player_damage = max(1, player_atk - enemy_def)
            combat["enemy_hp"] = max(0, combat["enemy_hp"] - player_damage)
            new_logs.append({
                "turn": state["turn"],
                "text": f"你向【{enemy_name}】發動攻擊，造成 {player_damage} 點傷害！（敵人剩餘 HP: {combat['enemy_hp']}/{combat['enemy_max_hp']}）",
                "type": "combat",
            })

        elif subaction == "skill":
            skill_id = player_action.get("skill_id", "")
            if skill_id == "heavy_strike":
                if char["ep"] < 15:
                    raise InvalidActionError("精力不足，無法施展重擊！")
                char["ep"] -= 15
                player_damage = max(2, int(char["atk"] * 1.5) - combat["enemy_def"])
                combat["enemy_hp"] = max(0, combat["enemy_hp"] - player_damage)
                new_logs.append({
                    "turn": state["turn"],
                    "text": f"你凝神蓄力發動【重擊】！（消耗 15 精力）對【{enemy_name}】造成 {player_damage} 點巨大傷害！（敵人剩餘 HP: {combat['enemy_hp']}/{combat['enemy_max_hp']}）",
                    "type": "combat",
                })
            elif skill_id == "first_aid":
                if char["ep"] < 20:
                    raise InvalidActionError("精力不足，無法急救！")
                char["ep"] -= 20
                healed = min(25, char["max_hp"] - char["hp"])
                char["hp"] += healed
                new_logs.append({
                    "turn": state["turn"],
                    "text": f"你快速包紮傷口，恢復了 {healed} 點生命！（目前 HP: {char['hp']}/{char['max_hp']}）",
                    "type": "combat",
                })
            else:
                raise InvalidActionError(f"未知的技能：{skill_id}")

        elif subaction == "item":
            item_id = player_action.get("item_id", "")
            entry = next((i for i in state["inventory"] if i["item_id"] == item_id and i.get("count", 0) > 0), None)
            if not entry:
                raise InvalidActionError("背包內沒有該物品！")
            item_def = script_snapshot.get("items", {}).get(item_id, {})
            # 套用物品效果
            for eff in item_def.get("effects", []):
                msg = apply_effect(eff, script_snapshot, state)
                if msg:
                    new_logs.append({"turn": state["turn"], "text": msg, "type": "effect"})
            entry["count"] -= 1
            if entry["count"] == 0:
                state["inventory"] = [i for i in state["inventory"] if i["item_id"] != item_id]

        elif subaction == "defend":
            defend_active = True
            char["ep"] = min(char["max_ep"], char["ep"] + 10)
            new_logs.append({
                "turn": state["turn"],
                "text": "你架起武器專注防禦，防禦力暫時提升，並恢復了 10 點精力。",
                "type": "combat",
            })

        elif subaction == "escape":
            p_agi = char.get("attributes", {}).get("agility", 10)
            e_agi = combat.get("enemy_agility", 8)
            escape_rate = max(20.0, min(90.0, (p_agi / max(1, p_agi + e_agi)) * 100.0))
            roll = random_fn() * 100.0
            roll_result["escape_roll"] = roll
            roll_result["escape_rate"] = escape_rate
            if roll <= escape_rate:
                new_logs.append({
                    "turn": state["turn"],
                    "text": f"你把握空檔敏捷地脫離了戰場！（判定成功：{roll:.0f} <= {escape_rate:.0f}%）",
                    "type": "combat",
                })
                escape_node = combat.get("escape_node_id")
                flow_id = combat.get("flow_id")
                state["combat"] = None
                if escape_node and flow_id:
                    f_logs, _ = step_flowchart(script_snapshot, state, flow_id, escape_node, random_fn)
                    new_logs.extend(f_logs)
                available_actions = get_available_actions(script_snapshot, state)
                state["recent_logs"].extend(new_logs)
                return state, new_logs, available_actions, roll_result
            else:
                new_logs.append({
                    "turn": state["turn"],
                    "text": f"逃跑失敗！被【{enemy_name}】攔截了後路！（判定：{roll:.0f} > {escape_rate:.0f}%）",
                    "type": "combat",
                })

        # 檢查敵人是否戰敗
        if combat["enemy_hp"] <= 0:
            new_logs.append({
                "turn": state["turn"],
                "text": f"★ 戰鬥勝利！你擊敗了【{enemy_name}】！",
                "type": "combat",
            })
            win_node = combat.get("win_node_id")
            flow_id = combat.get("flow_id")
            state["combat"] = None
            if win_node and flow_id:
                f_logs, _ = step_flowchart(script_snapshot, state, flow_id, win_node, random_fn)
                new_logs.extend(f_logs)
            available_actions = get_available_actions(script_snapshot, state)
            state["recent_logs"].extend(new_logs)
            return state, new_logs, available_actions, roll_result

        # 敵方回合
        enemy_atk = combat.get("enemy_atk", 10)
        player_def = char.get("def", 5) * (1.5 if defend_active else 1.0)
        enemy_damage = max(1, int(enemy_atk - player_def))
        char["hp"] = max(0, char["hp"] - enemy_damage)
        new_logs.append({
            "turn": state["turn"],
            "text": f"【{enemy_name}】向你反擊，造成 {enemy_damage} 點傷害！（剩餘生命：{char['hp']}/{char['max_hp']}）",
            "type": "combat",
        })

        # 檢查玩家是否倒下
        if char["hp"] <= 0:
            lose_node = combat.get("lose_node_id")
            flow_id = combat.get("flow_id")
            state["combat"] = None
            new_logs.append({
                "turn": state["turn"],
                "text": "你眼前一黑倒了下去……但這不是終點！",
                "type": "combat",
            })
            if lose_node and flow_id:
                f_logs, _ = step_flowchart(script_snapshot, state, flow_id, lose_node, random_fn)
                new_logs.extend(f_logs)
            else:
                # 安全地點甦醒保護，不刪除存檔
                safe_loc = script_snapshot.get("safe_location_id", script_snapshot.get("start_location_id"))
                state["location_id"] = safe_loc
                char["hp"] = max(1, min(char["max_hp"], 30))
                char["ep"] = max(1, min(char["max_ep"], 30))
                fee = min(10, char["gold"])
                char["gold"] -= fee
                new_logs.append({
                    "turn": state["turn"],
                    "text": f"你在安全地點醒來，支付了 {fee} 金幣醫藥費。",
                    "type": "narrative",
                })
            available_actions = get_available_actions(script_snapshot, state)
            state["recent_logs"].extend(new_logs)
            return state, new_logs, available_actions, roll_result

        combat["round"] += 1
        available_actions = get_available_actions(script_snapshot, state)
        state["recent_logs"].extend(new_logs)
        return state, new_logs, available_actions, roll_result

    # ==========================================
    # 流程圖選項推進
    # ==========================================
    if action_type == "flow_choice":
        flow_id = player_action.get("flow_id", "")
        next_node_id = player_action.get("next_node_id", "")
        choice_id = player_action.get("choice_id", "")

        # 扣除選項成本（若有）
        cost = player_action.get("cost", {})
        if cost:
            if "gold" in cost and state["character"]["gold"] < cost["gold"]:
                raise InvalidActionError("金幣不足，無法選擇此項！")
            if "ep" in cost and state["character"]["ep"] < cost["ep"]:
                raise InvalidActionError("精力不足，無法選擇此項！")
            if "gold" in cost:
                state["character"]["gold"] -= cost["gold"]
            if "ep" in cost:
                state["character"]["ep"] -= cost["ep"]

        if next_node_id:
            f_logs, _ = step_flowchart(script_snapshot, state, flow_id, next_node_id, random_fn)
            new_logs.extend(f_logs)
        else:
            state["interaction"] = None

        available_actions = get_available_actions(script_snapshot, state)
        state["recent_logs"].extend(new_logs)
        return state, new_logs, available_actions, roll_result

    # ==========================================
    # 一般自由探索行動
    # ==========================================
    if action_type == "move":
        target_loc_id = player_action.get("target_location_id", "")
        current_loc = script_snapshot.get("locations", {}).get(state["location_id"], {})
        if target_loc_id not in current_loc.get("exits", []):
            raise InvalidActionError("無法直接前往未相連的地點。")

        target_loc = script_snapshot.get("locations", {}).get(target_loc_id, {})
        ep_cost = target_loc.get("travel_cost", {}).get("ep", 5)
        if state["character"]["ep"] < ep_cost:
            raise InvalidActionError(f"精力不足（需要 {ep_cost} 精力），請先休息！")

        state["character"]["ep"] -= ep_cost
        state["location_id"] = target_loc_id
        if target_loc_id not in state["discovered_locations"]:
            state["discovered_locations"].append(target_loc_id)

        # 推進回合與時段
        state["turn"] += 1
        state["time_of_day"] = get_time_of_day(state["turn"])

        new_logs.append({
            "turn": state["turn"],
            "text": f"你啟程穿過道路，在【{TIME_PHASE_NAMES[state['time_of_day']]}】抵達了【{target_loc.get('name')}】。（消耗 {ep_cost} 精力）",
            "type": "narrative",
        })

        # 檢查該地點進入時是否有觸發事件
        enter_event_flow = target_loc.get("on_enter_flow_id")
        if enter_event_flow and enter_event_flow in script_snapshot.get("flowcharts", {}):
            f_logs, _ = step_flowchart(script_snapshot, state, enter_event_flow, "start", random_fn)
            new_logs.extend(f_logs)

    elif action_type == "talk":
        npc_id = player_action.get("npc_id", "")
        effective_npc = get_effective_npc(npc_id, script_snapshot, state)
        flow_id = effective_npc.get("dialogue_flow_id", "")
        if flow_id and flow_id in script_snapshot.get("flowcharts", {}):
            f_logs, _ = step_flowchart(script_snapshot, state, flow_id, "start", random_fn)
            new_logs.extend(f_logs)
        else:
            new_logs.append({
                "turn": state["turn"],
                "text": f"你向【{effective_npc.get('name')}】打了聲招呼，對方朝你微笑點頭。",
                "type": "dialogue",
                "speaker": effective_npc.get("name"),
            })

    elif action_type == "interact_object":
        obj_id = player_action.get("object_id", "")
        current_loc = script_snapshot.get("locations", {}).get(state["location_id"], {})
        target_obj = next((o for o in current_loc.get("objects", []) if o.get("id") == obj_id), None)
        if not target_obj:
            raise InvalidActionError("未找到該可調查物件。")

        flow_id = target_obj.get("flow_id")
        if flow_id and flow_id in script_snapshot.get("flowcharts", {}):
            f_logs, _ = step_flowchart(script_snapshot, state, flow_id, "start", random_fn)
            new_logs.extend(f_logs)
        else:
            text = render_narrative_template(target_obj.get("description", "仔細觀察後沒有更多發現。"), script_snapshot, state)
            new_logs.append({"turn": state["turn"], "text": text, "type": "narrative"})
            for eff in target_obj.get("effects", []):
                msg = apply_effect(eff, script_snapshot, state)
                if msg:
                    new_logs.append({"turn": state["turn"], "text": msg, "type": "effect"})

    elif action_type == "activity":
        act_id = player_action.get("activity_id", "")
        current_loc = script_snapshot.get("locations", {}).get(state["location_id"], {})
        target_act = next((a for a in current_loc.get("activities", []) if a.get("id") == act_id), None)
        if not target_act:
            raise InvalidActionError("該地點無此生活活動。")

        # 檢查成本
        cost = target_act.get("cost", {})
        ep_cost = cost.get("ep", 0)
        gold_cost = cost.get("gold", 0)
        turn_cost = cost.get("turn", 1)

        if state["character"]["ep"] < ep_cost:
            raise InvalidActionError(f"精力不足（需要 {ep_cost} 精力），無法進行【{target_act.get('name')}】！")
        if state["character"]["gold"] < gold_cost:
            raise InvalidActionError(f"金幣不足（需要 {gold_cost} 金幣），無法進行【{target_act.get('name')}】！")

        state["character"]["ep"] -= ep_cost
        state["character"]["gold"] -= gold_cost
        if turn_cost > 0:
            state["turn"] += turn_cost
            state["time_of_day"] = get_time_of_day(state["turn"])

        # 執行效果或啟動流程圖
        flow_id = target_act.get("flow_id")
        if flow_id and flow_id in script_snapshot.get("flowcharts", {}):
            f_logs, _ = step_flowchart(script_snapshot, state, flow_id, "start", random_fn)
            new_logs.extend(f_logs)
        else:
            new_logs.append({
                "turn": state["turn"],
                "text": f"你在【{current_loc.get('name')}】完成了【{target_act.get('name')}】。",
                "type": "narrative",
            })
            for eff in target_act.get("effects", []):
                msg = apply_effect(eff, script_snapshot, state)
                if msg:
                    new_logs.append({"turn": state["turn"], "text": msg, "type": "effect"})

    elif action_type == "use_item":
        item_id = player_action.get("item_id", "")
        entry = next((i for i in state["inventory"] if i["item_id"] == item_id and i.get("count", 0) > 0), None)
        if not entry:
            raise InvalidActionError("背包內沒有該物品！")

        item_def = script_snapshot.get("items", {}).get(item_id, {})
        new_logs.append({"turn": state["turn"], "text": f"你使用了【{item_def.get('name')}】。", "type": "effect"})
        for eff in item_def.get("effects", []):
            msg = apply_effect(eff, script_snapshot, state)
            if msg:
                new_logs.append({"turn": state["turn"], "text": msg, "type": "effect"})

        entry["count"] -= 1
        if entry["count"] == 0:
            state["inventory"] = [i for i in state["inventory"] if i["item_id"] != item_id]

    elif action_type == "equip_item":
        item_id = player_action.get("item_id", "")
        entry = next((i for i in state["inventory"] if i["item_id"] == item_id), None)
        if not entry:
            raise InvalidActionError("背包內沒有該裝備！")

        item_def = script_snapshot.get("items", {}).get(item_id, {})
        slot = item_def.get("type")
        if slot not in ("weapon", "armor", "accessory"):
            raise InvalidActionError("該物品不是可裝備的品項。")

        currently_equipped = entry.get("equipped", False)
        char = state["character"]
        modifiers = item_def.get("modifiers", {})

        if currently_equipped:
            # 卸下
            entry["equipped"] = False
            state["equipment"][slot] = ""
            char["atk"] = max(0, char["atk"] - modifiers.get("atk", 0))
            char["def"] = max(0, char["def"] - modifiers.get("def", 0))
            new_logs.append({"turn": state["turn"], "text": f"卸下了【{item_def.get('name')}】。", "type": "equipment"})
        else:
            # 卸下原本該槽位已裝備的物品
            old_item_id = state["equipment"].get(slot)
            if old_item_id:
                old_entry = next((i for i in state["inventory"] if i["item_id"] == old_item_id), None)
                if old_entry:
                    old_entry["equipped"] = False
                    old_def = script_snapshot.get("items", {}).get(old_item_id, {})
                    old_mod = old_def.get("modifiers", {})
                    char["atk"] = max(0, char["atk"] - old_mod.get("atk", 0))
                    char["def"] = max(0, char["def"] - old_mod.get("def", 0))

            entry["equipped"] = True
            state["equipment"][slot] = item_id
            char["atk"] += modifiers.get("atk", 0)
            char["def"] += modifiers.get("def", 0)
            new_logs.append({"turn": state["turn"], "text": f"裝備了【{item_def.get('name')}】！（攻擊+{modifiers.get('atk', 0)}，防禦+{modifiers.get('def', 0)}）", "type": "equipment"})

    elif action_type == "gift_item":
        npc_id = player_action.get("npc_id", "")
        item_id = player_action.get("item_id", "")
        entry = next((i for i in state["inventory"] if i["item_id"] == item_id and i.get("count", 0) > 0), None)
        if not entry:
            raise InvalidActionError("背包內沒有該物品！")

        effective_npc = get_effective_npc(npc_id, script_snapshot, state)
        item_def = script_snapshot.get("items", {}).get(item_id, {})

        # 贈送好感度計算（預設物品價值越高好感越高）
        affinity_gain = item_def.get("gift_affinity", 5)
        state["relationships"][npc_id] = state["relationships"].get(npc_id, 0) + affinity_gain

        entry["count"] -= 1
        if entry["count"] == 0:
            state["inventory"] = [i for i in state["inventory"] if i["item_id"] != item_id]

        new_logs.append({
            "turn": state["turn"],
            "text": f"你將【{item_def.get('name')}】贈送給了【{effective_npc.get('name')}】，對方非常高興！（好感度 +{affinity_gain}，目前：{state['relationships'][npc_id]}）",
            "type": "dialogue",
        })

    else:
        raise InvalidActionError(f"未知的玩家行動：{action_type}")

    available_actions = get_available_actions(script_snapshot, state)
    state["recent_logs"].extend(new_logs)
    return state, new_logs, available_actions, roll_result


def validate_draft(script: dict[str, Any]) -> list[str]:
    """在發布前驗證型別、引用、成本及不含等待點的循環。"""
    errors = []
    if not isinstance(script, dict):
        return ["劇本必須為物件。"]
    for key in ("locations", "npcs", "items", "quests", "enemies", "flowcharts"):
        if not isinstance(script.get(key, {}), dict) or any(not isinstance(v, dict) for v in script.get(key, {}).values()):
            return [f"{key} 必須為識別碼對應物件。"]
    if script.get("safe_location_id", script.get("start_location_id")) not in script.get("locations", {}):
        errors.append("安全地點不存在。")
    node_types = {"start", "narrative", "choice", "condition", "check", "random", "effect", "combat", "end"}
    effects = {"modify_stat", "add_item", "remove_item", "change_affinity", "set_flag", "set_quest_stage", "complete_quest", "move_location", "add_clue", "end_interaction"}
    def walk(value, path="script", depth=0):
        if depth > 32:
            errors.append(f"{path} 巢狀深度超限。")
            return
        if isinstance(value, list):
            for i, child in enumerate(value): walk(child, f"{path}[{i}]", depth+1)
        elif isinstance(value, dict):
            for key, child in value.items():
                if key in ("effects", "choices", "branches", "activities", "objects", "initial_inventory", "traits"):
                    if not isinstance(child, list) or any(not isinstance(x, dict) for x in child):
                        errors.append(f"{path}.{key} 必須為物件陣列。")
                        continue
                if key in ("cost", "travel_cost"):
                    if not isinstance(child, dict) or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in child.values()):
                        errors.append(f"{path}.{key} 成本必須為非負有限數值。")
                if key == "effects" and isinstance(child, list):
                    for effect in child:
                        if isinstance(effect, dict) and effect.get("type") not in effects:
                            errors.append(f"{path} 含未知效果型別。")
                refs = {"item_id":"items", "npc_id":"npcs", "quest_id":"quests", "location_id":"locations", "flow_id":"flowcharts", "dialogue_flow_id":"flowcharts", "on_enter_flow_id":"flowcharts"}
                if key in refs and child and (not isinstance(child, str) or child not in script.get(refs[key], {})):
                    errors.append(f"{path}.{key} 引用不存在。")
                if key == "condition" and child is not None:
                    if not isinstance(child, dict):
                        errors.append(f"{path} 條件必須為物件。")
                    elif not any(k in child for k in ("all", "any", "none")):
                        field = child.get("field", "")
                        if child.get("op", "==") not in ("==", "!=", ">", ">=", "<", "<=", "in", "contains"):
                            errors.append(f"{path} 條件運算子無效。")
                        if not isinstance(field, str) or not (field in ("hp", "max_hp", "ep", "max_ep", "gold", "atk", "def", "location", "time_of_day", "turn") or field.startswith(("stat.", "item.", "flag.", "quest.", "affinity."))):
                            errors.append(f"{path} 條件欄位無效。")
                walk(child, f"{path}.{key}", depth+1)
    walk(script)
    if errors:
        return errors
    for fid, flow in script.get("flowcharts", {}).items():
        nodes = flow.get("nodes", {})
        if not isinstance(nodes, dict) or any(not isinstance(n, dict) for n in nodes.values()):
            errors.append(f"流程 {fid} 節點格式錯誤。")
            continue
        adjacency = {}
        for nid, node in nodes.items():
            kind = node.get("type")
            if kind not in node_types:
                errors.append(f"流程 {fid} 節點 {nid} 型別無效。")
            exits = []
            if kind in ("start", "narrative", "effect"):
                exits = [node.get("next_node_id")]
            elif kind == "condition": exits = [node.get("next_node_true"), node.get("next_node_false")]
            elif kind == "check": exits = [node.get("success_node_id"), node.get("fail_node_id")]
            elif kind == "combat": exits = [node.get(k) for k in ("win_node_id", "lose_node_id", "escape_node_id")]
            elif kind in ("choice", "random"):
                exits = [x.get("next_node_id") for x in node.get("choices" if kind == "choice" else "branches", [])]
            if any(not target or target not in nodes for target in exits):
                errors.append(f"流程 {fid} 節點 {nid} 缺少出口或指向不存在的節點。")
            adjacency[nid] = [] if kind in ("choice", "combat", "end") or node.get("wait_input") else exits
        visiting, visited = set(), set()
        def visit(nid):
            if nid in visiting: return True
            if nid in visited or nid not in adjacency: return False
            visiting.add(nid)
            cyclic = any(visit(nxt) for nxt in adjacency[nid])
            visiting.remove(nid); visited.add(nid)
            return cyclic
        if len(nodes) > 500:
            errors.append(f"流程 {fid} 超過 500 個節點，請拆分事件。")
        elif any(visit(nid) for nid in nodes):
            errors.append(f"流程 {fid} 含無等待點的自動循環。")
    if errors:
        return errors
    try:
        return _validate_links(script)
    except (TypeError, ValueError, AttributeError, KeyError):
        return ["劇本欄位型別或引用格式不正確。"]


def _validate_links(script: dict[str, Any]) -> list[str]:
    """劇本草稿靜態驗證器。回傳錯誤訊息清單，若為空表示結構通過。"""
    errors: list[str] = []

    # 1. 檢查地點
    locations = script.get("locations", {})
    if not locations:
        errors.append("劇本至少必須包含一個有效地點。")
    start_loc = script.get("start_location_id", "")
    if start_loc not in locations:
        errors.append(f"起始地點【{start_loc}】不存在於 locations 定義中。")

    for loc_id, loc in locations.items():
        for exit_id in loc.get("exits", []):
            if exit_id not in locations:
                errors.append(f"地點【{loc_id}】的出口【{exit_id}】不存在。")

    # 2. 檢查 NPC 替代角色
    npcs = script.get("npcs", {})
    for npc_id, npc in npcs.items():
        fallback = npc.get("fallback_character")
        if not fallback or not fallback.get("name"):
            errors.append(f"NPC 角色槽【{npc_id}】缺少虛構替代角色配置（fallback_character）。")

    # 3. 檢查流程圖結構
    flowcharts = script.get("flowcharts", {})
    for flow_id, flow in flowcharts.items():
        nodes = flow.get("nodes", {})
        if not nodes:
            errors.append(f"流程圖【{flow_id}】沒有任何節點。")
            continue

        if "start" not in nodes:
            errors.append(f"流程圖【{flow_id}】缺少起點節點（id: 'start'）。")

        for node_id, node in nodes.items():
            ntype = node.get("type")
            if not ntype:
                errors.append(f"流程圖【{flow_id}】節點【{node_id}】缺少 type。")
                continue

            # 檢查出口連線是否存在
            if ntype in ("start", "effect", "narrative"):
                nxt = node.get("next_node_id")
                if nxt and nxt not in nodes:
                    errors.append(f"流程圖【{flow_id}】節點【{node_id}】指向不存在的節點【{nxt}】。")

            elif ntype == "condition":
                nxt_t = node.get("next_node_true")
                nxt_f = node.get("next_node_false")
                if not nxt_t or nxt_t not in nodes:
                    errors.append(f"流程圖【{flow_id}】條件節點【{node_id}】的 true 分支【{nxt_t}】無效。")
                if not nxt_f or nxt_f not in nodes:
                    errors.append(f"流程圖【{flow_id}】條件節點【{node_id}】的 false 分支【{nxt_f}】無效。")

            elif ntype == "check":
                s_nxt = node.get("success_node_id")
                f_nxt = node.get("fail_node_id")
                if not s_nxt or s_nxt not in nodes:
                    errors.append(f"流程圖【{flow_id}】檢定節點【{node_id}】的成功分支【{s_nxt}】無效。")
                if not f_nxt or f_nxt not in nodes:
                    errors.append(f"流程圖【{flow_id}】檢定節點【{node_id}】的失敗分支【{f_nxt}】無效。")

            elif ntype == "random":
                branches = node.get("branches", [])
                if not branches:
                    errors.append(f"流程圖【{flow_id}】隨機節點【{node_id}】沒有配置分支權重。")
                for idx, b in enumerate(branches):
                    if b.get("weight", 0) <= 0:
                        errors.append(f"流程圖【{flow_id}】隨機節點【{node_id}】第 {idx+1} 分支權重必須大於 0。")
                    if b.get("next_node_id") not in nodes:
                        errors.append(f"流程圖【{flow_id}】隨機節點【{node_id}】第 {idx+1} 分支指向不存在的節點。")

            elif ntype == "choice":
                choices = node.get("choices", [])
                if not choices:
                    errors.append(f"流程圖【{flow_id}】選擇節點【{node_id}】沒有提供任何可選選項。")
                for c in choices:
                    nxt = c.get("next_node_id")
                    if nxt and nxt not in nodes:
                        errors.append(f"流程圖【{flow_id}】選擇節點【{node_id}】選項【{c.get('label')}】指向不存在的節點【{nxt}】。")

            elif ntype == "combat":
                enemy_id = node.get("enemy_id")
                if enemy_id not in script.get("enemies", {}):
                    errors.append(f"流程圖【{flow_id}】戰鬥節點【{node_id}】敵人【{enemy_id}】未在 enemies 定義。")
                for exit_key in ("win_node_id", "lose_node_id", "escape_node_id"):
                    nxt = node.get(exit_key)
                    if nxt and nxt not in nodes:
                        errors.append(f"流程圖【{flow_id}】戰鬥節點【{node_id}】的出口【{exit_key}: {nxt}】不存在。")

    return errors


def simulate_test_run(
    script: dict[str, Any],
    initial_state_override: dict[str, Any] | None,
    action: dict[str, Any],
    rng_seed: int = 42,
) -> dict[str, Any]:
    """管理員試跑器：以固定亂數與暫存狀態單步執行，回傳詳細追蹤歷程。"""
    rng = random.Random(rng_seed)
    mock_employee = {"employee_id": "TEST_EMP", "display_name": "試跑員工", "department": "研發部", "position": "工程師"}
    base_state = initial_state_override or create_initial_state(mock_employee, script)
    old_state = copy.deepcopy(base_state)
    for _ in range(base_state.get("_rng_draws", 0)):
        rng.random()

    if not action:
        return {"success": True, "logs": [], "new_state": base_state, "available_actions": get_available_actions(script, base_state), "roll_result": {}, "diff": {}}
    new_state, logs, actions, roll_result = advance(script, base_state, action, random_source=rng.random)

    new_state["_rng_draws"] = base_state.get("_rng_draws", 0) + len(roll_result.get("draws", []))

    # 計算狀態差異 (Diff)
    diff: dict[str, Any] = {}
    for key in ("turn", "time_of_day", "location_id"):
        if old_state.get(key) != new_state.get(key):
            diff[key] = {"old": old_state.get(key), "new": new_state.get(key)}

    for stat in ("hp", "ep", "gold", "atk", "def"):
        if old_state["character"].get(stat) != new_state["character"].get(stat):
            diff[f"character.{stat}"] = {"old": old_state["character"].get(stat), "new": new_state["character"].get(stat)}

    if old_state.get("flags") != new_state.get("flags"):
        diff["flags"] = {"old": old_state.get("flags"), "new": new_state.get("flags")}

    return {
        "success": True,
        "logs": logs,
        "new_state": new_state,
        "available_actions": actions,
        "roll_result": roll_result,
        "diff": diff,
    }


def create_demo_chapter() -> dict[str, Any]:
    """建立符合 Section 8 規範的完整示範劇本「穿越至陌生小鎮」。

    包含五個地點、四個 NPC 角色槽、八種物品、三項任務、兩個可避開的戰鬥事件與三種章節結果。
    至少一個主線目標（通行關卡）具備三種可行解法：
      1. 委託打工/採集累積通行費繳交給守衛長；
      2. 協助熟面孔老闆娘或工匠，取得介紹信通關；
      3. 在鎮郊工坊後山調查環境，發現隱密替代山道。
    """
    return {
        "world_no": "DEMO_TOWN",
        "world_name": "穿越至陌生小鎮",
        "description": "員工本人抵達未知故事世界，遇見由同事映射的人物，尋找立足方式及世界異常的線索。",
        "start_location_id": "town_square",
        "safe_location_id": "cozy_inn",
        "traits": [
            {"id": "athletic", "name": "健步如飛", "modifiers": {"attributes": {"agility": 3}, "ep": 20}},
            {"id": "scholarly", "name": "博聞強記", "modifiers": {"attributes": {"intellect": 3}, "gold": 30}},
            {"id": "charismatic", "name": "八面玲瓏", "modifiers": {"attributes": {"charisma": 3}, "gold": 20}},
            {"id": "resilient", "name": "身強體健", "modifiers": {"attributes": {"strength": 3}, "hp": 30}},
        ],
        "initial_inventory": [
            {"item_id": "travel_ration", "count": 2, "equipped": False},
            {"item_id": "worn_dagger", "count": 1, "equipped": False},
        ],
        "locations": {
            "town_square": {
                "id": "town_square",
                "name": "鎮口廣場",
                "description": "陌生小鎮的核心廣場，石砌地面略帶斑駁，中央有一座乾涸的噴泉，四周人來人往。",
                "exits": ["cozy_inn", "general_store", "suburb_workshop", "guard_post"],
                "travel_cost": {"ep": 5},
                "activities": [],
                "objects": [
                    {
                        "id": "fountain",
                        "name": "乾涸噴泉",
                        "description": "噴泉底部雕刻著奇怪的幾何紋路，隱約泛著微弱的光芒。",
                        "effects": [{"type": "add_clue", "clue_id": "fountain_pattern", "title": "噴泉符文", "description": "噴泉底部的未知紋路，與這個世界通常的裝飾風格迥異。"}],
                    }
                ],
            },
            "cozy_inn": {
                "id": "cozy_inn",
                "name": "溫暖旅店",
                "description": "木質調的溫馨旅店，空氣中飄散著烤麵包與麥芽酒的香氣，是旅人歇息的好地方。",
                "exits": ["town_square"],
                "travel_cost": {"ep": 5},
                "activities": [
                    {
                        "id": "rest_inn",
                        "name": "客棧休息",
                        "description": "花費 10 金幣並休息 1 回合，恢復所有生命與精力。",
                        "cost": {"gold": 10, "ep": 0, "turn": 1},
                        "effects": [
                            {"type": "modify_stat", "stat": "hp", "value": 100},
                            {"type": "modify_stat", "stat": "ep", "value": 100},
                        ],
                    }
                ],
                "objects": [],
            },
            "general_store": {
                "id": "general_store",
                "name": "晨風雜貨舖",
                "description": "琳瑯滿目的貨架上擺滿了各類冒險用具、乾糧與旅行補給品。",
                "exits": ["town_square"],
                "travel_cost": {"ep": 5},
                "activities": [
                    {
                        "id": "buy_herb",
                        "name": "購買野草草藥",
                        "description": "花費 15 金幣購買一包具療效的草藥。",
                        "cost": {"gold": 15, "ep": 0, "turn": 0},
                        "effects": [{"type": "add_item", "item_id": "wild_herb", "count": 1}],
                    },
                    {
                        "id": "buy_pickaxe",
                        "name": "購買工匠鐵鎬",
                        "description": "花費 25 金幣購買一把堅固的鐵鎬。",
                        "cost": {"gold": 25, "ep": 0, "turn": 0},
                        "effects": [{"type": "add_item", "item_id": "artisan_pickaxe", "count": 1}],
                    },
                ],
                "objects": [],
            },
            "suburb_workshop": {
                "id": "suburb_workshop",
                "name": "鎮郊工坊",
                "description": "位於小鎮邊緣的鐵匠工坊，叮叮噹噹的敲擊聲不絕於耳，後方連接險峻山道。",
                "exits": ["town_square"],
                "travel_cost": {"ep": 5},
                "activities": [
                    {
                        "id": "work_workshop",
                        "name": "工坊打工",
                        "description": "協助搬運礦石與拉風箱，消耗 20 精力與 1 回合，賺取 30 金幣。",
                        "cost": {"ep": 20, "turn": 1, "gold": 0},
                        "effects": [{"type": "modify_stat", "stat": "gold", "value": 30}],
                    },
                    {
                        "id": "gather_mountain",
                        "name": "後山採集",
                        "description": "前往後山林地採集原生草藥與礦物，消耗 15 精力與 1 回合。",
                        "cost": {"ep": 15, "turn": 1, "gold": 0},
                        "flow_id": "flow_gather_mountain",
                    },
                ],
                "objects": [
                    {
                        "id": "workshop_secret_trail",
                        "name": "後山隱密山徑",
                        "description": "草叢掩蓋下的一條狹窄山道，似乎能繞過前方的守衛關卡。",
                        "flow_id": "flow_secret_trail",
                    }
                ],
            },
            "guard_post": {
                "id": "guard_post",
                "name": "守衛關卡",
                "description": "通往下一個區域的必經隘口，厚實的木製柵欄與石堡封鎖了道路，守衛嚴陣以待。",
                "exits": ["town_square"],
                "travel_cost": {"ep": 5},
                "activities": [],
                "objects": [],
            },
        },
        "npcs": {
            "guard_captain": {
                "id": "guard_captain",
                "slot_name": "守衛長",
                "mapped_employee_id": "",
                "fallback_character": {
                    "name": "杜恩",
                    "title": "鐵面守衛長",
                    "bio": "嚴厲恪守職責的關卡守衛長，重視秩序與法規。",
                    "photo_file": "",
                },
                "schedule": {"morning": "guard_post", "noon": "guard_post", "dusk": "guard_post", "night": "cozy_inn"},
                "initial_affinity": 0,
                "dialogue_flow_id": "flow_guard_captain",
            },
            "innkeeper": {
                "id": "innkeeper",
                "slot_name": "旅店老闆",
                "mapped_employee_id": "",
                "fallback_character": {
                    "name": "瑪莎",
                    "title": "熱心老闆娘",
                    "bio": "溫和風趣的旅店主人，知道許多小鎮各處的祕密與八卦。",
                    "photo_file": "",
                },
                "schedule": {"morning": "cozy_inn", "noon": "cozy_inn", "dusk": "cozy_inn", "night": "cozy_inn"},
                "initial_affinity": 10,
                "dialogue_flow_id": "flow_innkeeper",
            },
            "merchant": {
                "id": "merchant",
                "slot_name": "熱心商人",
                "mapped_employee_id": "",
                "fallback_character": {
                    "name": "羅倫斯",
                    "title": "行商",
                    "bio": "四處遊歷的商人，手裡總有些稀奇古怪的小玩意。",
                    "photo_file": "",
                },
                "schedule": {"morning": "general_store", "noon": "town_square", "dusk": "general_store", "night": "cozy_inn"},
                "initial_affinity": 0,
                "dialogue_flow_id": "flow_merchant",
            },
            "artisan": {
                "id": "artisan",
                "slot_name": "老工匠",
                "mapped_employee_id": "",
                "fallback_character": {
                    "name": "奧古斯特",
                    "title": "老工匠",
                    "bio": "沉默寡言但技藝高超的鐵匠兼學者，對古老符文略懂一二。",
                    "photo_file": "",
                },
                "schedule": {"morning": "suburb_workshop", "noon": "suburb_workshop", "dusk": "suburb_workshop", "night": "suburb_workshop"},
                "initial_affinity": 0,
                "dialogue_flow_id": "flow_artisan",
            },
        },
        "items": {
            "travel_ration": {
                "id": "travel_ration",
                "name": "行囊口糧",
                "type": "consumable",
                "description": "乾燥的乾糧與燻肉，食用可迅速恢復 30 點精力。",
                "effects": [{"type": "modify_stat", "stat": "ep", "value": 30}],
                "gift_affinity": 5,
            },
            "worn_dagger": {
                "id": "worn_dagger",
                "name": "磨損匕首",
                "type": "weapon",
                "description": "穿越時帶在身上的隨身小刀，雖然有些磨損但依舊鋒利。攻擊力 +5。",
                "modifiers": {"atk": 5, "def": 0},
                "gift_affinity": 5,
            },
            "weird_coin": {
                "id": "weird_coin",
                "name": "古怪金幣",
                "type": "misc",
                "description": "表面刻著非同尋常花紋的重金幣，在小鎮上能作為貴重通貨流通。",
                "gift_affinity": 15,
            },
            "mayor_letter": {
                "id": "mayor_letter",
                "name": "鎮長介紹信",
                "type": "misc",
                "description": "由鎮上名望人士引薦的親筆信函，關卡守衛見信即放行。",
                "gift_affinity": 0,
            },
            "wild_herb": {
                "id": "wild_herb",
                "name": "野草草藥",
                "type": "consumable",
                "description": "小鎮後山採集的藥草，能包紮止血，恢復 35 點生命。",
                "effects": [{"type": "modify_stat", "stat": "hp", "value": 35}],
                "gift_affinity": 10,
            },
            "artisan_pickaxe": {
                "id": "artisan_pickaxe",
                "name": "工匠鐵鎬",
                "type": "weapon",
                "description": "精鋼打造的重鐵鎬，既是採集工具也能作為沉重兵器。攻擊力 +8。",
                "modifiers": {"atk": 8, "def": 0},
                "gift_affinity": 10,
            },
            "guard_permit": {
                "id": "guard_permit",
                "name": "守衛通行證",
                "type": "misc",
                "description": "繳納通行規費後取得的正式過關印信。",
                "gift_affinity": 0,
            },
            "unknown_fragment": {
                "id": "unknown_fragment",
                "name": "未知碎片",
                "type": "misc",
                "description": "在隱密山道深處拾得的發光石質碎片，刻印著穿越時隱約見過的幾何符紋。",
                "gift_affinity": 25,
            },
        },
        "quests": {
            "settling_in": {
                "id": "settling_in",
                "name": "初來乍到",
                "auto_start": True,
                "description": "穿越到未知小鎮，探索周邊環境並與居民交談，確認自己目前的處境。",
            },
            "pass_the_gate": {
                "id": "pass_the_gate",
                "name": "通行之路",
                "auto_start": True,
                "description": "小鎮對外出口被守衛關卡封鎖，需尋找方法前往下一個區域（解法：繳納過路費／獲取引薦信／尋找替代山道）。",
            },
            "anomaly_echoes": {
                "id": "anomaly_echoes",
                "name": "異常回響",
                "auto_start": False,
                "description": "小鎮周邊存在不明的符文碎片與空間擾動，調查這起異常與穿越之間的關聯。",
            },
        },
        "enemies": {
            "mountain_beast": {
                "id": "mountain_beast",
                "name": "後山兇惡野獸",
                "hp": 40,
                "atk": 12,
                "def": 3,
                "agility": 9,
            },
            "drunk_brawler": {
                "id": "drunk_brawler",
                "name": "醉酒挑釁者",
                "hp": 35,
                "atk": 10,
                "def": 2,
                "agility": 6,
            },
        },
        "flowcharts": {
            # 1. 守衛長對話流程（主線通關樞紐）
            "flow_guard_captain": {
                "id": "flow_guard_captain",
                "name": "守衛長對話",
                "nodes": {
                    "start": {"type": "start", "next_node_id": "check_passed"},
                    "check_passed": {
                        "type": "condition",
                        "condition": {"field": "flag.gate_passed", "op": "==", "value": True},
                        "next_node_true": "already_passed",
                        "next_node_false": "greet",
                    },
                    "already_passed": {
                        "type": "narrative",
                        "speaker": "守衛長",
                        "text": "「你的通行資格已經登記過了，前面的道路隨時為你開放，旅途小心。」",
                        "next_node_id": "end_normal",
                    },
                    "greet": {
                        "type": "narrative",
                        "speaker": "守衛長",
                        "text": "「站住！前方為管制區域。沒有合法通行手續或身分證明，任何人不得擅自通過。」",
                        "next_node_id": "choice_gate",
                    },
                    "choice_gate": {
                        "type": "choice",
                        "choices": [
                            {
                                "id": "pay_toll",
                                "label": "【繳交規費】支付 80 金幣辦理正式通行手續",
                                "condition": {"field": "gold", "op": ">=", "value": 80},
                                "cost": {"gold": 80},
                                "next_node_id": "toll_success",
                            },
                            {
                                "id": "show_letter",
                                "label": "【出示信函】遞交旅店老闆娘轉交的《鎮長介紹信》",
                                "condition": {"field": "item.mayor_letter", "op": ">=", "value": 1},
                                "next_node_id": "letter_success",
                            },
                            {
                                "id": "ask_about_gate",
                                "label": "詢問通過關卡的規定與理由",
                                "next_node_id": "inquire_gate",
                            },
                            {
                                "id": "leave_guard",
                                "label": "我稍後再來（離開）",
                                "next_node_id": "end_normal",
                            },
                        ],
                    },
                    "toll_success": {
                        "type": "effect",
                        "effects": [
                            {"type": "add_item", "item_id": "guard_permit", "count": 1},
                            {"type": "set_flag", "flag": "gate_passed", "value": True},
                            {"type": "complete_quest", "quest_id": "pass_the_gate", "method_used": "toll_fee"},
                        ],
                        "next_node_id": "toll_dialogue",
                    },
                    "toll_dialogue": {
                        "type": "narrative",
                        "speaker": "守衛長",
                        "text": "守衛長仔細清點了金幣，在卷宗上蓋下印章：「公事公辦，手續合格。放行！」【解法一：以金錢獲取通行資格】",
                        "next_node_id": "ending_toll",
                    },
                    "ending_toll": {
                        "type": "end",
                        "end_type": "game_ending",
                        "ending_id": "cleared_by_tax",
                        "ending_title": "正道啟程：守法公民的遠行",
                    },
                    "letter_success": {
                        "type": "effect",
                        "effects": [
                            {"type": "remove_item", "item_id": "mayor_letter", "count": 1},
                            {"type": "set_flag", "flag": "gate_passed", "value": True},
                            {"type": "change_affinity", "npc_id": "guard_captain", "value": 20},
                            {"type": "complete_quest", "quest_id": "pass_the_gate", "method_used": "recommendation"},
                        ],
                        "next_node_id": "letter_dialogue",
                    },
                    "letter_dialogue": {
                        "type": "narrative",
                        "speaker": "守衛長",
                        "text": "守衛長看著介紹信上的親筆簽名，臉色微變並挺直腰桿：「原來是老闆娘保薦的貴客！失敬，請立刻通行！」【解法二：以人脈與交情順利通關】",
                        "next_node_id": "ending_letter",
                    },
                    "ending_letter": {
                        "type": "end",
                        "end_type": "game_ending",
                        "ending_id": "cleared_by_network",
                        "ending_title": "貴人引薦：深受信賴的同袍",
                    },
                    "inquire_gate": {
                        "type": "narrative",
                        "speaker": "守衛長",
                        "text": "「近來外界頻生異常，鎮長下令嚴防流竄。要通過，要嘛繳納 80 金幣重稅登記，要嘛具備在地名望人士的親筆引薦，沒有第三條路！」",
                        "next_node_id": "choice_gate",
                    },
                    "end_normal": {"type": "end", "end_type": "return_to_exploration"},
                },
            },
            # 2. 旅店老闆娘對話流程（支線與人脈主線）
            "flow_innkeeper": {
                "id": "flow_innkeeper",
                "name": "旅店老闆娘對話",
                "nodes": {
                    "start": {"type": "start", "next_node_id": "greet_inn"},
                    "greet_inn": {
                        "type": "narrative",
                        "speaker": "旅店老闆娘",
                        "text": "「哎呀，瞧你一臉茫然的樣子，剛來小鎮吧？若是累了隨時能在這打尖歇歇腳。」",
                        "next_node_id": "choice_inn",
                    },
                    "choice_inn": {
                        "type": "choice",
                        "choices": [
                            {
                                "id": "ask_help",
                                "label": "詢問是否需要幫忙（好感委託）",
                                "condition": {"field": "flag.inn_help_done", "op": "!=", "value": True},
                                "next_node_id": "inn_quest_offer",
                            },
                            {
                                "id": "submit_herb",
                                "label": "遞交採集到的 2 包【野草草藥】幫忙旅店",
                                "condition": {
                                    "all": [
                                        {"field": "flag.inn_help_accepted", "op": "==", "value": True},
                                        {"field": "flag.inn_help_done", "op": "!=", "value": True},
                                        {"field": "item.wild_herb", "op": ">=", "value": 2},
                                    ]
                                },
                                "next_node_id": "inn_submit_herb",
                            },
                            {
                                "id": "brawler_event",
                                "label": "調查角落鬧事的醉漢（特殊遭遇）",
                                "condition": {
                                    "all": [
                                        {"field": "time_of_day", "op": "==", "value": "night"},
                                        {"field": "flag.brawler_settled", "op": "!=", "value": True},
                                    ]
                                },
                                "next_node_id": "encounter_brawler",
                            },
                            {"id": "leave_inn", "label": "只是隨便看看（離開）", "next_node_id": "end_inn"},
                        ],
                    },
                    "inn_quest_offer": {
                        "type": "effect",
                        "effects": [{"type": "set_flag", "flag": "inn_help_accepted", "value": True}],
                        "next_node_id": "inn_quest_dialogue",
                    },
                    "inn_quest_dialogue": {
                        "type": "narrative",
                        "speaker": "旅店老闆娘",
                        "text": "「近來鎮上藥材短缺，若你能去鎮郊工坊後山採集 2 包野草草藥給我，我便寫封引薦信，請守衛長為你行個方便！」",
                        "next_node_id": "end_inn",
                    },
                    "inn_submit_herb": {
                        "type": "effect",
                        "effects": [
                            {"type": "remove_item", "item_id": "wild_herb", "count": 2},
                            {"type": "add_item", "item_id": "mayor_letter", "count": 1},
                            {"type": "change_affinity", "npc_id": "innkeeper", "value": 30},
                            {"type": "set_flag", "flag": "inn_help_done", "value": True},
                        ],
                        "next_node_id": "inn_submit_dialogue",
                    },
                    "inn_submit_dialogue": {
                        "type": "narrative",
                        "speaker": "旅店老闆娘",
                        "text": "「太感謝了！這些草藥解了燃眉之急。這封《鎮長介紹信》你收著，守衛長看在我的面子上絕不敢刁難你！」",
                        "next_node_id": "end_inn",
                    },
                    "encounter_brawler": {
                        "type": "narrative",
                        "speaker": "醉酒挑釁者",
                        "text": "一名酒氣熏天的醉漢搖搖晃晃撞上你：「你看什麼看？！新來的鄉巴佬，想找碴嗎？！」",
                        "next_node_id": "choice_brawler",
                    },
                    "choice_brawler": {
                        "type": "choice",
                        "choices": [
                            {
                                "id": "pacify_brawler",
                                "label": "【口才安撫】運用魅力嘗試好言相勸（魅力檢定）",
                                "next_node_id": "check_brawler_pacify",
                            },
                            {
                                "id": "fight_brawler",
                                "label": "【正面迎戰】直接迎頭痛擊鬧事者（進入戰鬥）",
                                "next_node_id": "combat_brawler",
                            },
                        ],
                    },
                    "check_brawler_pacify": {
                        "type": "check",
                        "stat": "charisma",
                        "base_chance": 60,
                        "stat_coeff": 3.0,
                        "success_node_id": "brawler_pacified",
                        "fail_node_id": "combat_brawler",
                    },
                    "brawler_pacified": {
                        "type": "effect",
                        "effects": [
                            {"type": "set_flag", "flag": "brawler_settled", "value": True},
                            {"type": "change_affinity", "npc_id": "innkeeper", "value": 15},
                            {"type": "modify_stat", "stat": "gold", "value": 20},
                        ],
                        "next_node_id": "brawler_pacified_narrative",
                    },
                    "brawler_pacified_narrative": {
                        "type": "narrative",
                        "speaker": "旅店老闆娘",
                        "text": "你言辭懇切、不卑不亢地化解了紛爭，醉漢自討沒趣地嘟囔著坐下。老闆娘欣喜地塞給你 20 金幣以示酬謝！",
                        "next_node_id": "end_inn",
                    },
                    "combat_brawler": {
                        "type": "combat",
                        "enemy_id": "drunk_brawler",
                        "win_node_id": "brawler_won",
                        "lose_node_id": "end_inn",
                        "escape_node_id": "end_inn",
                    },
                    "brawler_won": {
                        "type": "effect",
                        "effects": [
                            {"type": "set_flag", "flag": "brawler_settled", "value": True},
                            {"type": "modify_stat", "stat": "gold", "value": 15},
                        ],
                        "next_node_id": "brawler_won_narrative",
                    },
                    "brawler_won_narrative": {
                        "type": "narrative",
                        "speaker": "系統",
                        "text": "你俐落地制伏了鬧事醉漢，贏得旅店內一陣叫好，從對方掉落的錢袋中取得了 15 金幣！",
                        "next_node_id": "end_inn",
                    },
                    "end_inn": {"type": "end", "end_type": "return_to_exploration"},
                },
            },
            # 3. 商人對話流程
            "flow_merchant": {
                "id": "flow_merchant",
                "name": "商人羅倫斯對話",
                "nodes": {
                    "start": {"type": "start", "next_node_id": "greet_mer"},
                    "greet_mer": {
                        "type": "narrative",
                        "speaker": "熱心商人",
                        "text": "「嘿！遠方的旅人，只要出得起價錢，這裡什麼都有。如果手頭緊，去工坊或後山打工採集也是賺錢的好門路。」",
                        "next_node_id": "choice_mer",
                    },
                    "choice_mer": {
                        "type": "choice",
                        "choices": [
                            {
                                "id": "ask_rumors",
                                "label": "詢問關於世界異常與穿越的傳聞",
                                "next_node_id": "mer_rumors",
                            },
                            {
                                "id": "leave_mer",
                                "label": "多謝提醒，我先四處看看",
                                "next_node_id": "end_mer",
                            },
                        ],
                    },
                    "mer_rumors": {
                        "type": "narrative",
                        "speaker": "熱心商人",
                        "text": "「傳聞後山深處經常有奇異的藍光閃爍，老鐵匠奧古斯特似乎在研究那些發光的石頭。若你想弄明白，不妨去拜訪他。」",
                        "next_node_id": "end_mer",
                    },
                    "end_mer": {"type": "end", "end_type": "return_to_exploration"},
                },
            },
            # 4. 老工匠對話流程
            "flow_artisan": {
                "id": "flow_artisan",
                "name": "老工匠奧古斯特對話",
                "nodes": {
                    "start": {"type": "start", "next_node_id": "greet_art"},
                    "greet_art": {
                        "type": "narrative",
                        "speaker": "老工匠",
                        "text": "老工匠放下鐵鎚，打量著你手上的裝備：「年輕人，你的腳步聲沉穩，但眼中帶著不屬於這片土地的疑惑。」",
                        "next_node_id": "choice_art",
                    },
                    "choice_art": {
                        "type": "choice",
                        "choices": [
                            {
                                "id": "show_fragment",
                                "label": "【展示碎片】拿出在後山發現的《未知碎片》請教",
                                "condition": {"field": "item.unknown_fragment", "op": ">=", "value": 1},
                                "next_node_id": "art_fragment_revealed",
                            },
                            {
                                "id": "ask_secret_trail",
                                "label": "詢問後山山道是否真有捷徑通往外界",
                                "next_node_id": "art_trail_hint",
                            },
                            {"id": "leave_art", "label": "不打擾您工作（離開）", "next_node_id": "end_art"},
                        ],
                    },
                    "art_fragment_revealed": {
                        "type": "effect",
                        "effects": [
                            {"type": "complete_quest", "quest_id": "anomaly_echoes", "method_used": "fragment_studied"},
                            {"type": "change_affinity", "npc_id": "artisan", "value": 40},
                            {"type": "modify_stat", "stat": "atk", "value": 3},
                        ],
                        "next_node_id": "art_fragment_narrative",
                    },
                    "art_fragment_narrative": {
                        "type": "narrative",
                        "speaker": "老工匠",
                        "text": "奧古斯特雙手顫抖接過碎片：「這…這正是古書記載的『異世之樞』殘片！你果然是穿越時空壁壘而來的行者！老夫替你的武器銘刻古老符印（攻擊+3），祝你早日找到答案。」",
                        "next_node_id": "end_art",
                    },
                    "art_trail_hint": {
                        "type": "narrative",
                        "speaker": "老工匠",
                        "text": "「後山密道隱蔽而危險，若你的敏捷或智力足夠識破山霧與碎石，確實能避開前方的關卡守衛直接出關。」",
                        "next_node_id": "end_art",
                    },
                    "end_art": {"type": "end", "end_type": "return_to_exploration"},
                },
            },
            # 5. 後山採集流程（含可避開戰鬥）
            "flow_gather_mountain": {
                "id": "flow_gather_mountain",
                "name": "後山採集事件",
                "nodes": {
                    "start": {"type": "start", "next_node_id": "random_gather_event"},
                    "random_gather_event": {
                        "type": "random",
                        "branches": [
                            {"weight": 6, "next_node_id": "gather_normal"},
                            {"weight": 4, "next_node_id": "gather_beast_encounter"},
                        ],
                    },
                    "gather_normal": {
                        "type": "effect",
                        "effects": [{"type": "add_item", "item_id": "wild_herb", "count": 1}],
                        "next_node_id": "gather_normal_text",
                    },
                    "gather_normal_text": {
                        "type": "narrative",
                        "text": "你在山崖邊細心搜尋，採集到了一株新鮮的【野草草藥】。",
                        "next_node_id": "end_gather",
                    },
                    "gather_beast_encounter": {
                        "type": "narrative",
                        "text": "正當你撥開樹叢時，一頭低吼的【後山兇惡野獸】猛然擋在眼前！",
                        "next_node_id": "choice_beast",
                    },
                    "choice_beast": {
                        "type": "choice",
                        "choices": [
                            {
                                "id": "distract_beast",
                                "label": "【投擲口糧】丟出《行囊口糧》引開野獸注意力（避開戰鬥）",
                                "condition": {"field": "item.travel_ration", "op": ">=", "value": 1},
                                "cost": {},
                                "next_node_id": "beast_distracted",
                            },
                            {
                                "id": "check_agility_beast",
                                "label": "【靈巧繞道】利用敏捷身手迅速撤退（敏捷檢定）",
                                "next_node_id": "check_beast_escape",
                            },
                            {
                                "id": "fight_beast",
                                "label": "【正面迎戰】拔出武器與野獸搏鬥（戰鬥）",
                                "next_node_id": "combat_beast_node",
                            },
                        ],
                    },
                    "beast_distracted": {
                        "type": "effect",
                        "effects": [
                            {"type": "remove_item", "item_id": "travel_ration", "count": 1},
                            {"type": "add_item", "item_id": "wild_herb", "count": 1},
                        ],
                        "next_node_id": "beast_distracted_text",
                    },
                    "beast_distracted_text": {
                        "type": "narrative",
                        "text": "野獸被誘人的口糧吸引過去大嚼，你趁機採下草藥悄然脫身！",
                        "next_node_id": "end_gather",
                    },
                    "check_beast_escape": {
                        "type": "check",
                        "stat": "agility",
                        "base_chance": 50,
                        "stat_coeff": 3.0,
                        "success_node_id": "beast_escaped",
                        "fail_node_id": "combat_beast_node",
                    },
                    "beast_escaped": {
                        "type": "narrative",
                        "text": "你縱身一躍躍上高處岩石，野獸撲了個空，你順利甩開追擊！",
                        "next_node_id": "end_gather",
                    },
                    "combat_beast_node": {
                        "type": "combat",
                        "enemy_id": "mountain_beast",
                        "win_node_id": "beast_slain",
                        "lose_node_id": "end_gather",
                        "escape_node_id": "end_gather",
                    },
                    "beast_slain": {
                        "type": "effect",
                        "effects": [
                            {"type": "add_item", "item_id": "wild_herb", "count": 2},
                            {"type": "modify_stat", "stat": "gold", "value": 25},
                        ],
                        "next_node_id": "beast_slain_text",
                    },
                    "beast_slain_text": {
                        "type": "narrative",
                        "text": "兇惡的野獸哀號倒地，你在獸穴旁拾取了 25 金幣與 2 株草藥！",
                        "next_node_id": "end_gather",
                    },
                    "end_gather": {"type": "end", "end_type": "return_to_exploration"},
                },
            },
            # 6. 後山秘密通道調查（解法三：探索環境通關）
            "flow_secret_trail": {
                "id": "flow_secret_trail",
                "name": "秘密山道探索",
                "nodes": {
                    "start": {"type": "start", "next_node_id": "trail_desc"},
                    "trail_desc": {
                        "type": "narrative",
                        "text": "藤蔓與落石掩映之下，露出一條極為陡峭的裂隙小徑。冷風從幽暗的石壁縫隙吹來，似乎能直接繞過前方的守衛關卡。",
                        "next_node_id": "choice_trail",
                    },
                    "choice_trail": {
                        "type": "choice",
                        "choices": [
                            {
                                "id": "check_trail_intellect",
                                "label": "【勘查路徑】運用智力分析石層結構與地圖（智力檢定）",
                                "next_node_id": "check_trail_int",
                            },
                            {
                                "id": "check_trail_agility",
                                "label": "【攀登穿越】憑藉矯健身手攀上險峻裂谷（敏捷檢定）",
                                "next_node_id": "check_trail_agi",
                            },
                            {"id": "leave_trail", "label": "太危險了，先退回工坊", "next_node_id": "end_trail"},
                        ],
                    },
                    "check_trail_int": {
                        "type": "check",
                        "stat": "intellect",
                        "base_chance": 50,
                        "stat_coeff": 3.0,
                        "success_node_id": "trail_success_effect",
                        "fail_node_id": "trail_failed",
                    },
                    "check_trail_agi": {
                        "type": "check",
                        "stat": "agility",
                        "base_chance": 50,
                        "stat_coeff": 3.0,
                        "success_node_id": "trail_success_effect",
                        "fail_node_id": "trail_failed",
                    },
                    "trail_failed": {
                        "type": "effect",
                        "effects": [{"type": "modify_stat", "stat": "hp", "value": -15}],
                        "next_node_id": "trail_failed_text",
                    },
                    "trail_failed_text": {
                        "type": "narrative",
                        "text": "一塊風化岩石突然崩碎，你摔了下來受到 15 點擦傷！只得暫時退回。",
                        "next_node_id": "end_trail",
                    },
                    "trail_success_effect": {
                        "type": "effect",
                        "effects": [
                            {"type": "add_item", "item_id": "unknown_fragment", "count": 1},
                            {"type": "set_flag", "flag": "gate_passed", "value": True},
                            {"type": "complete_quest", "quest_id": "pass_the_gate", "method_used": "secret_trail"},
                        ],
                        "next_node_id": "trail_success_text",
                    },
                    "trail_success_text": {
                        "type": "narrative",
                        "text": "你成功穿越了後山險隘！在裂谷深處的祭壇上，你發現並拾起了一枚散發幽光的【未知碎片】！前方豁然開朗，你已徹底繞過了守衛關卡！【解法三：環境調查密道潛越】",
                        "next_node_id": "ending_trail",
                    },
                    "ending_trail": {
                        "type": "end",
                        "end_type": "game_ending",
                        "ending_id": "cleared_by_secret_trail",
                        "ending_title": "暗道潛影：掌握祕辛的探索者",
                    },
                    "end_trail": {"type": "end", "end_type": "return_to_exploration"},
                },
            },
        },
    }
