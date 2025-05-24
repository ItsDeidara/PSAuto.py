console.log('[DEBUG] UIHelpers.js loaded');

export const UIHelpers = {
    debug(...args) {
        console.log('[DEBUG]', ...args);
    },
    error(...args) {
        console.error('[ERROR]', ...args);
    },
    showError(msg) {
        alert(msg); // Could be improved to a modal
    },
    getById(id) {
        return document.getElementById(id);
    },
    qs(sel) {
        return document.querySelector(sel);
    },
    qsa(sel) {
        return Array.from(document.querySelectorAll(sel));
    }
}; 