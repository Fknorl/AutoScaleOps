# 🏗️ Architecture

## System Overview

```
Internet User
     │
     ▼
ngrok / Cloudflare Tunnel
     │
     ▼
Flask App (port 8080) ──► Prometheus Metrics (/metrics)
     │                           │
     │                           ▼
     │                    Prometheus Server
     │                    (port 9090)
     │                           │
     │                    AI Predictor
     │                    (Auto-ARIMA)
     │                           │
     │                    Pushgateway
     │                    (port 9091)
     │                           │
     │                         KEDA
     │                    (reads prediction)
     │                           │
     ▼                           ▼
Kubernetes Pods ◄──── Scale Up/Down
```

---

## Components

### 1. Flask Application (`app/app.py`)
- Serves the web application on port 8080
- Exposes Prometheus metrics at `/metrics`
- `/health` endpoint for liveness/readiness probes
- `/hesapla` endpoint simulates CPU load

### 2. AI Predictor (`ai-model/predictor.py`)
- Fetches historical traffic from Prometheus (last 2 hours)
- Trains Auto-ARIMA model on the data
- Predicts traffic 5 minutes ahead
- Pushes prediction to Pushgateway every 60 seconds
- Includes false alarm detection (5-minute timer)

### 3. KEDA Auto-scaler
- Reads `predicted_rps_30min` metric from Prometheus
- Scales deployment when metric exceeds threshold (default: 10)
- Min replicas: 2, Max replicas: 10
- Cooldown period: 60 seconds

### 4. Dashboard (`dashboard/dashboard.py`)
- Real-time metrics visualization
- k6 load test management
- GreenOps policy configuration
- Event calendar for traffic planning
- System analysis and forecasting

### 5. Core Modules (`core/`)
| Module | Purpose |
|--------|---------|
| `instance_manager.py` | Unique 8-char instance ID per installation |
| `config_manager.py` | AES-256 encrypted configuration |
| `security.py` | Windows Credential Manager integration |
| `kubernetes_manager.py` | kubectl command wrapper |
| `tunnel_manager.py` | ngrok/Cloudflare tunnel management |
| `logger.py` | Rotating file logs + cloud logging |

---

## Instance Isolation

Each installation gets a unique ID based on:
- Hostname
- MAC address
- Timestamp

This ensures multiple users on the same network never conflict:

```
User A: namespace = autoscaleops-a3f2b1c8
User B: namespace = autoscaleops-7d9e4f21
User C: namespace = autoscaleops-b1c2d3e4
```

---

## Data Flow

```
1. Traffic arrives → Flask App
2. Flask increments http_requests_total counter
3. Prometheus scrapes /metrics every 15s
4. AI Predictor queries Prometheus for last 2h of data
5. Auto-ARIMA model predicts next 5 minutes
6. Prediction pushed to Pushgateway
7. KEDA reads prediction from Prometheus
8. KEDA scales deployment up/down
9. Dashboard shows everything in real-time
```