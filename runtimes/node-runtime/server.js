const express = require('express');
const app = express();
app.use(express.json());

app.post('/exec', (req, res) => {
    const { code } = req.body;
    try {
        const result = eval(code);
        res.json({ result: result });
    } catch (e) {
        res.status(500).json({ error: e.message });
    }
});

app.listen(5001, () => {
    console.log('Node runtime listening on 5001');
});
