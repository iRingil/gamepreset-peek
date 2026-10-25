@echo off
setlocal

:: Change directory to the project root.
:: %~dp0 is the script's directory, '../..' moves two levels up to the project root.
cd /d "%~dp0..\.."
echo Current working directory is: %cd%

:: The Nuitka build must be done first: infrastructure\nuitka\build.cmd.
set "DIST_DIR=build\GamePresetPeek.dist"
if not exist "%DIST_DIR%\GamePresetPeek.exe" (
    echo ERROR: %DIST_DIR%\GamePresetPeek.exe not found, run infrastructure\nuitka\build.cmd first
    exit /b 1
)

:: Inno Setup installed for all users (CI runners) or for the current user (winget --scope user).
set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_EXE%" set "ISCC_EXE=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_EXE%" (
    echo ERROR: Inno Setup 6 not found, install it: winget install JRSoftware.InnoSetup
    exit /b 1
)

:: The version is read back from the executable's properties, the way the installer script does.
set "APP_VERSION="
for /f "usebackq delims=" %%v in (`powershell -NoProfile -Command "$v = (Get-Item '%DIST_DIR%\GamePresetPeek.exe').VersionInfo; '{0}.{1}.{2}' -f $v.FileMajorPart, $v.FileMinorPart, $v.FileBuildPart"`) do set "APP_VERSION=%%v"
echo App version: %APP_VERSION%

:: Installer: build\GamePresetPeek-<version>-setup.exe.
"%ISCC_EXE%" /Q "infrastructure\inno\GamePresetPeek.iss"
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Inno Setup failed with error code %errorlevel%.
    exit /b %errorlevel%
)

:: Portable zip: the build folder with the portable marker, under a folder of its own inside the archive.
set "PORTABLE_DIR=build\portable\GamePresetPeek"
set "PORTABLE_ZIP=build\GamePresetPeek-%APP_VERSION%-portable.zip"
if exist "build\portable" rmdir /s /q "build\portable"
robocopy "%DIST_DIR%" "%PORTABLE_DIR%" /e /njh /njs /nfl /ndl /np >nul
if %errorlevel% geq 8 (
    echo ERROR: copying %DIST_DIR% failed with robocopy code %errorlevel%.
    exit /b 1
)
copy /y "infrastructure\inno\portable.txt" "%PORTABLE_DIR%\" >nul
if exist "%PORTABLE_ZIP%" del "%PORTABLE_ZIP%"
:: Windows' own tar, not Git's GNU tar from PATH: zip paths with forward slashes (Compress-Archive writes backslashes).
"%SystemRoot%\System32\tar.exe" -a -c -f "%PORTABLE_ZIP%" -C "build\portable" GamePresetPeek
if %errorlevel% neq 0 (
    echo ERROR: creating %PORTABLE_ZIP% failed.
    exit /b 1
)
rmdir /s /q "build\portable"

echo.
echo Script finished successfully: build\GamePresetPeek-%APP_VERSION%-setup.exe and %PORTABLE_ZIP%.

endlocal
