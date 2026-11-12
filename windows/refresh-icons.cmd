@echo off
rem Restart Explorer and clear Windows' icon cache, so Explorer loads the newest theme build.
rem Run it after build_theme.py: double-click it, or start it from Win+R.
taskkill /f /im explorer.exe
ie4uinit.exe -show
del /a /q "%LOCALAPPDATA%\IconCache.db" 2>nul
del /a /q "%LOCALAPPDATA%\Microsoft\Windows\Explorer\iconcache_*.db" 2>nul
start explorer.exe
