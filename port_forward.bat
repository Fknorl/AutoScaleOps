@echo off
setlocal EnableDelayedExpansion
title Port-Forward Manager
cd /d "%~dp0"
color 08

cls
echo.
echo  ================================================================
echo   Port-Forward Manager
echo   Bu pencereyi deney boyunca KAPATMAYIN!
echo  ================================================================
echo.

:: 8080 ve 9090 portlarini tutan surecleri kapat
echo  Portlar temizleniyor...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8080 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":9090 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 >nul
echo  [ OK ] Portlar serbest.
echo.

:: Prometheus port-forward arkaplanda baslat
echo  Prometheus 9090 baslatiliyor...
start /B kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090

:: Uygulama port-forward arkaplanda baslat
echo  Uygulama 8080 baslatiliyor...
start /B kubectl port-forward -n autoscaleops-74068768 svc/autoscaleops-app-service 8080:8080

:: 5 saniye bekle baglanti kurulsun
echo.
echo  Baglanti bekleniyor (5 saniye)...
timeout /t 5 >nul

:: Test et
echo.
echo  Baglanti test ediliyor...
echo.

:: 9090 testi
netstat -ano 2>nul | findstr ":9090 " | findstr "LISTENING" >nul
if !errorlevel! equ 0 (
    echo  [ OK ]  Prometheus 9090  --  BAGLI
) else (
    echo  [HATA] Prometheus 9090  --  BAGLI DEGIL
)

:: 8080 testi
netstat -ano 2>nul | findstr ":8080 " | findstr "LISTENING" >nul
if !errorlevel! equ 0 (
    echo  [ OK ]  Uygulama   8080  --  BAGLI
) else (
    echo  [HATA] Uygulama   8080  --  BAGLI DEGIL
)

echo.
echo  ================================================================
echo   Port-forward'lar calisiyor.
echo   Bu pencereyi kucultun ama KAPATMAYIN.
echo   Kapanirsa deney verileri kesilir!
echo  ================================================================
echo.

:: Bu pencere acik kalsin - port-forward'lar hayatta kalmak icin
:: arkaplan processleri bu pencere kapaninca devam eder
echo  Cikis yapmamak icin bir tusa basmayin.
echo  (Bu pencere kendini kapatmaz)
echo.

:BEKLE
timeout /t 60 >nul

:: Her dakika durum kontrol et
netstat -ano 2>nul | findstr ":8080 " | findstr "LISTENING" >nul
if !errorlevel! neq 0 (
    echo  [%time%] UYARI: 8080 kapandi, yeniden aciliyor...
    start /B kubectl port-forward -n autoscaleops-74068768 svc/autoscaleops-app-service 8080:8080
)

netstat -ano 2>nul | findstr ":9090 " | findstr "LISTENING" >nul
if !errorlevel! neq 0 (
    echo  [%time%] UYARI: 9090 kapandi, yeniden aciliyor...
    start /B kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
)

goto :BEKLE
