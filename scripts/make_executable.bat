@echo off
echo Creating standalone executable for Panorama Security Profile Group Auditor...
echo.

REM Check if Python is installed
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in the PATH.
    echo Please install Python and try again.
    exit /b 1
)

REM Run the Python script to create the executable
python make_executable.py

echo.
if %errorlevel% equ 0 (
    echo Batch process completed successfully.
) else (
    echo Batch process failed with error code %errorlevel%.
)

pause