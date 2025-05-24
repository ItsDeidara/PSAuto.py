console.log('[DEBUG] DeviceManager.js loaded');
export class DeviceManager {
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
        this.deviceList.addEventListener('change', () => this.onSelect());
        document.getElementById('addDeviceBtn').addEventListener('click', () => this.add());
        document.getElementById('editDeviceBtn').addEventListener('click', () => this.edit());
        document.getElementById('removeDeviceBtn').addEventListener('click', () => this.remove());
        document.getElementById('connectDeviceBtn').addEventListener('click', () => this.connect());
        document.getElementById('disconnectDeviceBtn').addEventListener('click', () => this.disconnect());
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
        }).catch(e => console.error('[DEBUG] Error loading devices:', e));
        fetch('/api/connection_status').then(r => r.json()).then(status => {
            this.connectionStatus.textContent = `Status: ${status.status} (${status.ip || 'none'})`;
        }).catch(e => console.error('[DEBUG] Error loading connection status:', e));
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
        }).then(() => this.load()).catch(e => console.error('[DEBUG] Error adding device:', e));
    }
    edit() {
        if (!this.selectedDeviceKey) { alert('Select a device to edit'); return; }
        const host = this.deviceHost.value.trim();
        const label = this.deviceLabel.value.trim();
        fetch(`/api/devices/${this.selectedDeviceKey}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host, label })
        }).then(() => this.load()).catch(e => console.error('[DEBUG] Error editing device:', e));
    }
    remove() {
        if (!this.selectedDeviceKey) { alert('Select a device to remove'); return; }
        if (!confirm('Remove this device?')) return;
        fetch(`/api/devices/${this.selectedDeviceKey}`, { method: 'DELETE' }).then(() => this.load()).catch(e => console.error('[DEBUG] Error removing device:', e));
    }
    connect() {
        const key = this.deviceList.value;
        const dev = this.devices.find(d => d.key === key);
        if (!dev) { alert('Select a device to connect'); return; }
        fetch('/api/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip: dev.host })
        }).then(r => r.json()).then(() => this.load()).catch(e => console.error('[DEBUG] Error connecting device:', e));
    }
    disconnect() {
        fetch('/api/disconnect', { method: 'POST' }).then(r => r.json()).then(() => this.load()).catch(e => console.error('[DEBUG] Error disconnecting device:', e));
    }
} 