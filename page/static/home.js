import { apiData, employeeLoginUrl, escapeHtml, formatNumber, requireEmployee, serverTimeOffset } from './script.js';

const employeeAccess = requireEmployee();
let entries = [], manuals = [], knowledgeMode = 'entries',
    serverOffset = 0, employeeCsrf = '',
    currentAttendance = null;
const search = document.querySelector('#search'),
    knowledge = document.querySelector('#knowledge'),
    knowledgeTabs = document.querySelector('#knowledgeTabs'),
    manualCategoryField = document.querySelector('#manualCategoryField'),
    manualCategory = document.querySelector('#manualCategory'),
    manualReader = document.querySelector('#manualReader'),
    manualReaderCategory = document.querySelector('#manualReaderCategory'),
    manualReaderTitle = document.querySelector('#manualReaderTitle'),
    manualReaderFile = document.querySelector('#manualReaderFile'),
    manualReaderSections = document.querySelector('#manualReaderSections'),
    closeManual = document.querySelector('#closeManual'),
    announcement = document.querySelector('#announcement'),
    metrics = document.querySelector('#metrics'),
    apiState = document.querySelector('#apiState'),
    modal = document.querySelector('#modal'),
    modalCategory = document.querySelector('#modalCategory'),
    modalTitle = document.querySelector('#modalTitle'),
    modalSummary = document.querySelector('#modalSummary'),
    modalDetail = document.querySelector('#modalDetail'),
    modalRelated = document.querySelector('#modalRelated'),
    currentClock = document.querySelector('#currentClock'),
    clockResult = document.querySelector('#clockResult'),
    employeeWelcome = document.querySelector('#employeeWelcome'),
    employeeProfile = document.querySelector('#employeeProfile'),
    makeupClock = document.querySelector('#makeupClock'),
    clockOutButton = document.querySelector('#clockOutButton'),
    employeeLeave = document.querySelector('#employeeLeave');
const esc = escapeHtml;
const number = formatNumber;
function renderKnowledge() {
    const q = search.value.trim().toLowerCase(),
        category = manualCategory.value;
    if (knowledgeMode === 'manuals') {
        const items = manuals.filter(item => (!category || item.category === category) &&
            (!q || `${item.title} ${item.category} ${item.file_name}`.toLowerCase().includes(q)));
        knowledge.innerHTML = items.length ? items.map(item => `<button class="knowledge-card" data-manual-id="${item.id}">
            <span class="tag">${esc(item.category)}</span><h3>${esc(item.title)}</h3>
            <p>${item.section_count} 個段落 · ${esc(item.file_name)}</p></button>`).join('')
            : '<div class="empty">找不到符合條件的SOP文件。</div>';
        return
    }
    const items = q ? entries.filter(item => Object.values(item).join(' ').toLowerCase().includes(q)) : entries;
    knowledge.innerHTML = items.length ? items.map(item =>
        `<button class="knowledge-card" data-id="${item.id}">
        <span class="tag">${esc(item.category)}</span>
        <h3>${esc(item.title)}</h3>
        <p>${esc(item.summary)}</p></button>`
    ).join('') : '<div class="empty">找不到相關條目。</div>'
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
        manualReaderSections.innerHTML = item.sections.map((section, index) =>
            `<details class="training-section" ${index === 0 ? 'open' : ''}><summary><span>${String(index + 1).padStart(2, '0')}</span>${esc(section.heading)}</summary>
            <div>${esc(section.content).replace(/\n/g, '<br>')}</div></details>`).join('') || '<div class="empty">此文件沒有可顯示的段落。</div>'
    } catch (error) { manualReaderSections.innerHTML = `<div class="error-note">${esc(error.message)}</div>` }
}
function renderAttendance(attendance) {
    currentAttendance = attendance;
    if (attendance) {
        clockResult.className = 'clock-result success-note';
        clockResult.textContent = `打卡時間｜${new Date(attendance.clocked_at).toLocaleString('zh-TW')}`;
        makeupClock.hidden = true;
        clockOutButton.disabled = attendance.action !== 'CLOCK_IN';
        clockOutButton.textContent = attendance.action === 'CLOCK_OUT' ? '已完成下班打卡' : '打卡下班'
    } else {
        clockResult.className = 'clock-result attendance-warning';
        clockResult.textContent = '您尚未打卡';
        makeupClock.hidden = false;
        makeupClock.disabled = false;
        clockOutButton.disabled = true
    } employeeLeave.disabled = false
}
async function syncServerTime() {
    const result = await serverTimeOffset();
    serverOffset = result.offset;
    return result.time
}
async function refreshAttendance() {
    const session = await apiData('/api/employee/session');
    if (!session.authenticated)
        return location.replace(employeeLoginUrl);
    employeeCsrf = session.csrf;
    renderAttendance(session.attendance)
}
async function clock(action) {
    const buttons = [makeupClock, clockOutButton, employeeLeave];
    buttons.forEach(button => button.disabled = true);
    try {
        const attendance = await apiData('/api/attendance/clock', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': employeeCsrf
            },
            body: JSON.stringify({ action })
        }); renderAttendance(attendance);
        if (action === 'CLOCK_OUT') {
            clockResult.textContent = `打卡時間｜${new Date(attendance.clocked_at).toLocaleString('zh-TW')}，下班打卡完成`;
            setTimeout(leaveSystem, 900)
        }
    } catch (error) {
        clockResult.className = 'clock-result error-note';
        clockResult.textContent = error.message;
        makeupClock.disabled = Boolean(currentAttendance);
        clockOutButton.disabled = !currentAttendance || currentAttendance.action !== 'CLOCK_IN';
        employeeLeave.disabled = false
    }
}
async function leaveSystem() {
    employeeLeave.disabled = true;
    try {
        await apiData('/api/employee/logout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: '{}'
        })
    } finally { location.replace(employeeLoginUrl) }
}
employeeAccess.then(async session => {
    const employee = session.employee;
    employeeCsrf = session.csrf;
    employeeWelcome.textContent = `${employee.display_name}，歡迎進入工作台`;
    employeeProfile.textContent = `${employee.employee_id}｜${employee.department}｜${employee.position}`;
    renderAttendance(session.attendance);
    await syncServerTime();
    return Promise.all([
        apiData('/api/dashboard'),
        apiData('/api/knowledge'),
        apiData('/api/manuals'),
        apiData('/api/public')])
}).then(([dashboard, knowledgeItems, manualItems, publicData]) => {
    entries = knowledgeItems;
    manuals = manualItems;
    const categories = [...new Set(manuals.map(item => item.category))];
    manualCategory.innerHTML = '<option value="">全部分類</option>' +
        categories.map(item => `<option value="${esc(item)}">${esc(item)}</option>`).join('');
    announcement.textContent = publicData.settings.announcement || '今天也請留意交接紀錄。';
    metrics.innerHTML = dashboard.metrics.map((item, index) =>
        `<article class="metric-card">
        <span>0${index + 1}</span>
        <p>${esc(item.label)}</p>
        <strong>${number(item.value)}</strong>
        ${esc(item.unit)}</article>`).join('');
    renderKnowledge();
    apiState.textContent = '資料已同步';
    apiState.classList.add('ok')
}).catch(error => {
    apiState.textContent = '資料服務未連線';
    knowledge.innerHTML = `<div class="error-note">${esc(error.message)}</div>`
});
const updateClock = () => currentClock.textContent = new Intl.DateTimeFormat('zh-TW', {
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
}).format(new Date(Date.now() + serverOffset));
updateClock();
setInterval(updateClock, 1000);
setInterval(() => {
    syncServerTime().catch(() => { });
    refreshAttendance().catch(() => { })
}, 60000);
makeupClock.onclick = () => clock('CLOCK_IN');
clockOutButton.onclick = () => clock('CLOCK_OUT');
employeeLeave.onclick = leaveSystem;
search.addEventListener('input', renderKnowledge);
manualCategory.addEventListener('change', renderKnowledge);
knowledgeTabs.onclick = event => {
    const button = event.target.closest('[data-knowledge-mode]');
    if (!button) return;
    knowledgeMode = button.dataset.knowledgeMode;
    knowledgeTabs.querySelectorAll('button').forEach(item => item.classList.toggle('active', item === button));
    manualCategoryField.hidden = knowledgeMode !== 'manuals';
    search.placeholder = knowledgeMode === 'manuals' ? '搜尋文件名稱或分類…' : '請輸入欲查詢內容…';
    manualReader.hidden = true;
    knowledge.hidden = false;
    renderKnowledge()
};
closeManual.onclick = () => { manualReader.hidden = true; knowledge.hidden = false };
knowledge.onclick = event => {
    const manualButton = event.target.closest('[data-manual-id]');
    if (manualButton) { openManual(manualButton.dataset.manualId); return }
    const button = event.target.closest('[data-id]');
    if (!button) return;
    const item = entries.find(entry => entry.id === button.dataset.id);
    if (!item) return;
    modalCategory.textContent = item.category;
    modalTitle.textContent = item.title;
    modalSummary.textContent = item.summary;
    modalDetail.textContent = item.detail;
    modalRelated.textContent = item.related;
    modal.classList.add('open')
};
document.addEventListener('click', event => {
    if (event.target === modal || event.target.closest('.close')) modal.classList.remove('open')
}); document.addEventListener('keydown', event => {
    if (event.key === 'Escape') modal.classList.remove('open')
});
