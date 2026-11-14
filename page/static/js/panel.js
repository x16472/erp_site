/**
 * Staff Tabs 控制器
 * 負責：按鈕 active 狀態切換 + 對應 panel 顯示/隱藏
 */
export const StaffTabs = {
    initialized: false,
    // 選擇器集中管理，方便維護
    selectors: {
        tabsContainer: '#staffTabs',
        tabButtons: '#staffTabs button',
        contentContainer: '.portal-content',
        panels: '.portal-content .panel'
    },
    /** 初始化：綁定事件 + 設定預設顯示 */
    init() {
        if (this.initialized) return;
        this.initialized = true;
        this.bindEvents();
        this.showActivePanel();
    },
    /** 綁定點擊事件（使用事件委派） */
    bindEvents() {
        const container = document.querySelector(this.selectors.tabsContainer);
        if (!container) return;

        container.addEventListener('click', (e) => {
            const btn = e.target.closest('button');
            if (!btn) return;
            this.switchTab(btn);
        });
    },
    /**
     * 切換分頁
     * @param {HTMLElement} btn - 被點擊的按鈕
     */
    switchTab(btn) {
        // 1. 更新按鈕 active 狀態
        document.querySelectorAll(this.selectors.tabButtons)
            .forEach(b => b.classList.toggle('active', b === btn));

        // 2. 顯示對應 panel
        const targetId = btn.dataset.panel;
        this.showPanel(targetId);
    },
    /**
     * 顯示指定 id 的 panel，其餘隱藏
     * @param {string} panelId
     */
    showPanel(panelId) {
        const panels = [...document.querySelectorAll(this.selectors.panels)];
        if (!panels.some(panel => panel.id === panelId)) return;
        panels.forEach(panel => {
            panel.classList.toggle('active', panel.id === panelId);
            panel.hidden = panel.id !== panelId;
        });
        document.querySelector(this.selectors.tabsContainer)?.dispatchEvent(new CustomEvent('panelchange', {
            detail: { panelId },
        }));
    },
    /** 根據目前有 active 的按鈕，顯示對應 panel（頁面載入時用） */
    showActivePanel() {
        const activeBtn = document.querySelector(`${this.selectors.tabButtons}.active`);
        if (activeBtn) {
            this.showPanel(activeBtn.dataset.panel);
        }
    }
};

export function bindTabs(tabList, {
    buttonSelector = '[data-panel]',
    panelSelector = '.admin-panel',
} = {}) {
    tabList.addEventListener('click', event => {
        const button = event.target.closest(buttonSelector);
        if (!button || !tabList.contains(button)) return;
        tabList.querySelectorAll(buttonSelector).forEach(item => {
            item.classList.toggle('active', item === button);
        });
        document.querySelectorAll(panelSelector).forEach(panel => {
            panel.classList.toggle('active', panel.id === button.dataset.panel);
        });
    });
}
