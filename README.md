# 🚀 AutoScaleOps

> **Cloud-free, self-hosted auto-scaling platform for your local machine.**  
> Run Kubernetes on your own hardware — zero cloud costs, full control.

---

## 🎯 What Is AutoScaleOps?

AutoScaleOps is an **AI-powered predictive auto-scaling system** that lets you:

- ✅ Run a production-grade Kubernetes cluster **on your own computer**
- ✅ Auto-scale your web app **before** traffic spikes hit (not after)
- ✅ Monitor everything via a **professional dashboard**
- ✅ Pay **zero cloud fees** — only your electricity bill

**Think of it as your own personal AWS, running on your laptop.**

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Your Computer                            │
│                                                              │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐   │
│  │  Flask App  │    │ AI Predictor │    │   Dashboard   │   │
│  │  (port 8080)│    │ (ARIMA Model)│    │  (port 8501)  │   │
│  └──────┬──────┘    └──────┬───────┘    └───────────────┘   │
│         │                  │                                  │
│  ┌──────▼──────────────────▼───────────────────────────┐     │
│  │              Kubernetes (Minikube)                   │     │
│  │   ┌─────────┐  ┌────────────┐  ┌────────────────┐  │     │
│  │   │  KEDA   │  │ Prometheus │  │  Pushgateway   │  │     │
│  │   └─────────┘  └────────────┘  └────────────────┘  │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐     │
│  │   Tunnel (ngrok/Cloudflare) → Internet Access       │     │
│  └─────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

---

## ⚡ Quick Start

### Prerequisites

| Tool | Version | Download |
|------|---------|----------|
| Docker Desktop | Latest | [docker.com](https://www.docker.com/products/docker-desktop) |
| Minikube | v1.32+ | [minikube.sigs.k8s.io](https://minikube.sigs.k8s.io/docs/start/) |
| kubectl | Latest | [kubernetes.io](https://kubernetes.io/docs/tasks/tools/) |
| Helm | v3.13+ | [helm.sh](https://helm.sh/docs/intro/install/) |
| Python | 3.11+ | [python.org](https://www.python.org/downloads/) |

### Installation

```powershell
# 1. Clone the repository
git clone https://github.com/yourname/AutoScaleOps-Product.git
cd AutoScaleOps-Product

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Run the installer
python installer/install.py

# 4. Start the system
.\scripts\start.ps1
```

### Access Points

| Service | URL |
|---------|-----|
| 🖥️ Dashboard | http://localhost:8501 |
| 🌐 Application | http://localhost:8080 |
| 📊 Prometheus | http://localhost:9090 |
| 📤 Pushgateway | http://localhost:9091 |

---

## 📁 Project Structure

```
AutoScaleOps-Product/
├── app/                    # Flask web application
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── ai-model/               # AI prediction engine (Auto-ARIMA)
│   ├── predictor.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── dashboard/              # Streamlit monitoring dashboard
│   ├── dashboard.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── charts/autoscaleops/    # Helm chart for Kubernetes deployment
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│
├── core/                   # Core system modules
│   ├── instance_manager.py  # Unique instance ID
│   ├── config_manager.py    # Encrypted config
│   ├── security.py          # Secret management
│   ├── kubernetes_manager.py # kubectl wrapper
│   ├── tunnel_manager.py    # ngrok/Cloudflare
│   └── logger.py            # Centralized logging
│
├── installer/              # Installation system
│   └── install.py
│
├── scripts/                # Start/Stop scripts
│   ├── start.ps1
│   └── stop.ps1
│
├── docs/                   # Documentation
├── tests/                  # Unit tests
└── requirements.txt
```

---

## 🔧 Usage

### Start the System
```powershell
.\scripts\start.ps1
```

### Stop the System
```powershell
.\scripts\stop.ps1           # Stops services, keeps Minikube running
.\scripts\stop.ps1 -StopMinikube  # Also stops Minikube cluster
```

### Run Load Test
Open the Dashboard → **🔥 Yük Testi** tab → Set parameters → Click **Başlat**

---

## 🔒 Security

- API keys stored in **Windows Credential Manager**
- Config encrypted with **AES-256**
- Machine-specific encryption keys
- Non-root Docker containers
- Kubernetes NetworkPolicy isolation

See [docs/SECURITY.md](docs/SECURITY.md) for details.

---

## 📊 How It Works

1. **Flask App** serves traffic and exposes Prometheus metrics
2. **Prometheus** scrapes metrics every 15 seconds
3. **AI Predictor** (Auto-ARIMA) predicts traffic 5 minutes ahead
4. **KEDA** scales pods based on AI prediction
5. **Dashboard** shows everything in real-time

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.