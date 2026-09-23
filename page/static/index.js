import { apiData, bindImageFallbacks, escapeHtml, formatNumber } from './script.js';

const esc = escapeHtml;
const menuButton = document.querySelector('#menuButton'),
    publicNav = document.querySelector('#publicNav'),
    heroTitle = document.querySelector('#heroTitle'),
    heroSubtitle = document.querySelector('#heroSubtitle'),
    announcement = document.querySelector('#announcement'),
    publicStats = document.querySelector('#campus'),
    staffGrid = document.querySelector('#staffGrid'),
    departmentFilter = document.querySelector('#departmentFilter'),
    teamCount = document.querySelector('#teamCount');
menuButton.onclick = () => publicNav.classList.toggle('open');
apiData('/api/public').then(data => {
    const settings = data.settings;
    document.body.dataset.theme = settings.theme;
    heroTitle.textContent = settings.hero_title;
    heroSubtitle.textContent = settings.hero_subtitle;
    announcement.textContent = settings.announcement;
    publicStats.innerHTML = data.stats.map(item =>
        `<div class="public-stat"><b>${formatNumber(item.value)}</b>
        <span>${esc(item.label)}</span></div>`).join('');
}).catch(error => {
    announcement.textContent = error.message;
    publicStats.innerHTML = '<div class="error-note">企業資料暫時無法載入。</div>'
});
function renderStaff(staff) {
    teamCount.textContent = `共 ${staff.length} 位夥伴`;
    staffGrid.innerHTML = staff.map(item =>
        `<article class="staff-card"><img src="${item.photo_file ?
            `static/staff/${encodeURIComponent(item.photo_file)}` : 'static/appicon.png'}" alt="${esc(item.display_name)}">
            <div>
                <span>${esc(item.department)}</span>
                <h3>${esc(item.display_name)}</h3>
                <b>${esc(item.position)}</b><p>${esc(item.traits || '以專業支援共同體營運')}</p>
            </div>
        </article>`).join('') || '<div class="empty">此部門目前沒有可公開的專業團隊資料。</div>';
    bindImageFallbacks(staffGrid)
}
async function loadStaff() {
    staffGrid.innerHTML = '<div class="empty">正在整理專業團隊…</div>';
    try {
        renderStaff(await apiData(`/api/staff/public?department=${encodeURIComponent(departmentFilter.value)}`))
    } catch (error) {
        staffGrid.innerHTML = `<div class="error-note">${esc(error.message)}</div>`
    }
}
apiData('/api/staff/departments').then(items => {
    departmentFilter.replaceChildren(new Option('全部部門', ''));
    items.forEach(item => departmentFilter.add(new Option(`${item.department}（${item.staff_count}）`, item.department)));
    loadStaff()
}).catch(error => {
    departmentFilter.disabled = true;
    staffGrid.innerHTML = `<div class="error-note">${esc(error.message)}</div>`
});
departmentFilter.onchange = loadStaff;
