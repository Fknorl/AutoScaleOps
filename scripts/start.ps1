# AutoScaleOps - Start Script
# Usage: .\scripts\start.ps1

Write-Host ""
Write-Host "AutoScaleOps - Starting System" -ForegroundColor Cyan
Write-Host ""

# Read Instance ID
$instanceFile = "$env:USERPROFILE\.autoscaleops\instance.json"

if (Test-Path $instanceFile) {
    $instanceData = Get-Content $instanceFile | ConvertFrom-Json
    $INSTANCE_ID  = $instanceData.instance_id
    $NAMESPACE    = $instanceData.namespace
    $PROFILE      = "autoscaleops-$INSTANCE_ID"
} else {
    Write-Host "HATA: Instance bulunamadi. Lutfen once setup.ps1 calistirin." -ForegroundColor Red
    exit 1
}

Write-Host "  Instance   : $INSTANCE_ID" -ForegroundColor White
Write-Host "  Namespace  : $NAMESPACE"   -ForegroundColor White
Write-Host ""

# Step 1: Minikube
Write-Host "  [1/6] Minikube kontrol ediliyor..." -ForegroundColor Cyan
$minikubeStatus = minikube status -p $PROFILE --format='{{.Host}}' 2>$null
if ($minikubeStatus -eq "Running") {
    Write-Host "  OK: Minikube zaten calisiyor" -ForegroundColor Green
} else {
    Write-Host "  Minikube baslatiliyor (birkac dakika surebilir)..." -ForegroundColor Yellow
    minikube start -p $PROFILE
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  HATA: Minikube baslatilamadi!" -ForegroundColor Red
        exit 1
    }
    Write-Host "  OK: Minikube baslatildi" -ForegroundColor Green
}

# Step 2: kubectl context
Write-Host ""
Write-Host "  [2/6] kubectl context ayarlaniyor..." -ForegroundColor Cyan
kubectl config use-context $PROFILE 2>$null
Write-Host "  OK: Context: $PROFILE" -ForegroundColor Green

# Step 3: Pod durumu
Write-Host ""
Write-Host "  [3/6] Pod durumu:" -ForegroundColor Cyan
kubectl get pods -n $NAMESPACE 2>$null
Write-Host ""

# Step 4: ServiceMonitor - Prometheus scrape config
Write-Host "  [4/6] Prometheus ServiceMonitor kontrol ediliyor..." -ForegroundColor Cyan

$existingSM = kubectl get servicemonitor autoscaleops-app -n monitoring 2>$null
if ($existingSM) {
    Write-Host "  OK: ServiceMonitor zaten var" -ForegroundColor Green
} else {
    Write-Host "  ServiceMonitor olusturuluyor..." -ForegroundColor Yellow

    $smYaml = @"
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: autoscaleops-app
  namespace: monitoring
  labels:
    release: prometheus
spec:
  namespaceSelector:
    matchNames:
      - $NAMESPACE
  selector:
    matchLabels:
      app: autoscaleops-app
  endpoints:
    - targetPort: 8080
      path: /metrics
      interval: 15s
"@

    $smYaml | kubectl apply -f -

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK: ServiceMonitor olusturuldu" -ForegroundColor Green
    } else {
        Write-Host "  UYARI: ServiceMonitor olusturulamadi (trafik gorunmeyebilir)" -ForegroundColor Yellow
    }
}

# Step 4: Prometheus Scrape Config
Write-Host "  [4/6] Prometheus scrape config kontrol ediliyor..." -ForegroundColor Cyan

$configYaml = "- job_name: 'autoscaleops-app'
  kubernetes_sd_configs:
    - role: pod
      namespaces:
        names:
          - $NAMESPACE
  relabel_configs:
    - source_labels: [__meta_kubernetes_pod_label_app]
      action: keep
      regex: autoscaleops-app
    - source_labels: [__meta_kubernetes_pod_ip, __meta_kubernetes_pod_container_port_number]
      separator: ':'
      target_label: __address__
    - target_label: __metrics_path__
      replacement: /metrics"

$secretYaml = @"
apiVersion: v1
kind: Secret
metadata:
  name: autoscaleops-scrape-config
  namespace: monitoring
stringData:
  config.yaml: |
$(($configYaml -split "`n" | ForEach-Object { "    " + $_ }) -join "`n")
"@

$secretYaml | Out-File -FilePath "$env:TEMP\scrape-secret.yaml" -Encoding utf8
kubectl apply -f "$env:TEMP\scrape-secret.yaml" 2>$null
$patchJson = '{"spec":{"additionalScrapeConfigs":{"name":"autoscaleops-scrape-config","key":"config.yaml"}}}'
kubectl patch prometheus prometheus-kube-prometheus-prometheus -n monitoring --type=merge -p $patchJson 2>$null
Write-Host "  OK: Scrape config hazir" -ForegroundColor Green

# Step 5: Port Forwarding
Write-Host ""
Write-Host "  [5/6] Port yonlendirmeleri baslatiliyor..." -ForegroundColor Cyan

Get-Process -Name "kubectl" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

Start-Process -FilePath "kubectl" `
    -ArgumentList "port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090 -n monitoring" `
    -WindowStyle Hidden
Start-Sleep -Seconds 1
Write-Host "  OK: Prometheus  -> http://localhost:9090" -ForegroundColor Green

Start-Process -FilePath "kubectl" `
    -ArgumentList "port-forward svc/prometheus-pushgateway 9091:9091 -n monitoring" `
    -WindowStyle Hidden
Start-Sleep -Seconds 1
Write-Host "  OK: Pushgateway -> http://localhost:9091" -ForegroundColor Green

Start-Process -FilePath "kubectl" `
    -ArgumentList "port-forward svc/autoscaleops-app-service 8080:8080 -n $NAMESPACE" `
    -WindowStyle Hidden
Start-Sleep -Seconds 1
Write-Host "  OK: Application -> http://localhost:8080" -ForegroundColor Green

# Step 6: Dashboard
Write-Host ""
Write-Host "  [6/6] Dashboard baslatiliyor..." -ForegroundColor Cyan
$dashboardPath = Join-Path (Split-Path $PSScriptRoot) "dashboard\dashboard.py"
$dashboardReady = $false
if (-not (Test-Path $dashboardPath)) {
    Write-Host "  UYARI: dashboard.py bulunamadi: $dashboardPath" -ForegroundColor Yellow
} else {
    # Streamlit yuklu mu kontrol et
    $streamlitCheck = python -m streamlit --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  HATA: streamlit yuklu degil. Calistir: pip install -r dashboard\requirements.txt" -ForegroundColor Red
    } else {
        # Port 8501'de eski process varsa temizle
        $oldProcs = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
        if ($oldProcs) {
            $oldProcs | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
            Start-Sleep -Seconds 1
        }

        # Start-Job ile baslat (output takip edilebilir)
        $streamlitJob = Start-Job -ScriptBlock {
            param($path)
            python -m streamlit run $path --server.port 8501 --server.headless true
        } -ArgumentList $dashboardPath

        # Port 8501 hazir olana kadar maks 30 saniye bekle
        Write-Host "  Streamlit bekleniyor (maks 30s)..." -ForegroundColor Yellow
        for ($i = 1; $i -le 30; $i++) {
            Start-Sleep -Seconds 1
            $tcpTest = Test-NetConnection -ComputerName 127.0.0.1 -Port 8501 `
                -WarningAction SilentlyContinue -InformationLevel Quiet 2>$null
            if ($tcpTest) { $dashboardReady = $true; break }
        }

        if ($dashboardReady) {
            Write-Host "  OK: Dashboard -> http://localhost:8501" -ForegroundColor Green
        } else {
            Write-Host "  HATA: Dashboard 30 saniyede baslamadi!" -ForegroundColor Red
            Write-Host "  Streamlit ciktisi:" -ForegroundColor DarkGray
            Receive-Job $streamlitJob -ErrorAction SilentlyContinue | Select-Object -First 20 | Write-Host
        }
    }
}

# Summary
Write-Host ""
Write-Host "-------------------------------------------" -ForegroundColor Green
Write-Host "  AutoScaleOps Hazir!" -ForegroundColor Green
Write-Host "-------------------------------------------" -ForegroundColor Green
Write-Host ""
Write-Host "  Dashboard   -> http://localhost:8501" -ForegroundColor Cyan
Write-Host "  Application -> http://localhost:8080" -ForegroundColor Cyan
Write-Host "  Prometheus  -> http://localhost:9090" -ForegroundColor Cyan
Write-Host "  Pushgateway -> http://localhost:9091" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Durdurmak icin: .\scripts\stop.ps1" -ForegroundColor DarkGray
Write-Host ""
Start-Sleep -Seconds 1
if ($dashboardReady) {
    Start-Process "http://localhost:8501"
}