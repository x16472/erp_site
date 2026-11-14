export const Theme = {
    storageKey: 'erp-color-mode',
    manualMode: null,
    initialized: false,

    init() {
        if (this.initialized) return;
        this.initialized = true;
        this.systemPreference = window.matchMedia('(prefers-color-scheme: dark)');
        try {
            const saved = localStorage.getItem(this.storageKey);
            if (saved === 'light' || saved === 'dark') this.manualMode = saved;
        } catch {
            // 儲存空間受限時，仍可在目前頁面切換。
        }
        this.apply();
        document.querySelectorAll('[data-theme-toggle]').forEach(button => {
            button.addEventListener('click', () => this.toggle());
        });
        this.systemPreference.addEventListener('change', () => {
            if (!this.manualMode) this.apply();
        });
        window.addEventListener('storage', event => {
            if (event.key !== this.storageKey && event.key !== null) return;
            this.manualMode = ['light', 'dark'].includes(event.newValue) ? event.newValue : null;
            this.apply();
        });
    },

    apply() {
        const mode = this.manualMode || (this.systemPreference.matches ? 'dark' : 'light');
        document.documentElement.dataset.colorMode = mode;
        document.querySelectorAll('[data-theme-toggle]').forEach(button => {
            const dark = mode === 'dark';
            button.textContent = dark ? '切換淺色' : '切換深色';
            button.setAttribute('aria-pressed', String(dark));
            button.setAttribute('aria-label', dark ? '切換為淺色模式' : '切換為深色模式');
        });
    },

    toggle() {
        this.manualMode = document.documentElement.dataset.colorMode === 'dark' ? 'light' : 'dark';
        this.apply();
        try {
            localStorage.setItem(this.storageKey, this.manualMode);
        } catch {
            // 不讓儲存失敗中斷使用者操作。
        }
    },

    colors() {
        const style = getComputedStyle(document.documentElement);
        return {
            background: style.getPropertyValue('--surface').trim(),
            foreground: style.getPropertyValue('--ink').trim(),
        };
    },
};
