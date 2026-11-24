import { requireEmployee } from './api.js';

export const MediaPage = {
    initialized: false,
    async init() {
        if (this.initialized) return;
        this.initialized = true;
        const tabs = document.querySelector('#staffTabs');
        const state = document.querySelector('#playerState');
        const platforms = {
            youtube: { name: 'YouTube', load: () => import('./media/youtube.js').then(module => module.YoutubePlayer) },
            bilibili: { name: 'BiliBili', load: () => import('./media/bilibili.js').then(module => module.BilibiliPlayer) },
            niconico: { name: 'ニコニコ', load: () => import('./media/niconico.js').then(module => module.NiconicoPlayer) },
            douyin: { name: 'Douyin', load: () => import('./media/douyin.js').then(module => module.DouyinPlayer) },
            tiktok: { name: 'TikTok', load: () => import('./media/tiktok.js').then(module => module.TiktokPlayer) },
            teris: { name: '俄羅斯方塊', load: () => import('./canvas/teris.js').then(module => module.TetrisGame) },
        };
        const loading = new Map();
        const players = new Map();
        const isActive = id => tabs.querySelector('.active')?.dataset.panel === id;
        let disposed = false;

        window.addEventListener('pagehide', () => {
            disposed = true;
            players.forEach(player => player.dispose());
        });
        window.addEventListener('pageshow', event => {
            if (event.persisted) location.reload();
        });

        state.textContent = '正在確認員工身分…';
        const session = await requireEmployee();
        if (disposed) return;

        async function openPanel(id) {
            if (disposed) return;
            const platform = platforms[id];
            if (!platform) return;
            players.forEach((player, platformId) => {
                if (platformId !== id) player.deactivate();
            });
            if (!loading.has(id)) {
                if (isActive(id)) state.textContent = `${platform.name}載入中…`;
                // 快速切換時共用同一份載入結果，避免重複綁定表單與縮圖事件。
                loading.set(id, platform.load().then(controller => {
                    if (disposed) return null;
                    const player = controller.init({
                        session,
                        isActive: () => isActive(id),
                        onStatus: message => {
                            if (isActive(id)) state.textContent = message;
                        },
                    });
                    players.set(id, player);
                    return player;
                }));
            }
            try {
                const player = await loading.get(id);
                if (!player || disposed) return;
                if (isActive(id)) player.activate();
                else player.deactivate();
            } catch (error) {
                console.error(`${platform.name}載入失敗`, error);
                if (!disposed && isActive(id)) state.textContent = `${platform.name}載入失敗，請重新整理或切換其他分頁。`;
            }
        }

        tabs.addEventListener('panelchange', event => openPanel(event.detail.panelId));
        openPanel(tabs.querySelector('.active')?.dataset.panel);
    },
};
