import { apiData, escapeHtml } from './api.js';

export class ManualReader {
    constructor(root, request = apiData) {
        this.root = root;
        this.request = request;
        this.documents = [];
        this.loaded = false;
        this.requestVersion = 0;
        this.list = root.querySelector('[data-manual-list]');
        this.reader = root.querySelector('[data-manual-reader]');
        this.search = root.querySelector('[data-manual-search]');
        this.category = root.querySelector('[data-manual-category]');
        this.status = root.querySelector('[data-manual-status]');
        this.sections = root.querySelector('[data-manual-sections]');
        this.toc = root.querySelector('[data-manual-toc]');
    }

    init() {
        this.search.addEventListener('input', () => this.renderList());
        this.category.addEventListener('change', () => this.renderList());
        this.root.querySelector('[data-manual-refresh]').addEventListener('click', () => this.load(true));
        this.root.querySelector('[data-manual-back]').addEventListener('click', () => this.showList());
        this.list.addEventListener('click', event => {
            const button = event.target.closest('[data-manual-id]');
            if (button) this.open(button.dataset.manualId);
        });
        this.toc.addEventListener('click', event => {
            const button = event.target.closest('[data-manual-section]');
            if (!button) return;
            const section = this.sections.children[Number(button.dataset.manualSection)];
            if (!section) return;
            section.open = true;
            section.scrollIntoView({ block: 'start', behavior: 'smooth' });
            section.querySelector('summary').focus();
        });
    }

    async load(force = false) {
        if (this.loaded && !force) return;
        const version = ++this.requestVersion;
        this.showList(false);
        this.status.textContent = '正在讀取 SOP 文件…';
        try {
            const documents = await this.request('/api/manuals');
            if (version !== this.requestVersion) return;
            this.documents = documents;
            this.loaded = true;
            const selectedCategory = this.category.value;
            this.category.replaceChildren(new Option('全部分類', ''));
            [...new Set(documents.map(item => item.category).filter(Boolean))].forEach(category => {
                this.category.add(new Option(category, category));
            });
            if ([...this.category.options].some(option => option.value === selectedCategory)) {
                this.category.value = selectedCategory;
            }
            this.status.textContent = `已載入 ${documents.length} 份 SOP 文件。`;
            this.renderList();
        } catch (error) {
            if (version !== this.requestVersion) return;
            this.status.textContent = `讀取失敗：${error.message}；可按「重新讀取」重試。`;
            if (!this.loaded) this.list.innerHTML = '<div class="empty">目前無法取得文件目錄。</div>';
        }
    }

    renderList() {
        const keyword = this.search.value.trim().toLocaleLowerCase('zh-TW');
        const documents = this.documents.filter(item =>
            (!this.category.value || item.category === this.category.value)
            && (!keyword || `${item.title} ${item.category} ${item.file_name}`.toLocaleLowerCase('zh-TW').includes(keyword)));
        this.list.innerHTML = documents.map(item => `
            <button class="knowledge-card" type="button" data-manual-id="${escapeHtml(item.id)}">
                <span class="tag">${escapeHtml(item.category || '未分類')}</span>
                <h3>${escapeHtml(item.title)}</h3>
                <p>${Number(item.section_count) || 0} 個章節 · ${escapeHtml(item.file_name)}</p>
            </button>`).join('') || '<div class="empty">目前沒有符合條件的 SOP 文件。</div>';
    }

    showList(cancelRequest = true) {
        if (cancelRequest) this.requestVersion += 1;
        this.reader.hidden = true;
        this.list.hidden = false;
    }

    async open(id) {
        const version = ++this.requestVersion;
        this.reader.hidden = false;
        this.list.hidden = true;
        this.root.querySelector('[data-manual-title]').textContent = '正在讀取文件…';
        this.root.querySelector('[data-manual-meta]').textContent = '';
        this.toc.replaceChildren();
        this.sections.textContent = '';
        try {
            const document = await this.request(`/api/manuals/document?id=${encodeURIComponent(id)}`);
            if (version !== this.requestVersion) return;
            this.root.querySelector('[data-manual-title]').textContent = document.title;
            this.root.querySelector('[data-manual-meta]').textContent = `${document.category || '未分類'} · ${document.file_name}`;
            const sections = document.sections || [];
            this.toc.innerHTML = sections.map((section, index) =>
                `<button class="btn second" type="button" data-manual-section="${index}">${escapeHtml(section.heading || `章節 ${index + 1}`)}</button>`).join('');
            this.sections.innerHTML = sections.map((section, index) => `
                <details class="training-section" ${index === 0 ? 'open' : ''}>
                    <summary>${escapeHtml(section.heading || `章節 ${index + 1}`)}</summary>
                    <div class="manual-section-content">${escapeHtml(section.content)}</div>
                </details>`).join('') || '<div class="empty">此文件尚無可閱讀章節，請由管理員確認同步結果。</div>';
        } catch (error) {
            if (version !== this.requestVersion) return;
            this.root.querySelector('[data-manual-title]').textContent = '文件讀取失敗';
            this.sections.textContent = `${error.message}；請返回目錄後重試。`;
        }
    }
}
