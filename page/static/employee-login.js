import { apiData, serverTimeOffset } from './script.js';

const
    form = document.querySelector('#accessForm'),
    statusBox = document.querySelector('#accessStatus'),
    clock = document.querySelector('#accessClock'),
    buttons = [...form.querySelectorAll('button[type="submit"]')];
const allowedNext = new Set(['/home.html', '/sales.html', '/exam.html', '/youtube.html', '/staff.html', '/mis.html']);
const requested = new URLSearchParams(location.search).get('next') || '/home.html';
const next = allowedNext.has(requested) ? requested : '/home.html';
let serverOffset = 0;
const renderClock = () => clock.textContent = new Date(Date.now() + serverOffset).toLocaleString('zh-TW', { hour12: false });
async function syncTime() {
    const result = await serverTimeOffset();
    serverOffset = result.offset;
    renderClock()
}
setInterval(renderClock, 1000);
setInterval(() => syncTime().catch(() => { }), 60000);
renderClock();
syncTime().catch(() => {
    statusBox.className = 'attendance-warning';
    statusBox.textContent = '目前使用本機時間，等待伺服器重新校時。'
});
apiData('/api/employee/session').then(session => {
    if (session?.authenticated) location.replace(next)
}).catch(() => { });
form.addEventListener('submit', async event => {
    event.preventDefault();
    const submitter = event.submitter;
    if (!submitter) return;
    buttons.forEach(button => button.disabled = true);
    statusBox.className = '';
    statusBox.textContent = '正在驗證員工資料…';
    try {
        const employeeId = new FormData(form).get('employee_id');
        const data = await apiData('/api/employee/login', {
            method: 'POST', credentials: 'include', headers: {
                'Content-Type': 'application/json'
            }, body: JSON.stringify({
                employee_id: employeeId, mode: submitter.value
            })
        }, '驗證失敗');
        const attendance = data.attendance;
        await syncTime(); if (attendance) {
            const occurred = new Date(attendance.clocked_at);
            statusBox.className = 'success-note';
            statusBox.textContent = data.access_mode === 'CLOCK_IN' ? `${data.employee.display_name}，上班打卡成功，正在進入…` : `前次打卡時間：${occurred.toLocaleString('zh-TW')}，正在進入…`
        } else {
            statusBox.className = 'attendance-warning';
            statusBox.textContent = '您尚未打卡，進入後請留意補打卡提醒。'
        }
        setTimeout(() => location.replace(next), 1200);
    } catch (error) {
        statusBox.className = 'error-note';
        statusBox.textContent = error.message;
        buttons.forEach(button => button.disabled = false)
    }
});
