$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Continue"

Clear-Host
Write-Host ""
Write-Host "  =============================================" -ForegroundColor Cyan
Write-Host "         AutoScaleOps  -  Baslatma Sihirbazi  " -ForegroundColor Cyan
Write-Host "  =============================================" -ForegroundColor Cyan
Write-Host ""

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$TOTAL_STEPS = 9

# ─────────────────────────────────────────────────────────────────────────────
# WINGET VARLIK KONTROLU  (winget yoksa sessizce atla)
# ─────────────────────────────────────────────────────────────────────────────
function EnsureWinget {
    if (IsInstalled "winget") { return $true }
    Write-Host ""
    Write-Host "  [!] winget bulunamadi." -ForegroundColor Yellow
    Write-Host "      Windows 10 1809+ veya Windows 11 gerektirir." -ForegroundColor Gray
    Write-Host "      winget.microsoft.com adresinden yukleyebilirsiniz." -ForegroundColor Gray
    return $false
}

# ─────────────────────────────────────────────────────────────────────────────
# YARDIMCI FONKSIYONLAR
# ─────────────────────────────────────────────────────────────────────────────
function Step($n, $msg) {
    Write-Host ""
    Write-Host "  [$n/$TOTAL_STEPS] $msg" -ForegroundColor Yellow
}
function OK($msg)   { Write-Host "        OK  $msg" -ForegroundColor Green }
function WARN($msg) { Write-Host "        !!  $msg" -ForegroundColor Yellow }
function ERR($msg)  { Write-Host "      HATA  $msg" -ForegroundColor Red }
function INFO($msg) { Write-Host "        ->  $msg" -ForegroundColor DarkGray }

function IsInstalled($cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

function WingetInstall($pkgId, $pkgName) {
    if (-not (IsInstalled "winget")) {
        WARN "$pkgName icin winget bulunamadi. Elle kurulum: winget.microsoft.com"
        return $false
    }
    INFO "Yukleniyor: $pkgName ..."
    $result = winget install $pkgId --silent --accept-package-agreements --accept-source-agreements 2>&1
    if ($LASTEXITCODE -eq 0 -or ($result -match "installed|already installed")) {
        OK "$pkgName kuruldu."
        return $true
    }
    WARN "$pkgName yuklenemedi. Elle kurun: winget install $pkgId"
    return $false
}

function RefreshPath {
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH","User")
}

# ─────────────────────────────────────────────────────────────────────────────
# [1/9] PYTHON
# ─────────────────────────────────────────────────────────────────────────────
Step 1 "Python kontrol ediliyor..."

if (-not (IsInstalled "python")) {
    WARN "Python bulunamadi — winget ile otomatik yukleniyor..."

    if (-not (EnsureWinget)) {
        ERR "Python bulunamadi ve winget de yok!"
        ERR "Lutfen python.org/downloads adresinden Python 3.11+ kurun."
        ERR "Kurulumda 'Add Python to PATH' secenegini mutlaka isaretleyin!"
        Read-Host "`n  Kurup tekrar calistirin — Enter ile cik"
        exit 1
    }

    INFO "Python 3.11 yukleniyor (1-3 dk)..."
    winget install Python.Python.3.11 `
        --silent `
        --accept-package-agreements `
        --accept-source-agreements `
        --override "/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1" 2>&1 |
        Where-Object { $_ -match "." } | ForEach-Object { INFO $_ }

    RefreshPath

    # winget PATH'i aninda guncellemiyor olabilir — py launcher'i dene
    if (-not (IsInstalled "python")) {
        if (IsInstalled "py") {
            # py launcher uzerinden calis
            Set-Alias python (py -3 -c "import sys; print(sys.executable)" 2>&1)
        }
        RefreshPath
    }

    if (-not (IsInstalled "python")) {
        ERR "Python yuklenemedi veya PATH'e eklenemedi."
        ERR "Lutfen python.org/downloads adresinden elle kurun."
        ERR "'Add Python to PATH' secenegini isaretleyin, sonra tekrar calistirin."
        Read-Host "`n  Enter ile cik"
        exit 1
    }

    OK "Python otomatik kuruldu."
}

$pyver = python --version 2>&1
OK "Python mevcut: $pyver"

INFO "Gerekli paketler yukleniyor..."
python -m pip install --upgrade pip --quiet 2>&1 | Out-Null
python -m pip install PyQt6 PyQt6-Qt6 PyQt6-sip matplotlib requests psutil `
    cryptography urllib3 pyyaml click rich jinja2 --quiet 2>&1 |
    Where-Object { $_ -notmatch "already|WARNING|Ignoring" } |
    ForEach-Object { INFO $_ }
OK "Python paketleri hazir."

# ─────────────────────────────────────────────────────────────────────────────
# [2/9] DOCKER DESKTOP
# ─────────────────────────────────────────────────────────────────────────────
Step 2 "Docker Desktop kontrol ediliyor..."

$dockerRunning = $false
$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -eq 0) {
    OK "Docker calisyor."
    $dockerRunning = $true
} else {
    $dockerExePaths = @(
        "C:\Program Files\Docker\Docker\Docker Desktop.exe",
        "$env:LOCALAPPDATA\Docker\Docker Desktop.exe"
    )
    $dockerExe = $dockerExePaths | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($dockerExe) {
        WARN "Docker kurulu ama kapali — baslatiliyor..."
        Start-Process $dockerExe
    } else {
        WARN "Docker bulunamadi — yukleniyor (2-5 dk)..."
        WingetInstall "Docker.DockerDesktop" "Docker Desktop" | Out-Null
        RefreshPath
        $dockerExe = $dockerExePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($dockerExe) { Start-Process $dockerExe }
    }

    INFO "Docker hazirlanana kadar bekleniyor (maks 90sn)..."
    $waited = 0
    while ($waited -lt 90) {
        Start-Sleep 5; $waited += 5
        if ((docker info 2>&1) -and $LASTEXITCODE -eq 0) {
            OK "Docker hazir."; $dockerRunning = $true; break
        }
        INFO "Bekleniyor: ${waited}s..."
    }

    if (-not $dockerRunning) {
        ERR "Docker 90 saniyede baslamadi."
        ERR "Docker Desktop'i elle acin, hazir olunca tekrar calistirin."
        Read-Host "Enter ile cik"; exit 1
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# [3/9] MINIKUBE
# ─────────────────────────────────────────────────────────────────────────────
Step 3 "Minikube kontrol ediliyor..."

if (-not (IsInstalled "minikube")) {
    WARN "Minikube bulunamadi — yukleniyor..."
    WingetInstall "Kubernetes.minikube" "Minikube" | Out-Null
    RefreshPath
}
if (IsInstalled "minikube") { OK "Minikube hazir." }
else { WARN "Minikube PATH'te gorunmuyor — terminali yeniden ac." }

# ─────────────────────────────────────────────────────────────────────────────
# [4/9] KUBECTL + HELM
# ─────────────────────────────────────────────────────────────────────────────
Step 4 "kubectl ve Helm kontrol ediliyor..."

if (-not (IsInstalled "kubectl")) {
    WARN "kubectl bulunamadi — yukleniyor..."
    WingetInstall "Kubernetes.kubectl" "kubectl" | Out-Null
    RefreshPath
}
OK "kubectl: $(kubectl version --client --short 2>&1 | Select-Object -First 1)"

if (-not (IsInstalled "helm")) {
    WARN "Helm bulunamadi — yukleniyor..."
    WingetInstall "Helm.Helm" "Helm" | Out-Null
    RefreshPath
}
OK "Helm: $(helm version --short 2>&1)"

# ─────────────────────────────────────────────────────────────────────────────
# [5/9] KUBERNETES CLUSTER
# ─────────────────────────────────────────────────────────────────────────────
Step 5 "Kubernetes cluster hazirlaniyor..."

$PROFILE_NAME = $null
try {
    $jsonRaw  = minikube profile list -o json 2>$null
    $profiles = $jsonRaw | ConvertFrom-Json
    $PROFILE_NAME = ($profiles.valid |
        Where-Object { $_.Name -like "autoscaleops*" } |
        Select-Object -First 1).Name
} catch {}

if (-not $PROFILE_NAME) { $PROFILE_NAME = "autoscaleops" }
INFO "Profil: $PROFILE_NAME"

$status = minikube status -p $PROFILE_NAME 2>&1
if ($status -match "Running") {
    OK "Cluster zaten calisiyor."
} else {
    INFO "Cluster baslatiliyor (1-3 dk)..."
    minikube start -p $PROFILE_NAME --driver=docker --cpus=4 --memory=6144 2>&1 |
        Select-Object -Last 3
    if ($LASTEXITCODE -ne 0) {
        ERR "Cluster baslanamadi. Docker acik mi?"
        Read-Host "Enter ile cik"; exit 1
    }
    OK "Cluster hazir."
}

kubectl create namespace $PROFILE_NAME --dry-run=client -o yaml 2>$null |
    kubectl apply -f - 2>&1 | Out-Null
OK "Namespace hazir: $PROFILE_NAME"

# ─────────────────────────────────────────────────────────────────────────────
# [6/9] PROMETHEUS + PUSHGATEWAY
# ─────────────────────────────────────────────────────────────────────────────
Step 6 "Prometheus + Pushgateway kontrol ediliyor..."

$promExists = helm status prometheus -n monitoring 2>&1
if ($LASTEXITCODE -eq 0) {
    OK "Prometheus zaten kurulu."
} else {
    INFO "Prometheus kuruluyor..."
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>&1 | Out-Null
    helm repo update 2>&1 | Out-Null
    helm upgrade --install prometheus prometheus-community/kube-prometheus-stack `
        --namespace monitoring --create-namespace `
        --set grafana.enabled=false `
        --set alertmanager.enabled=false `
        --wait --timeout 5m 2>&1 | Select-Object -Last 3
    if ($LASTEXITCODE -eq 0) { OK "Prometheus kuruldu." }
    else { WARN "Prometheus kurulamadi — dashboard metrikleri calismayabilir." }
}

$pgExists = helm status pushgateway -n monitoring 2>&1
if ($LASTEXITCODE -eq 0) {
    OK "Pushgateway zaten kurulu."
} else {
    INFO "Pushgateway kuruluyor..."
    helm upgrade --install pushgateway prometheus-community/prometheus-pushgateway `
        --namespace monitoring --create-namespace `
        --wait --timeout 2m 2>&1 | Select-Object -Last 2
    if ($LASTEXITCODE -eq 0) { OK "Pushgateway kuruldu." }
    else { WARN "Pushgateway kurulamadi." }
}

# ─────────────────────────────────────────────────────────────────────────────
# [7/9] KEDA
# ─────────────────────────────────────────────────────────────────────────────
Step 7 "KEDA kontrol ediliyor..."

$kedaExists = kubectl get namespace keda 2>&1
if ($LASTEXITCODE -eq 0) {
    OK "KEDA zaten kurulu."
} else {
    INFO "KEDA kuruluyor..."
    helm repo add kedacore https://kedacore.github.io/charts 2>&1 | Out-Null
    helm repo update 2>&1 | Out-Null
    helm upgrade --install keda kedacore/keda `
        --namespace keda --create-namespace `
        --wait --timeout 3m 2>&1 | Select-Object -Last 2
    if ($LASTEXITCODE -eq 0) { OK "KEDA kuruldu." }
    else { WARN "KEDA kurulamadi — otomatik olcekleme calismayabilir." }
}

# ─────────────────────────────────────────────────────────────────────────────
# [8/9] AUTOSCALEOPS CLI
# ─────────────────────────────────────────────────────────────────────────────
Step 8 "AutoScaleOps CLI kontrol ediliyor..."

Set-Location $SCRIPT_DIR
$cliCheck = autoscaleops --version 2>&1
if ($LASTEXITCODE -eq 0) {
    OK "AutoScaleOps CLI hazir: $cliCheck"
} else {
    INFO "AutoScaleOps CLI yukleniyor..."
    python -m pip install -e . --quiet 2>&1 | Out-Null
    $cliCheck = autoscaleops --version 2>&1
    if ($LASTEXITCODE -eq 0) { OK "CLI yuklendi: $cliCheck" }
    else { WARN "CLI yuklenemedi — manuel: pip install -e ." }
}

# autoscaleops doctor ile ozet kontrol
Write-Host ""
autoscaleops doctor 2>&1

# ─────────────────────────────────────────────────────────────────────────────
# [9/9] UYGULAMAYI BASLAT
# ─────────────────────────────────────────────────────────────────────────────
Step 9 "Uygulama baslatiliyor..."

Write-Host ""
Write-Host "  =============================================" -ForegroundColor Cyan
Write-Host "   Tum sistemler hazir! Uygulama aciliyor...  " -ForegroundColor Green
Write-Host "  =============================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $SCRIPT_DIR
python autoscaleops_app.py

# Cikis
Write-Host ""
if ($LASTEXITCODE -ne 0) {
    ERR "Uygulama hatayla kapandi. Yukari kaydiriniz."
    Read-Host "Enter ile cik"
} else {
    Write-Host "  Uygulama kapatildi. Iyi gunler!" -ForegroundColor Cyan
    Start-Sleep 2
}
