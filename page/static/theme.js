(() => {
    const storageKey = 'erp-color-mode';
    const root = document.documentElement;
    const systemPreference = window.matchMedia('(prefers-color-scheme: dark)');
    let manualMode = null;

    try {
        const saved = localStorage.getItem(storageKey);
        if (saved === 'light' || saved === 'dark') manualMode = saved;
    } catch {
        // 儲存空間受限時，仍可在目前頁面切換。
    }

    function applyMode(mode) {
        root.dataset.colorMode = mode;
        document.querySelectorAll('[data-theme-toggle]').forEach(button => {
            const dark = mode === 'dark';
            button.textContent = dark ? '切換淺色' : '切換深色';
            button.setAttribute('aria-pressed', String(dark));
            button.setAttribute('aria-label', dark ? '切換為淺色模式' : '切換為深色模式');
        });
    }

    function preferredMode() {
        return manualMode || (systemPreference.matches ? 'dark' : 'light');
    }

    applyMode(preferredMode());
    document.addEventListener('DOMContentLoaded', () => {
        applyMode(preferredMode());
        document.querySelectorAll('[data-theme-toggle]').forEach(button => {
            button.addEventListener('click', () => {
                manualMode = root.dataset.colorMode === 'dark' ? 'light' : 'dark';
                applyMode(manualMode);
                try {
                    localStorage.setItem(storageKey, manualMode);
                } catch {
                    // 不讓儲存失敗中斷使用者操作。
                }
            });
        });
    });

    systemPreference.addEventListener('change', () => {
        if (!manualMode) applyMode(preferredMode());
    });
    window.addEventListener('storage', event => {
        if (event.key !== storageKey && event.key !== null) return;
        manualMode = event.newValue === 'dark' || event.newValue === 'light' ? event.newValue : null;
        applyMode(preferredMode());
    });
})();
