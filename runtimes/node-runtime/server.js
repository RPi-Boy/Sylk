const express = require('express');
const { runInNewContext } = require('vm');

const app = express();
app.use(express.json());

app.post('/exec', (req, res) => {
    const code = req.body.code;
    let output = '';

    const sandbox = {
        console: {
            log: (...args) => { output += args.join(' ') + '\n'; },
            error: (...args) => { output += args.join(' ') + '\n'; }
        }
    };

    try {
        runInNewContext(code, sandbox);
        res.json({ result: output.trim() });
    } catch (e) {
        res.json({ result: e.toString() });
    }
});

app.listen(5000, () => {
    console.log('Node runtime listening on 5000');
});
