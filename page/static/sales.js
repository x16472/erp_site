import { apiData, escapeHtml, formatNumber, requireEmployee } from './script.js';

const
    operationForm = document.querySelector('#operationForm'),
    campus = document.querySelector('#campus'),
    process = document.querySelector('#process'),
    apiState = document.querySelector('#apiState'),
    formStatus = document.querySelector('#formStatus'),
    lastSubmission = document.querySelector('#lastSubmission'),
    mySubmissions = document.querySelector('#mySubmissions'),
    toast = document.querySelector('#toast');
const esc = escapeHtml;
const number = formatNumber;
let employeeCsrf = '';
const request = (path, options = {}) => apiData(path, options);
const employeeAccess = requireEmployee().then(session => {
    employeeCsrf = session.csrf;
    return session;
});
const activityNames = {
    SUBMITTED: '已送出', CHANGES_REQUESTED: '管理員要求補件', APPROVED: '管理員審核通過',
    REJECTED: '管理員退回', EMPLOYEE_REPLY: '員工補充回覆'
};
function renderMySubmissions(items) {
    mySubmissions.innerHTML = items.length ? items.map(item => `<article class="submission-card operation-thread">
        <header><b>${esc(item.category)} · ${esc(item.campus)}</b><span class="tag">${esc(item.status)}</span></header>
        <p>${esc(item.date)} · ${number(item.count)} 筆 · ${esc(item.note || '無備註')}</p>
        <div class="activity-list">${item.activities.map(activity => `<div class="activity-item">
            <b>${esc(activityNames[activity.action_type] || activity.action_type)}</b>
            ${activity.message ? `<p>${esc(activity.message)}</p>` : ''}
            <small>${esc(activity.actor_name || activity.actor_employee_id || '系統')} · ${esc(activity.created_at)}</small>
        </div>`).join('')}</div>
        ${['待審核', '要求補件', '員工已回覆'].includes(item.status) ? `<form class="operation-reply" data-reply-id="${esc(item.id)}">
            <label class="field"><span>補充回覆</span><textarea name="message" maxlength="1000" required placeholder="回覆管理員或補充日報內容"></textarea></label>
            <button class="btn secondary" type="submit">送出回覆</button>
        </form>` : ''}
    </article>`).join('') : '<div class="empty">目前尚無填報紀錄。</div>'
}
async function refreshMySubmissions() {
    renderMySubmissions(await request('/api/operations/mine'))
}
employeeAccess.then(() => Promise.all([request('/api/branches'),
request('/api/operations'), request('/api/time'), request('/api/operations/mine')])).then(([branches, processItems, time, submissions]) => {
    operationForm.date.value = time.current_time.slice(0, 10);
    campus.innerHTML = '<option value="">請選擇區域</option>' + branches.map(item =>
        `<option value="${esc(item.code)}">${esc(item.name)}</option>`).join('');
    process.innerHTML = processItems.map(item =>
        `<div class="process-node"><span>${item.id}</span>
            <div>
                <b>${esc(item.stage)}</b>
                <small>${esc(item.description)}</small>
            </div><em>${number(item.count)} 筆</em>
        </div>`).join('');
    renderMySubmissions(submissions);
    apiState.textContent = '服務已連線';
    apiState.classList.add('ok')
}).catch(() => { apiState.textContent = '資料服務未連線' });
operationForm.onsubmit = async event => {
    event.preventDefault();
    formStatus.className = '';
    formStatus.textContent = '送出中…';
    const payload = Object.fromEntries(new FormData(operationForm));
    const privatePattern = /(身分證|居留證|姓名|電話|手機|地址|電子郵件|e-?mail|\b[A-Z][12]\d{8}\b|\b09\d{8}\b|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,})/i;
    if (privatePattern.test(payload.note || '')) {
        formStatus.className = 'error-note';
        formStatus.textContent = '備註不得包含可辨識個人的姓名、證件、電話、地址或電子郵件。';
        operationForm.elements.note.focus();
        return
    }
    payload.count = Number(payload.count);
    try {
        await employeeAccess;
        const body = await request('/api/operations/submit', {
            method: 'POST', headers: {
                'Content-Type': 'application/json', 'X-CSRF-Token': employeeCsrf
            }, body: JSON.stringify(payload)
        });
        formStatus.className = 'success-note';
        formStatus.textContent = `${body.id} 已送交 MIS 待審。`;
        lastSubmission.innerHTML = `<div class="submission-card"><header>
            <b>${esc(body.category)}</b><span class="tag">待審核</span></header>
            <p>${esc(body.campus)} · ${esc(body.date)} · ${number(body.count)} 筆</p></div>`;
        operationForm.reset();
        operationForm.date.value = payload.date;
        toast.textContent = '營運日報已寫入待審資料表';
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 2200);
        await refreshMySubmissions()
    } catch (error) {
        formStatus.className = 'error-note';
        formStatus.textContent = error.message
    }
};
mySubmissions.onsubmit = async event => {
    const form = event.target.closest('[data-reply-id]');
    if (!form) return;
    event.preventDefault();
    const button = form.querySelector('button');
    button.disabled = true;
    try {
        await request('/api/operations/reply', {
            method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': employeeCsrf},
            body: JSON.stringify({id: form.dataset.replyId, message: form.elements.message.value})
        });
        await refreshMySubmissions();
        toast.textContent = '回覆已送交 MIS';
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 2200)
    } catch (error) {
        alert(error.message)
    } finally {
        button.disabled = false
    }
};
