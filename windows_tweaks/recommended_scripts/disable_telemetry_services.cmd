@echo off
rem Source: https://winaero.com/how-to-disable-telemetry-and-data-collection-in-windows-10/
rem Winaero lists Diagnostics Tracking Service / Connected User Experiences and Telemetry
rem plus dmwappushsvc, and its comments include sc commands for DiagTrack and dmwappushservice.

sc config DiagTrack start= disabled
sc config dmwappushservice start= disabled
sc stop DiagTrack
sc stop dmwappushservice
