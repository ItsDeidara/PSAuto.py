console.log('[DEBUG] EndOfLoopModal.js loaded');

export class EndOfLoopModal {
    constructor() {
        this.modal = document.getElementById('eolMacroModal');
        this.nameSpan = document.getElementById('eolMacroName');
        this.eolBlocklyDiv = document.getElementById('eolBlocklyDiv');
        this.editBtn = document.getElementById('editEOLBtn');
        this.saveBtn = document.getElementById('saveEOLMacroBtn');
        this.cancelBtn = document.getElementById('closeEOLModalBtn');
        this.eolWorkspace = null;
        this.toolbox = window.blocklyToolbox || null; // Should be set globally or imported
        this.init();
    }
    init() {
        this.editBtn.addEventListener('click', () => this.open());
        this.saveBtn.addEventListener('click', () => this.save());
        this.cancelBtn.addEventListener('click', () => this.close());
    }
    open() {
        const name = document.getElementById('macroEOLName').value.trim();
        if (!name) return;
        this.modal.style.display = 'block';
        this.nameSpan.textContent = name;
        if (this.eolWorkspace) this.eolWorkspace.dispose();
        this.eolWorkspace = Blockly.inject('eolBlocklyDiv', { toolbox: this.toolbox });
        fetch(`/api/macros`).then(r => r.json()).then(macros => {
            const macro = macros.find(m => m.name === name);
            if (macro) {
                // Load steps into Blockly
                if (window.MacroEditor && window.MacroEditor.macroStepsToBlockly) {
                    window.MacroEditor.macroStepsToBlockly.call({workspace: this.eolWorkspace, createBlockFromStep: window.MacroEditor.createBlockFromStep.bind({workspace: this.eolWorkspace})}, macro.steps || []);
                }
            } else {
                this.eolWorkspace.clear();
            }
        });
        console.log('[DEBUG] EndOfLoopModal opened for', name);
    }
    close() {
        this.modal.style.display = 'none';
        if (this.eolWorkspace) { this.eolWorkspace.dispose(); this.eolWorkspace = null; }
        console.log('[DEBUG] EndOfLoopModal closed');
    }
    save() {
        const name = document.getElementById('macroEOLName').value.trim();
        if (!name || !this.eolWorkspace) return;
        // Save steps from Blockly to macro file
        let steps = [];
        if (window.MacroEditor && window.MacroEditor.blocklyToMacroSteps) {
            steps = window.MacroEditor.blocklyToMacroSteps.call({workspace: this.eolWorkspace});
        }
        fetch('/api/macros', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, steps })
        }).then(() => {
            this.close();
            if (window.macroManager) {
                window.macroManager.load('manual');
            }
        });
        console.log('[DEBUG] EndOfLoopModal saved for', name);
    }
} 