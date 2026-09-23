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
const bilibiliPlayer = document.querySelector('#bilibiliPlayer');

async function resolveVideo(url, remember = true) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    submitButton.disabled = true;
    playerState.textContent = '後端驗證中';
    youtubeStatus.className = 'hint';
    youtubeStatus.textContent = '正在確認影片並取得標題…';
    try {
        await videoEmployeeAccess;
        const video = await apiData('/api/youtube/resolve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url }),
            signal: controller.signal,
        }, '影片資訊取得失敗');
        youtubePlayer.src = video.embed_url;
        videoTitle.textContent = video.title;
        openYoutube.href = video.watch_url;
        youtubeUrl.value = video.watch_url;
        if (remember) localStorage.setItem('YoutubeVideo', video.watch_url);
        youtubeStatus.className = 'hint success-note';
        youtubeStatus.textContent = '後端已驗證網址並取得 YouTube 影片標題。';
        playerState.textContent = '播放器已更新';
    } catch (error) {
        const message = error.name === 'AbortError' ? '影片資訊讀取逾時，請稍後重試。' : error.message;
        youtubeStatus.className = 'error-note';
        youtubeStatus.textContent = message;
        playerState.textContent = '影片載入失敗';
    } finally {
        clearTimeout(timer);
        submitButton.disabled = false;
    }
}

function initializeVideoPlayers() {
    const savedUrl = localStorage.getItem('YoutubeVideo');
    resolveVideo(savedUrl || DEFAULT_YT_URL, false);
}

youtubeForm.addEventListener('submit', event => {
    event.preventDefault();
    resolveVideo(youtubeUrl.value);
});

initializeVideoPlayers();


// 知識與營運 SOP 查詢功能

const knowledgeEmployeeAccess = requireEmployee();
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
