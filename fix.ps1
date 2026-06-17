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

# Windows Store sahte Python stub'ini atlamak icin gercek Python kontrolu
function IsPythonReal {
    try {
        $ver = python --version 2>&1
        if ($ver -match "Python \d+\.\d+\.\d+") { return $true }
    } catch {}
    return $false
}

function RefreshPath {
    $machinePath = [System.Environment]::GetEnvironmentVariable("PATH", "Machine")
    $userPath    = [System.Environment]::GetEnvironmentVariable("PATH", "User")
    $parts = @($machinePath, $userPath) | Where-Object { $_ }
    if ($parts) { $env:PATH = $parts -join ";" }
}

function DisableWindowsPythonStub {
    # Windows 10/11, Python kurulu olmadigi halde python.exe stub'i olusturuyor
    # Bu stub "Python bulunamadi" diyerek Microsoft Store'u aciyor
    $stubPath = "$env:LOCALAPPDATA\Microsoft\WindowsApps"
    if (Test-Path "$stubPath\python.exe") {
        try {
            Remove-Item "$stubPath\python.exe"  -ErrorAction SilentlyContinue
            Remove-Item "$stubPath\python3.exe" -ErrorAction SilentlyContinue
        } catch {}
    }
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
    # 0 = basarili, -1978335189 (0x8A15002B) = zaten kurulu
    if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq -1978335189) {
        OK "$pkgName hazir."
        return $true
    }
    WARN "$pkgName yuklenemedi (kod: $LASTEXITCODE). Manuel: winget install $pkgId"
    return $false
}

# -----------------------------------------------------------------------------
# KURULUM DURUMU KONTROL - setup_complete.json varsa saglik kontrolu yap
# -----------------------------------------------------------------------------
$setupFile = "$env:USERPROFILE\.autoscaleops\setup_complete.json"
$appPath   = Join-Path $SCRIPT_DIR "autoscaleops_app.py"

function StartDockerIfClosed {
    # Docker kurulu ama kapali mi? Sadece baslatmaya calis, kurulum yapmadan.
    $dockerExePaths = @(
        "C:\Program Files\Docker\Docker\Docker Desktop.exe",
        "$env:LOCALAPPDATA\Docker\Docker Desktop.exe"
    )
    $dockerExe = $dockerExePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $dockerExe) { return $false }  # Docker hic kurulu degil

    INFO "Docker Desktop baslatiliyor..."
    Start-Process $dockerExe
    $waited = 0
    while ($waited -lt 60) {
        Start-Sleep -Seconds 5; $waited += 5
        docker info 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { OK "Docker hazir."; return $true }
        INFO "Docker bekleniyor: ${waited}s..."
    }
    return $false
}

function QuickHealthCheck {
    Write-Host "  Sistem saglik kontrolu yapiliyor..." -ForegroundColor Cyan

    # 1. Python gercekten calisiyor mu?
    if (-not (IsPythonReal)) {
        WARN "Python bulunamadi - tam kurulum gerekli."
        return "REINSTALL"
    }

    # 2. Docker calisiyor mu? (Sadece kapali ise otomatik baslat, kurulum yapma)
    docker info 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        WARN "Docker calismiyor - baslatiliyor..."
        if (-not (StartDockerIfClosed)) {
            WARN "Docker baslanamadi - tam kurulum gerekli."
            return "REINSTALL"
        }
    }

    # 3. Minikube 'autoscaleops' profili var ve calisiyor mu?
    minikube status -p autoscaleops 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        INFO "Minikube cluster baslatiliyor..."
        minikube start -p autoscaleops --driver=docker 2>&1 | Select-Object -Last 3
        if ($LASTEXITCODE -ne 0) {
            WARN "Cluster baslanamadi - tam kurulum gerekli."
            return "REINSTALL"
        }
        OK "Cluster hazir."
    }

    # 4. Prometheus kurulu mu? (Kurulu degilse tam kurulum, kapali degilse devam)
    helm status prometheus -n monitoring 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        WARN "Prometheus kurulu degil - tam kurulum gerekli."
        return "REINSTALL"
    }

    OK "Tum sistemler saglikli."
    return "OK"
}

if (Test-Path $setupFile) {
    Write-Host ""
    Write-Host "  Onceki kurulum bulundu - kontrol ediliyor..." -ForegroundColor Cyan

    $healthResult = QuickHealthCheck

    if ($healthResult -eq "OK") {
        # Her sey saglikli - direkt uygulamayi ac
        Write-Host ""
        Write-Host "  =============================================" -ForegroundColor Cyan
        Write-Host "   Sistemler hazir! Uygulama aciliyor...       " -ForegroundColor Green
        Write-Host "  =============================================" -ForegroundColor Cyan
        Write-Host ""
        if (-not (Test-Path $appPath)) {
            ERR "autoscaleops_app.py bulunamadi: $appPath"
            Read-Host "Enter ile cik"; exit 1
        }
        Set-Location $SCRIPT_DIR
        python autoscaleops_app.py
        if ($LASTEXITCODE -ne 0) {
            ERR "Uygulama hatayla kapandi. Yukari kaydiriniz."
            Read-Host "Enter ile cik"
        }
        exit 0
    } else {
        # Eksik/bozuk kurulum - tam kurulum gerekiyor
        Write-Host ""
        WARN "Eksik veya bozuk kurulum tespit edildi."
        WARN "Tam kurulum yeniden baslatiliyor..."
        Write-Host ""
        # setup_complete.json'i sil ki kurulum bitince yeniden yazilsin
        Remove-Item $setupFile -ErrorAction SilentlyContinue
    }
}

# -----------------------------------------------------------------------------
# KURULUM ON IZNI (sadece ilk kurulumda gosterilir)
# -----------------------------------------------------------------------------
Write-Host "  Su araclar kontrol edilecek ve eksikse kurulacak:" -ForegroundColor White
Write-Host "    - Python 3.11" -ForegroundColor Gray
Write-Host "    - Docker Desktop" -ForegroundColor Gray
Write-Host "    - Minikube" -ForegroundColor Gray
Write-Host "    - kubectl" -ForegroundColor Gray
Write-Host "    - Helm" -ForegroundColor Gray
Write-Host "    - Kubernetes cluster (Minikube)" -ForegroundColor Gray
Write-Host "    - Prometheus, Pushgateway, KEDA (Helm)" -ForegroundColor Gray
Write-Host ""
Write-Host "  Zaten kurulu olanlar atlanacak." -ForegroundColor DarkGray
Write-Host ""
$izin = Read-Host "  Devam etmek istiyor musunuz? (e/h)"
if ($izin -notmatch "^[eEyY]") {
    Write-Host "  Iptal edildi." -ForegroundColor Yellow
    exit 0
}
Write-Host ""

# -----------------------------------------------------------------------------
# [1/9] PYTHON
# -----------------------------------------------------------------------------
Step 1 "Python kontrol ediliyor..."

# Once Windows Store stub'ini temizle
DisableWindowsPythonStub
RefreshPath

if (-not (IsPythonReal)) {
    WARN "Gercek Python bulunamadi - winget ile kuruluyor..."

    if (-not (EnsureWinget)) {
        ERR "Python bulunamadi ve winget de yok!"
        ERR "Lutfen python.org/downloads adresinden Python 3.11+ kurun."
        ERR "Kurulumda 'Add Python to PATH' secenegini mutlaka isaretleyin!"
        Read-Host "`n  Kurup tekrar calistirin - Enter ile cik"
        exit 1
    }

    INFO "Python 3.11 yukleniyor (1-3 dk)..."
    # InstallAllUsers=1 -> Program Files'a kurar, WindowsApps stub'undan once gelir
    winget install Python.Python.3.11 `
        --silent `
        --accept-package-agreements `
        --accept-source-agreements `
        --override "/quiet InstallAllUsers=1 PrependPath=1 Include_pip=1" 2>&1 | Out-Null

    DisableWindowsPythonStub
    RefreshPath
    Start-Sleep -Seconds 3

    if (-not (IsPythonReal)) {
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

# Zorunlu GUI paketleri
python -m pip install `
    PyQt6 PyQt6-Qt6 PyQt6-sip `
    matplotlib requests psutil `
    cryptography urllib3 pyyaml `
    click rich jinja2 `
    prometheus-client `
    --quiet 2>&1 | Out-Null
$coreOk = $LASTEXITCODE -eq 0

# Analiz/AI paketleri (agir, hata olsa devam et)
INFO "Analiz paketleri yukleniyor (pmdarima, streamlit vb.)..."
python -m pip install `
    pmdarima statsmodels pandas numpy scipy scikit-learn streamlit plotly `
    --quiet 2>&1 | Out-Null

if ($coreOk) { OK "Python paketleri hazir." }
else {
    WARN "Bazi paketler yuklenemedi - tekrar deneniyor..."
    python -m pip install PyQt6 matplotlib requests psutil prometheus-client --quiet 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { OK "Temel Python paketleri hazir." }
    else { WARN "Paket kurulumu basarisiz - uygulama hata verebilir." }
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
    ERR "Minikube yuklenemedi. Terminali yeniden acip tekrar deneyin."
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

# Eski autoscaleops-{hash} profillerini temizle (onceki yanlis kurulumlar)
$PROFILE_NAME = "autoscaleops"
try {
    $jsonRaw = minikube profile list -o json 2>&1
    if ($LASTEXITCODE -eq 0 -and $jsonRaw) {
        $profiles = $jsonRaw | ConvertFrom-Json
        $allProfiles = @($profiles.valid) + @($profiles.invalid) | Where-Object { $_ -ne $null }
        $oldProfiles = $allProfiles | Where-Object {
            $_.Name -like "autoscaleops-*"   # hash'li eski profiller
        }
        foreach ($old in $oldProfiles) {
            WARN "Eski profil siliniyor: $($old.Name)"
            minikube delete -p $old.Name 2>&1 | Out-Null
            OK "Silindi: $($old.Name)"
        }
    }
} catch {}
INFO "Profil: $PROFILE_NAME"

minikube status -p $PROFILE_NAME 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    OK "Cluster zaten calisiyor."
} else {
    INFO "Cluster baslatiliyor (1-3 dk)..."
    minikube start -p $PROFILE_NAME --driver=docker --cpus=4 --memory=6144 2>&1 | Select-Object -Last 5
    if ($LASTEXITCODE -ne 0) {
        WARN "Yuksek kaynak basarisiz - dusuk kaynak ile deneniyor..."
        minikube start -p $PROFILE_NAME --driver=docker --cpus=2 --memory=4096 2>&1 | Select-Object -Last 5
        if ($LASTEXITCODE -ne 0) {
            ERR "Cluster baslanamadi. Docker acik ve yeterli RAM var mi?"
            Read-Host "Enter ile cik"; exit 1
        }
    }
    OK "Cluster hazir."
}

# Context her durumda set edilmeli - cluster calisiyorsa da atlanmamali
minikube update-context -p $PROFILE_NAME 2>&1 | Out-Null
kubectl config use-context $PROFILE_NAME 2>&1 | Out-Null
OK "kubectl context ayarlandi: $PROFILE_NAME"

kubectl create namespace $PROFILE_NAME --dry-run=client -o yaml 2>&1 | kubectl apply -f - 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) { OK "Namespace hazir: $PROFILE_NAME" }
else { WARN "Namespace olusturulamadi - devam ediliyor." }

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
        --wait --timeout 5m 2>&1 | Select-Object -Last 3
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
        --wait --timeout 3m 2>&1 | Select-Object -Last 3
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

# Get-Command ile dogru kontrol (LASTEXITCODE yerine - CommandNotFoundException $LASTEXITCODE'u sifirlamaz)
$cliExists = Get-Command autoscaleops -ErrorAction SilentlyContinue
if ($cliExists) {
    OK "AutoScaleOps CLI zaten hazir."
} else {
    if (Test-Path (Join-Path $SCRIPT_DIR "pyproject.toml")) {
        INFO "AutoScaleOps CLI yukleniyor..."
        python -m pip install -e . --quiet 2>&1 | Out-Null
        $cliExists = Get-Command autoscaleops -ErrorAction SilentlyContinue
        if ($cliExists) { OK "CLI yuklendi." }
        else { WARN "CLI yuklenemedi - uygulama yine de calisacak." }
    } else {
        WARN "pyproject.toml bulunamadi - CLI atlandi."
    }
}

# -----------------------------------------------------------------------------
# [8b] KURULUM KAYDEDILIYOR - instance.json + setup_complete.json
# -----------------------------------------------------------------------------
$autoscaleopsDir = "$env:USERPROFILE\.autoscaleops"
New-Item -ItemType Directory -Force -Path $autoscaleopsDir | Out-Null

# instance.json: app'in kullanacagi cluster bilgileri
# fix.ps1'in olusturdugu "autoscaleops" profiliyle eslestirilir
$instanceFile = "$autoscaleopsDir\instance.json"
if (-not (Test-Path $instanceFile)) {
    $instanceData = @{
        instance_id      = "default"
        namespace        = "autoscaleops"
        minikube_profile = "autoscaleops"
        created_at       = (Get-Date -Format "o")
    } | ConvertTo-Json
    Set-Content -Path $instanceFile -Value $instanceData -Encoding UTF8
    OK "Instance kaydedildi (profil: autoscaleops)"
} else {
    OK "Instance zaten mevcut."
}

# setup_complete.json: wizard'in tekrar acilmasini onler
$setupData = @{
    completed_at = (Get-Date -Format "o")
    version      = "fix.ps1"
} | ConvertTo-Json
Set-Content -Path "$autoscaleopsDir\setup_complete.json" -Value $setupData -Encoding UTF8
OK "Kurulum kaydedildi - wizard bir daha acilmayacak."

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

if (-not (IsPythonReal)) {
    ERR "Python hala bulunamadi - uygulama baslatilemiyor."
    ERR "Terminali kapatip yeniden acin ve tekrar calistirin."
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
