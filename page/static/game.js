import { apiData, escapeHtml, formatNumber, requireEmployee } from './script.js';

// 影音播放功能
const DEFAULT_YT_URL = 'https://www.youtube.com/watch?v=BsvIwqyiaJw';

const videoEmployeeAccess = requireEmployee();
const youtubeForm = document.querySelector('#youtubeForm');
const youtubeUrl = document.querySelector('#youtubeUrl');
const youtubePlayer = document.querySelector('#youtubePlayer');
const youtubeStatus = document.querySelector('#youtubeStatus');
const playerState = document.querySelector('#playerState');
const videoTitle = document.querySelector('#videoTitle');
const openYoutube = document.querySelector('#openYoutube');
const submitButton = youtubeForm.querySelector('button[type="submit"]');
const playerStates = {};

function updatePlayerState(platform, message) {
    playerStates[platform] = message;
    const active = document.querySelector('#staffTabs .active')?.dataset.panel;
    if (active === platform || platform === 'youtube' && active === 'yt1') {
        playerState.textContent = message;
    }
}

document.querySelector('#staffTabs').addEventListener('click', event => {
    const tab = event.target.closest('[data-panel]');
    if (tab) playerState.textContent = playerStates[tab.dataset.panel] || '播放器就緒';
});

async function resolveVideo(url, remember = true) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    submitButton.disabled = true;
    updatePlayerState('youtube', '後端驗證中');
    youtubeStatus.className = 'hint';
    youtubeStatus.textContent = '正在確認影片並取得標題…';
    try {
        const session = await videoEmployeeAccess;
        const video = await apiData('/api/youtube/resolve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf },
            body: JSON.stringify({ url }),
            signal: controller.signal,
        }, '影片資訊取得失敗');
        youtubePlayer.src = video.embed_url;
        videoTitle.textContent = video.title;
        openYoutube.href = video.watch_url;
        youtubeUrl.value = video.watch_url;
        const remembered = !remember || rememberVideo('YoutubeVideo', video.watch_url);
        youtubeStatus.className = 'hint success-note';
        youtubeStatus.textContent = '後端已驗證網址並取得 YouTube 影片標題。';
        if (!remembered) youtubeStatus.textContent += ' 瀏覽器無法儲存播放紀錄。';
        updatePlayerState('youtube', '播放器已更新');
    } catch (error) {
        const message = error.name === 'AbortError' ? '影片資訊讀取逾時，請稍後重試。' : error.message;
        youtubeStatus.className = 'error-note';
        youtubeStatus.textContent = message;
        updatePlayerState('youtube', '影片載入失敗');
    } finally {
        clearTimeout(timer);
        submitButton.disabled = false;
    }
}

function initializeVideoPlayers() {
    const savedUrl = readVideoHistory('YoutubeVideo');
    resolveVideo(savedUrl || DEFAULT_YT_URL, false);
}

youtubeForm.addEventListener('submit', event => {
    event.preventDefault();
    resolveVideo(youtubeUrl.value);
});

initializeVideoPlayers();

const videoPlatforms = {
    bilibili: { name: 'BiliBili', storageKey: 'BilibiliVideo' },
    niconico: { name: 'ニコニコ', storageKey: 'NiconicoVideo' },
    douyin: { name: 'Douyin', storageKey: 'DouyinVideo' },
    tiktok: { name: 'TikTok', storageKey: 'TiktokVideo' },
};


function readVideoHistory(key) {
    try {
        return localStorage.getItem(key);
    } catch {
        return null;
    }
}

function rememberVideo(key, url) {
    try {
        localStorage.setItem(key, url);
        return true;
    } catch {
        return false;
    }
}

function initializePlatformPlayers() {
    document.querySelectorAll('[data-video-platform]').forEach(card => {
        const platform = card.dataset.videoPlatform;
        const config = videoPlatforms[platform];
        const form = card.querySelector('form');
        const input = form.querySelector('input');
        const button = form.querySelector('button[type="submit"]');
        const status = card.querySelector('[aria-live]');
        const player = card.querySelector('iframe');
        const meta = card.querySelector('.youtube-meta');
        const title = meta.querySelector('h2');
        const original = meta.querySelector('a');
        let initialized = false;

        async function loadVideo(value, remember = true) {
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), 12000);
            button.disabled = true;
            status.className = 'hint';
            status.textContent = '正在確認影片並取得標題…';
            updatePlayerState(platform, '後端驗證中');
            try {
                const session = await videoEmployeeAccess;
                const video = await apiData('/api/media/resolve', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf },
                    body: JSON.stringify({ platform, url: value }),
                    signal: controller.signal,
                }, '影片標題取得失敗');
                if (typeof video.title !== 'string' || !video.title.trim()) {
                    throw new Error('影音來源未回傳影片標題。');
                }
                player.removeAttribute('src');
                player.parentElement.hidden = !video.embed_url;
                if (video.embed_url) player.src = video.embed_url;
                title.textContent = video.title;
                player.title = video.title;
                original.href = video.watch_url;
                input.value = video.watch_url;
                meta.parentElement.hidden = false;
                updatePlayerState(platform, video.embed_url ? '播放器已更新' : '請由原站觀看');
                status.className = 'hint success-note';
                status.textContent = video.embed_url
                    ? (video.title_status === 'empty' ? '來源未填寫影片標題，已更新播放器。' : '已取得影片標題並更新播放器。')
                    : '此連結尚未取得影片標題；短網址與直播請由原站觀看，或貼上完整影片網址。';
                if (video.embed_url) status.textContent += ' 若影片無法播放，請由原站觀看。';
                if (remember && !rememberVideo(config.storageKey, video.watch_url)) {
                    status.textContent += ' 瀏覽器無法儲存播放紀錄。';
                }
            } catch (error) {
                status.className = 'error-note';
                status.textContent = error.name === 'AbortError' ? '影片標題讀取逾時，請稍後重試。' : error.message;
                updatePlayerState(platform, '影片資訊取得失敗');
            } finally {
                clearTimeout(timer);
                button.disabled = false;
            }
        }

        form.addEventListener('submit', event => {
            event.preventDefault();
            initialized = true;
            loadVideo(input.value);
        });
        // 隱藏分頁先還原輸入值，開啟分頁時才載入第三方播放器。
        const savedUrl = readVideoHistory(config.storageKey);
        if (savedUrl) input.value = savedUrl;
        document.querySelector('#staffTabs').addEventListener('click', event => {
            const tab = event.target.closest('[data-panel]');
            if (tab?.dataset.panel !== platform || initialized) return;
            initialized = true;
            if (savedUrl) loadVideo(savedUrl, false);
        });
    });
}

initializePlatformPlayers();


// 知識與營運 SOP 查詢功能
function initializeKnowledgeFeature() {
    if (!document.querySelector('#knowledge')) return;

    const knowledgeEmployeeAccess = videoEmployeeAccess;
    const search = document.querySelector('#search');
    const knowledge = document.querySelector('#knowledge');
    const knowledgeTabs = document.querySelector('#knowledgeTabs');
    const manualCategoryField = document.querySelector('#manualCategoryField');
    const manualCategory = document.querySelector('#manualCategory');
    const metrics = document.querySelector('#metrics');
    const manualReader = document.querySelector('#manualReader');
    const closeManual = document.querySelector('#closeManual');
    const manualReaderCategory = document.querySelector('#manualReaderCategory');
    const manualReaderTitle = document.querySelector('#manualReaderTitle');
    const manualReaderFile = document.querySelector('#manualReaderFile');
    const manualReaderSections = document.querySelector('#manualReaderSections');
    const modal = document.querySelector('#modal');
    const modalCategory = document.querySelector('#modalCategory');
    const modalTitle = document.querySelector('#modalTitle');
    const modalSummary = document.querySelector('#modalSummary');
    const modalDetail = document.querySelector('#modalDetail');
    const modalRelated = document.querySelector('#modalRelated');

    let entries = [];
    let manuals = [];
    let knowledgeMode = 'entries';

    function renderKnowledge() {
        const query = search.value.trim().toLowerCase();
        const category = manualCategory.value;
        if (knowledgeMode === 'manuals') {
            const items = manuals.filter(item => (
                (!category || item.category === category)
                && (!query || `${item.title} ${item.category} ${item.file_name}`.toLowerCase().includes(query))
            ));
            knowledge.innerHTML = items.length ? items.map(item => `
                <button class="knowledge-card" data-manual-id="${item.id}">
                    <span class="tag">${escapeHtml(item.category)}</span>
                    <h3>${escapeHtml(item.title)}</h3>
                    <p>${item.section_count} 個段落 · ${escapeHtml(item.file_name)}</p>
                </button>`).join('') : '<div class="empty">找不到符合條件的SOP文件。</div>';
            return;
        }

        const items = query
            ? entries.filter(item => Object.values(item).join(' ').toLowerCase().includes(query))
            : entries;
        knowledge.innerHTML = items.length ? items.map(item => `
            <button class="knowledge-card" data-id="${item.id}">
                <span class="tag">${escapeHtml(item.category)}</span>
                <h3>${escapeHtml(item.title)}</h3>
                <p>${escapeHtml(item.Date || item.summary || '')}</p>
            </button>`).join('') : '<div class="empty">找不到相關條目。</div>';
    }

    async function openManual(id) {
        manualReader.hidden = false;
        knowledge.hidden = true;
        manualReaderSections.innerHTML = '<div class="empty">正在讀取文件內容…</div>';
        try {
            const item = await apiData(`/api/manuals/document?id=${encodeURIComponent(id)}`);
            manualReaderCategory.textContent = item.category;
            manualReaderTitle.textContent = item.title;
            manualReaderFile.textContent = item.file_name;
            manualReaderSections.innerHTML = item.sections.map((section, index) => `
                <details class="training-section" ${index === 0 ? 'open' : ''}>
                    <summary><span>${String(index + 1).padStart(2, '0')}</span>${escapeHtml(section.heading)}</summary>
                    <div>${escapeHtml(section.content).replace(/\n/g, '<br>')}</div>
                </details>`).join('') || '<div class="empty">此文件沒有可顯示的段落。</div>';
        } catch (error) {
            manualReaderSections.innerHTML = `<div class="error-note">${escapeHtml(error.message)}</div>`;
        }
    }

    async function initializeKnowledgeSearch() {
        try {
            await knowledgeEmployeeAccess;
            const [dashboard, knowledgeItems, manualItems] = await Promise.all([
                apiData('/api/dashboard'),
                apiData('/api/knowledge'),
                apiData('/api/manuals'),
            ]);
            entries = knowledgeItems;
            manuals = manualItems;

            manualCategory.replaceChildren(new Option('全部分類', ''));
            [...new Set(manuals.map(item => item.category))].forEach(category => {
                manualCategory.add(new Option(category, category));
            });
            metrics.innerHTML = dashboard.metrics.map((item, index) => `
                <article class="metric-card">
                    <span>0${index + 1}</span>
                    <p>${escapeHtml(item.label)}</p>
                    <strong>${formatNumber(item.value)}</strong>
                    ${escapeHtml(item.unit)}
                </article>`).join('');
            knowledge.classList.remove('empty');
            renderKnowledge();
        } catch (error) {
            knowledge.innerHTML = `<div class="error-note">${escapeHtml(error.message)}</div>`;
        }
    }

    search.addEventListener('input', renderKnowledge);
    manualCategory.addEventListener('change', renderKnowledge);
    knowledgeTabs.addEventListener('click', event => {
        const button = event.target.closest('[data-knowledge-mode]');
        if (!button) return;
        knowledgeMode = button.dataset.knowledgeMode;
        knowledgeTabs.querySelectorAll('button').forEach(item => {
            item.classList.toggle('active', item === button);
        });
        manualCategoryField.hidden = knowledgeMode !== 'manuals';
        search.placeholder = knowledgeMode === 'manuals' ? '搜尋文件名稱或分類…' : '請輸入欲查詢內容…';
        manualReader.hidden = true;
        knowledge.hidden = false;
        renderKnowledge();
    });

    closeManual.addEventListener('click', () => {
        manualReader.hidden = true;
        knowledge.hidden = false;
    });

    knowledge.addEventListener('click', event => {
        const manualButton = event.target.closest('[data-manual-id]');
        if (manualButton) {
            openManual(manualButton.dataset.manualId);
            return;
        }

        const button = event.target.closest('[data-id]');
        if (!button) return;
        const item = entries.find(entry => String(entry.id) === button.dataset.id);
        if (!item) return;
        modalCategory.textContent = item.category;
        modalTitle.textContent = item.title;
        modalSummary.textContent = item.summary;
        modalDetail.textContent = item.detail;
        modalRelated.textContent = item.related;
        modal.classList.add('open');
    });

    document.addEventListener('click', event => {
        if (event.target === modal || event.target.closest('.close')) {
            modal.classList.remove('open');
        }
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') modal.classList.remove('open');
    });

    initializeKnowledgeSearch();
}

initializeKnowledgeFeature();
