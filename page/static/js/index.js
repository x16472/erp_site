import {
    apiData, bindImageFallbacks, escapeHtml, formatNumber
}
    from './api.js';

export const IndexPage = {
    initialized: false,
    init() {
        if (this.initialized) return;
        this.initialized = true;
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
        function closeMenu() {
            publicNav.classList.remove('open');
            menuButton.setAttribute('aria-expanded', 'false');
        }
        menuButton.onclick = () => {
            const open = publicNav.classList.toggle('open');
            menuButton.setAttribute('aria-expanded', String(open));
        };
        publicNav.addEventListener('click', event => {
            if (event.target.closest('a')) closeMenu();
        });
        document.addEventListener('keydown', event => {
            if (event.key === 'Escape' && publicNav.classList.contains('open')) {
                closeMenu();
                menuButton.focus();
            }
        });
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

        const contactDialog = document.querySelector('#contactDialog'),
            contactForm = document.querySelector('#contactForm'),
            contactStatus = document.querySelector('#contactStatus');

        document.querySelector('#contactOpen').addEventListener('click', () => {
            contactDialog.showModal();
        });
        document.querySelector('#contactClose').addEventListener('click', () => {
            contactDialog.close();
        });

        function isOutsideContactDialog(event) {
            const bounds = contactDialog.getBoundingClientRect();
            return event.clientX < bounds.left || event.clientX > bounds.right ||
                event.clientY < bounds.top || event.clientY > bounds.bottom;
        }

        let contactBackdropPressed = false;
        contactDialog.addEventListener('pointerdown', event => {
            contactBackdropPressed = event.target === contactDialog && isOutsideContactDialog(event);
        });
        contactDialog.addEventListener('click', event => {
            if (contactBackdropPressed && event.target === contactDialog && isOutsideContactDialog(event)) {
                contactDialog.close();
            }
            contactBackdropPressed = false;
        });
        contactForm.addEventListener('input', () => {
            contactStatus.hidden = true;
        });
        contactForm.addEventListener('submit', event => {
            event.preventDefault();
            const fields = new FormData(contactForm);
            const body = [
                `姓名：${fields.get('name').trim()}`,
                `聯絡電話：${fields.get('phone').trim()}`,
                `想了解的服務：${fields.get('service')}`,
                '',
                '需求說明：',
                fields.get('message').trim(),
            ].join('\r\n').replace(/\r?\n/g, '\r\n');
            const subject = encodeURIComponent('銀盾共同體｜商務合作詢問');
            // 只交由使用者的郵件程式建立草稿，不在網站上直接寄信。
            window.location.href = `${contactForm.getAttribute('action')}?subject=${subject}&body=${encodeURIComponent(body)}`;
            contactStatus.hidden = false;
        });
    },
};
