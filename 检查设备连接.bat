@echo off
chcp 65001 >nul
title 检查设备连接
color 09

echo ========================================
echo   检查安卓设备连接状态
echo ========================================
echo.

cd /d "%~dp0"

echo 正在检查设备连接...
echo.
echo ========================================
echo   已连接的设备列表：
echo ========================================
adb devices

echo.
echo ========================================
echo   设备详细信息：
echo ========================================
for /f "tokens=1" %%i in ('adb devices ^| findstr /v "List" ^| findstr /v "^$"') do (
    echo.
    echo 设备ID: %%i
    adb -s %%i shell getprop ro.product.model
    adb -s %%i shell getprop ro.build.version.release
    echo 分辨率: 
    adb -s %%i shell wm size
    echo DPI密度:
    adb -s %%i shell wm density
)

echo.
echo ========================================
echo   连接提示：
echo ========================================
echo.
echo 如果没有看到设备，请检查：
echo 1. USB线是否正确连接
echo 2. 手机是否开启了"开发者选项"
echo 3. 手机是否开启了"USB调试"
echo 4. 连接时手机上是否点击了"允许USB调试"
echo.
echo 如需截图当前手机屏幕，输入: S
echo 退出请按任意其他键...
echo.

set /p choice=请选择: 
if /i "%choice%"=="S" (
    echo.
    echo 正在截图...
    adb shell screencap -p /sdcard/screenshot.png
    adb pull /sdcard/screenshot.png
    echo ✅ 截图已保存到当前目录: screenshot.png
    start screenshot.png
)

echo.
echo ================================
echo 按任意键关闭窗口...
pause >nul 