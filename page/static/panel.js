/**
 * Staff Tabs 控制器
 * 負責：按鈕 active 狀態切換 + 對應 panel 顯示/隱藏
 */
const StaffTabs = {
    // 選擇器集中管理，方便維護
    selectors: {
        tabsContainer: '#staffTabs',
        tabButtons: '#staffTabs button',
        contentContainer: '.portal-content',
        panels: '.portal-content .panel'
    },
    /** 初始化：綁定事件 + 設定預設顯示 */
    init() {
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
        document.querySelectorAll(this.selectors.panels)
            .forEach(panel => {
                panel.style.display = panel.id === panelId ? 'block' : 'none';
            });
    },
    /** 根據目前有 active 的按鈕，顯示對應 panel（頁面載入時用） */
    showActivePanel() {
        const activeBtn = document.querySelector(`${this.selectors.tabButtons}.active`);
        if (activeBtn) {
            this.showPanel(activeBtn.dataset.panel);
        }
    }
};
// 頁面載入完成後初始化
document.addEventListener('DOMContentLoaded', () => StaffTabs.init());