@echo off
setlocal

:: Change directory to the project root.
:: %~dp0 is the script's directory, '../..' moves two levels up to the project root.
cd /d "%~dp0..\.."
echo Current working directory is: %cd%

:: Define the path to the virtualenv's Python relative to the project root.
set "PYTHON_EXE=.\.venv\Scripts\python.exe"
:: The version written into the executable's properties: up to four numbers.
set "APP_VERSION=0.1.0"

:: Check if the Python executable exists.
if not exist "%PYTHON_EXE%" (
    echo ERROR: python.exe not found in %cd%\.venv\Scripts\
    exit /b 1
)

echo Python found. Running Nuitka...

:: Build the app package into a standalone folder: build\GamePresetPeek.dist\GamePresetPeek.exe.
:: The package files keep their place under app\, so the database update can replace app\data\app.db there.
:: Nuitka downloads a C compiler on the first run when none is installed.
:: Qt plugins left: qwindows, qjpeg (covers), qico (window icon), qsvg (theme style sheet images), SVG icons, styles.
"%PYTHON_EXE%" -m nuitka ^
--mode=standalone ^
--assume-yes-for-downloads ^
--enable-plugin=pyside6 ^
--noinclude-qt-plugins=tls ^
--noinclude-dlls=PySide6/qt-plugins/platforms/qdirect2d.dll ^
--noinclude-dlls=PySide6/qt-plugins/platforms/qminimal.dll ^
--noinclude-dlls=PySide6/qt-plugins/platforms/qoffscreen.dll ^
--noinclude-dlls=PySide6/qt-plugins/imageformats/q[gpt]*.dll ^
--noinclude-dlls=PySide6/qt-plugins/imageformats/qicns.dll ^
--noinclude-dlls=PySide6/qt-plugins/imageformats/qw*.dll ^
--windows-console-mode=disable ^
--windows-icon-from-ico=src/app/data/app.ico ^
--include-data-dir=src/app/data=app/data ^
--include-data-files=src/app/i18n/locale=app/i18n/locale/=**/*.mo ^
--include-data-files=src/app/ui/vendor/qdarktheme/LICENSE.txt=app/ui/vendor/qdarktheme/LICENSE.txt ^
--include-data-files=LICENSE=LICENSE.txt ^
--include-package-data=fake_useragent ^
--output-dir=build ^
--output-folder-name=GamePresetPeek ^
--output-filename=GamePresetPeek.exe ^
--product-name="GamePreset Peek" ^
--file-description="GamePreset Peek" ^
--file-version=%APP_VERSION% ^
--product-version=%APP_VERSION% ^
--copyright="Copyright (c) 2026 iRingil" ^
--report=build/compilation-report.xml ^
src/app

:: Check if the previous command executed successfully.
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Nuitka failed with error code %errorlevel%.
    exit /b %errorlevel%
)

echo.
echo Script finished successfully. The app is in %cd%\build\GamePresetPeek.dist\.

endlocal
