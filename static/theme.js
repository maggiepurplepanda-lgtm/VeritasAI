(function () {
    const themeKey = 'veritasai-theme';
    const colorKey = 'veritasai-accent';
    const defaultAccent = '#38bdf8';

    function relativeLuminance(red, green, blue) {
        const channels = [red, green, blue].map((channel) => {
            const normalized = channel / 255;
            return normalized <= 0.03928
                ? normalized / 12.92
                : Math.pow((normalized + 0.055) / 1.055, 2.4);
        });
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
    }

    function contrastRatio(firstLuminance, secondLuminance) {
        const lighter = Math.max(firstLuminance, secondLuminance);
        const darker = Math.min(firstLuminance, secondLuminance);
        return (lighter + 0.05) / (darker + 0.05);
    }

    function contrastColor(hex) {
        const value = hex.replace('#', '');
        const red = parseInt(value.slice(0, 2), 16);
        const green = parseInt(value.slice(2, 4), 16);
        const blue = parseInt(value.slice(4, 6), 16);
        const luminance = relativeLuminance(red, green, blue);
        const darkContrast = contrastRatio(luminance, 0.005);
        const lightContrast = contrastRatio(luminance, 1);
        return darkContrast >= lightContrast ? '#0f172a' : '#ffffff';
    }

    function applyTheme(theme) {
        document.documentElement.dataset.theme = theme;
        const button = document.querySelector('.theme-toggle');
        if (button) {
            button.textContent = theme === 'light' ? '☀ Light' : '☾ Dark';
            button.setAttribute('aria-pressed', String(theme === 'light'));
        }
    }

    function applyAccent(color) {
        const accent = /^#[0-9a-f]{6}$/i.test(color) ? color : defaultAccent;
        document.documentElement.style.setProperty('--accent', accent);
        document.documentElement.style.setProperty('--accent-contrast', contrastColor(accent));
        document.documentElement.style.setProperty('--focus-ring', `${accent}73`);
        const picker = document.querySelector('.color-picker');
        if (picker) picker.value = accent;
    }

    function initialize() {
        const savedTheme = localStorage.getItem(themeKey) || 'dark';
        const savedAccent = localStorage.getItem(colorKey) || defaultAccent;
        applyTheme(savedTheme);
        applyAccent(savedAccent);

        const toggle = document.querySelector('.theme-toggle');
        if (toggle) toggle.addEventListener('click', () => {
            const nextTheme = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
            localStorage.setItem(themeKey, nextTheme);
            applyTheme(nextTheme);
        });

        const picker = document.querySelector('.color-picker');
        if (picker) picker.addEventListener('input', (event) => {
            localStorage.setItem(colorKey, event.target.value);
            applyAccent(event.target.value);
        });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize);
    else initialize();
})();