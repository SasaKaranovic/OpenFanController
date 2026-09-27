@echo off
rem Run the OpenFAN Python tests: software (unit/API) tests and hardware tests.
rem
rem Usage: run_tests.bat [options] [suite ...] [pytest args ...]
rem
rem   Software test suites (no hardware needed; default is all of them):
rem     api            REST API (webserver.py)
rem     board          board detection (board.py)
rem     config         config.yaml handling (config.py)
rem     fancommander   serial protocol encoding/parsing (FanCommander.py)
rem     serial         serial driver (serial_driver.py)
rem     known-bugs     only the tests documenting known bugs (xfail)
rem
rem   Hardware tests (hardware_tests\, driven by hardware_tests\devices.yaml):
rem     hardware                 run the hardware tests (added automatically with any option below)
rem     --list-devices           show the inventory and detected OpenFAN serial ports
rem     --device NAME            device from the inventory (sim-controller, sim-xl, sim-micro need no hardware)
rem     --scope supported/all    supported: skip unsupported features (default)
rem                              all: run them and verify the API reports them as unsupported
rem     --suite "a,b"            hardware suites: smoke,html,fan_control,profiles,aliases,sensors or all
rem     --base-url URL           test an already running server instead of starting one
rem     --server-config FILE     start webserver.py with a copy of this config file
rem     --server-port N          port for the started server
rem     --fans-connected "0,1"   (without --device) channels with a real fan attached
rem     --sensors-connected "0"  (without --device) channels with a real sensor attached
rem     --inventory FILE         use another inventory file
rem     NOTE: put comma separated values in quotes ("smoke,html"): cmd.exe splits arguments on commas.
rem
rem   Options:
rem     --setup        create .venv (if missing) and install requirements + test tools
rem     --cov          show a coverage report (software tests; needs pytest-cov)
rem     --list         list the tests instead of running them
rem     -h, --help     show this help
rem
rem   Anything else is passed straight to pytest, e.g.
rem     run_tests.bat api -k alias                     API tests with "alias" in their name
rem     run_tests.bat tests\test_config.py::test_set_fan_alias_persists
rem     run_tests.bat hardware --device sim-xl --scope all
rem     run_tests.bat --device lab-ctrl-01 --suite "smoke,html" -x
rem
rem Uses %PYTHON% if set, otherwise .venv (if present), otherwise python / py.

setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "SETUP=0"
set "HARDWARE=0"
set "HAS_PATH=0"
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
if /i "!ARG!"=="api"          ( set "SUITES=!SUITES! tests\test_api.py" & set "HAS_PATH=1" & goto next )
if /i "!ARG!"=="board"        ( set "SUITES=!SUITES! tests\test_board.py" & set "HAS_PATH=1" & goto next )
if /i "!ARG!"=="config"       ( set "SUITES=!SUITES! tests\test_config.py" & set "HAS_PATH=1" & goto next )
if /i "!ARG!"=="fancommander" ( set "SUITES=!SUITES! tests\test_fancommander.py" & set "HAS_PATH=1" & goto next )
if /i "!ARG!"=="serial"       ( set "SUITES=!SUITES! tests\test_serial_driver.py" & set "HAS_PATH=1" & goto next )
if /i "!ARG!"=="known-bugs"   ( set "PYTEST_ARGS=!PYTEST_ARGS! -m xfail" & goto next )
if /i "!ARG!"=="hardware"     ( set "SUITES=!SUITES! hardware_tests" & set "HAS_PATH=1" & set "HARDWARE=1" & goto next )
if /i "!ARG!"=="all"          goto next
if /i "!ARG!"=="--list-devices" ( set "PYTEST_ARGS=!PYTEST_ARGS! --list-devices" & set "HARDWARE=1" & goto next )
rem Hardware options that take a value (cmd.exe also splits "--scope=all" into "--scope" "all")
for %%o in (--device --scope --suite --base-url --server-config --server-port --fans-connected --sensors-connected --inventory --results-dir) do (
    if /i "!ARG!"=="%%o" ( set "HARDWARE=1" & goto take_value )
)
rem pytest options that take a value: keep the value as-is (so "-k api" stays a keyword)
for %%o in (-k -m -p -o -c --junitxml --maxfail --deselect --timeout --rootdir --basetemp) do (
    if /i "!ARG!"=="%%o" goto take_value
)
rem Anything else goes to pytest unchanged (keeps quotes, e.g. -k "alias or profile")
if /i "!ARG:~0,5!"=="tests"          set "HAS_PATH=1"
if /i "!ARG:~0,14!"=="hardware_tests" set "HAS_PATH=1"
set PYTEST_ARGS=!PYTEST_ARGS! %1
goto next

:take_value
if "%~2"=="" ( echo ERROR: %1 needs a value & exit /b 2 )
set PYTEST_ARGS=!PYTEST_ARGS! %1 %2
shift

:next
shift
goto parse
:parsed

rem Hardware options without an explicit test path -> run the hardware tests
if "%HARDWARE%"=="1" if "%HAS_PATH%"=="0" set "SUITES=!SUITES! hardware_tests"

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
