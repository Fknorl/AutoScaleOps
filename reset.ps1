# AutoScaleOps - Sifirlama Araci

$ErrorActionPreference = "SilentlyContinue"

function Write-Title {
    Clear-Host
    Write-Host ""
    Write-Host "  ================================================" -ForegroundColor Cyan
    Write-Host "       AutoScaleOps -- Sifirlama Araci            " -ForegroundColor Cyan
    Write-Host "  ================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Remove-AppData {
    $appDir = "$env:USERPROFILE\.autoscaleops"
    if (Test-Path $appDir) {
        Remove-Item $appDir -Recurse -Force
        Write-Host "  [OK] Veritabani ve profil silindi: $appDir" -ForegroundColor Green
    } else {
        Write-Host "  [--] Veri klasoru zaten yok, atlandi." -ForegroundColor DarkGray
    }
}

function Stop-App {
    $proc = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
        $_.MainWindowTitle -like "*AutoScaleOps*"
    }
    if ($proc) {
        $proc | Stop-Process -Force
        Write-Host "  [OK] Uygulama kapatildi." -ForegroundColor Green
    }
}

# ── ANA MENU ──────────────────────────────────────────────────────────────────

Write-Title

Write-Host "  Ne yapmak istiyorsunuz?" -ForegroundColor White
Write-Host ""
Write-Host "  [1]  Soft Reset  - Sadece veritabani ve profil verisi silinir" -ForegroundColor Yellow
Write-Host "       (K8s ve Docker dokunulmaz, uygulama sifirdan baslar)" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  [2]  Full Reset  - Her sey silinir" -ForegroundColor Red
Write-Host "       (Veritabani + Kubernetes kumesi + Docker image'lari)" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  [3]  Iptal" -ForegroundColor DarkGray
Write-Host ""

$secim = Read-Host "  Seciminiz (1/2/3)"

# ── SOFT RESET ────────────────────────────────────────────────────────────────

if ($secim -eq "1") {
    Write-Title
    Write-Host "  SOFT RESET secildi." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Silinecekler:" -ForegroundColor White
    Write-Host "    - $env:USERPROFILE\.autoscaleops\" -ForegroundColor DarkGray
    Write-Host "      (veritabani, profil, etkinlikler)" -ForegroundColor DarkGray
    Write-Host ""
    $onay = Read-Host "  Devam edilsin mi? (E/H)"
    if ($onay -notmatch "^[Ee]$") {
        Write-Host ""
        Write-Host "  Iptal edildi." -ForegroundColor DarkGray
        Read-Host "  Kapatmak icin Enter'a basin"
        exit
    }

    Write-Host ""
    Stop-App
    Remove-AppData

    # Minikube profilini de sil - yoksa sonraki baslatmada GUEST_NOT_FOUND hatasi verir
    Write-Host "  [..] Minikube profili temizleniyor..." -ForegroundColor Yellow
    $mk = Get-Command minikube -ErrorAction SilentlyContinue
    if ($mk) {
        minikube delete -p autoscaleops 2>&1 | Out-Null
        # minikube delete bozuk profilde calismazsa dosyalari dogrudan sil
        $mkPaths = @(
            "$env:USERPROFILE\.minikube\machines\autoscaleops",
            "$env:USERPROFILE\.minikube\profiles\autoscaleops"
        )
        foreach ($p in $mkPaths) {
            if (Test-Path $p) { Remove-Item $p -Recurse -Force -ErrorAction SilentlyContinue }
        }
        Write-Host "  [OK] Minikube profili silindi." -ForegroundColor Green
    } else {
        Write-Host "  [--] minikube bulunamadi, atlandi." -ForegroundColor DarkGray
    }

    Write-Host ""
    Write-Host "  Soft Reset tamamlandi." -ForegroundColor Green
    Write-Host "  Uygulama bir sonraki acilisinda sifirdan baslar." -ForegroundColor DarkGray
}

# ── FULL RESET ────────────────────────────────────────────────────────────────

elseif ($secim -eq "2") {
    Write-Title
    Write-Host "  FULL RESET secildi." -ForegroundColor Red
    Write-Host ""
    Write-Host "  Silinecekler:" -ForegroundColor White
    Write-Host "    - $env:USERPROFILE\.autoscaleops\" -ForegroundColor DarkGray
    Write-Host "    - Kubernetes kumesi  (minikube delete)" -ForegroundColor DarkGray
    Write-Host "    - Docker image ve container'lari  (docker system prune)" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Bu islem geri alinamaz!" -ForegroundColor Red
    $onay = Read-Host "  Devam edilsin mi? (E/H)"
    if ($onay -notmatch "^[Ee]$") {
        Write-Host ""
        Write-Host "  Iptal edildi." -ForegroundColor DarkGray
        Read-Host "  Kapatmak icin Enter'a basin"
        exit
    }

    Write-Host ""
    Stop-App
    Remove-AppData

    Write-Host "  [..] Kubernetes kumesi siliniyor..." -ForegroundColor Yellow
    $mk = Get-Command minikube -ErrorAction SilentlyContinue
    if ($mk) {
        minikube delete --all 2>&1 | Out-Null
        Write-Host "  [OK] Kubernetes kumesi silindi." -ForegroundColor Green
    } else {
        Write-Host "  [--] minikube bulunamadi, atlandi." -ForegroundColor DarkGray
    }

    Write-Host "  [..] Docker temizleniyor..." -ForegroundColor Yellow
    $dk = Get-Command docker -ErrorAction SilentlyContinue
    if ($dk) {
        docker system prune -f 2>&1 | Out-Null
        Write-Host "  [OK] Docker temizlendi." -ForegroundColor Green
    } else {
        Write-Host "  [--] Docker bulunamadi, atlandi." -ForegroundColor DarkGray
    }

    Write-Host ""
    Write-Host "  Full Reset tamamlandi." -ForegroundColor Green
    Write-Host "  Uygulama bir sonraki acilisinda tamamen temiz baslar." -ForegroundColor DarkGray
}

# ── IPTAL ─────────────────────────────────────────────────────────────────────

else {
    Write-Host ""
    Write-Host "  Iptal edildi." -ForegroundColor DarkGray
}

Write-Host ""
Read-Host "  Kapatmak icin Enter'a basin"
