const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const source = name => fs.readFileSync(path.join(__dirname, '../static/js', name), 'utf8');

test('API 錯誤保留狀態碼與修訂衝突代碼', async () => {
    const ctx = vm.createContext({ location: { pathname: '/game.html' }, fetch: async () => ({
        ok: false, status: 409, json: async () => ({ error: '修訂號不符', code: 'CONFLICT' }),
    }) });
    vm.runInContext(source('script.js').replace(/^export /gm, ''), ctx);
    await assert.rejects(vm.runInContext("apiData('/api/adventure/action')", ctx), error =>
        error.code === 'CONFLICT' && error.status === 409 && error.message === '修訂號不符');
});

test('編輯器寫入使用管理員 CSRF，而不是省略或使用員工 Token', async () => {
    let captured;
    const ctx = vm.createContext({
        apiData: async url => { assert.equal(url, '/api/admin/session'); return { authenticated: true, csrf: 'admin-token' }; },
        jsonRequest: async (url, body, options) => { captured = { url, body, options }; },
    });
    const editor = source('adventure-editor.js');
    vm.runInContext(editor.slice(editor.indexOf('async function adminRequest'), editor.indexOf('export async function initAdventureEditor')), ctx);
    await vm.runInContext("adminRequest('/api/admin/adventure/draft/save', {world_no:'TEST'})", ctx);
    assert.equal(captured.options.csrf, 'admin-token');
    assert.equal(captured.body.world_no, 'TEST');
});

test('回應遺失後重試沿用原 request_id 與原行動', async () => {
    const requests = [];
    const ctx = vm.createContext({
        isActionPending: false, pendingAction: null, activeSave: { save_no: 'S1' }, activeRevision: 1,
        requireEmployee: async () => ({ csrf: 'token' }), generateRequestId: () => 'R1',
        updateAdventureState() {}, renderGameScreen() {}, alert() {},
        jsonRequest: async (_, payload) => {
            requests.push(structuredClone(payload));
            if (requests.length === 1) throw new Error('連線中斷');
            return { revision: 2, state: { turn: 2 }, location: {}, npcs_in_scene: [], available_actions: [] };
        },
    });
    const player = source('adventure.js');
    vm.runInContext(player.slice(player.indexOf('async function dispatchAction'), player.indexOf('// ==========================================', player.indexOf('async function dispatchAction'))), ctx);
    await vm.runInContext("dispatchAction({action:'move', target_location_id:'inn'})", ctx);
    await vm.runInContext("dispatchAction({action:'talk', npc_id:'different'})", ctx);
    assert.deepEqual(requests[1], requests[0]);
    assert.equal(ctx.pendingAction, null);
    assert.equal(ctx.activeRevision, 2);
});

class Element {
    constructor(tag) { this.tagName = tag; this.children = []; this.listeners = {}; this.value = ''; this.checked = false; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    setAttribute(name, value) { this[name] = value; }
    addEventListener(name, handler) { this.listeners[name] = handler; }
    emit(name) { this.listeners[name]?.(); }
}
const descendants = root => [root, ...root.children.flatMap(descendants)];

test('作者表單保留數值與布林型別，修改戰鬥出口會回寫模型', () => {
    const ctx = vm.createContext({ document: { createElement: tag => new Element(tag) } });
    vm.runInContext(source('adventure-form.js').replace(/^export /gm, ''), ctx);
    const root = new Element('div');
    const model = { base_chance: 50, condition: { field: 'flag.helped', op: '==', value: true }, win_node_id: 'win' };
    ctx.root = root; ctx.model = model; ctx.before = () => {}; ctx.after = () => {};
    vm.runInContext("renderFields(root, model, before, after, {nodeIds:['win','other']})", ctx);
    const inputs = descendants(root);
    const chance = inputs.find(e => e['aria-label'] === '基本成功率');
    chance.value = '75'; chance.emit('change');
    const condition = inputs.find(e => e['aria-label'] === '值' && e.type === 'checkbox');
    condition.checked = false; condition.emit('change');
    const win = inputs.find(e => e['aria-label'] === '勝利出口');
    win.value = 'other'; win.emit('change');
    assert.equal(model.base_chance, 75);
    assert.equal(model.condition.value, false);
    assert.equal(model.win_node_id, 'other');
});

test('作者可透過表單增加選項，不必輸入 JSON', () => {
    const ctx = vm.createContext({ document: { createElement: tag => new Element(tag) } });
    vm.runInContext(source('adventure-form.js').replace(/^export /gm, ''), ctx);
    const root = new Element('div'); ctx.root = root; ctx.model = { choices: [] };
    vm.runInContext('renderFields(root, model, () => {}, () => {})', ctx);
    const add = descendants(root).find(e => e.textContent === '新增一筆');
    add.emit('click');
    assert.equal(ctx.model.choices.length, 1);
    assert.equal(ctx.model.choices[0].cost.gold, 0);
});


test('存檔卡片顯示流水號，繼續冒險仍使用 UUID', () => {
    const cards = [];
    const save = {
        world_no: 'DEMO_TOWN', slot_index: 1, save_no: 'SAVE_internal_uuid', version_no: 'VER_internal_uuid',
        save_display_no: 'SAVE_000004', version_display_no: 'V000002', revision: 1, character: {},
    };
    const ctx = vm.createContext({
        advSlotsGrid: { innerHTML: '', appendChild: card => cards.push(card) },
        activeWorldNo: 'DEMO_TOWN', esc: value => String(value),
        document: { createElement: () => ({}) }, saves: [save],
    });
    const player = source('adventure.js');
    vm.runInContext(player.slice(player.indexOf('function renderSlots('), player.indexOf('async function openCreateModal(')), ctx);
    vm.runInContext('renderSlots(saves)', ctx);
    assert.match(cards[0].innerHTML, /存檔：SAVE_000004/);
    assert.match(cards[0].innerHTML, /版本：V000002/);
    assert.match(cards[0].innerHTML, /data-save-no="SAVE_internal_uuid"/);
    assert.doesNotMatch(cards[0].innerHTML.replace(/<[^>]*>/g, ''), /internal_uuid/);
});
