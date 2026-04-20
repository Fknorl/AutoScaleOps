@echo off
setlocal EnableDelayedExpansion
title AutoScaleOps - Deney Baslat
cd /d "%~dp0"
color 0F

:: ============================================================
::  EKRAN 1 — HOSGELDINIZ
:: ============================================================
cls
echo.
echo  ================================================================
echo   AutoScaleOps  ^|  Akademik Deney Sistemi
echo   Kubernetes AI Otomatik Olcekleme Arastirmasi
echo  ================================================================
echo.
echo   Bu script iki arac baslatiyor:
echo.
echo   [1]  traffic_simulator.py
echo        Uygulamaya HTTP istegi gonderir.
echo        Gece az, oglen fazla + rastgele pik simule eder.
echo        Hedef: http://localhost:8080
echo.
echo   [2]  metrics_logger.py
echo        Her 5 saniyede bir olcer, CSV dosyasina yazar.
echo        Kaydedilen: Gercek RPS, Tahmin RPS, Pod Sayisi, CPU, RAM
echo.
echo   Deney bitince analiz.py otomatik calisir ve
echo   akademik rapor olusturulur.
echo.
echo  ================================================================
echo.
set /p ONAY="   Devam etmek icin ENTER, cikmak icin Q + ENTER :  "
if /i "!ONAY!"=="Q" goto :CIKIS


:: ============================================================
::  EKRAN 2 — MOD SECIMI
:: ============================================================
:EKRAN_MOD
cls
echo.
echo  ================================================================
echo   ADIM 1 / 4  —  Deney Modunu Secin
echo  ================================================================
echo.
echo   [ A ]  MOD A  —  REAKTIF OLCEKLEME  ( Kontrol Grubu )
echo.
echo          - ARIMA yapay zeka modeli KAPALI
echo          - Yuk gelince metrik yukselir, KEDA karar verir,
echo            yeni pod baslar  (60-120 saniye surer)
echo          - Bu gecikme = "cold-start problemi"
echo          - Olcer: piklerde kac sn gec yanit, pod gecikmesi
echo.
echo   [ B ]  MOD B  —  ARIMA TAHMINLI  ( Deney Grubu )
echo.
echo          - Auto-ARIMA gecmis trafigi analiz eder
echo          - 30 dakika sonrasini TAHMIN ederek onceden
echo            pod havuzu hazirlar, cold-start ortadan kalkar
echo          - Olcer: tahmin isabeti (MAE/RMSE), over-provisioning
echo.
echo   [ L ]  SADECE LOGGER  ( Trafik gondermeden izle )
echo.
echo   [ Q ]  Cikis
echo.
echo  ================================================================
echo.
set "MOD="
set /p MOD="   Seciminiz  (A / B / L / Q) :  "

if /i "!MOD!"=="Q" goto :CIKIS
if /i "!MOD!"=="A" goto :MOD_A_ONAY
if /i "!MOD!"=="B" goto :MOD_B_ONAY
if /i "!MOD!"=="L" goto :MOD_L_ONAY

:: Gecersiz giris
echo.
echo   [HATA] Gecersiz secim: "!MOD!"
echo   Sadece A, B, L veya Q girebilirsiniz.
echo.
pause
goto :EKRAN_MOD

:MOD_A_ONAY
set "MOD_LABEL=MOD A - Reaktif Olcekleme (ARIMA Kapali)"
echo.
echo   [SECILDI] MOD A
echo.
echo   DIKKAT: MOD A'yi calistirmadan once ARIMA'yi durdurun:
echo.
echo   kubectl scale deployment/autoscaleops-ai-deployment
echo         --replicas=0 -n autoscaleops-74068768
echo.
echo   Bunu simdi yapmak ister misiniz?
set /p ARIMA_STOP="   (E/H) :  "
if /i "!ARIMA_STOP!"=="E" (
    echo   ARIMA durduruluyor...
    kubectl scale deployment/autoscaleops-ai-deployment --replicas=0 -n autoscaleops-74068768 2>&1
    echo   [OK] ARIMA durduruldu.
)
goto :PORTFORWARD

:MOD_B_ONAY
set "MOD_LABEL=MOD B - ARIMA Tahminli Olcekleme"
echo.
echo   [SECILDI] MOD B
echo   ARIMA deployment kontrol ediliyor...
kubectl get deployment autoscaleops-ai-deployment -n autoscaleops-74068768 2>nul | find "autoscaleops-ai" >nul
if !errorlevel! neq 0 (
    echo   [UYARI] ARIMA deployment bulunamadi. Devam ediliyor...
) else (
    echo   [OK] ARIMA deployment aktif.
)
goto :PORTFORWARD

:MOD_L_ONAY
set "MOD_LABEL=Sadece Logger"
echo.
echo   [SECILDI] Sadece Logger modu.
goto :PORTFORWARD


:: ============================================================
::  EKRAN 3 — PORT-FORWARD
:: ============================================================
:PORTFORWARD
cls
echo.
echo  ================================================================
echo   ADIM 2 / 4  —  Kubernetes Baglantilari
echo  ================================================================
echo.
echo   Onceki port-forward surecleri temizleniyor...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| find ":9090" ^| find "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| find ":8080" ^| find "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
timeout /t 2 >nul
echo   [ OK ]  Portlar serbest birakildi.
echo.

echo   Prometheus  ( port 9090 ) aciliyor...
start "[ PORT-FORWARD ] Prometheus 9090" cmd /k "color 08 && echo. && echo  PORT-FORWARD aktif: Prometheus 9090 && echo  Bu pencereyi KAPATMAYIN! && echo. && kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090"
timeout /t 3 >nul
echo   [ OK ]  Prometheus penceresi acildi.
echo.

echo   Uygulama  ( port 8080 ) aciliyor...
start "[ PORT-FORWARD ] Uygulama 8080" cmd /k "color 08 && echo. && echo  PORT-FORWARD aktif: Uygulama 8080 && echo  Bu pencereyi KAPATMAYIN! && echo. && kubectl port-forward -n autoscaleops-74068768 svc/autoscaleops-app-service 8080:8080"
timeout /t 3 >nul
echo   [ OK ]  Uygulama penceresi acildi.
echo.

echo  ================================================================
echo.
echo   2 gri port-forward penceresi acildi.
echo   Her ikisinde "Forwarding from 127.0.0.1" yazmali.
echo.
set /p DEVAM="   Devam etmek icin ENTER, cikmak icin Q + ENTER :  "
if /i "!DEVAM!"=="Q" goto :CIKIS


:: ============================================================
::  EKRAN 4 — SURE SECIMI
:: ============================================================
:EKRAN_SURE
cls
echo.
echo  ================================================================
echo   ADIM 3 / 4  —  Deney Suresini Secin
echo  ================================================================
echo.
echo   Makale icin onerim : 48 saat (minimum kabul goren sure)
echo   Hizli test icin    :  1 saat yeterli
echo.
echo   [ 1 ]    1 saat   =    3.600 saniye
echo   [ 2 ]    6 saat   =   21.600 saniye
echo   [ 3 ]   24 saat   =   86.400 saniye
echo   [ 4 ]   48 saat   =  172.800 saniye   ( TAM DENEY - onerilen )
echo   [ 5 ]   Ozel sure gir (saniye cinsinden)
echo   [ Q ]   Cikis
echo.
echo  ================================================================
echo.
set "SURE="
set /p SURE="   Seciminiz  (1 / 2 / 3 / 4 / 5 / Q) :  "

if /i "!SURE!"=="Q" goto :CIKIS

set "DURATION="
set "DURATION_LABEL="
if "!SURE!"=="1" ( set "DURATION=3600"   & set "DURATION_LABEL=1 saat" )
if "!SURE!"=="2" ( set "DURATION=21600"  & set "DURATION_LABEL=6 saat" )
if "!SURE!"=="3" ( set "DURATION=86400"  & set "DURATION_LABEL=24 saat" )
if "!SURE!"=="4" ( set "DURATION=172800" & set "DURATION_LABEL=48 saat" )
if "!SURE!"=="5" (
    echo.
    set /p DURATION="   Kac saniye? :  "
    set "DURATION_LABEL=Ozel"
)

:: Gecersiz giris kontrolu
if "!DURATION!"=="" (
    echo.
    echo   [HATA] Gecersiz secim: "!SURE!"
    echo   Sadece 1, 2, 3, 4, 5 veya Q girebilirsiniz.
    echo.
    pause
    goto :EKRAN_SURE
)


:: ============================================================
::  CIKTI DOSYASI ADI
:: ============================================================
set TIMESTAMP=%date:~10,4%%date:~7,2%%date:~4,2%_%time:~0,2%%time:~3,2%
set TIMESTAMP=%TIMESTAMP: =0%
set "OUTPUT=results_%MOD%_%TIMESTAMP%.csv"
set "REPORT=rapor_%MOD%_%TIMESTAMP%.txt"


:: ============================================================
::  EKRAN 5 — OZET ONAY
:: ============================================================
cls
echo.
echo  ================================================================
echo   ADIM 4 / 4  —  Ozet ve Onay
echo  ================================================================
echo.
echo   Mod           :  !MOD_LABEL!
echo   Sure          :  !DURATION_LABEL!  ( !DURATION! saniye )
echo   Veri dosyasi  :  !OUTPUT!
echo   Rapor dosyasi :  !REPORT!
echo   Trafik hedefi :  http://localhost:8080
echo   Prometheus    :  http://localhost:9090
echo.
if /i "!MOD!"=="L" (
    echo   Acilacak Pencere:
    echo     [1]  Metrik Logger  ( yesil pencere )
) else (
    echo   Acilacak Pencereler:
    echo     [1]  Trafik Ureteci  ( mavi  pencere )  HTTP istekleri gonderir
    echo     [2]  Metrik Logger   ( yesil pencere )  CSV'ye kaydeder
)
echo.
echo   Deney bitince analiz.py otomatik calisir ve
echo   !REPORT! adinda akademik rapor olusturulur.
echo.
echo  ================================================================
echo.
set /p ONAY2="   Baslatmak icin ENTER, iptal icin Q + ENTER :  "
if /i "!ONAY2!"=="Q" goto :CIKIS


:: ============================================================
::  BASLAT
:: ============================================================
cls
echo.
echo  ================================================================
echo   Baslatiliyor...
echo  ================================================================
echo.

if /i "!MOD!"=="L" (
    start "[ LOGGER ] AutoScaleOps - Mod !MOD! - Metrik Kaydedici" cmd /k "color 0A && python metrics_logger.py --mode !MOD! --output !OUTPUT! --duration !DURATION! && echo. && echo  Rapor olusturuluyor... && python analiz.py --input !OUTPUT! --mode !MOD! --output !REPORT! && echo. && echo  RAPOR HAZIR: !REPORT! && pause"
    echo   [ OK ]  Metrik Logger acildi.
) else (
    start "[ TRAFIK ] AutoScaleOps - Mod !MOD! - Trafik Ureteci" cmd /k "color 03 && python traffic_simulator.py --mode !MOD! --target http://localhost:8080 --duration !DURATION!"
    echo   [ OK ]  Trafik Ureteci acildi.
    timeout /t 2 >nul
    start "[ LOGGER ] AutoScaleOps - Mod !MOD! - Metrik Kaydedici" cmd /k "color 0A && python metrics_logger.py --mode !MOD! --output !OUTPUT! --duration !DURATION! && echo. && echo  Rapor olusturuluyor... && python analiz.py --input !OUTPUT! --mode !MOD! --output !REPORT! && echo. && echo  RAPOR HAZIR: !REPORT! && pause"
    echo   [ OK ]  Metrik Logger acildi.
)

echo.
echo  ================================================================
echo.
echo   DENEY BASLATILDI!
echo.
if /i "!MOD!"=="L" (
    echo     Yesil pencere  =  Metrik Logger calisiyor
) else (
    echo     Mavi  pencere  =  HTTP trafik gonderiliyor
    echo     Yesil pencere  =  Metrikler CSV'ye yaziliyor
)
echo.
echo   Sonuc dosyasi bu klasorde olusacak:
echo   %~dp0!OUTPUT!
echo.
echo   Deney bitince yesil pencere otomatik olarak
echo   akademik rapor olusturacak: !REPORT!
echo.
echo   Durdurmak icin: ilgili pencereye tikla + Ctrl+C
echo.
echo  ================================================================
echo.
pause
goto :EOF


:CIKIS
cls
echo.
echo   Cikiliyor... Iyi gunler!
echo.
timeout /t 2 >nul
endlocal
exit /b 0
