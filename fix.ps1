$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Continue"

Clear-Host
Write-Host ""
Write-Host "  =========================================" -ForegroundColor Cyan
Write-Host "       AutoScaleOps  -  Kurulum Sihirbazi  " -ForegroundColor Cyan
Write-Host "  =========================================" -ForegroundColor Cyan
Write-Host ""

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path

# ─────────────────────────────────────────────────────────────────────────────
# YARDIMCI FONKSIYONLAR
# ─────────────────────────────────────────────────────────────────────────────
function Step($n, $total, $msg) {
    Write-Host "  [$n/$total] $msg" -ForegroundColor Yellow
}
function OK($msg) {
    Write-Host "        [OK] $msg" -ForegroundColor Green
}
function WARN($msg) {
    Write-Host "        [!]  $msg" -ForegroundColor Yellow
}
function ERR($msg) {
    Write-Host "       [HATA] $msg" -ForegroundColor Red
}
function IsInstalled($cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

# ─────────────────────────────────────────────────────────────────────────────
# [1/7] PYTHON PAKETLERI
# ─────────────────────────────────────────────────────────────────────────────
Step 1 7 "Python paketleri kontrol ediliyor..."

if (-not (IsInstalled "python")) {
    ERR "Python bulunamadi! Lutfen python.org/downloads adresinden kurun."
    ERR "Kurulumda 'Add Python to PATH' secenegini isaretleyin."
    Read-Host "`n  Kurup tekrar calistirin. Enter ile cik"
    exit 1
}
python -m pip install --upgrade pip --quiet 2>&1 | Out-Null
python -m pip install PyQt6 PyQt6-Qt6 PyQt6-sip matplotlib requests psutil cryptography urllib3 --quiet 2>&1 | Where-Object { $_ -notmatch "already|WARNING|Ignoring" } | ForEach-Object { Write-Host "        $_" }
OK "Tum Python paketleri hazir."
Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
# WINGET KONTROLU
# ─────────────────────────────────────────────────────────────────────────────
$hasWinget = IsInstalled "winget"

function WingetInstall($pkgId, $pkgName) {
    if (-not $hasWinget) {
        WARN "$pkgName icin winget bulunamadi. Elle kurulum gerekli."
        return $false
    }
    Write-Host "        Yukleniyor: $pkgName ..." -ForegroundColor DarkGray
    $result = winget install $pkgId --silent --accept-package-agreements --accept-source-agreements 2>&1
    if ($LASTEXITCODE -eq 0 -or ($result -match "installed|already installed")) {
        OK "$pkgName kuruldu."
        return $true
    }
    WARN "$pkgName yuklenemedi. Elle kurun: winget install $pkgId"
    return $false
}

# ─────────────────────────────────────────────────────────────────────────────
# [2/7] DOCKER DESKTOP
# ─────────────────────────────────────────────────────────────────────────────
Step 2 7 "Docker Desktop kontrol ediliyor..."

$dockerRunning = $false
$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -eq 0) {
    OK "Docker zaten calisyor."
    $dockerRunning = $true
} else {
    # Kurulu mu ama kapali mi?
    $dockerExePaths = @(
        "C:\Program Files\Docker\Docker\Docker Desktop.exe",
        "$env:LOCALAPPDATA\Docker\Docker Desktop.exe"
    )
    $dockerExe = $dockerExePaths | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($dockerExe) {
        WARN "Docker kurulu ama kapali. Baslatiliyor..."
        Start-Process $dockerExe
    } else {
        WARN "Docker bulunamadi. Yukleniyor (2-5 dakika surebilir)..."
        WingetInstall "Docker.DockerDesktop" "Docker Desktop" | Out-Null
        $dockerExe = $dockerExePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($dockerExe) {
            Write-Host "        Docker baslatiliyor..." -ForegroundColor DarkGray
            Start-Process $dockerExe
        }
    }

    # Docker'in hazir olmasini bekle (maks 90 sn)
    Write-Host "        Docker hazirlanana kadar bekleniyor (maks 90sn)..." -ForegroundColor DarkGray
    $waited = 0
    while ($waited -lt 90) {
        Start-Sleep 5
        $waited += 5
        $info = docker info 2>&1
        if ($LASTEXITCODE -eq 0) {
            OK "Docker hazir."
            $dockerRunning = $true
            break
        }
        Write-Host "        Bekleniyor: ${waited}s..." -ForegroundColor DarkGray
    }

    if (-not $dockerRunning) {
        ERR "Docker 90 saniyede baslamadir."
        ERR "Lutfen Docker Desktop'i elle acin, hazir olduktan sonra bu scripti tekrar calistirin."
        Read-Host "`n  Enter ile cik"
        exit 1
    }
}
Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
# [3/7] MINIKUBE
# ─────────────────────────────────────────────────────────────────────────────
Step 3 7 "Minikube kontrol ediliyor..."

if (IsInstalled "minikube") {
    OK "Minikube zaten kurulu."
} else {
    WARN "Minikube bulunamadi. Yukleniyor..."
    WingetInstall "Kubernetes.minikube" "Minikube" | Out-Null
    # PATH'e ekle (winget sonrasi terminal yenilenmeyebilir)
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
    if (IsInstalled "minikube") { OK "Minikube kuruldu." }
    else { WARN "Minikube PATH'te gorunmuyor. Terminali kapatip acin." }
}
Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
# [4/7] KUBECTL
# ─────────────────────────────────────────────────────────────────────────────
Step 4 7 "kubectl kontrol ediliyor..."

if (IsInstalled "kubectl") {
    OK "kubectl zaten kurulu."
} else {
    WARN "kubectl bulunamadi. Yukleniyor..."
    WingetInstall "Kubernetes.kubectl" "kubectl" | Out-Null
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
    if (IsInstalled "kubectl") { OK "kubectl kuruldu." }
    else { WARN "kubectl PATH'te gorunmuyor. Terminali kapatip acin." }
}
Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
# [5/7] HELM
# ─────────────────────────────────────────────────────────────────────────────
Step 5 7 "Helm kontrol ediliyor..."

if (IsInstalled "helm") {
    OK "Helm zaten kurulu."
} else {
    WARN "Helm bulunamadi. Yukleniyor..."
    WingetInstall "Helm.Helm" "Helm" | Out-Null
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
    if (IsInstalled "helm") { OK "Helm kuruldu." }
    else { WARN "Helm PATH'te gorunmuyor. Terminali kapatip acin." }
}
Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
# [6/7] KUBERNETES CLUSTER + NAMESPACE
# ─────────────────────────────────────────────────────────────────────────────
Step 6 7 "Kubernetes cluster hazirlaniyor..."

# Profil adini JSON ile bul (encoding sorunu olmaz)
$PROFILE_NAME = $null
try {
    $jsonRaw  = minikube profile list -o json 2>$null
    $profiles = $jsonRaw | ConvertFrom-Json
    $PROFILE_NAME = ($profiles.valid | Where-Object { $_.Name -like "autoscaleops*" } | Select-Object -First 1).Name
} catch {}

if (-not $PROFILE_NAME) {
    WARN "'autoscaleops' profili yok. Yeni profil olusturuluyor: autoscaleops"
    $PROFILE_NAME = "autoscaleops"
}
Write-Host "        Profil: $PROFILE_NAME" -ForegroundColor DarkGray

# Cluster basla
$status = minikube status -p $PROFILE_NAME 2>&1
if ($status -match "Running") {
    OK "Cluster zaten calisiyor."
} else {
    Write-Host "        Cluster baslatiliyor (1-3 dakika surebilir)..." -ForegroundColor DarkGray
    minikube start -p $PROFILE_NAME --driver=docker --cpus=4 --memory=6144 2>&1 | Select-Object -Last 3
    if ($LASTEXITCODE -ne 0) {
        ERR "Cluster baslanamadi. Docker acik mi?"
        Read-Host "Enter ile cik"
        exit 1
    }
    OK "Cluster hazir."
}

# Namespace olustur (zaten varsa sessizce gec)
Write-Host "        Namespace olusturuluyor: $PROFILE_NAME" -ForegroundColor DarkGray
kubectl create namespace $PROFILE_NAME --dry-run=client -o yaml 2>$null | kubectl apply -f - 2>&1 | Out-Null
OK "Namespace hazir: $PROFILE_NAME"
Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
# [7/7] UYGULAMAYI BASLAT
# ─────────────────────────────────────────────────────────────────────────────
Step 7 7 "Uygulama baslatiliyor..."
Write-Host ""
Write-Host "  =========================================" -ForegroundColor Cyan
Write-Host "   HAZIR! AutoScaleOps baslatiliyor...     " -ForegroundColor Green
Write-Host "  =========================================" -ForegroundColor Cyan
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
