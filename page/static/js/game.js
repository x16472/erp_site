import { YoutubeThumbnailApp } from './youtube_thumbnail.js';
import { apiData, requireEmployee } from './api.js';

const platforms = {
    youtube: { name: 'YouTube', storageKey: 'YoutubeVideo', endpoint: '/api/youtube/resolve' },
    bilibili: { name: 'BiliBili', storageKey: 'BilibiliVideo', endpoint: '/api/media/resolve' },
    niconico: { name: 'ニコニコ', storageKey: 'NiconicoVideo', endpoint: '/api/media/resolve' },
    douyin: { name: 'Douyin', storageKey: 'DouyinVideo', endpoint: '/api/media/resolve' },
    tiktok: { name: 'TikTok', storageKey: 'TiktokVideo', endpoint: '/api/media/resolve' },
};

export const MediaPage = {
    initialized: false,
    async init() {
        if (this.initialized) return;
        this.initialized = true;
        YoutubeThumbnailApp.UI.initEvents();
        const tabs = document.querySelector('#staffTabs');
        const state = document.querySelector('#playerState');
        state.textContent = '正在確認員工身分…';
        const session = await requireEmployee();
        const players = new Map();
        const activePlatform = () => tabs.querySelector('.active')?.dataset.panel;

        for (const card of document.querySelectorAll('[data-video-platform]')) {
            const platform = card.dataset.videoPlatform;
            const config = platforms[platform];
            if (!config) continue;
            const form = card.querySelector('form');
            const input = form.querySelector('input');
            const button = form.querySelector('button[type="submit"]');
            const status = card.querySelector('[aria-live]');
            const frame = card.querySelector('iframe');
            const metadata = card.querySelector('.youtube-meta');
            const title = metadata.querySelector('h2');
            const original = metadata.querySelector('a');
            const metadataContainer = metadata.parentElement === card ? metadata : metadata.parentElement;
            let initialized = false;
            let video = null;
            let request = null;
            let disposed = false;
            let playerStatus = '播放器就緒';

            try {
                input.value = localStorage.getItem(config.storageKey) || input.value;
            } catch {
                // 瀏覽器禁止儲存時仍可使用輸入及播放功能。
            }

            function updateStatus(message) {
                playerStatus = message;
                if (activePlatform() === platform) state.textContent = message;
            }

            function synchronizeFrame() {
                const url = activePlatform() === platform ? video?.embed_url : '';
                if (url) {
                    if (frame.getAttribute('src') !== url) frame.src = url;
                } else {
                    // 卸載隱藏的播放器，避免切換分頁後繼續播放聲音。
                    frame.removeAttribute('src');
                }
                frame.parentElement.hidden = !video?.embed_url;
            }

            async function loadVideo(value, remember = true) {
                request?.abort();
                const controller = new AbortController();
                request = controller;
                let timedOut = false;
                const timer = setTimeout(() => {
                    timedOut = true;
                    controller.abort();
                }, 15000);
                video = null;
                synchronizeFrame();
                metadataContainer.hidden = true;
                original.removeAttribute('href');
                button.disabled = true;
                status.className = 'hint';
                status.textContent = '正在確認影片並取得標題…';
                updateStatus('影片資訊讀取中');
                try {
                    const payload = platform === 'youtube' ? { url: value } : { platform, url: value };
                    const resolved = await apiData(config.endpoint, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf },
                        body: JSON.stringify(payload),
                        signal: controller.signal,
                    }, '影片資訊取得失敗');
                    if (disposed || request !== controller) return;
                    if (!resolved?.watch_url || !resolved.title?.trim()) throw new Error('影音來源未回傳完整影片資訊。');
                    video = resolved;
                    title.textContent = resolved.title;
                    frame.title = `${config.name}：${resolved.title}`;
                    original.href = resolved.watch_url;
                    if (input.value.trim() === value) input.value = resolved.watch_url;
                    metadataContainer.hidden = false;
                    synchronizeFrame();
                    updateStatus(resolved.embed_url ? '播放器已更新' : '請由原站觀看');
                    status.className = 'hint success-note';
                    status.textContent = resolved.embed_url
                        ? '已更新播放器；若來源禁止嵌入，請由原站觀看。'
                        : '此連結無法嵌入播放，請由原站觀看或貼上完整影片網址。';
                    if (resolved.title_status === 'empty') status.textContent += ' 來源未填寫影片標題。';
                    if (remember) {
                        try {
                            localStorage.setItem(config.storageKey, resolved.watch_url);
                        } catch {
                            status.textContent += ' 瀏覽器無法儲存播放紀錄。';
                        }
                    }
                } catch (error) {
                    if (disposed || request !== controller) return;
                    status.className = 'error-note';
                    status.textContent = timedOut ? '影片資訊讀取逾時，請稍後重試。' : error.message;
                    updateStatus('影片資訊取得失敗');
                } finally {
                    clearTimeout(timer);
                    if (request === controller) {
                        request = null;
                        button.disabled = false;
                    }
                }
            }

            form.addEventListener('submit', event => {
                event.preventDefault();
                initialized = true;
                loadVideo(input.value.trim());
            });
            players.set(platform, {
                activate() {
                    synchronizeFrame();
                    if (activePlatform() !== platform) return;
                    state.textContent = playerStatus;
                    if (initialized) return;
                    initialized = true;
                    if (input.value.trim()) loadVideo(input.value.trim(), false);
                },
                dispose() {
                    disposed = true;
                    request?.abort();
                    frame.removeAttribute('src');
                },
            });
            synchronizeFrame();
            metadataContainer.hidden = true;
        }

        const synchronizePlayers = () => players.forEach(player => player.activate());
        tabs.addEventListener('panelchange', synchronizePlayers);
        synchronizePlayers();
        window.addEventListener('pagehide', () => {
            players.forEach(player => player.dispose());
        });
        window.addEventListener('pageshow', event => {
            if (event.persisted) location.reload();
        });
    },
};
