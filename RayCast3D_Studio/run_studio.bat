@echo off
REM RayCast3D Studio Launcher for Windows
REM Finds Python and runs the studio - dependencies install automatically.

where python >nul 2>nul
if %errorlevel%==0 (
    python "%~dp0RayCast3D_Studio.py"
    exit /b
)

where python3 >nul 2>nul
if %errorlevel%==0 (
    python3 "%~dp0RayCast3D_Studio.py"
    exit /b
)

REM Check common Windows install locations
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" "%~dp0RayCast3D_Studio.py"
    exit /b
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0RayCast3D_Studio.py"
    exit /b
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" "%~dp0RayCast3D_Studio.py"
    exit /b
)

echo ERROR: Python not found. Please install Python from https://www.python.org/downloads/
echo Make sure to check "Add Python to PATH" during installation.
pause
