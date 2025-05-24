console.log('[DEBUG] ManualControls.js loaded');

export class ManualControls {
    constructor() {
        this.manualButton = document.getElementById('manualButton');
        this.manualStick = document.getElementById('manualStick');
        this.manualDirection = document.getElementById('manualDirection');
        this.manualMagnitude = document.getElementById('manualMagnitude');
        this.manualStickDuration = document.getElementById('manualStickDuration');
        this.autoButton = document.getElementById('autoButton');
        this.autoInterval = document.getElementById('autoInterval');
        this.autoDuration = document.getElementById('autoDuration');
        this.init();
    }
    init() {
        document.getElementById('sendManualButtonBtn').addEventListener('click', () => this.sendManualButton());
        document.getElementById('sendManualStickBtn').addEventListener('click', () => this.sendManualStick());
        document.getElementById('startManualAutoclickerBtn').addEventListener('click', () => this.startManualAutoclicker());
        document.getElementById('stopManualAutoclickerBtn').addEventListener('click', () => this.stopManualAutoclicker());
    }
    sendManualButton() {
        const button = this.manualButton.value;
        console.log('[DEBUG] Sending manual button:', button);
        fetch('/api/button', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ button })
        });
    }
    sendManualStick() {
        const stick = this.manualStick.value;
        const direction = this.manualDirection.value;
        const magnitude = parseFloat(this.manualMagnitude.value);
        const duration = parseInt(this.manualStickDuration.value);
        console.log('[DEBUG] Sending manual stick:', { stick, direction, magnitude, duration });
        fetch('/api/stick', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ stick, direction, magnitude })
        });
        if (direction !== 'NEUTRAL' && duration > 0) {
            setTimeout(() => {
                fetch('/api/stick', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ stick, direction: 'NEUTRAL', magnitude: 0.0 })
                });
            }, duration);
        }
    }
    startManualAutoclicker() {
        const button = this.autoButton.value;
        const interval = parseInt(this.autoInterval.value);
        const duration = parseInt(this.autoDuration.value) || 0;
        console.log('[DEBUG] Starting manual autoclicker:', { button, interval, duration });
        fetch('/api/manual_autoclicker/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ button, interval, duration })
        });
    }
    stopManualAutoclicker() {
        console.log('[DEBUG] Stopping manual autoclicker');
        fetch('/api/manual_autoclicker/stop', { method: 'POST' });
    }
} 