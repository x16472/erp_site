const DEFAULT_API_ERROR = '資料服務暫時無法使用';

export const employeeLoginUrl = `employee-login.html?next=${encodeURIComponent(location.pathname)}`;

export function escapeHtml(value) {
    const node = document.createElement('div');
    node.textContent = value ?? '';
    return node.innerHTML;
}

export function formatNumber(value) {
    return new Intl.NumberFormat('zh-TW').format(value);
}

export async function apiResponse(path, options = {}) {
    const response = await fetch(path, {
        credentials: 'include',
        ...options,
    });
    const body = await response.json().catch(() => ({}));
    return { response, body };
}

export async function apiData(path, options = {}, fallbackMessage = DEFAULT_API_ERROR) {
    const { response, body } = await apiResponse(path, options);
    if (response.status === 401 && body.code === 'EMPLOYEE_AUTH_REQUIRED') {
        location.replace(employeeLoginUrl);
        throw new Error('需要員工驗證');
    }
    if (!response.ok) {
        throw new Error(body.error || fallbackMessage);
    }
    return body.data;
}

export async function requireEmployee() {
    const session = await apiData('/api/employee/session');
    if (!session?.authenticated) {
        location.replace(employeeLoginUrl);
        throw new Error('需要員工驗證');
    }
    return session;
}

export function jsonRequest(path, payload, { csrf = '', method = 'POST', fallbackMessage } = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (csrf) headers['X-CSRF-Token'] = csrf;
    return apiData(path, {
        method,
        headers,
        body: JSON.stringify(payload),
    }, fallbackMessage);
}

export async function serverTimeOffset() {
    const started = Date.now();
    const time = await apiData('/api/time', { cache: 'no-store' }, '校時失敗');
    const ended = Date.now();
    return {
        offset: Number(time.unix_ms) + (ended - started) / 2 - ended,
        time,
    };
}

export function bindTabs(tabList, {
    buttonSelector = '[data-panel]',
    panelSelector = '.admin-panel',
} = {}) {
    tabList.addEventListener('click', event => {
        const button = event.target.closest(buttonSelector);
        if (!button || !tabList.contains(button)) return;
        tabList.querySelectorAll(buttonSelector).forEach(item => {
            item.classList.toggle('active', item === button);
        });
        document.querySelectorAll(panelSelector).forEach(panel => {
            panel.classList.toggle('active', panel.id === button.dataset.panel);
        });
    });
}

export function bindImageFallbacks(root, fallback = 'static/appicon.png') {
    root.querySelectorAll('img').forEach(image => {
        image.addEventListener('error', () => {
            image.src = fallback;
        }, { once: true });
    });
}

export function bindAdminAccess({
    loginForm,
    loginStatus,
    logoutButton,
    onAuthenticated,
    onUnauthenticated,
}) {
    loginForm.addEventListener('submit', async event => {
        event.preventDefault();
        loginStatus.className = '';
        loginStatus.textContent = '驗證中…';
        try {
            const session = await jsonRequest(
                '/api/admin/login',
                Object.fromEntries(new FormData(loginForm)),
                { fallbackMessage: '管理員驗證失敗' },
            );
            loginForm.reset();
            loginStatus.textContent = '';
            await onAuthenticated(session);
        } catch (error) {
            loginStatus.className = 'error-note';
            loginStatus.textContent = error.message;
        }
    });

    logoutButton.addEventListener('click', async () => {
        try {
            await jsonRequest('/api/admin/logout', {});
            await onUnauthenticated();
        } catch (error) {
            loginStatus.className = 'error-note';
            loginStatus.textContent = error.message;
        }
    });

    requireEmployee()
        .then(() => apiData('/api/admin/session'))
        .then(session => session?.authenticated ? onAuthenticated(session) : onUnauthenticated())
        .catch(() => onUnauthenticated());
}
