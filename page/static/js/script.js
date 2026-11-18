import { Theme } from './theme.js';
import { StaffTabs } from './panel.js';

const pages = {
    index: () => import('./index.js').then(module => module.IndexPage),
    home: () => import('./home.js').then(module => module.HomePage),
    sales: () => import('./sales.js').then(module => module.SalesPage),
    exam: () => import('./exam.js').then(module => module.ExamPage),
    workflow: () => import('./workflow.js').then(module => module.WorkflowPage),
    game: () => import('./game.js').then(module => module.MediaPage),
    staff: () => import('./staff.js').then(module => module.StaffPage),
    mis: () => import('./mis.js').then(module => module.MisPage),
    'employee-login': () => import('./employee-login.js').then(module => module.EmployeeLoginPage),
};

export const Application = {
    async init() {
        Theme.init();
        StaffTabs.init();
        const loadPage = pages[document.body.dataset.page];
        if (!loadPage) throw new Error('此頁面尚未設定啟動模組。');
        const controller = await loadPage();
        await controller.init();
        // 1. 確保在頁面模組 (controller.init) 完成事件綁定後，再自動切換分頁
        this.activateTabFromUrl();
    },
    // 2. 新增統一處理網址分頁切換的方法
    activateTabFromUrl() {
        const urlParams = new URLSearchParams(window.location.search);
        if (!urlParams.toString()) return;
        // 定義要支援的網址參數與對應的 HTML data 屬性
        const panel = urlParams.get('panel') || urlParams.get('data-panel');

        if (panel) {
            const targetBtn = document.querySelector(`[data-panel="${panel}"]`);
            targetBtn?.click();
        }
        // 切換完畢後，將網址列的 ?panel=... 抹除，還原成乾淨的網址（不會重新整理頁面）
        // 洗掉網址參數維持美觀
        if (urlParams.toString()) {
            window.history.replaceState({}, '', window.location.pathname);
        }
    }
};

Application.init().catch(error => {
    console.error('頁面啟動失敗', error);
    const status = document.querySelector('#apiState, #playerState, #loginStatus');
    if (status) {
        status.textContent = '頁面載入失敗，請重新整理。';
        status.classList.add('error-note');
    }
});