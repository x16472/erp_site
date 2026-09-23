import { apiData, bindAdminAccess, bindImageFallbacks, bindTabs, escapeHtml } from './script.js';

const request = (path, options = {}) => apiData(path, options, '操作失敗');
const esc = escapeHtml;
const apiState = document.querySelector('#apiState'),
    loginShell = document.querySelector('#loginShell'),
    staffConsole = document.querySelector('#staffConsole'),
    loginForm = document.querySelector('#loginForm'),
    loginStatus = document.querySelector('#loginStatus'),
    adminName = document.querySelector('#adminName'),
    logoutButton = document.querySelector('#logoutButton'),
    staffForm = document.querySelector('#staffForm'),
    staffList = document.querySelector('#staffList'),
    staffStatus = document.querySelector('#staffStatus'),
    staffPhoto = document.querySelector('#staffPhoto'),
    photoPreview = document.querySelector('#photoPreview'),
    resetStaff = document.querySelector('#resetStaff'),
    filterForm = document.querySelector('#filterForm'),
    employeeFilter = document.querySelector('#employeeFilter'),
    attendanceBody = document.querySelector('#attendanceBody'),
    recordCount = document.querySelector('#recordCount'),
    clockInCount = document.querySelector('#clockInCount'),
    clockOutCount = document.querySelector('#clockOutCount'),
    staffTabs = document.querySelector('#staffTabs'),
    staffDepartment = document.querySelector('#staffDepartment'),
    departmentForm = document.querySelector('#departmentForm'),
    departmentList = document.querySelector('#departmentList'),
    departmentStatus = document.querySelector('#departmentStatus'),
    resetDepartment = document.querySelector('#resetDepartment');
let csrf = '', staffItems = [], departmentItems = [],
    previewUrl = '';
function showLogin() {
    loginShell.hidden = false;
    staffConsole.hidden = true;
    apiState.textContent = '需要管理員登入';
    apiState.classList.remove('ok')
}
function photoUrl(item) {
    return item.photo_file ? `static/staff/${encodeURIComponent(item.photo_file)}` : 'static/appicon.png'
}
function renderStaff() {
    staffList.innerHTML = staffItems.map(item =>
        `<article class="staff-admin-card ${item.is_active ? '' : 'inactive'}"><img src="${photoUrl(item)}" alt="${esc(item.display_name)}">
        <div><b>${esc(item.employee_id)}｜${esc(item.display_name)}</b>
            <small>${esc(item.department)} · ${esc(item.position)}${item.is_active ? '' : ' · 已停用'}</small></div>
            <div class="btn-group"><button class="btn secondary" data-edit="${esc(item.employee_id)}">編輯</button>
                ${item.is_active ? `<button class="btn secondary" data-disable="${esc(item.employee_id)}">停用</button>` : ''}</div></article>`).join('') || '<div class="empty">目前沒有員工資料。</div>';
    employeeFilter.innerHTML = '<option value="">全部員工</option>' + staffItems.filter(item => item.is_active).map(item =>
        `<option value="${esc(item.employee_id)}">${esc(item.employee_id)}｜${esc(item.display_name)}</option>`).join('');
    bindImageFallbacks(staffList)
}
async function loadStaff() {
    staffItems = await request('/api/admin/staff');
    renderStaff()
}
function renderDepartments() {
    staffDepartment.innerHTML = '<option value="">請選擇部門</option>' + departmentItems.filter(item => item.is_active).map(item => `<option value="${esc(item.name)}">${esc(item.name)}</option>`).join(''); departmentList.innerHTML = departmentItems.map(item => `<article class="staff-admin-card ${item.is_active ? '' : 'inactive'}"><div><b>${esc(item.name)}</b><small>${item.staff_count} 位在職員工${item.is_active ? '' : ' · 已停用'}</small></div><div class="btn-group"><button class="btn secondary" data-department-edit="${item.id}">編輯</button>${item.is_active ? `<button class="btn secondary" data-department-disable="${item.id}">停用</button>` : ''}</div></article>`).join('') || '<div class="empty">目前沒有部門資料。</div>'
}
async function loadDepartments() {
    departmentItems = await request('/api/admin/departments'); renderDepartments()
}
async function showConsole(session) {
    loginShell.hidden = true; staffConsole.hidden = false;
    csrf = session.csrf; adminName.textContent = session.username;
    apiState.textContent = '管理員已登入'; apiState.classList.add('ok');
    await Promise.all([loadDepartments(), loadStaff(), loadAttendance()])
}
async function loadAttendance() {
    attendanceBody.innerHTML = '<tr><td colspan="6">正在讀取…</td></tr>'; try { const values = new FormData(filterForm), query = new URLSearchParams(); for (const [key, value] of values) if (value) query.set(key, value); const items = await request(`/api/admin/attendance?${query}`); recordCount.textContent = items.length; clockInCount.textContent = items.filter(item => item.action === 'CLOCK_IN').length; clockOutCount.textContent = items.filter(item => item.action === 'CLOCK_OUT').length; attendanceBody.innerHTML = items.length ? items.map(item => `<tr><td>${esc(new Date(item.clocked_at).toLocaleString('zh-TW'))}</td><td>${esc(item.employee_id)}</td><td>${esc(item.display_name)}</td><td>${esc(item.department)}</td><td>${esc(item.position)}</td><td><span class="tag">${item.action === 'CLOCK_IN' ? '上班' : '下班'}</span></td></tr>`).join('') : '<tr><td colspan="6">目前沒有符合條件的打卡紀錄。</td></tr>' } catch (error) { attendanceBody.innerHTML = `<tr><td colspan="6">${esc(error.message)}</td></tr>` }
}
const readPhoto = file => new Promise((resolve, reject) => {
    const reader = new FileReader(); reader.onload = () => resolve({
        name: file.name, type: file.type, data: reader.result
    });
    reader.onerror = () => reject(new Error('照片讀取失敗'));
    reader.readAsDataURL(file)
});
let focusingInvalid = false; staffForm.addEventListener('invalid', event => { if (focusingInvalid) return; focusingInvalid = true; event.target.focus(); staffStatus.className = 'error-note'; staffStatus.textContent = `請完成必填欄位：${event.target.closest('.field')?.querySelector('span')?.textContent || '員工資料'}`; setTimeout(() => { focusingInvalid = false }, 0) }, true);
function resetStaffForm() {
    staffForm.reset();
    staffForm.elements.employee_id.readOnly = false; staffForm.elements.employee_id.closest('.primary-key-field').classList.remove('locked'); photoPreview.src = 'static/appicon.png'; staffStatus.textContent = ''; if (previewUrl) { URL.revokeObjectURL(previewUrl); previewUrl = '' }
}
staffPhoto.onchange = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    const file = staffPhoto.files[0]; previewUrl = file ? URL.createObjectURL(file) : '';
    photoPreview.src = previewUrl || 'static/appicon.png'
};
staffList.onclick = async event => {
    const edit = event.target.closest('[data-edit]'),
        disable = event.target.closest('[data-disable]');
    if (edit) {
        const item = staffItems.find(row => row.employee_id === edit.dataset.edit);
        if (!item) return;
        for (const name of ['employee_id', 'display_name', 'gender', 'age', 'department', 'position', 'traits', 'biography']) staffForm.elements[name].value = item[name] ?? ''; staffForm.elements.employee_id.readOnly = true; staffForm.elements.employee_id.closest('.primary-key-field').classList.add('locked'); photoPreview.src = photoUrl(item); staffForm.scrollIntoView({ behavior: 'smooth' })
    } if (disable && confirm(`確定停用員工 ${disable.dataset.disable}？`)) {
        await request('/api/admin/staff', {
            method: 'DELETE', headers: {
                'Content-Type': 'application/json', 'X-CSRF-Token': csrf
            }, body: JSON.stringify({ employee_id: disable.dataset.disable })
        }); await loadStaff();
        await loadAttendance()
    }
};
staffForm.onsubmit = async event => {
    event.preventDefault();
    const submitter = event.submitter;
    submitter.disabled = true;
    staffStatus.className = '';
    staffStatus.textContent = '正在驗證並儲存…';
    try {
        const formData = new FormData(staffForm),
            file = formData.get('photo');
        formData.delete('photo');
        const payload = Object.fromEntries(formData);
        if (file && file.size) payload.photo = await readPhoto(file);
        await request('/api/admin/staff', {
            method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify(payload)
        });
        await loadStaff();
        resetStaffForm();
        staffStatus.className = 'success-note';
        staffStatus.textContent = '員工文字資料與照片已完成更新。'
    } catch (error) {
        staffStatus.className = 'error-note';
        staffStatus.textContent = error.message
    } finally { submitter.disabled = false }
};
bindTabs(staffTabs);
departmentList.onclick = async event => {
    const edit = event.target.closest('[data-department-edit]'),
        disable = event.target.closest('[data-department-disable]');
    if (edit) {
        const item = departmentItems.find(row => row.id === Number(edit.dataset.departmentEdit));
        if (item) {
            departmentForm.elements.id.value = item.id;
            departmentForm.elements.name.value = item.name;
            departmentForm.elements.name.focus()
        }
    }
    if (disable && confirm('確定停用此部門？')) {
        await request('/api/admin/departments', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
            body: JSON.stringify({ id: Number(disable.dataset.departmentDisable) })
        }); await loadDepartments()
    }
};
departmentForm.onsubmit = async event => {
    event.preventDefault();
    departmentStatus.textContent = '儲存中…';
    const payload = Object.fromEntries(new FormData(departmentForm));
    payload.id = Number(payload.id || 0); try {
        await request('/api/admin/departments', {
            method: 'POST', headers: {
                'Content-Type': 'application/json', 'X-CSRF-Token': csrf
            },
            body: JSON.stringify(payload)
        }); departmentForm.reset();
        await Promise.all([loadDepartments(), loadStaff()]);
        departmentStatus.className = 'success-note';
        departmentStatus.textContent = '部門資料已更新。'
    } catch (error) {
        departmentStatus.className = 'error-note';
        departmentStatus.textContent = error.message
    }
};
resetDepartment.onclick = () => {
    departmentForm.reset();
    departmentStatus.textContent = '';
    departmentForm.elements.name.focus()
};
resetStaff.onclick = resetStaffForm;
filterForm.onsubmit = event => {
    event.preventDefault();
    loadAttendance()
};
bindAdminAccess({
    loginForm,
    loginStatus,
    logoutButton,
    onAuthenticated: showConsole,
    onUnauthenticated: () => {
        csrf = '';
        showLogin();
    },
});
