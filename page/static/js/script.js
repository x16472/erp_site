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
    },
};

Application.init().catch(error => {
    console.error('頁面啟動失敗', error);
    const status = document.querySelector('#apiState, #playerState, #loginStatus');
    if (status) {
        status.textContent = '頁面載入失敗，請重新整理。';
        status.classList.add('error-note');
    }
});
