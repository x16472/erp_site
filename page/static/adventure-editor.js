import { apiData, jsonRequest, escapeHtml } from './script.js';
import { renderFields, nodeTemplates, clone } from './adventure-form.js';

const esc = escapeHtml;

// 編輯器狀態
let currentWorldNo = 'DEMO_TOWN';
let currentDraft = null;
let currentDraftRevision = 1;
let isDirty = false;
let currentSection = 'flowcharts';
let currentFlowId = 'flow_guard_captain';
let selectedNodeId = null;
let zoom = 1.0;
let pan = { x: 40, y: 40 };
let isDraggingNode = false;
let draggedNode = null;
let dragStartPos = { x: 0, y: 0 };
let isPanning = false;
let panStartPos = { x: 0, y: 0 };
let connectingFrom = null; // { nodeId, portType, branchKey }
let undoStack = [];
let redoStack = [];
let staffOptions = [];
let isListView = false;
let initialization = null;
let eventsBound = false;
let simState = null;
let simActions = [];
let simPending = false;

// DOM 元素
const advWorldSelect = document.querySelector('#advWorldSelect');
const advNewWorldBtn = document.querySelector('#advNewWorldBtn');
const advStatusPill = document.querySelector('#advStatusPill');
const advDraftRev = document.querySelector('#advDraftRev');
const advDirtyTag = document.querySelector('#advDirtyTag');
const advSaveDraftBtn = document.querySelector('#advSaveDraftBtn');
const advValidateBtn = document.querySelector('#advValidateBtn');
const advTestRunBtn = document.querySelector('#advTestRunBtn');
const advPublishBtn = document.querySelector('#advPublishBtn');

const advNavCol = document.querySelector('#advNavCol');
const advFlowSubnavList = document.querySelector('#advFlowSubnavList');

const advCanvasTitle = document.querySelector('#advCanvasTitle');
const advCanvasViewport = document.querySelector('#advCanvasViewport');
const advCanvasLayer = document.querySelector('#advCanvasLayer');
const advConnectionsSvg = document.querySelector('#advConnectionsSvg');
const advNodeListView = document.querySelector('#advNodeListView');
const advNodeListTableBody = document.querySelector('#advNodeListTableBody');

const advZoomIn = document.querySelector('#advZoomIn');
const advZoomOut = document.querySelector('#advZoomOut');
const advZoomReset = document.querySelector('#advZoomReset');
const advToggleView = document.querySelector('#advToggleView');
const advAddNodeSelect = document.querySelector('#advAddNodeSelect');
const advUndoBtn = document.querySelector('#advUndoBtn');
const advRedoBtn = document.querySelector('#advRedoBtn');

const advInspectorCol = document.querySelector('#advInspectorCol');
const advInspectorTitle = document.querySelector('#advInspectorTitle');
const advInspectorBody = document.querySelector('#advInspectorBody');

const advSimModal = document.querySelector('#advSimModal');
const advSimCloseBtn = document.querySelector('#advSimCloseBtn');
const advSimRunBtn = document.querySelector('#advSimRunBtn');
const advSimTrace = document.querySelector('#advSimTrace');

function setDirty(dirty = true) {
    isDirty = dirty;
    if (advDirtyTag) advDirtyTag.hidden = !dirty;
}

function pushUndo() {
    if (!currentDraft) return;
    undoStack.push(JSON.stringify(currentDraft.content));
    if (undoStack.length > 30) undoStack.shift();
    redoStack = [];
    setDirty(true);
}

function undo() {
    if (!undoStack.length) return;
    redoStack.push(JSON.stringify(currentDraft.content));
    const prev = undoStack.pop();
    currentDraft.content = JSON.parse(prev);
    renderAll();
}

function redo() {
    if (!redoStack.length) return;
    undoStack.push(JSON.stringify(currentDraft.content));
    const next = redoStack.pop();
    currentDraft.content = JSON.parse(next);
    renderAll();
}

/** 初始化 MIS 冒險編輯器 */
async function adminRequest(path, payload) {
    const session = await apiData('/api/admin/session');
    if (!session?.authenticated) throw new Error('請先登入管理員。');
    return jsonRequest(path, payload, { csrf: session.csrf });
}

export async function initAdventureEditor() {
    if (initialization) return initialization;
    initialization = (async () => {
        if (!eventsBound) { bindEditorEvents(); eventsBound = true; }
        await loadWorlds();
        await loadStaffOptions();
        if (advWorldSelect.options.length) await loadDraft(currentWorldNo);
    })().catch(error => { initialization = null; alert(error.message); });
    return initialization;
}

/** 載入所有世界列表 */
async function loadWorlds() {
    try {
        const worlds = await apiData('/api/admin/adventure/worlds');
        if (advWorldSelect && worlds && worlds.length) {
            advWorldSelect.innerHTML = worlds.map(w => `
                <option value="${esc(w.world_no)}" ${w.world_no === currentWorldNo ? 'selected' : ''}>
                    ${esc(w.world_name)} (${esc(w.world_no)})
                </option>
            `).join('');
            const activeW = worlds.find(w => w.world_no === currentWorldNo) || worlds[0];
            currentWorldNo = activeW.world_no;
            advWorldSelect.value = currentWorldNo;
            updateWorldStatusBadge(activeW.is_open);
        }
    } catch (err) {
        console.error('載入世界列表失敗：', err);
    }
}

function updateWorldStatusBadge(isOpen) {
    if (advStatusPill) {
        advStatusPill.textContent = isOpen ? '已開放遊玩' : '未開放草稿';
        advStatusPill.className = `adv-status-pill ${isOpen ? '' : 'closed'}`;
    }
}

/** 載入員工映射名單 */
async function loadStaffOptions() {
    try {
        staffOptions = await apiData('/api/admin/adventure/staff-options') || [];
    } catch (err) {
        console.error('載入員工選項失敗：', err);
    }
}

/** 載入指定世界的草稿 */
async function loadDraft(worldNo) {
    try {
        currentDraft = await apiData(`/api/admin/adventure/draft?world_no=${encodeURIComponent(worldNo)}`);
        currentDraftRevision = currentDraft.revision;
        if (advDraftRev) advDraftRev.textContent = currentDraftRevision;
        setDirty(false);
        undoStack = [];
        redoStack = [];

        // 確保初始流程圖 ID 合法
        const flowKeys = Object.keys(currentDraft.content?.flowcharts || {});
        if (!flowKeys.includes(currentFlowId)) {
            currentFlowId = flowKeys[0] || '';
        }

        renderAll();
    } catch (err) {
        console.error('載入草稿失敗：', err);
    }
}

/** 渲染整體畫面（導覽、畫布與屬性員） */
function renderAll() {
    renderSubnavFlows();
    if (currentSection === 'flowcharts') {
        renderFlowchartWorkspace();
    } else {
        renderResourceWorkspace();
    }
}

/** 渲染左側流程圖子清單 */
function renderSubnavFlows() {
    if (!advFlowSubnavList || !currentDraft) return;
    const flows = currentDraft.content?.flowcharts || {};
    advFlowSubnavList.innerHTML = Object.entries(flows).map(([fid, f]) => `
        <button type="button" class="adv-subnav-item ${fid === currentFlowId && currentSection === 'flowcharts' ? 'active' : ''}" data-flow-id="${esc(fid)}">
            🔀 ${esc(f.name || fid)}
        </button>
    `).join('') + `
        <button type="button" class="adv-subnav-item" id="advCreateFlowBtn" style="color: var(--accent, #2563eb); font-weight: 700;">
            + 新增流程圖
        </button>
    `;
}

/** 渲染流程圖工作區 */
function renderFlowchartWorkspace() {
    const flows = currentDraft?.content?.flowcharts || {};
    const flow = flows[currentFlowId];

    if (!flow) {
        if (advCanvasTitle) advCanvasTitle.textContent = '無選取流程圖';
        if (advNodeListView) advNodeListView.hidden = true;
        clearCanvas();
        return;
    }

    if (advCanvasTitle) advCanvasTitle.textContent = `流程圖：${flow.name || currentFlowId}`;

    if (isListView) {
        renderNodeListView(flow);
    } else {
        renderCanvasGraph(flow);
    }
    renderNodeInspector();
}

/** 清空畫布節點與連線 */
function clearCanvas() {
    advCanvasLayer.querySelectorAll('.adv-node-item').forEach(n => n.remove());
    if (advConnectionsSvg) advConnectionsSvg.innerHTML = '';
}

/** 繪製圖形化流程圖（DOM 節點與 SVG 連線） */
function renderCanvasGraph(flow) {
    if (advNodeListView) advNodeListView.hidden = true;
    clearCanvas();

    const nodes = flow.nodes || {};
    let defaultX = 60;
    let defaultY = 60;

    // 建立節點 DOM
    Object.entries(nodes).forEach(([nid, node], idx) => {
        if (node.x === undefined) node.x = defaultX + (idx % 4) * 260;
        if (node.y === undefined) node.y = defaultY + Math.floor(idx / 4) * 160;

        const el = document.createElement('div');
        el.className = `adv-node-item type-${node.type} ${nid === selectedNodeId ? 'selected' : ''}`;
        el.dataset.nodeId = nid;
        el.style.left = `${node.x}px`;
        el.style.top = `${node.y}px`;

        const typeLabels = {
            start: '起點 (Start)',
            narrative: '敘事 (Narrative)',
            choice: '等待選擇 (Choice)',
            condition: '條件分支 (Condition)',
            check: '屬性檢定 (Check)',
            random: '隨機分支 (Random)',
            effect: '狀態效果 (Effect)',
            combat: '戰鬥 (Combat)',
            end: '結束 (End)',
        };

        let previewText = node.text || node.label || '';
        if (node.type === 'condition') {
            previewText = `條件: ${node.condition?.field || ''} ${node.condition?.op || ''} ${node.condition?.value || ''}`;
        } else if (node.type === 'check') {
            previewText = `檢定: ${node.stat} (基礎 ${node.base_chance}%)`;
        } else if (node.type === 'combat') {
            previewText = `敵人: ${node.enemy_id}`;
        } else if (node.type === 'choice') {
            previewText = `選項數: ${(node.choices || []).length}`;
        }

        el.innerHTML = `
            <div class="adv-node-head">
                <span>${esc(typeLabels[node.type] || node.type)}</span>
                <span style="font-size: 0.7rem; opacity: 0.8;">#${esc(nid)}</span>
            </div>
            <div class="adv-node-body">${esc(previewText || '(空內容)')}</div>
            ${node.type !== 'start' ? '<button type="button" aria-label="連線入口" class="adv-node-port in" data-port="in"></button>' : ''}
            ${node.type !== 'end' ? '<button type="button" aria-label="連線出口" class="adv-node-port out" data-port="out"></button>' : ''}
        `;

        advCanvasLayer.appendChild(el);
    });

    applyTransform();
    drawConnections(flow);
}

/** 繪製節點間的 SVG 連線 */
function drawConnections(flow) {
    if (!advConnectionsSvg) return;
    advConnectionsSvg.innerHTML = `
        <defs>
            <marker id="advArrow" markerWidth="10" markerHeight="10" refX="6" refY="3" orient="auto">
                <path d="M0,0 L0,6 L6,3 z" fill="#94a3b8" />
            </marker>
            <marker id="advArrowActive" markerWidth="10" markerHeight="10" refX="6" refY="3" orient="auto">
                <path d="M0,0 L0,6 L6,3 z" fill="#2563eb" />
            </marker>
        </defs>
    `;

    const nodes = flow.nodes || {};

    const drawPath = (fromId, toId, className = 'adv-connection-path') => {
        const fromNode = nodes[fromId];
        const toNode = nodes[toId];
        if (!fromNode || !toNode) return;

        // 起點：右側出口；終點：左側入口
        const startX = (fromNode.x || 0) + 220;
        const startY = (fromNode.y || 0) + 40;
        const endX = (toNode.x || 0);
        const endY = (toNode.y || 0) + 40;

        const dx = Math.max(40, Math.abs(endX - startX) * 0.5);
        const d = `M ${startX} ${startY} C ${startX + dx} ${startY}, ${endX - dx} ${endY}, ${endX} ${endY}`;

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', d);
        path.setAttribute('class', className);
        path.setAttribute('marker-end', 'url(#advArrow)');
        advConnectionsSvg.appendChild(path);
    };

    Object.entries(nodes).forEach(([nid, node]) => {
        if (node.next_node_id) {
            drawPath(nid, node.next_node_id);
        }
        if (node.next_node_true) {
            drawPath(nid, node.next_node_true, 'adv-connection-path branch-true');
        }
        if (node.next_node_false) {
            drawPath(nid, node.next_node_false, 'adv-connection-path branch-false');
        }
        if (node.success_node_id) {
            drawPath(nid, node.success_node_id, 'adv-connection-path branch-true');
        }
        if (node.fail_node_id) {
            drawPath(nid, node.fail_node_id, 'adv-connection-path branch-false');
        }
        if (node.win_node_id) {
            drawPath(nid, node.win_node_id, 'adv-connection-path branch-true');
        }
        if (node.lose_node_id) {
            drawPath(nid, node.lose_node_id, 'adv-connection-path branch-false');
        }
        if (node.escape_node_id) {
            drawPath(nid, node.escape_node_id);
        }
        if (node.choices) {
            node.choices.forEach(c => {
                if (c.next_node_id) drawPath(nid, c.next_node_id);
            });
        }
        if (node.branches) {
            node.branches.forEach(b => {
                if (b.next_node_id) drawPath(nid, b.next_node_id);
            });
        }
    });
}

function applyTransform() {
    if (advCanvasLayer) {
        advCanvasLayer.style.transform = `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`;
    }
}

/** 繪製表單式節點清單 (無障礙與行動友善) */
function renderNodeListView(flow) {
    if (!advNodeListView || !advNodeListTableBody) return;
    advNodeListView.hidden = false;
    const nodes = flow.nodes || {};

    const nodeOptions = Object.keys(nodes).map(k => `<option value="${esc(k)}">${esc(k)}</option>`).join('');

    advNodeListTableBody.innerHTML = Object.entries(nodes).map(([nid, node]) => `
        <tr data-node-id="${esc(nid)}">
            <td><b>${esc(nid)}</b></td>
            <td><span class="adv-status-pill">${esc(node.type)}</span></td>
            <td>${esc(node.text || node.label || node.stat || node.enemy_id || '-')}</td>
            <td>
                ${node.type !== 'end' ? `
                    <select class="adv-select adv-inline-next" data-node-id="${esc(nid)}" style="width: 140px;">
                        <option value="">(無)</option>
                        ${Object.keys(nodes).map(k => `<option value="${esc(k)}" ${k === node.next_node_id ? 'selected' : ''}>${esc(k)}</option>`).join('')}
                    </select>
                ` : '章節結束'}
            </td>
            <td>
                <button type="button" class="btn second" data-select-node="${esc(nid)}">編輯屬性</button>
            </td>
        </tr>
    `).join('');
}

function renderNodeInspector() {
    const flow = currentDraft?.content?.flowcharts?.[currentFlowId];
    const node = flow?.nodes?.[selectedNodeId];
    if (!node) { advInspectorBody.textContent = '請選取節點。'; return; }
    advInspectorTitle.textContent = `節點：${selectedNodeId}`;
    renderFields(advInspectorBody, node, pushUndo, () => drawConnections(flow), { nodeIds: Object.keys(flow.nodes), lockType: true });
    const remove = document.createElement('button');
    remove.type = 'button'; remove.textContent = '刪除節點'; remove.className = 'btn second';
    remove.onclick = () => {
        if (!confirm(`刪除節點 ${selectedNodeId}？引用此節點的連線也需調整。`)) return;
        pushUndo(); delete flow.nodes[selectedNodeId]; selectedNodeId = null; renderAll();
    };
    advInspectorBody.append(remove);
}

/** 渲染非流程圖之資源編輯區（世界設定、員工角色映射、NPC、地點、物品、任務等） */
function renderResourceWorkspace() {
    if (!advCanvasViewport || !advInspectorBody) return;
    if (advCanvasTitle) advCanvasTitle.textContent = `資源編輯：${currentSection}`;
    if (advNodeListView) advNodeListView.hidden = true;
    clearCanvas();

    const content = currentDraft?.content || {};

    if (currentSection === 'world_settings') {
        advInspectorTitle.textContent = '世界設定';
        const world = {};
        for (const key of ['world_name', 'description', 'start_location_id', 'safe_location_id', 'traits', 'initial_inventory']) {
            world[key] = content[key] ?? (['traits', 'initial_inventory'].includes(key) ? [] : '');
        }
        renderFields(advInspectorBody, world, pushUndo, () => Object.assign(content, world));
    } else if (currentSection === 'staff_mapping') {
        advInspectorTitle.textContent = '員工角色映射管理';
        const npcs = content.npcs || {};
        advInspectorBody.innerHTML = `
            <p class="adventure-muted" style="margin-top: 0;">將在職員工安排為劇中 NPC。發布時會保存角色快照；若同事本人進入遊戲，將自動替換為虛構替代角色。</p>
            ${Object.entries(npcs).map(([nid, npc]) => `
                <div style="border: 1px solid var(--border, #e2e8f0); border-radius: 8px; padding: 0.75rem; margin-bottom: 0.75rem;">
                    <b>NPC 槽位：${esc(npc.slot_name || nid)}</b>
                    <div class="adv-form-group" style="margin-top: 0.4rem;">
                        <label>映射員工</label>
                        <select class="adv-select adv-staff-map-select" data-npc-id="${esc(nid)}">
                            <option value="">(未映射，使用虛構角色)</option>
                            ${staffOptions.map(s => `
                                <option value="${esc(s.employee_id)}" ${s.employee_id === npc.mapped_employee_id ? 'selected' : ''}>
                                    ${esc(s.display_name)} (${esc(s.employee_id)}) - ${esc(s.department)} ${esc(s.position)}
                                </option>
                            `).join('')}
                        </select>
                    </div>
                    <div class="adv-form-group">
                        <label>虛構替代角色姓名 (本人入戲時替換)</label>
                        <input type="text" class="adv-input adv-fallback-name" data-npc-id="${esc(nid)}" value="${esc(npc.fallback_character?.name || '')}">
                    </div>
                </div>
            `).join('')}
        `;
        document.querySelectorAll('.adv-staff-map-select').forEach(sel => {
            sel.onchange = () => {
                pushUndo();
                const nid = sel.dataset.npcId;
                const chosen = staffOptions.find(s => s.employee_id === sel.value);
                npcs[nid].mapped_employee_id = sel.value;
                npcs[nid].mapped_employee_snapshot = chosen ? {
                    employee_id: chosen.employee_id,
                    display_name: chosen.display_name,
                    department: chosen.department,
                    position: chosen.position,
                    photo_file: chosen.photo_file,
                } : null;
            };
        });
        document.querySelectorAll('.adv-fallback-name').forEach(inp => {
            inp.onchange = () => {
                pushUndo();
                const nid = inp.dataset.npcId;
                npcs[nid].fallback_character = npcs[nid].fallback_character || {};
                npcs[nid].fallback_character.name = inp.value;
            };
        });
    } else {
        advInspectorTitle.textContent = `資源管理：${currentSection}`;
        content[currentSection] ??= {};
        renderFields(advInspectorBody, content[currentSection], pushUndo, () => {}, {});
    }

}

/** 綁定編輯器各項滑鼠、快捷鍵與工具列事件 */
function bindEditorEvents() {
    window.addEventListener('beforeunload', event => { if (isDirty) { event.preventDefault(); event.returnValue = ''; } });
    advWorldSelect?.addEventListener('change', async () => {
        if (isDirty && !confirm('放棄尚未儲存的草稿？')) { advWorldSelect.value = currentWorldNo; return; }
        currentWorldNo = advWorldSelect.value;
        await loadDraft(currentWorldNo);
    });
    advNewWorldBtn?.addEventListener('click', async () => {
        const worldNo = prompt('新世界編號（1～50 字）');
        if (!worldNo?.trim()) return;
        const worldName = prompt('新世界名稱');
        if (!worldName?.trim()) return;
        try {
            await adminRequest('/api/admin/adventure/worlds/save', { world_no: worldNo.trim(), world_name: worldName.trim(), description: '', is_open: false });
            currentWorldNo = worldNo.trim(); await loadWorlds(); await loadDraft(currentWorldNo);
        } catch (error) { alert(error.message); }
    });
    // 導覽切換
    advNavCol?.addEventListener('click', event => {
        const item = event.target.closest('[data-nav]');
        if (item) {
            advNavCol.querySelectorAll('[data-nav]').forEach(b => b.classList.remove('active'));
            item.classList.add('active');
            currentSection = item.dataset.nav;
            renderAll();
            return;
        }

        const subitem = event.target.closest('[data-flow-id]');
        if (subitem) {
            advNavCol.querySelectorAll('[data-nav]').forEach(b => b.classList.remove('active'));
            document.querySelector('[data-nav="flowcharts"]')?.classList.add('active');
            currentSection = 'flowcharts';
            currentFlowId = subitem.dataset.flowId;
            selectedNodeId = null;
            renderAll();
            return;
        }

        if (event.target.closest('#advCreateFlowBtn')) {
            const fid = prompt('請輸入新流程圖英文識別碼 (例如: flow_inn_gossip)：');
            if (fid && fid.trim()) {
                const flowKey = fid.trim();
                pushUndo();
                currentDraft.content.flowcharts[flowKey] = {
                    id: flowKey,
                    name: flowKey,
                    nodes: {
                        start: { type: 'start', next_node_id: 'node_1', x: 60, y: 60 },
                        node_1: { type: 'narrative', text: '全新劇情事件起點。', next_node_id: 'end', x: 260, y: 60 },
                        end: { type: 'end', end_type: 'return_to_exploration', x: 480, y: 60 },
                    },
                };
                currentFlowId = flowKey;
                renderAll();
            }
        }
    });


    function connectPort(event) {
        const port = event.target.closest('[data-port]');
        if (!port) return;
        const nid = port.closest('[data-node-id]')?.dataset.nodeId;
        const flow = currentDraft?.content?.flowcharts?.[currentFlowId];
        if (!flow || !nid) return;
        if (port.dataset.port === 'out') {
            const node = flow.nodes[nid];
            let fields = ['next_node_id'];
            if (node.type === 'condition') fields = ['next_node_true', 'next_node_false'];
            if (node.type === 'check') fields = ['success_node_id', 'fail_node_id'];
            if (node.type === 'combat') fields = ['win_node_id', 'lose_node_id', 'escape_node_id'];
            if (node.type === 'choice' || node.type === 'random') {
                const key = node.type === 'choice' ? 'choices' : 'branches';
                fields = (node[key] || []).map((_, i) => `${key}.${i}.next_node_id`);
            }
            if (!fields.length) { alert('請先在節點表單新增選項或分支。'); return; }
            const choice = fields.length === 1 ? fields[0] : prompt('輸入要連線的出口：\n' + fields.join('\n'), fields[0]);
            if (fields.includes(choice)) connectingFrom = { nid, field: choice };
        } else if (connectingFrom) {
            pushUndo();
            let target = flow.nodes[connectingFrom.nid];
            const path = connectingFrom.field.split('.');
            for (const part of path.slice(0, -1)) target = target[part];
            target[path[path.length - 1]] = nid;
            connectingFrom = null; drawConnections(flow); renderNodeInspector();
        }
        event.stopPropagation();
    }
    advCanvasViewport?.addEventListener('click', event => { if (event.detail === 0) connectPort(event); });
    advCanvasViewport?.addEventListener('pointerdown', event => {
        if (event.target.closest('[data-port="out"]')) { connectPort(event); event.preventDefault(); }
    });
    advCanvasViewport?.addEventListener('pointerup', event => {
        if (event.target.closest('[data-port="in"]')) connectPort(event);
    });

    // 畫布滑鼠互動：拖曳節點、平移與滾輪縮放
    advCanvasViewport?.addEventListener('pointerdown', event => {
        if (event.target.closest('[data-port]')) return;
        const nodeEl = event.target.closest('.adv-node-item');
        if (nodeEl) {
            pushUndo();
            isDraggingNode = true;
            draggedNode = nodeEl;
            selectedNodeId = nodeEl.dataset.nodeId;
            document.querySelectorAll('.adv-node-item').forEach(n => n.classList.remove('selected'));
            nodeEl.classList.add('selected');
            renderNodeInspector();

            dragStartPos = {
                x: event.clientX,
                y: event.clientY,
                origLeft: parseFloat(nodeEl.style.left) || 0,
                origTop: parseFloat(nodeEl.style.top) || 0,
            };
            event.stopPropagation();
            return;
        }

        // 點擊空白處平移畫布
        isPanning = true;
        advCanvasViewport.classList.add('panning');
        panStartPos = {
            x: event.clientX - pan.x,
            y: event.clientY - pan.y,
        };
    });

    window.addEventListener('pointermove', event => {
        if (isDraggingNode && draggedNode) {
            const dx = (event.clientX - dragStartPos.x) / zoom;
            const dy = (event.clientY - dragStartPos.y) / zoom;
            const newX = Math.round(dragStartPos.origLeft + dx);
            const newY = Math.round(dragStartPos.origTop + dy);

            draggedNode.style.left = `${newX}px`;
            draggedNode.style.top = `${newY}px`;

            const flow = currentDraft?.content?.flowcharts?.[currentFlowId];
            if (flow && flow.nodes[draggedNode.dataset.nodeId]) {
                flow.nodes[draggedNode.dataset.nodeId].x = newX;
                flow.nodes[draggedNode.dataset.nodeId].y = newY;
                drawConnections(flow);
            }
            return;
        }

        if (isPanning) {
            pan.x = event.clientX - panStartPos.x;
            pan.y = event.clientY - panStartPos.y;
            applyTransform();
        }
    });

    window.addEventListener('pointerup', () => {
        if (isDraggingNode) {
            isDraggingNode = false;
            draggedNode = null;
        }
        if (isPanning) {
            isPanning = false;
            advCanvasViewport?.classList.remove('panning');
        }
    });

    // 縮放控制
    advZoomIn?.addEventListener('click', () => { zoom = Math.min(1.5, zoom + 0.1); applyTransform(); });
    advZoomOut?.addEventListener('click', () => { zoom = Math.max(0.5, zoom - 0.1); applyTransform(); });
    advZoomReset?.addEventListener('click', () => { zoom = 1.0; pan = { x: 40, y: 40 }; applyTransform(); });

    // 切換圖形 vs 清單檢視
    advToggleView?.addEventListener('click', () => {
        isListView = !isListView;
        advToggleView.textContent = isListView ? '圖形畫布' : '節點清單';
        renderFlowchartWorkspace();
    });

    // 新增節點
    advAddNodeSelect?.addEventListener('change', () => {
        const type = advAddNodeSelect.value;
        if (!type) return;
        advAddNodeSelect.value = '';

        const flow = currentDraft?.content?.flowcharts?.[currentFlowId];
        if (!flow) return;

        const newId = `node_${Date.now().toString(36).substring(4)}`;
        pushUndo();
        flow.nodes[newId] = { ...clone(nodeTemplates[type]), x: Math.round((-pan.x + 300) / zoom), y: Math.round((-pan.y + 200) / zoom) };

        selectedNodeId = newId;
        renderFlowchartWorkspace();
    });

    // 復原 / 重做
    advUndoBtn?.addEventListener('click', undo);
    advRedoBtn?.addEventListener('click', redo);

    // 快捷鍵 (Ctrl+Z, Ctrl+Y, Ctrl+S)
    window.addEventListener('keydown', event => {
        if (!document.querySelector('#adventurePanel.active') || event.target.closest('input, textarea, select, [contenteditable]')) return;
        if (event.ctrlKey && event.key === 'z') { event.preventDefault(); undo(); }
        if (event.ctrlKey && event.key === 'y') { event.preventDefault(); redo(); }
        if (event.ctrlKey && event.key === 's') { event.preventDefault(); saveDraft(); }
    });

    // 儲存草稿
    advSaveDraftBtn?.addEventListener('click', saveDraft);

    // 靜態驗證
    advValidateBtn?.addEventListener('click', async () => {
        try {
            const res = await adminRequest('/api/admin/adventure/validate', { content: currentDraft.content });
            if (res.valid) {
                alert('✓ 劇本結構驗證通過！無懸空連線與缺少出口錯誤。');
            } else {
                alert('✗ 劇本驗證失敗，發現以下錯誤：\n\n- ' + res.errors.join('\n- '));
            }
        } catch (err) {
            alert('驗證請求失敗：' + err.message);
        }
    });

    // 正式發布
    advPublishBtn?.addEventListener('click', async () => {
        if (!confirm(`確定要將世界【${currentWorldNo}】的目前草稿發布為正式版本嗎？\n發布後將建立不可變版本快照並對員工開放遊玩。`)) return;
        try {
            if (isDirty && !(await saveDraft())) return;
            const res = await adminRequest('/api/admin/adventure/publish', {
                world_no: currentWorldNo,
                expected_revision: currentDraftRevision,
            });
            alert(`★ 成功發布版本：【${res.version_no}】！世界已正式開放遊玩。`);
            await loadWorlds();
            await loadDraft(currentWorldNo);
        } catch (err) {
            alert('發布失敗：' + err.message);
        }
    });

    // 每次開啟可明確重設；單步之間保留獨立狀態。
    async function stepSimulation(reset = false) {
        if (simPending) return;
        simPending = true;
        advSimRunBtn.disabled = true;
        try {
            const actionIndex = Number(document.querySelector('#advSimActionType').value);
            const res = await adminRequest('/api/admin/adventure/test-run', {
                content: currentDraft.content, initial_state: reset ? null : simState,
                action: reset ? {} : simActions[actionIndex] || {},
                rng_seed: Number(document.querySelector('#advSimSeed').value) || 42,
            });
            simState = res.new_state; simActions = res.available_actions;
            document.querySelector('#advSimActionType').replaceChildren(...simActions.map((a, i) => {
                const option = document.createElement('option'); option.value = i; option.textContent = a.label; return option;
            }));
            advSimTrace.textContent = res.logs.map(l => l.text).join('\n') + '\n' + JSON.stringify(res.diff, null, 2);
        } catch (error) { advSimTrace.textContent = error.message; }
        finally { simPending = false; advSimRunBtn.disabled = false; }
    }
    advTestRunBtn?.addEventListener('click', async () => { advSimModal.hidden = false; await stepSimulation(true); });
    advSimCloseBtn?.addEventListener('click', () => { advSimModal.hidden = true; });
    advSimRunBtn?.addEventListener('click', () => stepSimulation());
    const resetSimulation = document.createElement('button'); resetSimulation.type = 'button';
    resetSimulation.textContent = '重設試跑'; resetSimulation.className = 'btn second';
    resetSimulation.onclick = () => stepSimulation(true); advSimRunBtn?.after(resetSimulation);

    // 清單檢視中的下一出口快速下拉選單
    advNodeListTableBody?.addEventListener('change', event => {
        const sel = event.target.closest('.adv-inline-next');
        if (!sel) return;
        const nid = sel.dataset.nodeId;
        const flow = currentDraft?.content?.flowcharts?.[currentFlowId];
        if (flow && flow.nodes[nid]) {
            pushUndo();
            flow.nodes[nid].next_node_id = sel.value;
        }
    });
    advNodeListTableBody?.addEventListener('click', event => {
        const btn = event.target.closest('[data-select-node]');
        if (!btn) return;
        selectedNodeId = btn.dataset.selectNode;
        renderNodeInspector();
    });
}

/** 提交儲存草稿 */
async function saveDraft() {
    try {
        const res = await adminRequest('/api/admin/adventure/draft/save', {
            world_no: currentWorldNo,
            expected_revision: currentDraftRevision,
            content: currentDraft.content,
        });
        currentDraftRevision = res.revision;
        if (advDraftRev) advDraftRev.textContent = currentDraftRevision;
        setDirty(false);
        alert('草稿已成功儲存！修訂號：' + currentDraftRevision);
        return true;
    } catch (err) {
        alert('儲存草稿失敗：' + err.message);
    }
}

// 監聽 MIS 頂部分頁切換以初始化
document.querySelector('#adminTabs')?.addEventListener('click', event => {
    const tab = event.target.closest('[data-panel]');
    if (tab && tab.dataset.panel === 'adventurePanel') {
        initAdventureEditor();
    }
});
