# API

Swagger: `http://127.0.0.1:8000/docs`

Main endpoints:

```text
POST /api/v1/readings
GET  /api/v1/users/{user_id}/latest
GET  /api/v1/users/{user_id}/history?minutes=30&limit=300
GET  /api/v1/users/{user_id}/health-status
GET  /api/v1/users/{user_id}/baseline
GET  /api/v1/users/{user_id}/alerts
POST /api/v1/users/{user_id}/reset-baseline
```

The reading payload contains acceleration and gyroscope values and does not contain GSR.
