const forbiddenKeys = new Set(['__proto__', 'prototype', 'constructor']);
const labels = {
    name: '名稱', description: '說明', text: '敘事', type: '型別', id: '識別碼',
    next_node_id: '下一節點', next_node_true: '成立出口', next_node_false: '不成立出口',
    success_node_id: '成功出口', fail_node_id: '失敗出口', win_node_id: '勝利出口',
    lose_node_id: '戰敗出口', escape_node_id: '逃跑出口', choices: '選項', effects: '效果',
    branches: '隨機分支', condition: '條件', field: '欄位', op: '運算子', value: '值',
    cost: '成本', label: '顯示文字', weight: '權重', speaker: '發話者',
    schedule: '人物行程', morning: '清晨', noon: '正午', dusk: '傍晚', night: '深夜',
    fallback_character: '替代角色', mapped_employee_id: '映射員工編號',
    dialogue_flow_id: '對話流程', initial_affinity: '初始關係', slot_name: '角色職務',
    start_location_id: '起始地點', safe_location_id: '安全地點', exits: '地點出口',
    activities: '生活活動', objects: '調查物件', items: '物品', traits: '初始特長',
    auto_start: '自動開始', stat: '屬性', count: '數量', item_id: '物品編號',
    quest_id: '任務編號', npc_id: '人物編號', location_id: '地點編號', flow_id: '事件流程',
    base_chance: '基本成功率', stat_coeff: '屬性係數', situational_mod: '情境修正',
    end_type: '結束類型', ending_title: '結局標題', ending_id: '結局編號',
};

export const nodeTemplates = {
    start: { type: 'start', next_node_id: '' },
    narrative: { type: 'narrative', speaker: '', text: '', wait_input: false, next_node_id: '' },
    choice: { type: 'choice', choices: [] },
    condition: { type: 'condition', condition: { field: 'gold', op: '>=', value: 0 }, next_node_true: '', next_node_false: '' },
    check: { type: 'check', stat: 'agility', base_chance: 50, stat_coeff: 2, situational_mod: 0, success_node_id: '', fail_node_id: '' },
    random: { type: 'random', branches: [] },
    effect: { type: 'effect', effects: [], next_node_id: '' },
    combat: { type: 'combat', enemy_id: '', win_node_id: '', lose_node_id: '', escape_node_id: '' },
    end: { type: 'end', end_type: 'return_to_exploration', ending_id: '', ending_title: '' },
};

export function clone(value) { return JSON.parse(JSON.stringify(value)); }

function newArrayValue(key) {
    const defaults = {
        effects: { type: 'modify_stat', stat: 'gold', value: 0 },
        choices: { id: `choice_${Date.now()}`, label: '新選項', next_node_id: '', cost: { gold: 0 } },
        branches: { weight: 1, next_node_id: '' },
        activities: { id: `activity_${Date.now()}`, name: '新活動', cost: { gold: 0, ep: 0, turn: 1 }, effects: [] },
        objects: { id: `object_${Date.now()}`, name: '新物件', description: '', effects: [] },
        initial_inventory: { item_id: '', count: 1, equipped: false },
        traits: { id: `trait_${Date.now()}`, name: '新特長', modifiers: { attributes: {} } },
        all: { field: 'gold', op: '>=', value: 0 }, any: { field: 'gold', op: '>=', value: 0 },
    };
    return clone(defaults[key] ?? '');
}

/** 以型別化表單維護同一份劇本；使用者不必輸入 JSON。 */
export function renderFields(container, model, beforeChange, afterChange, options = {}) {
    container.replaceChildren();
    const mutate = operation => { beforeChange(); operation(); afterChange(); };
    const rerender = () => renderFields(container, model, beforeChange, afterChange, options);
    const button = (title, action) => {
        const el = document.createElement('button');
        el.type = 'button'; el.className = 'btn second'; el.textContent = title;
        el.addEventListener('click', action); return el;
    };
    function fields(parent, value, path, depth = 0) {
        if (depth > 20) return;
        for (const [key, child] of Object.entries(value)) {
            if (['x', 'y', 'mapped_employee_snapshot'].includes(key)) continue;
            const row = document.createElement('div'); row.className = 'field';
            const title = document.createElement('label');
            title.textContent = `${labels[key] || key}${Array.isArray(value) ? `（${Number(key) + 1}）` : ''}`;
            row.append(title);
            if (child !== null && typeof child === 'object') {
                const details = document.createElement('details'); details.open = depth < 2;
                const summary = document.createElement('summary'); summary.textContent = labels[key] || key;
                details.append(summary); fields(details, child, [...path, key], depth + 1); row.append(details);
            } else {
                const choices = (key.endsWith('node_id') || key.endsWith('_node_true') || key.endsWith('_node_false')) ? options.nodeIds : null;
                let input;
                if (choices) {
                    input = document.createElement('select');
                    for (const val of ['', ...choices]) {
                        const option = document.createElement('option'); option.value = val; option.textContent = val || '請選擇';
                        option.selected = val === child; input.append(option);
                    }
                } else {
                    input = document.createElement(key === 'text' || key === 'description' ? 'textarea' : 'input');
                    if (typeof child === 'boolean') { input.type = 'checkbox'; input.checked = child; }
                    else { input.type = typeof child === 'number' ? 'number' : 'text'; input.value = child ?? ''; }
                }
                input.setAttribute('aria-label', title.textContent);
                if (key === 'type' && options.lockType && depth === 0) input.disabled = true;
                input.addEventListener('change', () => {
                    const next = typeof child === 'boolean' ? input.checked : typeof child === 'number' ? Number(input.value) : input.value;
                    if (typeof next === 'number' && !Number.isFinite(next)) return;
                    mutate(() => { value[key] = next; });
                });
                row.append(input);
                if (key === 'value') {
                    const type = document.createElement('select'); type.setAttribute('aria-label', '條件值型別');
                    for (const kind of ['string', 'number', 'boolean']) {
                        const option = document.createElement('option'); option.value = kind; option.textContent = kind;
                        option.selected = kind === typeof child; type.append(option);
                    }
                    type.onchange = () => { mutate(() => { value[key] = type.value === 'number' ? 0 : type.value === 'boolean' ? false : ''; }); rerender(); };
                    row.append(type);
                }
            }
            if (!(key === 'type' && options.lockType && depth === 0)) {
                row.append(button('移除', () => {
                    mutate(() => { if (Array.isArray(value)) value.splice(Number(key), 1); else delete value[key]; }); rerender();
                }));
            }
            parent.append(row);
        }
        if (Array.isArray(value)) {
            parent.append(button('新增一筆', () => { mutate(() => value.push(newArrayValue(path[path.length - 1]))); rerender(); }));
        } else {
            const keyInput = document.createElement('input'); keyInput.placeholder = '新增欄位或資源識別碼';
            keyInput.setAttribute('aria-label', '新增欄位或資源識別碼');
            const type = document.createElement('select'); type.setAttribute('aria-label', '新欄位型別');
            for (const kind of ['文字', '數字', '布林', '物件', '清單']) {
                const option = document.createElement('option'); option.textContent = kind; type.append(option);
            }
            parent.append(keyInput, type, button('新增欄位', () => {
                const key = keyInput.value.trim();
                if (!key || forbiddenKeys.has(key) || Object.hasOwn(value, key)) return;
                mutate(() => { value[key] = ({ 文字: '', 數字: 0, 布林: false, 物件: {}, 清單: [] })[type.value]; }); rerender();
            }));
        }
    }
    fields(container, model, []);
}
