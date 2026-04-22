$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Continue"

Clear-Host
Write-Host ""
Write-Host "  =============================================" -ForegroundColor Cyan
Write-Host "       AutoScaleOps  -  Baslatma Sihirbazi    " -ForegroundColor Cyan
Write-Host "  =============================================" -ForegroundColor Cyan
Write-Host ""

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $SCRIPT_DIR -or -not (Test-Path $SCRIPT_DIR)) {
    $SCRIPT_DIR = Get-Location
}
$TOTAL_STEPS = 9

# -----------------------------------------------------------------------------
# YARDIMCI FONKSIYONLAR
# -----------------------------------------------------------------------------
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

function RefreshPath {
    $machinePath = [System.Environment]::GetEnvironmentVariable("PATH", "Machine")
    $userPath    = [System.Environment]::GetEnvironmentVariable("PATH", "User")
    if ($machinePath -and $userPath) {
        $env:PATH = $machinePath + ";" + $userPath
    } elseif ($machinePath) {
        $env:PATH = $machinePath
    } elseif ($userPath) {
        $env:PATH = $userPath
    }
    # Komut cache'ini temizle
    $env:PATH = $env:PATH
}

function EnsureWinget {
    if (IsInstalled "winget") { return $true }
    Write-Host ""
    Write-Host "  [!] winget bulunamadi." -ForegroundColor Yellow
    Write-Host "      Windows 10 1809+ veya Windows 11 gerektirir." -ForegroundColor Gray
    Write-Host "      https://aka.ms/getwinget adresinden yukleyebilirsiniz." -ForegroundColor Gray
    return $false
}

function WingetInstall($pkgId, $pkgName) {
    if (-not (IsInstalled "winget")) {
        WARN "$pkgName icin winget bulunamadi."
        return $false
    }
    INFO "Yukleniyor: $pkgName ..."
    winget install $pkgId --silent --accept-package-agreements --accept-source-agreements 2>&1 | Out-Null
    # Hem 0 (basarili) hem de 0x8A15002B (zaten kurulu) kabul edilir
    if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq -1978335189) {
        OK "$pkgName hazir."
        return $true
    }
    WARN "$pkgName yuklenemedi (kod: $LASTEXITCODE). Manuel: winget install $pkgId"
    return $false
}

# -----------------------------------------------------------------------------
# [1/9] PYTHON
# -----------------------------------------------------------------------------
Step 1 "Python kontrol ediliyor..."

if (-not (IsInstalled "python")) {
    WARN "Python bulunamadi - winget ile otomatik yukleniyor..."

    if (-not (EnsureWinget)) {
        ERR "Python bulunamadi ve winget de yok!"
        ERR "Lutfen python.org/downloads adresinden Python 3.11+ kurun."
        ERR "Kurulumda 'Add Python to PATH' secenegini mutlaka isaretleyin!"
        Read-Host "`n  Kurup tekrar calistirin - Enter ile cik"
        exit 1
    }

    INFO "Python 3.11 yukleniyor (1-3 dk)..."
    winget install Python.Python.3.11 `
        --silent `
        --accept-package-agreements `
        --accept-source-agreements `
        --override "/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1" 2>&1 | Out-Null

    RefreshPath
    Start-Sleep -Seconds 3

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

INFO "Gerekli Python paketleri yukleniyor..."
python -m pip install --upgrade pip --quiet 2>&1 | Out-Null
python -m pip install PyQt6 PyQt6-Qt6 PyQt6-sip matplotlib requests psutil `
    cryptography urllib3 pyyaml click rich jinja2 --quiet 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    OK "Python paketleri hazir."
} else {
    WARN "Bazi paketler yuklenemedi - uygulama baslatilirken hata olabilir."
}

# -----------------------------------------------------------------------------
# [2/9] DOCKER DESKTOP
# -----------------------------------------------------------------------------
Step 2 "Docker Desktop kontrol ediliyor..."

$dockerRunning = $false
docker info 2>&1 | Out-Null
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
        WARN "Docker kurulu ama kapali - baslatiliyor..."
        Start-Process $dockerExe
    } else {
        WARN "Docker bulunamadi - yukleniyor (2-5 dk)..."
        WingetInstall "Docker.DockerDesktop" "Docker Desktop" | Out-Null
        RefreshPath
        $dockerExe = $dockerExePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($dockerExe) {
            Start-Process $dockerExe
        } else {
            ERR "Docker Desktop yuklenemedi. docker.com adresinden manuel kurun."
            Read-Host "Enter ile cik"; exit 1
        }
    }

    INFO "Docker baslayana kadar bekleniyor (maks 120sn)..."
    $waited = 0
    while ($waited -lt 120) {
        Start-Sleep -Seconds 5
        $waited += 5
        docker info 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            OK "Docker hazir."; $dockerRunning = $true; break
        }
        INFO "Bekleniyor: ${waited}s..."
    }

    if (-not $dockerRunning) {
        ERR "Docker 120 saniyede baslamadi."
        ERR "Docker Desktop'i elle acin, hazir olunca tekrar calistirin."
        Read-Host "Enter ile cik"; exit 1
    }
}

# -----------------------------------------------------------------------------
# [3/9] MINIKUBE
# -----------------------------------------------------------------------------
Step 3 "Minikube kontrol ediliyor..."

if (-not (IsInstalled "minikube")) {
    WARN "Minikube bulunamadi - yukleniyor..."
    WingetInstall "Kubernetes.minikube" "Minikube" | Out-Null
    RefreshPath
    Start-Sleep -Seconds 2
}
if (IsInstalled "minikube") {
    OK "Minikube hazir."
} else {
    ERR "Minikube yuklenemedi. Lutfen terminali yeniden acip tekrar deneyin."
    Read-Host "Enter ile cik"; exit 1
}

# -----------------------------------------------------------------------------
# [4/9] KUBECTL + HELM
# -----------------------------------------------------------------------------
Step 4 "kubectl ve Helm kontrol ediliyor..."

if (-not (IsInstalled "kubectl")) {
    WARN "kubectl bulunamadi - yukleniyor..."
    WingetInstall "Kubernetes.kubectl" "kubectl" | Out-Null
    RefreshPath
    Start-Sleep -Seconds 2
}
if (IsInstalled "kubectl") {
    $kubectlVer = kubectl version --client 2>&1 | Select-Object -First 1
    OK "kubectl hazir: $kubectlVer"
} else {
    ERR "kubectl yuklenemedi."
    Read-Host "Enter ile cik"; exit 1
}

if (-not (IsInstalled "helm")) {
    WARN "Helm bulunamadi - yukleniyor..."
    WingetInstall "Helm.Helm" "Helm" | Out-Null
    RefreshPath
    Start-Sleep -Seconds 2
}
if (IsInstalled "helm") {
    $helmVer = helm version 2>&1 | Select-Object -First 1
    OK "Helm hazir: $helmVer"
} else {
    ERR "Helm yuklenemedi."
    Read-Host "Enter ile cik"; exit 1
}

# -----------------------------------------------------------------------------
# [5/9] KUBERNETES CLUSTER
# -----------------------------------------------------------------------------
Step 5 "Kubernetes cluster hazirlaniyor..."

$PROFILE_NAME = "autoscaleops"
try {
    $jsonRaw = minikube profile list -o json 2>&1
    if ($LASTEXITCODE -eq 0 -and $jsonRaw) {
        $profiles = $jsonRaw | ConvertFrom-Json
        $existing = $profiles.valid | Where-Object { $_.Name -like "autoscaleops*" } | Select-Object -First 1
        if ($existing) { $PROFILE_NAME = $existing.Name }
    }
} catch {
    # JSON parse hatasi - varsayilan isim kullan
}
INFO "Profil: $PROFILE_NAME"

minikube status -p $PROFILE_NAME 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    OK "Cluster zaten calisiyor."
} else {
    INFO "Cluster baslatiliyor (1-3 dk)..."

    # Once 4 CPU / 6GB dene, basarisiz olursa 2 CPU / 4GB ile tekrar dene
    minikube start -p $PROFILE_NAME --driver=docker --cpus=4 --memory=6144 2>&1 | Select-Object -Last 5
    if ($LASTEXITCODE -ne 0) {
        WARN "Yuksek kaynak ile baslatma basarisiz - dusuk kaynak ile tekrar deneniyor..."
        minikube start -p $PROFILE_NAME --driver=docker --cpus=2 --memory=4096 2>&1 | Select-Object -Last 5
        if ($LASTEXITCODE -ne 0) {
            ERR "Cluster baslanamadi. Docker acik ve yeterli RAM var mi?"
            Read-Host "Enter ile cik"; exit 1
        }
    }
    OK "Cluster hazir."
}

kubectl create namespace $PROFILE_NAME --dry-run=client -o yaml 2>&1 | kubectl apply -f - 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    OK "Namespace hazir: $PROFILE_NAME"
} else {
    WARN "Namespace olusturulamadi - devam ediliyor."
}

# -----------------------------------------------------------------------------
# [6/9] PROMETHEUS + PUSHGATEWAY
# -----------------------------------------------------------------------------
Step 6 "Prometheus + Pushgateway kontrol ediliyor..."

helm status prometheus -n monitoring 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    OK "Prometheus zaten kurulu."
} else {
    INFO "Prometheus repo ekleniyor..."
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>&1 | Out-Null
    helm repo update 2>&1 | Out-Null

    INFO "Prometheus kuruluyor (3-5 dk)..."
    helm upgrade --install prometheus prometheus-community/kube-prometheus-stack `
        --namespace monitoring --create-namespace `
        --set grafana.enabled=false `
        --set alertmanager.enabled=false `
        --wait --timeout 5m 2>&1 | Select-Object -Last 5
    if ($LASTEXITCODE -eq 0) { OK "Prometheus kuruldu." }
    else { WARN "Prometheus kurulamadi - dashboard metrikleri calismayabilir." }
}

helm status pushgateway -n monitoring 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    OK "Pushgateway zaten kurulu."
} else {
    INFO "Pushgateway kuruluyor..."
    helm upgrade --install pushgateway prometheus-community/prometheus-pushgateway `
        --namespace monitoring --create-namespace `
        --wait --timeout 2m 2>&1 | Select-Object -Last 3
    if ($LASTEXITCODE -eq 0) { OK "Pushgateway kuruldu." }
    else { WARN "Pushgateway kurulamadi." }
}

# -----------------------------------------------------------------------------
# [7/9] KEDA
# -----------------------------------------------------------------------------
Step 7 "KEDA kontrol ediliyor..."

kubectl get namespace keda 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    OK "KEDA zaten kurulu."
} else {
    INFO "KEDA repo ekleniyor..."
    helm repo add kedacore https://kedacore.github.io/charts 2>&1 | Out-Null
    helm repo update 2>&1 | Out-Null

    INFO "KEDA kuruluyor..."
    helm upgrade --install keda kedacore/keda `
        --namespace keda --create-namespace `
        --wait --timeout 3m 2>&1 | Select-Object -Last 3
    if ($LASTEXITCODE -eq 0) { OK "KEDA kuruldu." }
    else { WARN "KEDA kurulamadi - otomatik olcekleme calismayabilir." }
}

# -----------------------------------------------------------------------------
# [8/9] AUTOSCALEOPS CLI
# -----------------------------------------------------------------------------
Step 8 "AutoScaleOps CLI kontrol ediliyor..."

Set-Location $SCRIPT_DIR

autoscaleops --version 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    OK "AutoScaleOps CLI zaten hazir."
} else {
    if (Test-Path (Join-Path $SCRIPT_DIR "pyproject.toml")) {
        INFO "AutoScaleOps CLI yukleniyor..."
        python -m pip install -e . --quiet 2>&1 | Out-Null
        autoscaleops --version 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { OK "CLI yuklendi." }
        else { WARN "CLI yuklenemedi - uygulama yine de calisacak." }
    } else {
        WARN "pyproject.toml bulunamadi - CLI atlandi."
    }
}

# -----------------------------------------------------------------------------
# [9/9] UYGULAMAYI BASLAT
# -----------------------------------------------------------------------------
Step 9 "Uygulama baslatiliyor..."

$appPath = Join-Path $SCRIPT_DIR "autoscaleops_app.py"
if (-not (Test-Path $appPath)) {
    ERR "autoscaleops_app.py bulunamadi: $appPath"
    ERR "Dosyanin dogru klasorde oldugundan emin olun."
    Read-Host "Enter ile cik"; exit 1
}

Write-Host ""
Write-Host "  =============================================" -ForegroundColor Cyan
Write-Host "   Tum sistemler hazir! Uygulama aciliyor...  " -ForegroundColor Green
Write-Host "  =============================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $SCRIPT_DIR
python autoscaleops_app.py

Write-Host ""
if ($LASTEXITCODE -ne 0) {
    ERR "Uygulama hatayla kapandi. Yukari kaydiriniz."
    Read-Host "Enter ile cik"
} else {
    Write-Host "  Uygulama kapatildi. Iyi gunler!" -ForegroundColor Cyan
    Start-Sleep -Seconds 2
}
