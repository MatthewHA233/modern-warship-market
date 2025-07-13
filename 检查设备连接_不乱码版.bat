@echo off
chcp 65001 >nul
title Check Device
color 09

echo Check Android Device
echo ========================
echo.

cd /d "%~dp0"

echo Checking...
adb devices

echo.
for /f "tokens=1" %%i in ('adb devices ^| findstr /v "List" ^| findstr /v "^$"') do (
    echo ID: %%i
    for /f "tokens=3" %%j in ('adb -s %%i shell wm size') do echo size: %%j
    for /f "tokens=3" %%k in ('adb -s %%i shell wm density') do echo DPI: %%k
)

set /p choice=Press Enter to screenshot: 
echo Taking screenshot...
adb shell screencap -p /sdcard/screenshot.png
adb pull /sdcard/screenshot.png
echo Screenshot saved: screenshot.png
start screenshot.png

echo.
pause >nul 