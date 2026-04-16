# 📥 Installation Guide

## Step 1: Install Prerequisites

### Docker Desktop
```powershell
# Download from: https://www.docker.com/products/docker-desktop
# After install, verify:
docker --version
# Expected: Docker version 24.x.x
```

### Minikube
```powershell
# Download and install:
winget install minikube
# Or from: https://minikube.sigs.k8s.io/docs/start/

# Verify:
minikube version
```

### kubectl
```powershell
winget install kubectl
kubectl version --client
```

### Helm
```powershell
winget install helm
helm version
```

### Python 3.11+
```powershell
# Download from: https://www.python.org/downloads/
python --version
# Expected: Python 3.11.x
```

---

## Step 2: Clone & Install Dependencies

```powershell
git clone https://github.com/yourname/AutoScaleOps-Product.git
cd AutoScaleOps-Product
pip install -r requirements.txt
```

---

## Step 3: Run Installer

```powershell
python installer/install.py
```

The installer will:
1. ✅ Check all prerequisites
2. ✅ Create Minikube profile: `autoscaleops-{id}`
3. ✅ Create Kubernetes namespace: `autoscaleops-{id}`
4. ✅ Install KEDA (auto-scaler)
5. ✅ Install Prometheus (monitoring)
6. ✅ Deploy AutoScaleOps app
7. ✅ Verify everything is running

**Estimated time: 10–15 minutes**

---

## Step 4: Build Docker Images

```powershell
# Switch to your Minikube Docker context
minikube -p autoscaleops-{YOUR_ID} docker-env | Invoke-Expression

# Build images
docker build -t autoscaleops-app:latest ./app
docker build -t autoscaleops-ai:latest ./ai-model
```

---

## Step 5: Start the System

```powershell
.\scripts\start.ps1
```

Then open: **http://localhost:8501**

---

## 🔧 Troubleshooting

### Minikube won't start
```powershell
# Check Docker is running first
docker ps

# Try with more resources
minikube start -p autoscaleops-{id} --driver=docker --cpus=4 --memory=8192
```

### Pods not starting
```powershell
# Check pod status
kubectl get pods -n autoscaleops-{id}

# Check pod logs
kubectl logs -n autoscaleops-{id} <pod-name>

# Describe pod for events
kubectl describe pod -n autoscaleops-{id} <pod-name>
```

### Port forward fails
```powershell
# Kill existing port forwards
Get-Process kubectl | Stop-Process -Force

# Restart
.\scripts\start.ps1
```

### Dashboard shows disconnected services
Make sure port forwards are running:
```powershell
Get-Process kubectl
```
If empty, run `.\scripts\start.ps1` again.