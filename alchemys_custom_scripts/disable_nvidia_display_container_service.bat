@echo off
echo Stopping Nvidia Display Container LS service...
sc stop NVDisplay.ContainerLocalSystem

echo Setting startup type to Disabled...
sc config NVDisplay.ContainerLocalSystem start= disabled

echo Done.
pause