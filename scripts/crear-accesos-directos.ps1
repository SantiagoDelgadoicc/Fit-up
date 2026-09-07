<#
.SYNOPSIS
    Crea los accesos directos de Fit-Up, en el escritorio y en la carpeta del
    proyecto, con su icono.

.DESCRIPTION
    Los accesos apuntan a `scripts\Fit-Up.bat`, que vive en el repositorio: así
    actualizar la app es un `git pull` y no hay que rehacerlos.

    El icono se convierte a .ico y se deja en `local\`, que está fuera de
    control de versiones. Es deliberado: la imagen de origen puede ser de un
    tercero y el repositorio es público. Cada equipo genera el suyo.

.PARAMETER Imagen
    PNG de origen. Por defecto, `local\icono-origen.png` si existe.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\crear-accesos-directos.ps1 -Imagen "C:\ruta\icono.png"
#>
[CmdletBinding()]
param(
    [string]$Imagen
)

$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $PSScriptRoot
$local = Join-Path $raiz "local"
$destinoIco = Join-Path $local "fitup.ico"
$lanzador = Join-Path $raiz "scripts\Fit-Up.bat"

if (-not (Test-Path $local)) { New-Item -ItemType Directory -Path $local | Out-Null }

if (-not $Imagen) {
    $porDefecto = Join-Path $local "icono-origen.png"
    if (Test-Path $porDefecto) { $Imagen = $porDefecto }
}

# --- Icono -------------------------------------------------------------
# Se genera un .ico con varias resoluciones porque Windows elige una distinta
# segun donde lo pinte: 16 px en la barra de tareas, 48 en el escritorio, 256
# en vista de iconos grandes. Con una sola imagen el reescalado lo hace el
# sistema y se ve sucio en los tamanos pequenos.
#
# Cada resolucion va como PNG embebido, admitido en el formato desde Vista.
# Basta con anteponer las cabeceras ICONDIR e ICONDIRENTRY, y asi no hace falta
# ninguna dependencia para convertir la imagen.
#
# 256 es el maximo del formato: el byte de tamano solo llega a 255 y el 0 se
# interpreta como 256. Un PNG de 1024 se acepta pero no se dibuja.
$tamanos = @(16, 24, 32, 48, 64, 128, 256)

if ($Imagen -and (Test-Path $Imagen)) {
    Add-Type -AssemblyName System.Drawing

    $origen = [System.Drawing.Image]::FromFile((Resolve-Path $Imagen))
    $imagenes = @()

    foreach ($lado in $tamanos) {
        $lienzo = New-Object System.Drawing.Bitmap($lado, $lado,
            [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
        $g = [System.Drawing.Graphics]::FromImage($lienzo)
        $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
        $g.DrawImage($origen, 0, 0, $lado, $lado)
        $g.Dispose()

        $buffer = New-Object System.IO.MemoryStream
        $lienzo.Save($buffer, [System.Drawing.Imaging.ImageFormat]::Png)
        $imagenes += , @{ Lado = $lado; Datos = $buffer.ToArray() }
        $buffer.Dispose()
        $lienzo.Dispose()
    }
    $origen.Dispose()

    $flujo = New-Object System.IO.MemoryStream
    $escritor = New-Object System.IO.BinaryWriter($flujo)

    $escritor.Write([UInt16]0)                  # reservado
    $escritor.Write([UInt16]1)                  # tipo: 1 = icono
    $escritor.Write([UInt16]$imagenes.Count)

    # Los datos empiezan despues de la cabecera y de todas las entradas.
    $offset = 6 + (16 * $imagenes.Count)
    foreach ($img in $imagenes) {
        $byteLado = if ($img.Lado -ge 256) { 0 } else { $img.Lado }
        $escritor.Write([Byte]$byteLado)        # ancho
        $escritor.Write([Byte]$byteLado)        # alto
        $escritor.Write([Byte]0)                # colores de la paleta
        $escritor.Write([Byte]0)                # reservado
        $escritor.Write([UInt16]1)              # planos
        $escritor.Write([UInt16]32)             # bits por pixel
        $escritor.Write([UInt32]$img.Datos.Length)
        $escritor.Write([UInt32]$offset)
        $offset += $img.Datos.Length
    }
    foreach ($img in $imagenes) { $escritor.Write($img.Datos) }

    $escritor.Flush()
    [System.IO.File]::WriteAllBytes($destinoIco, $flujo.ToArray())
    $escritor.Dispose()
    $flujo.Dispose()
    Write-Host "  icono generado: $destinoIco ($($imagenes.Count) resoluciones)"
}
elseif (-not (Test-Path $destinoIco)) {
    Write-Warning "Sin imagen de origen: los accesos usaran el icono por defecto de Windows."
    Write-Warning "Vuelve a ejecutar con -Imagen <ruta de tu imagen PNG>."
}

# --- Accesos directos --------------------------------------------------
$shell = New-Object -ComObject WScript.Shell

function New-Acceso {
    param([string]$Ruta, [string]$Descripcion)

    $acceso = $shell.CreateShortcut($Ruta)
    $acceso.TargetPath = $lanzador
    # Sin esto, el .bat se ejecutaría con el escritorio como directorio actual
    # y las rutas relativas del proyecto no resolverían.
    $acceso.WorkingDirectory = $raiz
    $acceso.Description = $Descripcion
    $acceso.WindowStyle = 7      # minimizada: la consola es ruido, no interfaz
    if (Test-Path $destinoIco) { $acceso.IconLocation = $destinoIco }
    $acceso.Save()
    Write-Host "  acceso creado: $Ruta"
}

$escritorio = [Environment]::GetFolderPath("Desktop")
New-Acceso -Ruta (Join-Path $escritorio "Fit-Up.lnk") -Descripcion "Abrir Fit-Up"
New-Acceso -Ruta (Join-Path $raiz "Fit-Up.lnk") -Descripcion "Abrir Fit-Up"

Write-Host ""
Write-Host "Listo. Doble clic en Fit-Up y se abre el navegador solo."
