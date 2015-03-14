@echo off

rem This script redirects output of the program and appends it to 
rem errors.out when error occures. You have to check this file manually.
rem 
rem Schtasks /Create /TN synctogit /SC DAILY /TR "C:\Users\___\synctogit\SyncToGit\NoShell.vbs C:\Users\___\synctogit\SyncToGit\sync.bat" /RI 10

set R=%RANDOM%

cd /d "%~dp0"
..\Scripts\python main.py -b config.ini > current.%R%.out 2>&1

if "%ERRORLEVEL%"=="0" goto success
goto error

:error
echo FAIL
>>errors.out (
echo -----
date /T
time /T
type current.%R%.out
)
del current.%R%.out
exit /B 1

:success
del current.%R%.out
exit /B 0
