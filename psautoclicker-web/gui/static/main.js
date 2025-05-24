// main.js
console.log('[DEBUG] main.js loaded');
import { DeviceManager } from '/static/DeviceManager.js';
import { MacroManager } from '/static/MacroManager.js';
import { MacroEditor } from '/static/MacroEditor.js';
import { ManualControls } from '/static/ManualControls.js';
import { MacroLog } from '/static/MacroLog.js';
import { EndOfLoopModal } from '/static/EndOfLoopModal.js';
import { UIHelpers } from '/static/UIHelpers.js';

window.addEventListener('DOMContentLoaded', () => {
    UIHelpers.debug('PSAutoClicker modular frontend loaded and DOM ready');
    window.deviceManager = new DeviceManager();
    UIHelpers.debug('DeviceManager initialized');
    const macroManager = new MacroManager();
    window.macroManager = macroManager;
    UIHelpers.debug('MacroManager initialized');
    MacroEditor.init();
    window.MacroEditor = MacroEditor;
    UIHelpers.debug('MacroEditor initialized');
    window.manualControls = new ManualControls();
    UIHelpers.debug('ManualControls initialized');
    window.macroLog = new MacroLog();
    UIHelpers.debug('MacroLog initialized');
    window.endOfLoopModal = new EndOfLoopModal();
    UIHelpers.debug('EndOfLoopModal initialized');
});

// DeviceManager: handles device CRUD, connection, and dropdown
class DeviceManager {
    constructor() {
        this.devices = [];
        this.selectedDeviceKey = null;
        this.deviceList = document.getElementById('deviceList');
        this.deviceLabel = document.getElementById('deviceLabel');
        this.deviceHost = document.getElementById('deviceHost');
        this.connectionStatus = document.getElementById('connectionStatus');
        this.init();
    }
    init() {
        document.getElementById('deviceList').addEventListener('change', () => this.onSelect());
        document.querySelector('button[onclick="addDevice()"]')?.addEventListener('click', () => this.add());
        document.querySelector('button[onclick="editDevice()"]')?.addEventListener('click', () => this.edit());
        document.querySelector('button[onclick="removeDevice()"]')?.addEventListener('click', () => this.remove());
        document.querySelector('button[onclick="connectDevice()"]')?.addEventListener('click', () => this.connect());
        document.querySelector('button[onclick="disconnectDevice()"]')?.addEventListener('click', () => this.disconnect());
        this.load();
    }
    load() {
        fetch('/api/devices').then(r => r.json()).then(devs => {
            console.log('[DEBUG] Devices loaded from backend:', devs);
            this.devices = devs;
            this.deviceList.innerHTML = '';
            devs.forEach((d, i) => {
                console.log(`[DEBUG] Adding device option: key=${d.key}, host=${d.host}, label=${d.label}`);
                const opt = document.createElement('option');
                opt.value = d.key;
                opt.textContent = d.label ? `${d.label} (${d.host})` : d.host;
                this.deviceList.appendChild(opt);
            });
            if (devs.length > 0) {
                this.deviceList.selectedIndex = 0;
                this.selectedDeviceKey = devs[0].key;
                this.updateFields();
            } else {
                this.selectedDeviceKey = null;
                this.deviceLabel.value = '';
                this.deviceHost.value = '';
            }
        });
        fetch('/api/connection_status').then(r => r.json()).then(status => {
            this.connectionStatus.textContent = `Status: ${status.status} (${status.ip || 'none'})`;
        });
    }
    onSelect() {
        this.selectedDeviceKey = this.deviceList.value;
        this.updateFields();
    }
    updateFields() {
        const dev = this.devices.find(d => d.key === this.selectedDeviceKey);
        if (dev) {
            this.deviceLabel.value = dev.label || '';
            this.deviceHost.value = dev.host || '';
        }
    }
    add() {
        const host = this.deviceHost.value.trim();
        const label = this.deviceLabel.value.trim();
        if (!host) { alert('Host/IP required'); return; }
        fetch('/api/devices', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host, label })
        }).then(() => this.load());
    }
    edit() {
        if (!this.selectedDeviceKey) { alert('Select a device to edit'); return; }
        const host = this.deviceHost.value.trim();
        const label = this.deviceLabel.value.trim();
        fetch(`/api/devices/${this.selectedDeviceKey}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host, label })
        }).then(() => this.load());
    }
    remove() {
        if (!this.selectedDeviceKey) { alert('Select a device to remove'); return; }
        if (!confirm('Remove this device?')) return;
        fetch(`/api/devices/${this.selectedDeviceKey}`, { method: 'DELETE' }).then(() => this.load());
    }
    connect() {
        const key = this.deviceList.value;
        const dev = this.devices.find(d => d.key === key);
        if (!dev) { alert('Select a device to connect'); return; }
        fetch('/api/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip: dev.host })
        }).then(r => r.json()).then(() => this.load());
    }
    disconnect() {
        fetch('/api/disconnect', { method: 'POST' }).then(r => r.json()).then(() => this.load());
    }
}

// MacroManager: handles macro CRUD, import/export, auto-refresh
class MacroManager {
    constructor() {
        this.macroList = document.getElementById('macroList');
        this.refreshBtn = document.getElementById('refreshMacrosBtn');
        this.autoRefreshCb = document.getElementById('autoRefreshMacros');
        this.autoRefreshInterval = null;
        this.init();
    }
    init() {
        this.refreshBtn.addEventListener('click', () => this.load('manual'));
        this.autoRefreshCb.addEventListener('change', () => this.toggleAutoRefresh());
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
                MacroEditor.loadMacro(macros[0].name);
            }
        });
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
}

// MacroEditor: handles macro editing, Blockly, and save
const MacroEditor = {
    workspace: null,
    macroName: document.getElementById('macroName'),
    macroDesc: document.getElementById('macroDesc'),
    macroEOLName: document.getElementById('macroEOLName'),
    form: document.getElementById('macroForm'),
    blocklyDiv: document.getElementById('blocklyDiv'),
    toolbox: {
        "kind": "flyoutToolbox",
        "contents": [
            { "kind": "block", "type": "macro_button" },
            { "kind": "block", "type": "macro_stick" },
            { "kind": "block", "type": "macro_autoclicker" },
            { "kind": "block", "type": "macro_simul" },
            { "kind": "block", "type": "macro_repeat" },
            { "kind": "block", "type": "macro_comment" }
        ]
    },
    init() {
        this.workspace = Blockly.inject('blocklyDiv', { toolbox: this.toolbox });
        this.form.onsubmit = (e) => { e.preventDefault(); this.save(); };
        document.getElementById('macroList').addEventListener('change', () => {
            const name = document.getElementById('macroList').value;
            this.loadMacro(name);
        });
    },
    loadMacro(name) {
        fetch('/api/macros').then(r => r.json()).then(macros => {
            const macro = macros.find(m => m.name === name);
            if (macro) {
                this.macroName.value = macro.name;
                this.macroDesc.value = macro.description || '';
                this.macroEOLName.value = macro.end_of_loop_macro_name || '';
                this.macroStepsToBlockly(macro.steps || []);
            }
        });
    },
    save() {
        const name = this.macroName.value;
        const description = this.macroDesc.value;
        const end_of_loop_macro_name = this.macroEOLName.value;
        const steps = this.blocklyToMacroSteps();
        const macro = {
            name,
            description,
            steps,
            end_of_loop_macro_name: end_of_loop_macro_name || undefined
        };
        fetch('/api/macros', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(macro)
        }).then(() => MacroManager.load('manual'));
    },
    // ... (blocklyToMacroSteps, macroStepsToBlockly, etc. as before) ...
};

// (You would also modularize manual controls, macro log, and EOL modal similarly)
// For brevity, only the main structure is shown here. 