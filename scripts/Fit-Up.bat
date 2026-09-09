@echo off
rem Lanzador de Fit-Up. Es el destino de los accesos directos.
rem
rem Vive en el repositorio y no en el escritorio para que actualizar la app sea
rem un `git pull`: los accesos directos apuntan aqui y no hay que rehacerlos.
rem
rem El acceso directo abre esta ventana minimizada, asi que los errores se
rem avisan ademas con un cuadro de dialogo: un fallo dentro de una ventana que
rem nadie mira es un fallo invisible.
setlocal

rem Puerto configurable para poder levantar otra app del mismo tipo a la vez.
if "%FITUP_PUERTO%"=="" set FITUP_PUERTO=8000
if not "%~1"=="" set FITUP_PUERTO=%~1

cd /d "%~dp0.."

if not exist "frontend\dist\index.html" (
    call :aviso "Falta la interfaz compilada.\n\nEjecuta una vez:\n    cd frontend\n    npm install\n    npm run build"
    exit /b 1
)

rem El puerto ocupado es el fallo mas probable: Fit-Up ya abierto, o la otra
rem app usando el mismo numero. Se comprueba antes de arrancar para poder
rem decirlo con claridad, en vez de soltar la traza de uvicorn.
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort %FITUP_PUERTO% -State Listen -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    call :aviso "El puerto %FITUP_PUERTO% ya esta ocupado.\n\nProbablemente Fit-Up ya este abierto: mira en la barra de tareas o en http://127.0.0.1:%FITUP_PUERTO%\n\nPara levantar otra app a la vez, usala en otro puerto:\n    Fit-Up.bat 8001"
    exit /b 1
)

cd backend

rem Migraciones y catalogo al dia antes de servir. Es idempotente: en un
rem arranque normal no hace nada y tarda milisegundos.
python -m fitup.cli init >nul 2>&1
if errorlevel 1 (
    call :aviso "No se pudo preparar la base de datos.\n\nAbre una consola en la carpeta backend y ejecuta 'python -m fitup.cli init' para ver el detalle."
    exit /b 1
)

echo.
echo   Fit-Up esta arrancando en el puerto %FITUP_PUERTO%.
echo   El navegador se abrira solo. Cierra esta ventana para parar el servidor.
echo.

python -m fitup.cli serve --abrir --puerto %FITUP_PUERTO%
exit /b %errorlevel%

:aviso
rem Cuadro de dialogo ademas de la consola, porque el acceso directo abre esta
rem ventana minimizada. Un solo PowerShell para las dos salidas: asi el texto
rem se lee igual en los dos sitios y los \n se convierten una sola vez.
powershell -NoProfile -Command "$m = ('%~1' -replace '\\n', [Environment]::NewLine); Write-Host ''; Write-Host $m -ForegroundColor Yellow; Write-Host ''; Add-Type -AssemblyName PresentationFramework; [void][System.Windows.MessageBox]::Show($m, 'Fit-Up', 'OK', 'Warning')"
goto :eof
