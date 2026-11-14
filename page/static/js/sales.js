import { apiData, escapeHtml, formatNumber, requireEmployee } from './api.js';

export const SalesPage = {
    initialized: false,
    init() {
        if (this.initialized) return;
        this.initialized = true;
        const operationForm = document.querySelector('#operationForm'),
            campus = document.querySelector('#campus'),
            process = document.querySelector('#process'),
            apiState = document.querySelector('#apiState'),
            formStatus = document.querySelector('#formStatus'),
            lastSubmission = document.querySelector('#lastSubmission'),
            mySubmissions = document.querySelector('#mySubmissions'),
            filters = document.querySelector('#historyFilters'),
            historyStatus = document.querySelector('#historyStatus'),
            refreshButton = document.querySelector('#refreshHistory'),
            submitButton = operationForm.querySelector('[type="submit"]'),
            toast = document.querySelector('#toast');
        const esc = escapeHtml, number = formatNumber;
        const request = (path, options = {}) => apiData(path, options);
        let employeeCsrf = '', records = [], branchNames = new Map(), ready = false, submitting = false;
        const employeeAccess = requireEmployee().then(session => {
            employeeCsrf = session.csrf;
            return session;
        });
        const activityNames = {
            SUBMITTED: '已送出', CHANGES_REQUESTED: '管理員要求補件', APPROVED: '管理員審核通過',
            REJECTED: '管理員退回', EMPLOYEE_REPLY: '員工補充回覆'
        };
        function notify(message) {
            toast.textContent = message;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 2200);
        }
        function renderMySubmissions() {
            const values = new FormData(filters), search = String(values.get('search') || '').trim().toLocaleLowerCase();
            const from = values.get('from'), to = values.get('to');
            if (from && to && from > to) {
                historyStatus.textContent = '起始日期不得晚於結束日期。';
                return;
            }
            const items = records.filter(item => {
                const text = [item.id, item.campus, branchNames.get(item.campus), item.category, item.note].join(' ').toLocaleLowerCase();
                return (!search || text.includes(search)) && (!values.get('status') || item.status === values.get('status'))
                    && (!from || item.date >= from) && (!to || item.date <= to);
            });
            historyStatus.textContent = `顯示 ${items.length}／${records.length} 筆紀錄`;
            mySubmissions.innerHTML = items.length ? items.map(item => `<article class="submission-card operation-thread">
        <header><b>${esc(item.category)} · ${esc(branchNames.get(item.campus) || item.campus)}</b><span class="tag">${esc(item.status)}</span></header>
        <small>單號 ${esc(item.id)} · 送出時間 ${esc(item.submitted_at || '未記錄')}</small>
        <p>${esc(item.date)} · ${number(item.count)} 筆 · ${esc(item.note || '無備註')}</p>
        <div class="activity-list">${(item.activities || []).map(activity => `<div class="activity-item">
                    <b>${esc(activityNames[activity.action_type] || activity.action_type)}</b>
                    ${activity.message ? `<p>${esc(activity.message)}</p>` : ''}
                    <small>${esc(activity.actor_name || activity.actor_employee_id || '系統')} · ${esc(activity.created_at)}</small>
                </div>`).join('')}</div>
        ${['待審核', '要求補件', '員工已回覆'].includes(item.status) ? `<form class="operation-reply" data-reply-id="${esc(item.id)}">
                    <label class="field"><span>補充回覆</span><textarea name="message" maxlength="1000" required placeholder="回覆管理員或補充日報內容"></textarea></label>
                    <button class="btn second" type="submit">送出回覆</button>
                    <p class="reply-status" aria-live="polite"></p>
                </form>` : ''}
    </article>`).join('') : `<div class="empty">${records.length ? '沒有符合條件的紀錄。' : '目前尚無填報紀錄。'}</div>`;
        }
        async function refreshMySubmissions() {
            refreshButton.disabled = true;
            historyStatus.textContent = '正在更新紀錄…';
            try {
                await employeeAccess;
                records = await request('/api/operations/mine', { cache: 'no-store' });
                renderMySubmissions();
            } catch (error) {
                historyStatus.textContent = `紀錄更新失敗：${error.message}；請按重新整理紀錄重試。`;
            } finally { refreshButton.disabled = false; }
        }
        async function refreshSummary() {
            try {
                const items = await request('/api/operations', { cache: 'no-store' });
                process.innerHTML = items.length ? items.map(item => `<div class="process-node"><span>${esc(item.id)}</span><div><b>${esc(item.stage)}</b><small>${esc(item.description)}</small></div><em>${number(item.count)} 筆</em></div>`).join('') : '<div class="empty">目前沒有填報分類摘要。</div>';
            } catch (error) { process.innerHTML = `<div class="error-note">摘要載入失敗：${esc(error.message)}</div>`; }
        }
        async function initializeForm() {
            await employeeAccess;
            const [branches, categories, time] = await Promise.all([
                request('/api/branches'), request('/api/operations/categories'), request('/api/time')
            ]);
            branchNames = new Map(branches.map(item => [item.code, item.name]));
            campus.innerHTML = '<option value="">請選擇區域</option>' + branches.map(item => `<option value="${esc(item.code)}">${esc(item.name)}</option>`).join('');
            operationForm.elements.category.innerHTML = '<option value="">請選擇類別</option>' + categories.map(item => `<option value="${esc(item.code)}">${esc(item.code)}</option>`).join('');
            if (!branches.length || !categories.length) throw new Error('尚未建立營運據點或日報類別，請聯絡管理員。');
            operationForm.elements.date.value = time.work_date || time.current_time.slice(0, 10);
            operationForm.elements.category.disabled = false;
            submitButton.disabled = false;
            ready = true;
            apiState.textContent = '服務已連線';
            apiState.classList.add('ok');
            if (records.length) renderMySubmissions();
        }
        initializeForm().catch(error => {
            apiState.textContent = '填報資料載入失敗';
            formStatus.className = 'error-note';
            formStatus.textContent = error.message;
        });
        refreshMySubmissions();
        employeeAccess.then(refreshSummary).catch(() => {});
        filters.addEventListener('input', renderMySubmissions);
        filters.addEventListener('submit', event => event.preventDefault());
        filters.addEventListener('reset', () => setTimeout(renderMySubmissions, 0));
        refreshButton.onclick = refreshMySubmissions;
        operationForm.addEventListener('reset', () => {
            const day = operationForm.elements.date.value;
            setTimeout(() => { operationForm.elements.date.value = day; }, 0);
        });
        operationForm.onsubmit = async event => {
            event.preventDefault();
            if (!ready || submitting) return;
            formStatus.className = '';
            const payload = Object.fromEntries(new FormData(operationForm));
            const privatePattern = /(身分證|居留證|姓名|電話|手機|地址|電子郵件|e-?mail|\b[A-Z][12]\d{8}\b|\b09\d{8}\b|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,})/i;
            if (privatePattern.test(payload.note || '')) {
                formStatus.className = 'error-note';
                formStatus.textContent = '備註不得包含可辨識個人的姓名、證件、電話、地址或電子郵件。';
                operationForm.elements.note.focus();
                return;
            }
            submitting = true;
            submitButton.disabled = true;
            formStatus.textContent = '送出中…';
            payload.count = Number(payload.count);
            try {
                const body = await request('/api/operations/submit', {
                    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': employeeCsrf }, body: JSON.stringify(payload)
                });
                formStatus.className = 'success-note';
                formStatus.textContent = `${body.id} 已送交 MIS 待審。`;
                lastSubmission.innerHTML = `<div class="submission-card"><header><b>${esc(body.category)}</b><span class="tag">${esc(body.status)}</span></header><p>${esc(branchNames.get(body.campus) || body.campus)} · ${esc(body.date)} · ${number(body.count)} 筆</p></div>`;
                operationForm.reset();
                operationForm.elements.date.value = payload.date;
                notify('營運日報已寫入待審資料表');
                await Promise.all([refreshMySubmissions(), refreshSummary()]);
            } catch (error) {
                formStatus.className = 'error-note';
                formStatus.textContent = error.message;
            } finally { submitting = false; submitButton.disabled = false; }
        };
        mySubmissions.onsubmit = async event => {
            const form = event.target.closest('[data-reply-id]');
            if (!form) return;
            event.preventDefault();
            const button = form.querySelector('button'), status = form.querySelector('.reply-status');
            if (button.disabled) return;
            button.disabled = true;
            try {
                await request('/api/operations/reply', {
                    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': employeeCsrf },
                    body: JSON.stringify({ id: form.dataset.replyId, message: form.elements.message.value })
                });
                status.textContent = '回覆已送交 MIS。';
                notify('回覆已送交 MIS');
                await refreshMySubmissions();
            } catch (error) { status.textContent = error.message; status.className = 'reply-status error-note'; }
            finally { button.disabled = false; }
        };
    },
};
