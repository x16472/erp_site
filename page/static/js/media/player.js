import { apiData } from '../api.js';

export function createMediaPlayer(platform, config, { session, isActive, onStatus }) {
    const card = document.querySelector(`[data-video-platform="${platform}"]`);
    if (!card) throw new Error(`找不到 ${config.name} 播放器。`);
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
        if (isActive()) onStatus(message);
    }

    function synchronizeFrame() {
        const url = isActive() ? video?.embed_url : '';
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
    synchronizeFrame();
    metadataContainer.hidden = true;
    return {
        activate() {
            synchronizeFrame();
            if (!isActive()) return;
            onStatus(playerStatus);
            if (initialized) return;
            initialized = true;
            if (input.value.trim()) loadVideo(input.value.trim(), false);
        },
        deactivate() {
            frame.removeAttribute('src');
        },
        dispose() {
            disposed = true;
            request?.abort();
            frame.removeAttribute('src');
        },
    };
}
