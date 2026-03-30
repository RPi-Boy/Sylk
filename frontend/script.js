async function submitTask() {
    const code = document.getElementById('task-code').value;
    const response = await fetch('http://localhost:8000/tasks', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            code: code,
            language: 'python'
        }),
    });
    const result = await response.json();
    console.log('Task submitted:', result);
    alert('Task Submitted! ID: ' + result.task_id);
}

async function refreshTelemetry() {
    // TODO: Implement GET to /telemetry
    console.log('Refreshing telemetry...');
}

// Refresh every 5s
setInterval(refreshTelemetry, 5000);
