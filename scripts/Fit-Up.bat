@echo off
rem Lanzador de Fit-Up. Es el destino de los accesos directos.
rem
rem Vive en el repositorio y no en el escritorio para que actualizar la app sea
rem un `git pull`: los accesos directos apuntan aqui y no hay que rehacerlos.
setlocal

cd /d "%~dp0.."

if not exist "frontend\dist\index.html" (
    echo.
    echo   Falta la interfaz compilada. Ejecuta una vez:
    echo.
    echo       cd frontend ^&^& npm install ^&^& npm run build
    echo.
    pause
    exit /b 1
)

cd backend

rem Migraciones y catalogo al dia antes de servir. Es idempotente: en un
rem arranque normal no hace nada y tarda milisegundos.
python -m fitup.cli init >nul 2>&1
if errorlevel 1 (
    echo.
    echo   No se pudo preparar la base de datos. Detalle:
    echo.
    python -m fitup.cli init
    echo.
    pause
    exit /b 1
)

echo.
echo   Fit-Up esta arrancando. El navegador se abrira solo.
echo   Cierra esta ventana para parar el servidor.
echo.

python -m fitup.cli serve --abrir
