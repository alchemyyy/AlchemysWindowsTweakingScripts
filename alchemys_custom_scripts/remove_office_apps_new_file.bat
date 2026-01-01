@echo off
REM Remove Microsoft Office items from "New" context menu
REM This script renames ShellNew keys to disable them (can be restored later)

echo ================================================
echo Remove Office Items from Right-Click "New" Menu
echo ================================================
echo.
echo This will disable Office file types from the context menu.
echo The registry keys will be renamed (not deleted) so they can be restored.
echo.
pause

REM Check for admin rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script requires administrator privileges.
    echo Please right-click the file and select "Run as administrator"
    pause
    exit /b 1
)

echo.
echo Processing Office extensions...
echo.

REM Word Documents
reg query "HKEY_CLASSES_ROOT\.docx\ShellNew" >nul 2>&1
if %errorlevel% equ 0 (
    reg copy "HKEY_CLASSES_ROOT\.docx\ShellNew" "HKEY_CLASSES_ROOT\.docx\ShellNew-backup" /s /f >nul 2>&1
    reg delete "HKEY_CLASSES_ROOT\.docx\ShellNew" /f >nul 2>&1
    echo [OK] Removed .docx ^(Word Document^)
) else (
    echo [--] .docx already removed or not found
)

reg query "HKEY_CLASSES_ROOT\.doc\ShellNew" >nul 2>&1
if %errorlevel% equ 0 (
    reg copy "HKEY_CLASSES_ROOT\.doc\ShellNew" "HKEY_CLASSES_ROOT\.doc\ShellNew-backup" /s /f >nul 2>&1
    reg delete "HKEY_CLASSES_ROOT\.doc\ShellNew" /f >nul 2>&1
    echo [OK] Removed .doc ^(Word 97-2003 Document^)
) else (
    echo [--] .doc already removed or not found
)

REM Excel Spreadsheets
reg query "HKEY_CLASSES_ROOT\.xlsx\ShellNew" >nul 2>&1
if %errorlevel% equ 0 (
    reg copy "HKEY_CLASSES_ROOT\.xlsx\ShellNew" "HKEY_CLASSES_ROOT\.xlsx\ShellNew-backup" /s /f >nul 2>&1
    reg delete "HKEY_CLASSES_ROOT\.xlsx\ShellNew" /f >nul 2>&1
    echo [OK] Removed .xlsx ^(Excel Workbook^)
) else (
    echo [--] .xlsx already removed or not found
)

reg query "HKEY_CLASSES_ROOT\.xls\ShellNew" >nul 2>&1
if %errorlevel% equ 0 (
    reg copy "HKEY_CLASSES_ROOT\.xls\ShellNew" "HKEY_CLASSES_ROOT\.xls\ShellNew-backup" /s /f >nul 2>&1
    reg delete "HKEY_CLASSES_ROOT\.xls\ShellNew" /f >nul 2>&1
    echo [OK] Removed .xls ^(Excel 97-2003 Workbook^)
) else (
    echo [--] .xls already removed or not found
)

REM PowerPoint Presentations
reg query "HKEY_CLASSES_ROOT\.pptx\ShellNew" >nul 2>&1
if %errorlevel% equ 0 (
    reg copy "HKEY_CLASSES_ROOT\.pptx\ShellNew" "HKEY_CLASSES_ROOT\.pptx\ShellNew-backup" /s /f >nul 2>&1
    reg delete "HKEY_CLASSES_ROOT\.pptx\ShellNew" /f >nul 2>&1
    echo [OK] Removed .pptx ^(PowerPoint Presentation^)
) else (
    echo [--] .pptx already removed or not found
)

reg query "HKEY_CLASSES_ROOT\.ppt\ShellNew" >nul 2>&1
if %errorlevel% equ 0 (
    reg copy "HKEY_CLASSES_ROOT\.ppt\ShellNew" "HKEY_CLASSES_ROOT\.ppt\ShellNew-backup" /s /f >nul 2>&1
    reg delete "HKEY_CLASSES_ROOT\.ppt\ShellNew" /f >nul 2>&1
    echo [OK] Removed .ppt ^(PowerPoint 97-2003 Presentation^)
) else (
    echo [--] .ppt already removed or not found
)

REM Access Databases
reg query "HKEY_CLASSES_ROOT\.accdb\ShellNew" >nul 2>&1
if %errorlevel% equ 0 (
    reg copy "HKEY_CLASSES_ROOT\.accdb\ShellNew" "HKEY_CLASSES_ROOT\.accdb\ShellNew-backup" /s /f >nul 2>&1
    reg delete "HKEY_CLASSES_ROOT\.accdb\ShellNew" /f >nul 2>&1
    echo [OK] Removed .accdb ^(Access Database^)
) else (
    echo [--] .accdb already removed or not found
)

reg query "HKEY_CLASSES_ROOT\.mdb\ShellNew" >nul 2>&1
if %errorlevel% equ 0 (
    reg copy "HKEY_CLASSES_ROOT\.mdb\ShellNew" "HKEY_CLASSES_ROOT\.mdb\ShellNew-backup" /s /f >nul 2>&1
    reg delete "HKEY_CLASSES_ROOT\.mdb\ShellNew" /f >nul 2>&1
    echo [OK] Removed .mdb ^(Access 97-2003 Database^)
) else (
    echo [--] .mdb already removed or not found
)

REM OneNote
reg query "HKEY_CLASSES_ROOT\.one\ShellNew" >nul 2>&1
if %errorlevel% equ 0 (
    reg copy "HKEY_CLASSES_ROOT\.one\ShellNew" "HKEY_CLASSES_ROOT\.one\ShellNew-backup" /s /f >nul 2>&1
    reg delete "HKEY_CLASSES_ROOT\.one\ShellNew" /f >nul 2>&1
    echo [OK] Removed .one ^(OneNote Notebook^)
) else (
    echo [--] .one already removed or not found
)

echo.
echo ================================================
echo Done! Office items removed from context menu.
echo ================================================
echo.
echo NOTE: Backups were created with "-backup" suffix.
echo You may need to log out or restart to see changes.
echo.
pause
