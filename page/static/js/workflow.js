export const WorkflowPage = {
    initialized: false,
    init() {
        if (this.initialized) return;
        this.initialized = true;
        const tabs = document.querySelector('#staffTabs');
        const status = document.querySelector('#playerState');
        const tools = {
            pl1: { name: 'SD 參數讀取', load: () => import('./sd_prompt.js').then(module => module.PromptTool) },
            pl2: { name: 'Go Playground', load: () => import('./canvas/golang.js').then(module => module.GoPlayground) },
            pl3: { name: 'Python Playground', load: () => import('./canvas/python.js').then(module => module.PythonPlayground) },
            pl4: { name: '俄羅斯方塊', load: () => import('./canvas/teris.js').then(module => module.TetrisGame) },
            pl5: { name: '穿越冒險', load: () => import('./adventure.js').then(module => module.AdventurePlayer) },
        };
        const loading = new Map();
        const isActive = id => tabs.querySelector('.active')?.dataset.panel === id;

        async function openPanel(id) {
            const tool = tools[id];
            if (!tool) return;
            if (!loading.has(id)) {
                if (isActive(id)) status.textContent = `${tool.name}載入中…`;
                // 各分頁獨立載入，單一工具失敗不阻擋其他工作面板。
                loading.set(id, tool.load().then(controller => controller.init()));
            }
            try {
                await loading.get(id);
                if (isActive(id) && id !== 'pl5') status.textContent = tool.name;
            } catch (error) {
                console.error(`${tool.name}載入失敗`, error);
                if (isActive(id)) status.textContent = `${tool.name}載入失敗，請重新整理或切換其他分頁。`;
            }
        }

        tabs.addEventListener('panelchange', event => openPanel(event.detail.panelId));
        openPanel(tabs.querySelector('.active')?.dataset.panel);
    },
};
