import { apiData, employeeLoginUrl, jsonRequest, requireEmployee, serverTimeOffset } from './script.js';

let serverOffset = 0;
let employeeCsrf = '';
let currentAttendance = null;

const announcement = document.querySelector('#announcement');
const apiState = document.querySelector('#apiState');
const currentClock = document.querySelector('#currentClock');
const clockResult = document.querySelector('#clockResult');
const employeeWelcome = document.querySelector('#employeeWelcome');
const employeeProfile = document.querySelector('#employeeProfile');
const makeupClock = document.querySelector('#makeupClock');
const clockOutButton = document.querySelector('#clockOutButton');
const employeeLeave = document.querySelector('#employeeLeave');

function renderAttendance(attendance) {
    currentAttendance = attendance;
    if (attendance) {
        clockResult.className = 'clock-result success-note';
        clockResult.textContent = `打卡時間｜${new Date(attendance.clocked_at).toLocaleString('zh-TW')}`;
        makeupClock.hidden = true;
        clockOutButton.disabled = attendance.action !== 'CLOCK_IN';
        clockOutButton.textContent = attendance.action === 'CLOCK_OUT' ? '已完成下班打卡' : '打卡下班';
    } else {
        clockResult.className = 'clock-result attendance-warning';
        clockResult.textContent = '您尚未打卡';
        makeupClock.hidden = false;
        makeupClock.disabled = false;
        clockOutButton.disabled = true;
    }
    employeeLeave.disabled = false;
}

async function syncServerTime() {
    const result = await serverTimeOffset();
    serverOffset = result.offset;
}

async function refreshAttendance() {
    const session = await apiData('/api/employee/session');
    if (!session.authenticated) {
        location.replace(employeeLoginUrl);
        return;
    }
    employeeCsrf = session.csrf;
    renderAttendance(session.attendance);
}

async function clock(action) {
    const buttons = [makeupClock, clockOutButton, employeeLeave];
    buttons.forEach(button => button.disabled = true);
    try {
        const attendance = await jsonRequest('/api/attendance/clock', { action }, { csrf: employeeCsrf });
        renderAttendance(attendance);
        if (action === 'CLOCK_OUT') {
            clockResult.textContent = `打卡時間｜${new Date(attendance.clocked_at).toLocaleString('zh-TW')}，下班打卡完成`;
            setTimeout(leaveSystem, 900);
        }
    } catch (error) {
        clockResult.className = 'clock-result error-note';
        clockResult.textContent = error.message;
        makeupClock.disabled = Boolean(currentAttendance);
        clockOutButton.disabled = !currentAttendance || currentAttendance.action !== 'CLOCK_IN';
        employeeLeave.disabled = false;
    }
}

async function leaveSystem() {
    employeeLeave.disabled = true;
    try {
        await jsonRequest('/api/employee/logout', {});
    } finally {
        location.replace(employeeLoginUrl);
    }
}

async function initializeHome() {
    try {
        const session = await requireEmployee();
        const employee = session.employee;
        employeeCsrf = session.csrf;
        employeeWelcome.textContent = `${employee.display_name}，歡迎進入工作台`;
        employeeProfile.textContent = `${employee.employee_id}｜${employee.department}｜${employee.position}`;
        renderAttendance(session.attendance);
        await syncServerTime();

        const publicData = await apiData('/api/public');
        announcement.textContent = publicData.settings.announcement || '今天也請留意交接紀錄。';
        apiState.textContent = '資料已同步';
        apiState.classList.add('ok');
    } catch (error) {
        apiState.textContent = '資料服務未連線';
        announcement.textContent = error.message;
    }
}

const updateClock = () => {
    currentClock.textContent = new Intl.DateTimeFormat('zh-TW', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
    }).format(new Date(Date.now() + serverOffset));
};

updateClock();
setInterval(updateClock, 1000);
setInterval(() => {
    syncServerTime().catch(() => {});
    refreshAttendance().catch(() => {});
}, 60000);

makeupClock.addEventListener('click', () => clock('CLOCK_IN'));
clockOutButton.addEventListener('click', () => clock('CLOCK_OUT'));
employeeLeave.addEventListener('click', leaveSystem);

initializeHome();
