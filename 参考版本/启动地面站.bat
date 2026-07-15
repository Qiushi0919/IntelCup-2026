@echo off
chcp 65001 >nul
title IntelCup 地面站

echo ============================================
echo   正在启动 IntelCup 地面站...
echo ============================================
echo.
echo 如果闪退，请截图此窗口内容反馈
echo.

cd /d "%~dp0IntelCup-2026-ground-station\ground_station"

python main.py

echo.
echo 程序已退出（按任意键关闭）
pause
