# Sylk API Specification

## Endpoints

### POST `/tasks`
Submit a new code execution task.
- Request Body: `TaskIn`
- Response: `TaskOut`

### GET `/tasks/{task_id}`
Retrieve task status and results.
- Response: `TaskOut`

### POST `/register`
Node registration.
- Request Body: `NodeRegister`

### POST `/heartbeat`
Node health and telemetry.
- Request Body: `NodeHeartbeat`

### GET `/telemetry`
SSE stream for dashboard updates.
