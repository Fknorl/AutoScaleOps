@echo off
title AutoScaleOps - Kurulum ve Baslat
cd /d "%~dp0"

echo.
echo  =============================================
echo       AutoScaleOps  -  Kurulum Sihirbazi
echo  =============================================
echo.
echo  fix.ps1 calistiriliyor...
echo  (Ilk acilista kurulum 5-10 dakika surebilir)
echo.

PowerShell -NoProfile -ExecutionPolicy Bypass -File "%~dp0fix.ps1"

echo.
pause
