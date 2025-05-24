console.log('[DEBUG] MacroLog.js loaded');

export class MacroLog {
    constructor() {
        this.logElem = document.getElementById('macroLog');
        this.lastJobId = null;
        this.socket = io();
        this.init();
    }
    init() {
        this.socket.on('macro_log', (data) => this.onMacroLog(data));
    }
    onMacroLog(data) {
        if (data.job_id === this.lastJobId) {
            const logLines = (data.log || []);
            this.logElem.innerHTML = logLines.map(this.colorizeLogLine).join('<br>');
        }
    }
    colorizeLogLine(line) {
        if (/error|fail/i.test(line)) {
            return `<span style='color:#ff4e4e;'>${MacroLog.escapeHtml(line)}</span>`;
        } else if (/finished|stopping/i.test(line)) {
            return `<span style='color:#b8e994;'>${MacroLog.escapeHtml(line)}</span>`;
        } else if (/started|starting/i.test(line)) {
            return `<span style='color:#4e8cff;'>${MacroLog.escapeHtml(line)}</span>`;
        } else if (/repeat/i.test(line)) {
            return `<span style='color:#ffe066;'>${MacroLog.escapeHtml(line)}</span>`;
        } else if (/comment/i.test(line)) {
            return `<span style='color:#a29bfe;'>${MacroLog.escapeHtml(line)}</span>`;
        } else if (/stick/i.test(line)) {
            return `<span style='color:#00b894;'>${MacroLog.escapeHtml(line)}</span>`;
        } else if (/button/i.test(line)) {
            return `<span style='color:#fab1a0;'>${MacroLog.escapeHtml(line)}</span>`;
        } else if (/autoclicker/i.test(line)) {
            return `<span style='color:#fdcb6e;'>${MacroLog.escapeHtml(line)}</span>`;
        } else if (/end-of-loop/i.test(line)) {
            return `<span style='color:#81ecec;'>${MacroLog.escapeHtml(line)}</span>`;
        }
        return MacroLog.escapeHtml(line);
    }
    static escapeHtml(text) {
        return text.replace(/[&<>"]'/g, function(m) {
            return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'})[m];
        });
    }
    setJobId(jobId) {
        this.lastJobId = jobId;
    }
} 