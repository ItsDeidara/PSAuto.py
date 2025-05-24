console.log('[DEBUG] MacroEditor.js loaded');

export const MacroEditor = {
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
        this.form.addEventListener('submit', (e) => { e.preventDefault(); this.save(); });
        document.getElementById('macroList').addEventListener('change', () => {
            const name = document.getElementById('macroList').value;
            this.loadMacro(name);
        });
        document.getElementById('moveBlockUpBtn').addEventListener('click', () => this.moveBlockUp());
        document.getElementById('moveBlockDownBtn').addEventListener('click', () => this.moveBlockDown());
        document.getElementById('clearMacroEditorBtn').addEventListener('click', () => this.clearMacroEditor());
        document.getElementById('editEOLBtn').addEventListener('click', () => this.editEndOfLoopMacro());
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
        }).catch(e => console.error('[DEBUG] Error loading macro:', e));
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
        }).then(() => {
            if (window.macroManager) {
                window.macroManager.load('manual');
            }
        });
    },
    blocklyToMacroSteps() {
        // Convert Blockly workspace to macro steps array
        const blocks = this.workspace.getTopBlocks(true);
        const steps = [];
        for (const block of blocks) {
            // Example: extract type, fields, and next
            let step = null;
            if (block.type === 'macro_button') {
                step = [block.getFieldValue('BUTTON'), parseInt(block.getFieldValue('DELAY_MS') || '0'), block.getFieldValue('COMMENT') || undefined];
            } else if (block.type === 'macro_stick') {
                step = [[block.getFieldValue('STICK'), block.getFieldValue('DIRECTION'), parseFloat(block.getFieldValue('MAGNITUDE'))], parseInt(block.getFieldValue('DELAY_MS') || '0'), block.getFieldValue('COMMENT') || undefined];
            } else if (block.type === 'macro_autoclicker') {
                step = [{ type: 'autoclicker', button: block.getFieldValue('BUTTON'), interval: parseInt(block.getFieldValue('INTERVAL')), duration: parseInt(block.getFieldValue('DURATION') || '0') }, parseInt(block.getFieldValue('DELAY_MS') || '0'), block.getFieldValue('COMMENT') || undefined];
            } else if (block.type === 'macro_repeat') {
                // Repeat: ["REPEAT", count, [steps]]
                const count = parseInt(block.getFieldValue('COUNT'));
                const nestedSteps = this.blocklyToMacroStepsFromBlock(block);
                step = [["REPEAT", count, nestedSteps], parseInt(block.getFieldValue('DELAY_MS') || '0'), block.getFieldValue('COMMENT') || undefined];
            } else if (block.type === 'macro_comment') {
                step = ["COMMENT", 0, block.getFieldValue('COMMENT')];
            }
            if (step) steps.push(step);
        }
        return steps;
    },
    blocklyToMacroStepsFromBlock(block) {
        // For nested blocks (e.g., inside repeat)
        const steps = [];
        let child = block.getInputTargetBlock('DO');
        while (child) {
            let step = null;
            if (child.type === 'macro_button') {
                step = [child.getFieldValue('BUTTON'), parseInt(child.getFieldValue('DELAY_MS') || '0'), child.getFieldValue('COMMENT') || undefined];
            } else if (child.type === 'macro_stick') {
                step = [[child.getFieldValue('STICK'), child.getFieldValue('DIRECTION'), parseFloat(child.getFieldValue('MAGNITUDE'))], parseInt(child.getFieldValue('DELAY_MS') || '0'), child.getFieldValue('COMMENT') || undefined];
            } else if (child.type === 'macro_autoclicker') {
                step = [{ type: 'autoclicker', button: child.getFieldValue('BUTTON'), interval: parseInt(child.getFieldValue('INTERVAL')), duration: parseInt(child.getFieldValue('DURATION') || '0') }, parseInt(child.getFieldValue('DELAY_MS') || '0'), child.getFieldValue('COMMENT') || undefined];
            } else if (child.type === 'macro_repeat') {
                const count = parseInt(child.getFieldValue('COUNT'));
                const nestedSteps = this.blocklyToMacroStepsFromBlock(child);
                step = [["REPEAT", count, nestedSteps], parseInt(child.getFieldValue('DELAY_MS') || '0'), child.getFieldValue('COMMENT') || undefined];
            } else if (child.type === 'macro_comment') {
                step = ["COMMENT", 0, child.getFieldValue('COMMENT')];
            }
            if (step) steps.push(step);
            child = child.getNextBlock();
        }
        return steps;
    },
    macroStepsToBlockly(steps) {
        // Clear workspace and add blocks for each step
        this.workspace.clear();
        let prevBlock = null;
        for (const step of steps) {
            let block = null;
            // Button step: [button, delay, comment?]
            if (typeof step[0] === 'string' && step[0] !== 'COMMENT') {
                block = this.workspace.newBlock('macro_button');
                block.setFieldValue(step[0], 'BUTTON');
                block.setFieldValue(String(step[1] || 0), 'DELAY_MS');
                if (step[2]) block.setFieldValue(step[2], 'COMMENT');
            }
            // Stick step: [[stick, direction, magnitude], delay, comment?]
            else if (Array.isArray(step[0]) && typeof step[0][0] === 'string' && step[0][0].endsWith('_STICK')) {
                block = this.workspace.newBlock('macro_stick');
                block.setFieldValue(step[0][0], 'STICK');
                block.setFieldValue(step[0][1], 'DIRECTION');
                block.setFieldValue(String(step[0][2]), 'MAGNITUDE');
                block.setFieldValue(String(step[1] || 0), 'DELAY_MS');
                if (step[2]) block.setFieldValue(step[2], 'COMMENT');
            }
            // Autoclicker step: [{type: 'autoclicker', ...}, delay, comment?]
            else if (typeof step[0] === 'object' && step[0].type === 'autoclicker') {
                block = this.workspace.newBlock('macro_autoclicker');
                block.setFieldValue(step[0].button, 'BUTTON');
                block.setFieldValue(String(step[0].interval), 'INTERVAL');
                block.setFieldValue(String(step[0].duration || 0), 'DURATION');
                block.setFieldValue(String(step[1] || 0), 'DELAY_MS');
                if (step[2]) block.setFieldValue(step[2], 'COMMENT');
            }
            // Repeat step: [["REPEAT", count, [steps]], delay, comment?]
            else if (Array.isArray(step[0]) && step[0][0] === 'REPEAT') {
                block = this.workspace.newBlock('macro_repeat');
                block.setFieldValue(String(step[0][1]), 'COUNT');
                block.setFieldValue(String(step[1] || 0), 'DELAY_MS');
                if (step[2]) block.setFieldValue(step[2], 'COMMENT');
                // Recursively add nested steps
                const nestedSteps = step[0][2];
                const nestedBlocks = [];
                for (const nestedStep of nestedSteps) {
                    const nestedBlock = this.createBlockFromStep(nestedStep);
                    if (nestedBlock) nestedBlocks.push(nestedBlock);
                }
                // Chain nested blocks
                for (let i = 0; i < nestedBlocks.length; i++) {
                    if (i > 0) nestedBlocks[i - 1].nextConnection.connect(nestedBlocks[i].previousConnection);
                }
                if (nestedBlocks.length > 0) {
                    block.getInput('DO').connection.connect(nestedBlocks[0].previousConnection);
                }
            }
            // Comment step: ["COMMENT", 0, comment]
            else if (step[0] === 'COMMENT') {
                block = this.workspace.newBlock('macro_comment');
                block.setFieldValue(step[2] || '', 'COMMENT');
            }
            if (block) {
                block.initSvg && block.initSvg();
                block.render && block.render();
                if (prevBlock) {
                    prevBlock.nextConnection.connect(block.previousConnection);
                } else {
                    block.previousConnection && block.previousConnection.disconnect();
                }
                prevBlock = block;
            }
        }
    },
    createBlockFromStep(step) {
        let block = null;
        if (typeof step[0] === 'string' && step[0] !== 'COMMENT') {
            block = this.workspace.newBlock('macro_button');
            block.setFieldValue(step[0], 'BUTTON');
            block.setFieldValue(String(step[1] || 0), 'DELAY_MS');
            if (step[2]) block.setFieldValue(step[2], 'COMMENT');
        } else if (Array.isArray(step[0]) && typeof step[0][0] === 'string' && step[0][0].endsWith('_STICK')) {
            block = this.workspace.newBlock('macro_stick');
            block.setFieldValue(step[0][0], 'STICK');
            block.setFieldValue(step[0][1], 'DIRECTION');
            block.setFieldValue(String(step[0][2]), 'MAGNITUDE');
            block.setFieldValue(String(step[1] || 0), 'DELAY_MS');
            if (step[2]) block.setFieldValue(step[2], 'COMMENT');
        } else if (typeof step[0] === 'object' && step[0].type === 'autoclicker') {
            block = this.workspace.newBlock('macro_autoclicker');
            block.setFieldValue(step[0].button, 'BUTTON');
            block.setFieldValue(String(step[0].interval), 'INTERVAL');
            block.setFieldValue(String(step[0].duration || 0), 'DURATION');
            block.setFieldValue(String(step[1] || 0), 'DELAY_MS');
            if (step[2]) block.setFieldValue(step[2], 'COMMENT');
        } else if (Array.isArray(step[0]) && step[0][0] === 'REPEAT') {
            block = this.workspace.newBlock('macro_repeat');
            block.setFieldValue(String(step[0][1]), 'COUNT');
            block.setFieldValue(String(step[1] || 0), 'DELAY_MS');
            if (step[2]) block.setFieldValue(step[2], 'COMMENT');
            // Recursively add nested steps
            const nestedSteps = step[0][2];
            const nestedBlocks = [];
            for (const nestedStep of nestedSteps) {
                const nestedBlock = this.createBlockFromStep(nestedStep);
                if (nestedBlock) nestedBlocks.push(nestedBlock);
            }
            for (let i = 0; i < nestedBlocks.length; i++) {
                if (i > 0) nestedBlocks[i - 1].nextConnection.connect(nestedBlocks[i].previousConnection);
            }
            if (nestedBlocks.length > 0) {
                block.getInput('DO').connection.connect(nestedBlocks[0].previousConnection);
            }
        } else if (step[0] === 'COMMENT') {
            block = this.workspace.newBlock('macro_comment');
            block.setFieldValue(step[2] || '', 'COMMENT');
        }
        if (block) {
            block.initSvg && block.initSvg();
            block.render && block.render();
        }
        return block;
    },
    moveBlockUp() {
        // Move selected block up in the workspace
        const block = this.workspace.getSelected();
        if (!block) return;
        const prev = block.getPreviousBlock();
        if (prev) {
            block.moveBefore(prev);
        }
    },
    moveBlockDown() {
        // Move selected block down in the workspace
        const block = this.workspace.getSelected();
        if (!block) return;
        const next = block.getNextBlock();
        if (next) {
            next.moveBefore(block);
        }
    },
    clearMacroEditor() {
        this.workspace.clear();
    },
    editEndOfLoopMacro() {
        if (window.endOfLoopModal) {
            window.endOfLoopModal.open();
        }
    },
};

window.MacroEditor = MacroEditor; 