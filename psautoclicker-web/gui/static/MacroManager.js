console.log('[DEBUG] MacroManager.js loaded');
export class MacroManager {
    constructor() {
        this.macroList = document.getElementById('macroList');
        this.refreshBtn = document.getElementById('refreshMacrosBtn');
        this.autoRefreshCb = document.getElementById('autoRefreshMacros');
        this.autoRefreshInterval = null;
        this.currentJobId = null;
        this.init();
    }
    init() {
        this.refreshBtn.addEventListener('click', () => this.load('manual'));
        this.autoRefreshCb.addEventListener('change', () => this.toggleAutoRefresh());
        document.getElementById('runMacroBtn').addEventListener('click', () => this.runMacro());
        document.getElementById('editMacroBtn').addEventListener('click', () => this.editMacro());
        document.getElementById('deleteMacroBtn').addEventListener('click', () => this.deleteMacro());
        document.getElementById('importMacroBtn').addEventListener('click', () => this.importMacro());
        document.getElementById('exportMacroBtn').addEventListener('click', () => this.exportMacro());
        document.getElementById('downloadMacroFromGitHubBtn').addEventListener('click', () => this.downloadMacroFromGitHub());
        this.macroList.addEventListener('change', () => this.onMacroListChange());
        this.toggleAutoRefresh();
        this.load('manual');
    }
    load(source = 'manual') {
        console.log(`[DEBUG] loadMacros called (${source})`);
        fetch('/api/macros').then(r => r.json()).then(macros => {
            console.log(`[DEBUG] Macros loaded:`, macros);
            this.macroList.innerHTML = '';
            macros.forEach((m, i) => {
                const opt = document.createElement('option');
                opt.value = m.name;
                opt.textContent = m.name;
                this.macroList.appendChild(opt);
            });
            if (macros.length > 0) {
                this.macroList.selectedIndex = 0;
                if (window.MacroEditor) {
                    window.MacroEditor.loadMacro(macros[0].name);
                }
            }
        }).catch(e => console.error('[DEBUG] Error loading macros:', e));
    }
    toggleAutoRefresh() {
        if (this.autoRefreshCb.checked) {
            this.autoRefreshInterval = setInterval(() => this.load('auto'), 30000);
            this.refreshBtn.title = "The macro list auto-refreshes every 30 seconds. Click to refresh manually.";
            console.log('[DEBUG] Macro auto-refresh enabled');
        } else {
            clearInterval(this.autoRefreshInterval);
            this.refreshBtn.title = "Auto-refresh is disabled. Click to refresh manually.";
            console.log('[DEBUG] Macro auto-refresh disabled');
        }
    }
    runMacro() {
        const name = this.macroList.value;
        if (!name) return alert('Select a macro to run.');
        fetch('/api/run_macro', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        }).then(r => r.json()).then(data => {
            if (data.job_id) {
                this.currentJobId = data.job_id;
                this.listenMacroLog(data.job_id);
            } else {
                alert(data.error || 'Failed to start macro.');
            }
        });
    }
    stopMacro() {
        if (!this.currentJobId) return alert('No running macro.');
        fetch('/api/stop_macro', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job_id: this.currentJobId })
        }).then(r => r.json()).then(data => {
            if (data.status !== 'stopping') {
                alert(data.error || 'Failed to stop macro.');
            }
        });
    }
    editMacro() {
        const name = this.macroList.value;
        if (!name) return alert('Select a macro to edit.');
        if (window.MacroEditor) {
            window.MacroEditor.loadMacro(name);
        }
    }
    deleteMacro() {
        const name = this.macroList.value;
        if (!name) return alert('Select a macro to delete.');
        if (!confirm(`Delete macro '${name}'?`)) return;
        fetch(`/api/macros/${encodeURIComponent(name)}`, { method: 'DELETE' })
            .then(r => r.json()).then(data => {
                if (data.status === 'ok') {
                    this.load('manual');
                } else {
                    alert(data.error || 'Failed to delete macro.');
                }
            });
    }
    importMacro() {
        const fileInput = document.getElementById('importMacroFile');
        fileInput.onchange = () => {
            const file = fileInput.files[0];
            if (!file) return;
            const formData = new FormData();
            formData.append('file', file);
            fetch('/api/macros/import', {
                method: 'POST',
                body: formData
            }).then(r => r.json()).then(data => {
                if (data.status === 'ok') {
                    this.load('manual');
                } else {
                    alert(data.error || 'Failed to import macro.');
                }
            });
        };
        fileInput.click();
    }
    exportMacro() {
        const name = this.macroList.value;
        if (!name) return alert('Select a macro to export.');
        window.open(`/api/macros/export/${encodeURIComponent(name)}`);
    }
    downloadMacroFromGitHub() {
        const url = prompt('Enter GitHub raw URL to macro .json:');
        if (!url) return;
        fetch(url).then(r => r.json()).then(macro => {
            fetch('/api/macros', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(macro)
            }).then(r => r.json()).then(data => {
                if (data.status === 'ok') {
                    this.load('manual');
                } else {
                    alert(data.error || 'Failed to download macro.');
                }
            });
        }).catch(e => alert('Failed to fetch macro from GitHub.'));
    }
    onMacroListChange() {
        const name = this.macroList.value;
        if (window.MacroEditor) {
            window.MacroEditor.loadMacro(name);
        }
    }
    listenMacroLog(job_id) {
        if (!window.io) return;
        const socket = window.io();
        socket.emit('join_job', { job_id });
        socket.on('macro_log', (data) => {
            if (data.job_id === job_id && window.macroLog) {
                window.macroLog.updateLog(data.log, data.status);
            }
        });
    }
} 