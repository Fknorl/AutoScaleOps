# AutoScaleOps - Setup Entry Point
# Usage: .\setup.ps1

param(
    [switch]$Uninstall = $false,
    [switch]$CLI = $false
)

# Uninstall modu
if ($Uninstall) {
    $confirm = Read-Host "Her sey silinecek. Emin misin? (yes/no)"
    if ($confirm -ne "yes") {
        Write-Host "Iptal edildi."
        exit 0
    }
    $instanceFile = "$env:USERPROFILE\.autoscaleops\instance.json"
    if (Test-Path $instanceFile) {
        $data = Get-Content $instanceFile | ConvertFrom-Json
        $profile = "autoscaleops-$($data.instance_id)"
        Write-Host "Siliniyor: $profile" -ForegroundColor Yellow
        minikube delete -p $profile
        Remove-Item -Recurse -Force "$env:USERPROFILE\.autoscaleops" -ErrorAction SilentlyContinue
        Write-Host "Kaldirma tamamlandi!" -ForegroundColor Green
    } else {
        Write-Host "Kurulum bulunamadi." -ForegroundColor Gray
    }
    exit 0
}

# CLI modu
if ($CLI) {
    Write-Host "CLI modu baslatiliyor..." -ForegroundColor Yellow
    python installer\install.py
    exit 0
}

# Banner
Clear-Host
Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "         AutoScaleOps  -  Setup                        " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# Python kontrolu
Write-Host "  Python kontrol ediliyor..." -ForegroundColor Gray
$pyVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  HATA: Python bulunamadi!" -ForegroundColor Red
    Write-Host "  Indir: https://www.python.org/downloads/" -ForegroundColor Gray
    Read-Host "Cikmak icin Enter'a bas"
    exit 1
}
Write-Host "  OK: $pyVersion" -ForegroundColor Green

# Bagimliliklar
Write-Host "  [1/3] Installer bagimliliklar kuruluyor..." -ForegroundColor Gray
pip install flask requests cryptography keyring pyyaml -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "  UYARI: installer pip install basarisiz, devam ediliyor..." -ForegroundColor Yellow
} else {
    Write-Host "  OK: Installer hazir" -ForegroundColor Green
}

Write-Host "  [2/3] Desktop UI (PyQt6) kuruluyor..." -ForegroundColor Gray
pip install -r requirements_desktop.txt -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "  UYARI: requirements_desktop.txt hatasi, devam ediliyor..." -ForegroundColor Yellow
} else {
    Write-Host "  OK: PyQt6 hazir" -ForegroundColor Green
}

Write-Host "  [3/3] Dashboard & AI bagimliliklar kuruluyor..." -ForegroundColor Gray
pip install -r requirements.txt -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "  UYARI: requirements.txt hatasi, devam ediliyor..." -ForegroundColor Yellow
} else {
    Write-Host "  OK: Dashboard bagimliliklar hazir" -ForegroundColor Green
}

# Web Installer Baslat
Write-Host ""
Write-Host "  Kurulum arayuzu baslatiliyor..." -ForegroundColor Cyan
Write-Host "  Tarayici otomatik acilacak: http://localhost:5000" -ForegroundColor White
Write-Host ""
Write-Host "  BU PENCEREYI KAPATMA - kurulum burada calisiyor!" -ForegroundColor Yellow
Write-Host ""

python installer\web_installer.py