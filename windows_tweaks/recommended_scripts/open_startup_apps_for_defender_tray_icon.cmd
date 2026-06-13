@echo off
rem Source: https://winaero.com/disable-defender-security-center-tray-icon/
rem INI tweak: DefenderTrayIconEnabled=0
rem Winaero's modern-build instructions disable the "Windows Defender notification icon"
rem startup entry manually in Task Manager. This opens that exact Startup tab.

taskmgr /0 /startup
