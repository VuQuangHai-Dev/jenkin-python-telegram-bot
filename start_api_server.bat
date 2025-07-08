@echo off
title Telegram Bot API Server

REM =================================================================
REM CONFIGURE YOUR DETAILS HERE
REM =================================================================

REM 1. Put your API ID and API Hash from my.telegram.org here.
set API_ID=YOUR_API_ID
set API_HASH=YOUR_API_HASH

REM 2. Make sure this is the correct name of the .exe file you downloaded.
set API_EXECUTABLE=telegram-bot-api-7.1-windows-amd64.exe

REM 3. This is the SOCKS5 proxy address for WARP.
set PROXY="socks5://127.0.0.1:40000"

REM =================================================================
REM END OF CONFIGURATION
REM =================================================================

echo Starting Telegram Bot API server...
echo.
echo Executable: %API_EXECUTABLE%
echo API ID:     %API_ID%
echo Proxy:      %PROXY%
echo.

REM Check if the executable file exists
if not exist "%API_EXECUTABLE%" (
    echo ERROR: The file '%API_EXECUTABLE%' was not found.
    echo Please make sure the .exe file is in the same directory as this script and the name is correct.
    echo.
    pause
    exit /b
)

REM Run the server
REM The --local flag allows the server to accept requests from a bot on the same machine.
%API_EXECUTABLE% --api-id=%API_ID% --api-hash=%API_HASH% --proxy=%PROXY% --local

echo.
echo Server has stopped.
pause 