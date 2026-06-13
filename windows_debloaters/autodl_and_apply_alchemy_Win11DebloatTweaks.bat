@echo off
setlocal EnableDelayedExpansion
set "TARGET_DIR=%~dp0Win11Debloat\Regfiles\"
set "SYSPREP_DIR=%TARGET_DIR%Sysprep\"
set "ERROR_COUNT=0"

:: Define all reg files (no .reg extension)
set "REG_FILES="
set "REG_FILES=!REG_FILES! Disable_AI_Recall"
set "REG_FILES=!REG_FILES! Disable_Animations"
set "REG_FILES=!REG_FILES! Disable_Bing_Cortana_In_Search"
set "REG_FILES=!REG_FILES! Disable_Chat_Taskbar"
set "REG_FILES=!REG_FILES! Disable_Click_to_Do"
set "REG_FILES=!REG_FILES! Disable_Copilot"
set "REG_FILES=!REG_FILES! Disable_Desktop_Spotlight"
set "REG_FILES=!REG_FILES! Disable_DVR"
set "REG_FILES=!REG_FILES! Disable_Edge_Ads_And_Suggestions"
set "REG_FILES=!REG_FILES! Disable_Edge_AI_Features"
set "REG_FILES=!REG_FILES! Disable_Enhance_Pointer_Precision"
set "REG_FILES=!REG_FILES! Disable_Fast_Startup"
set "REG_FILES=!REG_FILES! Disable_Game_Bar_Integration"
set "REG_FILES=!REG_FILES! Disable_Give_access_to_context_menu"
set "REG_FILES=!REG_FILES! Disable_Include_in_library_from_context_menu"
set "REG_FILES=!REG_FILES! Disable_Lockscreen_Tips"
set "REG_FILES=!REG_FILES! Disable_Notepad_AI_Features"
set "REG_FILES=!REG_FILES! Disable_Paint_AI_Features"
set "REG_FILES=!REG_FILES! Disable_Settings_365_Ads"
set "REG_FILES=!REG_FILES! Disable_Share_from_context_menu"
set "REG_FILES=!REG_FILES! Disable_Start_Recommended"
set "REG_FILES=!REG_FILES! Disable_Sticky_Keys_Shortcut"
set "REG_FILES=!REG_FILES! Disable_Telemetry"
set "REG_FILES=!REG_FILES! Disable_Windows_Suggestions"
set "REG_FILES=!REG_FILES! Enable_Dark_Mode"
set "REG_FILES=!REG_FILES! Enable_Last_Active_Click"
set "REG_FILES=!REG_FILES! Hide_Onedrive_Folder"
set "REG_FILES=!REG_FILES! Hide_Search_Taskbar"
set "REG_FILES=!REG_FILES! Launch_File_Explorer_To_This_PC"
set "REG_FILES=!REG_FILES! Show_Extensions_For_Known_File_Types"
set "REG_FILES=!REG_FILES! Show_Hidden_Folders"
set "REG_FILES=!REG_FILES! Uninstall_Microsoft_Edge"
set "REG_FILES=!REG_FILES! Uninstall_Microsoft_OneDrive"

:: Check if TARGET_DIR exists, if not download the repo
if not exist "%TARGET_DIR%" (
    echo Win11Debloat not found. Downloading from GitHub...
    echo.

    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/Raphire/Win11Debloat/archive/refs/heads/master.zip' -OutFile '%TEMP%\Win11Debloat.zip'; Expand-Archive -Path '%TEMP%\Win11Debloat.zip' -DestinationPath '%~dp0' -Force; Remove-Item '%TEMP%\Win11Debloat.zip'; Start-Sleep -Seconds 1; Rename-Item -Path '%~dp0Win11Debloat-master' -NewName 'Win11Debloat' -Force"

    if not exist "%TARGET_DIR%" (
        echo ERROR: Failed to download or extract Win11Debloat.
        pause
        exit /b 1
    )

    echo Download complete.
    echo.
)

:: Apply Sysprep registry tweaks first
if exist "%SYSPREP_DIR%" (
    echo Applying Sysprep registry tweaks from: %SYSPREP_DIR%
    echo.
    for %%F in (%REG_FILES%) do (
        call :ApplyReg "%SYSPREP_DIR%" "%%F.reg"
    )
    echo.
)

:: Apply main registry tweaks
echo Applying registry tweaks from: %TARGET_DIR%
echo.
for %%F in (%REG_FILES%) do (
    call :ApplyReg "%TARGET_DIR%" "%%F.reg"
)

echo.
if !ERROR_COUNT! GTR 0 (
    echo Completed with !ERROR_COUNT! error^(s^).
) else (
    echo All registry tweaks applied successfully.
)
pause
exit /b 0

:ApplyReg
set "REG_DIR=%~1"
set "REG_FILE=%~2"
if not exist "%REG_DIR%%REG_FILE%" exit /b 0
echo Applying: %REG_FILE%
regedit /s "%REG_DIR%%REG_FILE%"
if !ERRORLEVEL! NEQ 0 (
    echo   ERROR: Failed to apply %REG_FILE% ^(exit code: !ERRORLEVEL!^)
    set /a ERROR_COUNT+=1
    exit /b 1
)
exit /b 0
