@echo off
REM ===================================================================
REM  build.bat - Windows build script for the manuscript
REM  Windows counterpart of `make pdf` (the Makefile uses Unix shell
REM  syntax - `if command -v`, `rm -f` - and cannot run on Windows).
REM
REM  Usage:
REM     build.bat        compile paper\template.tex -> paper\template.pdf
REM     build.bat clean  remove intermediate files
REM     build.bat open   compile then open the PDF
REM ===================================================================
setlocal
chcp 65001 >nul

set "TEX_DIR=paper"
set "MAIN_TEX=template.tex"
set "ROOT=%~dp0"

REM ---- Locate MiKTeX (portable install, no system-wide install needed) ----
set "MIKTEX_BIN=F:\zero trust\tools\miktex\texmfs\install\miktex\bin\x64"

if exist "%MIKTEX_BIN%\pdflatex.exe" (
    set "PATH=%MIKTEX_BIN%;%PATH%"
    set "PDFLATEX=%MIKTEX_BIN%\pdflatex.exe"
) else (
    where pdflatex >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] pdflatex not found.
        echo         Expected portable path: %MIKTEX_BIN%
        echo         Edit MIKTEX_BIN in this script, or add MiKTeX to PATH.
        exit /b 1
    )
    set "PDFLATEX=pdflatex"
)

pushd "%ROOT%%TEX_DIR%"

if /i "%~1"=="clean" goto clean

REM ---- Two passes so cross-references and citation numbers resolve ----
echo.
echo   Compiling %MAIN_TEX% ...
echo.
call :compile 1
if errorlevel 1 goto failed
call :compile 2
if errorlevel 1 goto failed

popd
echo.
echo   [OK] Built: %TEX_DIR%\%MAIN_TEX:.tex=.pdf%
echo.
if /i "%~1"=="open" start "" "%ROOT%%TEX_DIR%\%MAIN_TEX:.tex=.pdf%"
endlocal
exit /b 0

:compile
echo   --- pass %1 ---
"%PDFLATEX%" -interaction=nonstopmode -file-line-error "%MAIN_TEX%" > "pass%1.log" 2>&1
if errorlevel 1 (
    echo   [ERROR] pass %1 failed. Error lines:
    findstr /C:".tex:" "pass%1.log"
    goto :fail_here
)
findstr /C:"Output written" "pass%1.log"
exit /b 0

:fail_here
popd
endlocal
exit /b 1

:failed
popd
echo.
echo   Build failed. See %TEX_DIR%\pass1.log and %TEX_DIR%\template.log
endlocal
exit /b 1

:clean
echo   Cleaning intermediate files...
del /q *.aux *.bbl *.blg *.fdb_latexmk *.fls *.log *.out *.toc *.synctex.gz pass*.log 2>nul
popd
endlocal
exit /b 0
