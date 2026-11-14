import { apiData, escapeHtml, requireEmployee, jsonRequest } from './api.js';

export const AdventurePlayer = {
    initialized: false,
    init() {
        if (this.initialized) return;
        this.initialized = true;
        const esc = escapeHtml;

        // 遊戲狀態與快取
        let currentEmployee = null;
        let activeWorldNo = 'DEMO_TOWN';
        let activeWorldData = null;
        let activeSave = null;
        let activeState = null;
        let activeRevision = 1;
        let hasInitialized = false;
        let adventureStatus = '就緒';
        let isActionPending = false;
        let selectedSlot = 1;
        let selectedTrait = '';
        let pendingAction = null;
        let historyCursor = 0;
        let historyLogs = [];
        const advMainStage = document.querySelector('#advMainStage');
        const advWorkspaceMain = document.querySelector('#advWorkspaceMain');
        const advLogPanel = document.querySelector('#advLogPanel');

        // DOM 節點快取
        const playerStateEl = document.querySelector('#playerState');
        const adventureSection = document.querySelector('#pl5');
        const adventureEntry = document.querySelector('#adventureEntry');
        const adventureGame = document.querySelector('#adventureGame');
        const advSlotsGrid = document.querySelector('#advSlotsGrid');
        const advWorldTitle = document.querySelector('#advWorldTitle');
        const advWorldDesc = document.querySelector('#advWorldDesc');

        // Modal 節點
        const advCreateModal = document.querySelector('#advCreateModal');
        const advModalCloseBtn = document.querySelector('#advModalCloseBtn');
        const advCancelCreate = document.querySelector('#advCancelCreate');
        const advConfirmCreate = document.querySelector('#advConfirmCreate');
        const advPlayerPreview = document.querySelector('#advPlayerPreview');
        const advTraitsList = document.querySelector('#advTraitsList');

        // 遊戲主畫面節點
        const advBackToSaves = document.querySelector('#advBackToSaves');
        const advWorldNameDisplay = document.querySelector('#advWorldNameDisplay');
        const advSlotIndexDisplay = document.querySelector('#advSlotIndexDisplay');
        const advRevDisplay = document.querySelector('#advRevDisplay');
        const advSaveStatus = document.querySelector('#advSaveStatus');

        const advTimeBadge = document.querySelector('#advTimeBadge');
        const advLocTitle = document.querySelector('#advLocTitle');
        const advLocDesc = document.querySelector('#advLocDesc');
        const advTurnCounter = document.querySelector('#advTurnCounter');
        const advNpcPills = document.querySelector('#advNpcPills');
        const advObjPills = document.querySelector('#advObjPills');

        const advDialogueBox = document.querySelector('#advDialogueBox');
        const advSpeakerName = document.querySelector('#advSpeakerName');
        const advDialogueText = document.querySelector('#advDialogueText');
        const advDialogueChoices = document.querySelector('#advDialogueChoices');

        const advCombatArena = document.querySelector('#advCombatArena');
        const advCombatRound = document.querySelector('#advCombatRound');
        const advFighterPlayerName = document.querySelector('#advFighterPlayerName');
        const advCombatPlayerHpVal = document.querySelector('#advCombatPlayerHpVal');
        const advCombatPlayerHpBar = document.querySelector('#advCombatPlayerHpBar');
        const advCombatPlayerEpVal = document.querySelector('#advCombatPlayerEpVal');
        const advCombatPlayerEpBar = document.querySelector('#advCombatPlayerEpBar');
        const advFighterEnemyName = document.querySelector('#advFighterEnemyName');
        const advCombatEnemyHpVal = document.querySelector('#advCombatEnemyHpVal');
        const advCombatEnemyHpBar = document.querySelector('#advCombatEnemyHpBar');
        const advCombatActions = document.querySelector('#advCombatActions');

        const advActionsPanel = document.querySelector('#advActionsPanel');
        const advActionsGrid = document.querySelector('#advActionsGrid');
        const advLogStream = document.querySelector('#advLogStream');
        const advLoadMoreHistory = document.querySelector('#advLoadMoreHistory');

        // 側欄節點
        const advCharAvatar = document.querySelector('#advCharAvatar');
        const advCharName = document.querySelector('#advCharName');
        const advCharDept = document.querySelector('#advCharDept');
        const advCharTrait = document.querySelector('#advCharTrait');
        const advCharHpText = document.querySelector('#advCharHpText');
        const advCharHpBar = document.querySelector('#advCharHpBar');
        const advCharEpText = document.querySelector('#advCharEpText');
        const advCharEpBar = document.querySelector('#advCharEpBar');
        const advCharGold = document.querySelector('#advCharGold');
        const advStatAtk = document.querySelector('#advStatAtk');
        const advStatDef = document.querySelector('#advStatDef');
        const advStatStr = document.querySelector('#advStatStr');
        const advStatAgi = document.querySelector('#advStatAgi');
        const advStatInt = document.querySelector('#advStatInt');
        const advStatCha = document.querySelector('#advStatCha');

        const advBagCount = document.querySelector('#advBagCount');
        const advEquipWeapon = document.querySelector('#advEquipWeapon');
        const advEquipArmor = document.querySelector('#advEquipArmor');
        const advInventoryList = document.querySelector('#advInventoryList');
        const advMapGrid = document.querySelector('#advMapGrid');
        const advJournalContent = document.querySelector('#advJournalContent');
        const advMobileTabs = document.querySelector('#advMobileTabs');
        const advSidebar = document.querySelector('#advSidebar');

        let currentJournalTab = 'quests';
        let currentMobileSub = 'scene';

        function updateAdventureState(statusText, activeTab = document.querySelector('#staffTabs .active')?.dataset.panel) {
            adventureStatus = statusText;
            if (advSaveStatus) {
                advSaveStatus.textContent = statusText;
            }
            if (activeTab === 'pl5' && playerStateEl) {
                playerStateEl.textContent = `穿越冒險：${statusText}`;
            }
        }
        function generateRequestId() {
            return 'REQ_' + Math.random().toString(36).substring(2, 10) + '_' + Date.now();
        }

        /** 第一次切換到穿越冒險分頁時才初始化 */
        async function ensureInitialized() {
            if (hasInitialized) return;
            hasInitialized = true;
            updateAdventureState('載入存檔中…');
            try {
                const session = await requireEmployee();
                currentEmployee = session.employee;
                await loadWorldsAndSaves();
                updateAdventureState('就緒');
            } catch (err) {
                hasInitialized = false;
                updateAdventureState('載入失敗');
                console.error('穿越冒險初始化失敗：', err);
            }
        }

        /** 載入開放世界與存檔清單 */
        async function loadWorldsAndSaves() {
            const worlds = await apiData('/api/adventure/worlds');
            if (!worlds?.length) { advSlotsGrid.textContent = '目前沒有開放的世界。'; return; }
            if (worlds && worlds.length) {
                activeWorldData = worlds[0];
                activeWorldNo = activeWorldData.world_no;
                if (advWorldTitle) advWorldTitle.textContent = activeWorldData.world_name;
                if (advWorldDesc) advWorldDesc.textContent = activeWorldData.description;
            }

            const saves = await apiData('/api/adventure/saves');
            renderSlots(saves || []);
        }

        /** 繪製 3 個存檔欄位 */
        function renderSlots(saves) {
            advSlotsGrid.innerHTML = '';
            const worldSaves = saves.filter(s => s.world_no === activeWorldNo);

            for (let slot = 1; slot <= 3; slot++) {
                const existing = worldSaves.find(s => s.slot_index === slot);
                const card = document.createElement('div');
                card.className = `portal-card adventure-slot-card ${existing ? '' : 'adventure-slot-empty'}`;

                if (existing) {
                    const timeDesc = { morning: '清晨', noon: '正午', dusk: '傍晚', night: '深夜' }[existing.time_of_day] || '白天';
                    card.innerHTML = `
                <div>
                    <span class="adventure-slot-badge">存檔槽位 ${slot}</span>
                    <h3 class="adventure-slot-title">${esc(existing.character?.display_name || '冒險者')}</h3>
                    <div class="adventure-slot-meta">
                        身分：${esc(existing.character?.department || '')} · ${esc(existing.character?.position || '')}<br>
                        存檔：${esc(existing.save_display_no || "—")}<br>
                        版本：${esc(existing.version_display_no || "—")} · 修訂號 ${existing.revision}
                    </div>
                    <div class="adventure-slot-stats">
                        <span>第 ${existing.turn} 回合</span>
                        <span>時段：${timeDesc}</span>
                        <span>生命：${existing.hp}/${existing.max_hp}</span>
                        <span>金幣：${existing.gold}</span>
                    </div>
                </div>
                <button type="button" class="btn primary" data-action="continue-save" data-save-no="${esc(existing.save_no)}">繼續冒險</button>
            `;
                } else {
                    card.innerHTML = `
                <div>
                    <span class="adventure-slot-badge">存檔槽位 ${slot}</span>
                    <h3 class="adventure-slot-title">空存檔</h3>
                    <p class="adventure-muted hint">尚未建立任何冒險紀錄</p>
                </div>
                <button type="button" class="btn second" data-action="new-save" data-slot="${slot}">+ 建立新角色</button>
            `;
                }
                advSlotsGrid.appendChild(card);
            }
        }

        /** 開啟建立新角色彈窗 */
        async function openCreateModal(slot) {
            selectedSlot = slot;
            selectedTrait = '';
            if (advPlayerPreview && currentEmployee) {
                advPlayerPreview.innerHTML = `
            <img class="adventure-preview-avatar staff-photo-preview" src="${currentEmployee.photo_file ? `static/staff/${esc(currentEmployee.photo_file)}` : 'static/appicon.png'}" alt="照片">
            <div>
                <b>${esc(currentEmployee.display_name)}</b>（${esc(currentEmployee.employee_id)}）<br>
                <span class="adventure-muted hint">${esc(currentEmployee.department)} · ${esc(currentEmployee.position)}</span>
            </div>
        `;
            }

            const traits = activeWorldData?.traits || [];
            selectedTrait = traits[0]?.id || '';
            advTraitsList.innerHTML = traits.map((t, idx) => `
        <button type="button" class="adventure-trait-card ${idx === 0 ? 'selected' : ''} btn second" data-trait-id="${esc(t.id)}">
            <b>${esc(t.name)}</b><span>${esc(t.desc || '')}</span>
        </button>`).join('') || '<p>使用共同基礎能力。</p>';

            advCreateModal.showModal();
        }

        function closeCreateModal() {
            advCreateModal.close();
        }

        /** 提交建立新存檔 */
        async function submitCreateSave() {
            if (advConfirmCreate.disabled) return;
            advConfirmCreate.disabled = true;
            updateAdventureState('正在進入故事世界…');
            try {
                const session = await requireEmployee();
                const payload = {
                    world_no: activeWorldNo,
                    slot_index: selectedSlot,
                    trait_id: selectedTrait,
                };
                const result = await jsonRequest('/api/adventure/saves/create', payload, {
                    csrf: session.csrf,
                    fallbackMessage: '建立存檔失敗',
                });
                closeCreateModal();
                openGameScreen(result);
            } catch (err) {
                alert(err.message || '建立存檔失敗');
                updateAdventureState('就緒');
            } finally {
                advConfirmCreate.disabled = false;
            }
        }

        /** 開啟並載入存檔主遊戲畫面 */
        async function openSaveGame(saveNo) {
            updateAdventureState('正在載入存檔…');
            try {
                const result = await apiData(`/api/adventure/state?save_no=${encodeURIComponent(saveNo)}`);
                openGameScreen(result);
            } catch (err) {
                alert(err.message || '載入存檔失敗');
                updateAdventureState('就緒');
            }
        }

        /** 切換顯示至遊戲畫面並更新 DOM */
        function openGameScreen(data) {
            activeSave = data;
            historyCursor = 0;
            historyLogs = [];
            activeState = data.state;
            activeRevision = data.revision;

            adventureEntry.hidden = true;
            adventureGame.hidden = false;

            renderGameScreen();
            syncMobilePanels();
            updateAdventureState(activeState.combat ? '戰鬥中' : '就緒');
        }

        /** 渲染遊戲主畫面的全部內容 */
        function renderGameScreen() {
            if (!activeSave || !activeState) return;

            // 頂部資訊
            advWorldNameDisplay.textContent = activeSave.world_name || '陌生小鎮';
            advSlotIndexDisplay.textContent = activeSave.slot_index;
            advRevDisplay.textContent = activeRevision;

            // 場景資訊卡
            advTimeBadge.textContent = activeState.time_name || '白天';
            advLocTitle.textContent = activeSave.location?.name || '未知地點';
            advLocDesc.textContent = activeSave.location?.description || '';
            advTurnCounter.textContent = activeState.turn || 1;

            // 在場 NPC
            const npcs = activeSave.npcs_in_scene || [];
            advNpcPills.innerHTML = npcs.length ? npcs.map(npc => `
        <div class="adventure-npc-pill tag">
            <img src="${npc.photo_file ? `static/staff/${esc(npc.photo_file)}` : 'static/appicon.png'}" alt="${esc(npc.name)}">
            <span>${esc(npc.name)}（${esc(npc.title || '居民')}）</span>
        </div>
    `).join('') : '<span class="adventure-muted hint">無特定人物</span>';

            // 環境物件
            const objects = activeSave.location?.objects || [];
            advObjPills.innerHTML = objects.length ? objects.map(obj => `
        <div class="adventure-obj-pill tag">🔍 ${esc(obj.name)}</div>
    `).join('') : '<span class="adventure-muted hint">無顯著物件</span>';

            // 側欄角色屬性
            const char = activeState.character || {};
            advCharName.textContent = char.display_name || '冒險者';
            advCharDept.textContent = `${char.department || ''} · ${char.position || ''}`;
            advCharTrait.textContent = char.trait_name || '無特長';
            if (advCharAvatar && char.photo_file) {
                advCharAvatar.src = `static/staff/${esc(char.photo_file)}`;
            }

            const hpPercent = Math.max(0, Math.min(100, (char.hp / char.max_hp) * 100));
            advCharHpText.textContent = `${char.hp} / ${char.max_hp}`;
            advCharHpBar.value = hpPercent;

            const epPercent = Math.max(0, Math.min(100, (char.ep / char.max_ep) * 100));
            advCharEpText.textContent = `${char.ep} / ${char.max_ep}`;
            advCharEpBar.value = epPercent;

            advCharGold.textContent = `${char.gold} 金幣`;

            advStatAtk.textContent = char.atk || 10;
            advStatDef.textContent = char.def || 5;
            const attrs = char.attributes || {};
            advStatStr.textContent = attrs.strength || 10;
            advStatAgi.textContent = attrs.agility || 10;
            advStatInt.textContent = attrs.intellect || 10;
            advStatCha.textContent = attrs.charisma || 10;

            // 側欄背包與裝備
            const equip = activeState.equipment || {};
            advEquipWeapon.textContent = equip.weapon || '無';
            advEquipArmor.textContent = equip.armor || '無';

            const inv = activeState.inventory || [];
            advBagCount.textContent = `${inv.reduce((sum, i) => sum + i.count, 0)} 件`;
            advInventoryList.innerHTML = inv.length ? inv.map(i => `
        <div class="adventure-inv-item">
            <div>
                <span class="adventure-inv-name">${esc(i.name)} x${i.count}</span>
                <p class="adventure-muted hint">${esc(i.description || '')}</p>
            </div>
            <div class="adventure-inv-actions actions">
                ${i.type === 'consumable' ? `<button type="button" class="adventure-inv-btn btn second" data-item-action="use" data-item-id="${esc(i.item_id)}">使用</button>` : ''}
                ${['weapon', 'armor', 'accessory'].includes(i.type) ? `<button type="button" class="adventure-inv-btn btn second" data-item-action="equip" data-item-id="${esc(i.item_id)}">${i.equipped ? '卸下' : '裝備'}</button>` : ''}
            </div>
        </div>
    `).join('') : '<p class="adventure-muted hint">背包空空如也</p>';

            // 地圖列表
            const exits = activeSave.location?.exits || [];
            advMapGrid.innerHTML = exits.map(e => `
        <div class="adventure-map-item card-head">
            <span>📍 ${esc(e.name)}</span>
            <button type="button" class="btn second" data-travel-id="${esc(e.id)}">啟程前往</button>
        </div>
    `).join('');

            // 手札內容
            renderJournalContent();

            // 歷史紀錄
            renderLogs(activeState.recent_logs || []);

            // 根據狀態切換展示區塊（對話 vs 戰鬥 vs 自由探索）
            if (activeState.combat) {
                advDialogueBox.hidden = true;
                advActionsPanel.hidden = true;
                advCombatArena.hidden = false;
                renderCombat(activeState.combat);
            } else if (activeState.interaction) {
                advCombatArena.hidden = true;
                advActionsPanel.hidden = true;
                advDialogueBox.hidden = false;
                renderDialogue();
            } else {
                advCombatArena.hidden = true;
                advDialogueBox.hidden = true;
                advActionsPanel.hidden = false;
                renderActions(activeSave.available_actions || []);
            }
        }

        /** 繪製對話與選項 */
        function renderDialogue() {
            const choices = activeSave.available_actions || [];
            const lastLog = [...(activeState.recent_logs || [])].reverse().find(l => l.type === 'dialogue' || l.type === 'narrative');

            advSpeakerName.textContent = lastLog?.speaker || '對話事件';
            advDialogueText.textContent = lastLog?.text || '請選擇你的回應：';

            advDialogueChoices.innerHTML = choices.map(c => `
        <button type="button" class="adventure-choice-btn btn second" data-choice-payload='${esc(JSON.stringify(c))}'>
            ${esc(c.label)}
        </button>
    `).join('');
        }

        /** 繪製戰鬥畫面 */
        function renderCombat(combat) {
            advCombatRound.textContent = combat.round || 1;
            advFighterPlayerName.textContent = activeState.character?.display_name || '玩家';
            advFighterEnemyName.textContent = combat.enemy_name || '敵人';

            const char = activeState.character || {};
            const pHpPct = Math.max(0, Math.min(100, (char.hp / char.max_hp) * 100));
            advCombatPlayerHpVal.textContent = `${char.hp}/${char.max_hp}`;
            advCombatPlayerHpBar.value = pHpPct;

            const pEpPct = Math.max(0, Math.min(100, (char.ep / char.max_ep) * 100));
            advCombatPlayerEpVal.textContent = `${char.ep}/${char.max_ep}`;
            advCombatPlayerEpBar.value = pEpPct;

            const eHpPct = Math.max(0, Math.min(100, (combat.enemy_hp / combat.enemy_max_hp) * 100));
            advCombatEnemyHpVal.textContent = `${combat.enemy_hp}/${combat.enemy_max_hp}`;
            advCombatEnemyHpBar.value = eHpPct;

            const actions = activeSave.available_actions || [];
            advCombatActions.innerHTML = actions.map(a => `
        <button type="button" class="btn ${a.subaction === 'attack' ? 'primary' : 'second'}" data-action-payload='${esc(JSON.stringify(a))}'>
            ${esc(a.label)}
        </button>
    `).join('');
        }

        /** 繪製自由探索可用行動按鈕 */
        function renderActions(actions) {
            advActionsGrid.innerHTML = '';
            if (!actions.length) {
                advActionsGrid.innerHTML = '<p class="adventure-muted hint">暫無可用行動。</p>';
                return;
            }

            actions.forEach(a => {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'btn second adventure-act-btn';
                btn.innerHTML = `
            <span class="adventure-act-title">${esc(a.label)}</span>
            ${a.desc ? `<span class="adventure-act-desc">${esc(a.desc)}</span>` : ''}
            ${a.cost && Object.keys(a.cost).length ? `<span class="adventure-act-cost">消耗：${Object.entries(a.cost).map(([k, v]) => `${k === 'turn' ? '回合' : k === 'ep' ? '精力' : '金幣'} -${v}`).join('，')}</span>` : ''}
        `;
                btn.addEventListener('click', () => dispatchAction(a));
                advActionsGrid.appendChild(btn);
            });
        }

        /** 繪製敘事紀錄清單 */
        function renderLogs(logs) {
            advLogStream.innerHTML = logs.map(l => `
        <div class="adventure-log-item ${esc(l.type || 'narrative')} hint">
            <span class="adventure-muted hint">[第 ${l.turn} 回合]</span>
            ${esc(l.text)}
        </div>
    `).join('');
            advLogStream.scrollTop = advLogStream.scrollHeight;
        }

        /** 繪製故事手札內容 */
        function renderJournalContent() {
            if (currentJournalTab === 'quests') {
                const quests = activeState.quests || [];
                advJournalContent.innerHTML = quests.length ? quests.map(q => `
            <div class="adv-quest-item">
                <b>${esc(q.name)}</b> ${q.completed ? '（★ 已達成）' : `（階段 ${q.stage}）`}<br>
                <span class="adventure-muted hint">${esc(q.description)}</span>
                ${q.method_used ? `<div class="hint">採用解法：${esc(q.method_used)}</div>` : ''}
            </div>
        `).join('') : '<p class="adventure-muted hint">暫無進行中的任務</p>';
            } else if (currentJournalTab === 'relations') {
                const rels = activeState.relationships || [];
                advJournalContent.innerHTML = rels.length ? rels.map(r => `
            <div class="adv-quest-item">
                <b>${esc(r.name)}</b>（${esc(r.title || '人物')}）<br>
                好感度：<span class="tag">${r.affinity}</span>
            </div>
        `).join('') : '<p class="adventure-muted hint">尚未結識任何人</p>';
            } else {
                const clues = activeState.clues || [];
                advJournalContent.innerHTML = clues.length ? clues.map(c => `
            <div class="adv-quest-item">
                🔑 <b>${esc(c)}</b>
            </div>
        `).join('') : '<p class="adventure-muted hint">尚未發現關鍵線索</p>';
            }
        }

        /** 核心提交行動函式（具防重、樂觀修訂號鎖定與交易） */
        async function dispatchAction(actionPayload) {
            if (isActionPending) return;
            isActionPending = true;
            updateAdventureState('行動處理中…');

            try {
                const session = await requireEmployee();
                const requestId = pendingAction?.request_id || generateRequestId();
                const payload = pendingAction || {
                    save_no: activeSave.save_no,
                    request_id: requestId,
                    expected_revision: activeRevision,
                    action: actionPayload,
                };

                pendingAction = payload;
                const result = await jsonRequest('/api/adventure/action', payload, {
                    csrf: session.csrf,
                    fallbackMessage: '行動執行失敗',
                });

                pendingAction = null;
                // 更新狀態
                activeState = result.state;
                activeRevision = result.revision;
                activeSave.location = result.location;
                activeSave.npcs_in_scene = result.npcs_in_scene;
                activeSave.available_actions = result.available_actions;

                renderGameScreen();
                updateAdventureState(activeState.combat ? '戰鬥中' : '就緒');
            } catch (err) {
                if (err.code === 'CONFLICT') {
                    pendingAction = null;
                    alert('存檔狀態已在其他視窗或操作中更新，正在為您同步最新狀態…');
                    await openSaveGame(activeSave.save_no);
                } else {
                    if (err.status && err.status < 500) pendingAction = null;
                    alert((err.message || '行動執行失敗') + (pendingAction ? '；再次操作將先確認上一筆行動結果。' : ''));
                    updateAdventureState('就緒');
                }
            } finally {
                isActionPending = false;
            }
        }

        // ==========================================
        // 事件綁定
        // ==========================================

        // 1. 監聽頂部分頁切換
        document.querySelector('#staffTabs')?.addEventListener('click', event => {
            const tab = event.target.closest('[data-panel]');
            if (!tab) return;
            if (tab.dataset.panel === 'pl5') {
                ensureInitialized();
                // 點擊事件可能早於共用控制器切換 active，使用目標分頁更新狀態。
                updateAdventureState(activeState ? (activeState.combat ? '戰鬥中' : '就緒') : adventureStatus, tab.dataset.panel);
            } else if (playerStateEl) {
                playerStateEl.textContent = '工作區就緒';
            }
        });

        // 2. 存檔列表點擊委派
        advSlotsGrid?.addEventListener('click', event => {
            const newBtn = event.target.closest('[data-action="new-save"]');
            if (newBtn) {
                openCreateModal(parseInt(newBtn.dataset.slot, 10));
                return;
            }
            const contBtn = event.target.closest('[data-action="continue-save"]');
            if (contBtn) {
                openSaveGame(contBtn.dataset.saveNo);
                return;
            }
        });

        // 3. Modal 關閉與選擇特長
        advModalCloseBtn?.addEventListener('click', closeCreateModal);
        advCancelCreate?.addEventListener('click', closeCreateModal);
        advConfirmCreate?.addEventListener('click', submitCreateSave);

        advTraitsList?.addEventListener('click', event => {
            const card = event.target.closest('[data-trait-id]');
            if (!card) return;
            advTraitsList.querySelectorAll('.adventure-trait-card').forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
            selectedTrait = card.dataset.traitId;
        });

        // 4. 返回存檔列表
        advBackToSaves?.addEventListener('click', () => {
            if (isActionPending || pendingAction) { alert('請先確認目前行動結果，再切換存檔。'); return; }
            adventureGame.hidden = true;
            adventureEntry.hidden = false;
            loadWorldsAndSaves();
        });

        // 5. 對話選項點擊
        advDialogueChoices?.addEventListener('click', event => {
            const btn = event.target.closest('[data-choice-payload]');
            if (!btn) return;
            const payload = JSON.parse(btn.dataset.choicePayload);
            dispatchAction(payload);
        });

        // 6. 戰鬥操作點擊
        advCombatActions?.addEventListener('click', event => {
            const btn = event.target.closest('[data-action-payload]');
            if (!btn) return;
            const payload = JSON.parse(btn.dataset.actionPayload);
            dispatchAction(payload);
        });

        // 7. 地圖快速移動
        advMapGrid?.addEventListener('click', event => {
            const btn = event.target.closest('[data-travel-id]');
            if (!btn) return;
            dispatchAction({
                action: 'move',
                target_location_id: btn.dataset.travelId,
            });
        });

        // 8. 背包物品點擊
        advInventoryList?.addEventListener('click', event => {
            const btn = event.target.closest('[data-item-action]');
            if (!btn) return;
            const action = btn.dataset.itemAction;
            const itemId = btn.dataset.itemId;
            if (action === 'use') {
                dispatchAction({ action: 'use_item', item_id: itemId });
            } else if (action === 'equip') {
                dispatchAction({ action: 'equip_item', item_id: itemId });
            }
        });

        // 9. 手札 Tab 切換
        document.querySelector('.adventure-journal-tabs')?.addEventListener('click', event => {
            const btn = event.target.closest('[data-j]');
            if (!btn) return;
            document.querySelectorAll('.adv-j-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentJournalTab = btn.dataset.j;
            renderJournalContent();
        });

        // 手機抽屜與桌面共用顯示狀態，避免縮放後遺留 hidden。
        function syncMobilePanels() {
            const mobile = window.matchMedia('(max-width: 679px)').matches;
            const showScene = !mobile || ['scene', 'log'].includes(currentMobileSub);
            if (advWorkspaceMain) advWorkspaceMain.hidden = !showScene;
            if (advMainStage) advMainStage.hidden = mobile && currentMobileSub !== 'scene';
            if (advLogPanel) advLogPanel.hidden = mobile && currentMobileSub !== 'log';
            advSidebar.hidden = mobile && showScene;
            const ids = { char: 'advSubChar', bag: 'advSubBag', map: 'advSubMap', quests: 'advSubQuests' };
            document.querySelectorAll('#advSidebar .adventure-card').forEach(card => {
                card.hidden = mobile && !showScene && card.id !== ids[currentMobileSub];
            });
        }
        advMobileTabs?.addEventListener('click', event => {
            const btn = event.target.closest('[data-sub]');
            if (!btn) return;
            currentMobileSub = btn.dataset.sub;
            advMobileTabs.querySelectorAll('.adventure-m-tab').forEach(b => b.classList.toggle('active', b === btn));
            syncMobilePanels();
        });
        window.matchMedia('(max-width: 679px)').addEventListener('change', syncMobilePanels);
        adventureSection?.addEventListener('error', event => {
            if (event.target instanceof HTMLImageElement && !event.target.src.endsWith('/static/appicon.png')) event.target.src = 'static/appicon.png';
        }, true);
        advLoadMoreHistory?.addEventListener('click', async () => {
            if (!activeSave || advLoadMoreHistory.disabled) return;
            advLoadMoreHistory.disabled = true;
            try {
                const rows = await apiData(`/api/adventure/history?save_no=${encodeURIComponent(activeSave.save_no)}&before_id=${historyCursor}`);
                if (rows.length) {
                    historyCursor = rows[rows.length - 1].cursor;
                    historyLogs = [...rows.slice().reverse().flatMap(row => row.response.new_logs || []), ...historyLogs];
                    renderLogs(historyLogs);
                }
            } catch (error) { alert(error.message); }
            finally { advLoadMoreHistory.disabled = false; }
        });

        // 若初始進入即在 pl5 分頁
        {
            const activeTab = document.querySelector('#staffTabs .active')?.dataset.panel;
            if (activeTab === 'pl5') {
                ensureInitialized();
            }
        }
    },
};
