const express = require('express');
const { runInNewContext } = require('vm');

const app = express();
app.use(express.json());

app.post('/exec', async (req, res) => {
    const code = req.body.code;
    let output = '';

    let codeStr = code;
    // Replace modern ES Module 'export default' so it doesn't syntax error in VM
    codeStr = codeStr.replace(/export\s+default\s+function/g, 'module.exports = async function');
    codeStr = codeStr.replace(/export\s+default/g, 'module.exports =');

    const sandbox = {
        console: {
            log: (...args) => { output += args.join(' ') + '\n'; },
            error: (...args) => { output += args.join(' ') + '\n'; }
        },
        module: { exports: {} },
        require: require
    };
    sandbox.exports = sandbox.module.exports;

    try {
        let retValue;
        
        try {
            retValue = await runInNewContext(codeStr, sandbox);
        } catch (rawErr) {
            // Handle Syntax errors like top-level `return` or `await`
            const wrappedCode = `(async function() {\n${codeStr}\n})()`;
            retValue = await runInNewContext(wrappedCode, sandbox);
        }

        // Check if the user exported a handler instead of returning directly
        if (typeof sandbox.module.exports === 'function') {
            retValue = await sandbox.module.exports();
        } else if (sandbox.module.exports && typeof sandbox.module.exports.handler === 'function') {
            retValue = await sandbox.module.exports.handler();
        } else if (sandbox.module.exports && typeof sandbox.module.exports.default === 'function') {
            retValue = await sandbox.module.exports.default();
        } else {
            // If no explicit exports, but they defined a global function in the sandbox, call it automatically!
            const keys = Object.keys(sandbox).filter(k => !['console', 'module', 'exports', 'require'].includes(k));
            for (const key of keys) {
                if (typeof sandbox[key] === 'function') {
                    // Call the first custom function we find
                    const funcRes = await sandbox[key]();
                    if (funcRes !== undefined) {
                        retValue = funcRes;
                        break;
                    }
                }
            }
        }

        if (retValue !== undefined && retValue !== null) {
            const strVal = typeof retValue === 'object' ? JSON.stringify(retValue, null, 2) : String(retValue);
            output += (output ? '\n' : '') + strVal;
        }
        res.json({ result: output.trim() });
    } catch (e) {
        res.json({ result: e.toString() });
    }
});

app.listen(5000, () => {
    console.log('Node runtime listening on 5000');
});
