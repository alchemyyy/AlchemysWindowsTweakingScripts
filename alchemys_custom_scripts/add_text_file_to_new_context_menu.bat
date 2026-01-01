@echo off
echo Restoring "New Text Document" to context menu...
echo.

REM Create the .txt file association if missing
reg add "HKEY_CLASSES_ROOT\.txt" /ve /d "txtfile" /f

REM Create txtfile association
reg add "HKEY_CLASSES_ROOT\txtfile" /ve /d "Text Document" /f

REM Add the ShellNew key with NullFile value
reg add "HKEY_CLASSES_ROOT\.txt\ShellNew" /v "NullFile" /t REG_SZ /d "" /f

REM Optional: Add FileName value (alternative method)
REM reg add "HKEY_CLASSES_ROOT\.txt\ShellNew" /v "FileName" /t REG_SZ /d "template.txt" /f

REM Add ItemName for localized display
reg add "HKEY_CLASSES_ROOT\.txt\ShellNew" /v "ItemName" /t REG_EXPAND_SZ /d "@%%SystemRoot%%\system32\notepad.exe,-469" /f

echo.
echo Registry entries have been added.
echo.
echo Done! The "New Text Document" option should now appear in your right-click menu.
echo If it doesn't appear immediately, try logging off and back on.
echo.
pause
