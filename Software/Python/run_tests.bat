@echo off
rem Run the OpenFAN Python software tests (no hardware needed).
rem
rem Usage: run_tests.bat [options] [suite ...] [pytest args ...]
rem
rem   Suites (any combination; default is all):
rem     api            REST API (webserver.py)
rem     board          board detection (board.py)
rem     config         config.yaml handling (config.py)
rem     fancommander   serial protocol encoding/parsing (FanCommander.py)
rem     serial         serial driver (serial_driver.py)
rem     known-bugs     only the tests documenting known bugs (xfail)
rem
rem   Options:
rem     --setup        create .venv (if missing) and install requirements + test tools
rem     --cov          show a coverage report (needs pytest-cov)
rem     --list         list the tests instead of running them
rem     -h, --help     show this help
rem
rem   Anything else is passed straight to pytest, e.g.
rem     run_tests.bat api -k alias          only API tests with "alias" in their name
rem     run_tests.bat tests\test_config.py::test_set_fan_alias_persists
rem     run_tests.bat -x -v                 verbose, stop at the first failure
rem
rem Uses %PYTHON% if set, otherwise .venv (if present), otherwise python / py.

setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "SETUP=0"
set "SUITES="
set "PYTEST_ARGS="

:parse
if "%~1"=="" goto parsed
set "ARG=%~1"
if /i "!ARG!"=="-h"           goto usage
if /i "!ARG!"=="--help"       goto usage
if /i "!ARG!"=="--setup"      ( set "SETUP=1" & goto next )
if /i "!ARG!"=="--cov"        ( set "PYTEST_ARGS=!PYTEST_ARGS! --cov=. --cov-report=term-missing" & goto next )
if /i "!ARG!"=="--list"       ( set "PYTEST_ARGS=!PYTEST_ARGS! --collect-only -q" & goto next )
if /i "!ARG!"=="api"          ( set "SUITES=!SUITES! tests\test_api.py" & goto next )
if /i "!ARG!"=="board"        ( set "SUITES=!SUITES! tests\test_board.py" & goto next )
if /i "!ARG!"=="config"       ( set "SUITES=!SUITES! tests\test_config.py" & goto next )
if /i "!ARG!"=="fancommander" ( set "SUITES=!SUITES! tests\test_fancommander.py" & goto next )
if /i "!ARG!"=="serial"       ( set "SUITES=!SUITES! tests\test_serial_driver.py" & goto next )
if /i "!ARG!"=="known-bugs"   ( set "PYTEST_ARGS=!PYTEST_ARGS! -m xfail" & goto next )
if /i "!ARG!"=="all"          goto next
rem Pass anything else to pytest unchanged (keeps quotes, e.g. -k "alias or profile")
set PYTEST_ARGS=!PYTEST_ARGS! %1
:next
shift
goto parse
:parsed

if "%SETUP%"=="1" (
    if not exist ".venv\Scripts\python.exe" (
        echo Creating virtual environment in .venv ...
        if defined PYTHON ( "%PYTHON%" -m venv .venv ) else ( call :find_system_python & "!SYS_PY!" -m venv .venv )
        if errorlevel 1 ( echo ERROR: could not create .venv & exit /b 1 )
    )
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
    if errorlevel 1 ( echo ERROR: installing requirements failed & exit /b 1 )
)

if defined PYTHON (
    set "PY=%PYTHON%"
) else if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    call :find_system_python
    set "PY=!SYS_PY!"
)
if not defined PY ( echo ERROR: Python not found. Install Python 3 or set PYTHON=C:\path\to\python.exe & exit /b 1 )

"%PY%" -c "import pytest" >nul 2>&1
if errorlevel 1 (
    echo ERROR: pytest is not installed for "%PY%".
    echo Run "run_tests.bat --setup" ^(creates .venv^) or "%PY% -m pip install -r requirements-dev.txt".
    exit /b 1
)

for /f "delims=" %%v in ('"%PY%" --version 2^>^&1') do echo Using: %%v ^(%PY%^)
"%PY%" -m pytest %SUITES% %PYTEST_ARGS%
exit /b %errorlevel%

:find_system_python
set "SYS_PY="
where python >nul 2>&1 && ( set "SYS_PY=python" & goto :eof )
where py >nul 2>&1 && ( set "SYS_PY=py" & goto :eof )
goto :eof

:usage
for /f "usebackq skip=1 tokens=* delims=" %%l in ("%~f0") do (
    set "LINE=%%l"
    if /i not "!LINE:~0,3!"=="rem" goto :eof
    echo(!LINE:~4!
)
exit /b 0
