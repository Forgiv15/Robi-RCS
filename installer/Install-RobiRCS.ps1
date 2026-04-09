param(
    [string]$InstallDir = "${env:LOCALAPPDATA}\Programs\Robi RCS",
    [string]$PythonExe = "",
    [switch]$NoDesktopShortcut,
    [switch]$NoStartMenuShortcut,
    [switch]$NoResultDialog
)

$ErrorActionPreference = 'Stop'

function Write-Step([string]$Message) {
    Write-Host "[Robi RCS] $Message"
}

function Show-ResultDialog {
    param(
        [string]$Title,
        [string]$Message,
        [ValidateSet(16, 48, 64)]
        [int]$Icon = 64
    )

    if ($NoResultDialog) {
        Write-Host $Message
        return
    }

    try {
        $shell = New-Object -ComObject WScript.Shell
        [void]$shell.Popup($Message, 0, $Title, $Icon)
    } catch {
        Write-Host $Message
    }
}

function Resolve-PythonExe {
    param([string]$UserPythonExe)

    if ($UserPythonExe) {
        if (-not (Test-Path $UserPythonExe)) {
            throw "A megadott Python nem talalhato: $UserPythonExe"
        }
        return (Resolve-Path $UserPythonExe).Path
    }

    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCommand) {
        foreach ($version in @('-3.13', '-3.14')) {
            try {
                $resolved = & py $version -c "import sys; print(sys.executable)"
                if ($LASTEXITCODE -eq 0 -and $resolved) {
                    return $resolved.Trim()
                }
            } catch {
            }
        }
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $version = & $pythonCommand.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        if ($LASTEXITCODE -eq 0 -and ($version.Trim() -eq '3.13' -or $version.Trim() -eq '3.14')) {
            return $pythonCommand.Source
        }
    }

    throw 'Python 3.13 vagy 3.14 szukseges az installer futtatasahoz.'
}

function New-Shortcut {
    param(
        [string]$ShortcutPath,
        [string]$TargetPath,
        [string]$WorkingDirectory,
        [string]$Description
    )

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $TargetPath
    $shortcut.WorkingDirectory = $WorkingDirectory
    $shortcut.Description = $Description
    $shortcut.Save()
}

function Test-InstalledHealth {
    param(
        [string]$PythonExe,
        [string]$OpenEMSRoot
    )

    if (-not (Test-Path $PythonExe) -or -not (Test-Path $OpenEMSRoot)) {
        return $null
    }

    $healthCode = @"
import json
import os
import sys

openems_root = r'''$OpenEMSRoot'''
os.environ['OPENEMS_INSTALL_PATH'] = openems_root
os.environ['PATH'] = openems_root + os.pathsep + os.environ.get('PATH', '')

status = {
    'python': sys.executable,
    'dependencies': {},
}

for name in ('PySide6', 'numpy', 'trimesh', 'gmsh', 'pyvista', 'pyvistaqt', 'pyqtgraph', 'imageio', 'robi_rcs', 'openEMS', 'CSXCAD'):
    try:
        __import__(name)
        status['dependencies'][name] = 'ok'
    except Exception as exc:
        status['dependencies'][name] = f'hiba: {exc}'

status['ok'] = all(value == 'ok' for value in status['dependencies'].values())
print(json.dumps(status))
"@

    $output = & $PythonExe -c $healthCode 2>&1
    if ($LASTEXITCODE -ne 0 -or -not $output) {
        return $null
    }

    $lines = @($output | ForEach-Object { "$_" } | Where-Object { $_.Trim() })
    if (-not $lines) {
        return $null
    }

    try {
        $jsonLine = $lines | Select-Object -Last 1
        return ($jsonLine | ConvertFrom-Json -ErrorAction Stop)
    } catch {
        return $null
    }
}

function Get-HealthProblems {
    param($Health)

    if (-not $Health) {
        return @('Az utoellenorzes nem adott ertelmezheto valaszt.')
    }

    $problems = @()
    foreach ($item in $Health.dependencies.PSObject.Properties) {
        if ($item.Value -ne 'ok') {
            $problems += "$($item.Name): $($item.Value)"
        }
    }
    return $problems
}

try {
    $repoRoot = Split-Path -Parent $PSScriptRoot
    $resolvedInstallDir = [System.IO.Path]::GetFullPath($InstallDir)
    $pythonExe = Resolve-PythonExe -UserPythonExe $PythonExe
    $venvDir = Join-Path $resolvedInstallDir '.venv'
    $venvPython = Join-Path $venvDir 'Scripts\python.exe'
    $openemsRoot = Join-Path $resolvedInstallDir 'openEMS'

    Write-Step "Telepitesi cel: $resolvedInstallDir"
    Write-Step "Python: $pythonExe"

    Write-Step 'Meglevo telepites ellenorzese'
    $existingHealth = Test-InstalledHealth -PythonExe $venvPython -OpenEMSRoot $openemsRoot
    if ($existingHealth -and $existingHealth.ok) {
        $alreadyInstalledMessage = @"
A Robi RCS mar telepitve van, es minden szukseges komponens rendben van.

Telepitesi mappa: $resolvedInstallDir
Python: $($existingHealth.python)
openEMS: hasznalhato
"@
        Write-Step 'Meglevo telepites rendben van, ujratelepites nem szukseges.'
        Show-ResultDialog -Title 'Robi RCS telepito' -Message $alreadyInstalledMessage.Trim() -Icon 64
        exit 0
    }
    if ($existingHealth) {
        Write-Step 'Meglevo telepites hianyos vagy serult, ujratelepites indul.'
    }

    New-Item -ItemType Directory -Force -Path $resolvedInstallDir | Out-Null

    $copyItems = @('main.py', 'pyproject.toml', 'README.md', 'docs', 'src', 'openEMS', 'Run-RobiRCS.cmd')
    foreach ($item in $copyItems) {
        $source = Join-Path $repoRoot $item
        if (-not (Test-Path $source)) {
            throw "Hianyzo telepitesi forras: $source"
        }
        $destination = Join-Path $resolvedInstallDir $item
        if (Test-Path $destination) {
            Remove-Item -Path $destination -Recurse -Force
        }
        Copy-Item -Path $source -Destination $destination -Recurse -Force
    }

    Write-Step 'Virtualis kornyezet letrehozasa'
    & $pythonExe -m venv $venvDir

    Write-Step 'pip frissitese'
    & $venvPython -m pip install --upgrade pip

    Write-Step 'Robi RCS csomag telepitese'
    & $venvPython -m pip install $resolvedInstallDir

    $cpTag = & $venvPython -c "import sys; print(f'cp{sys.version_info.major}{sys.version_info.minor}')"
    $cpTag = $cpTag.Trim()
    $csxWheel = Get-ChildItem -Path (Join-Path $openemsRoot 'python') -Filter "csxcad-*-$cpTag-$cpTag-win_amd64.whl" | Select-Object -First 1
    $openemsWheel = Get-ChildItem -Path (Join-Path $openemsRoot 'python') -Filter "openems-*-$cpTag-$cpTag-win_amd64.whl" | Select-Object -First 1

    if (-not $csxWheel -or -not $openemsWheel) {
        throw "Nem talalhato kompatibilis openEMS wheel a $cpTag ABI-hoz."
    }

    Write-Step 'openEMS Python bindingek telepitese'
    & $venvPython -m pip install $csxWheel.FullName $openemsWheel.FullName

    $buildDir = Join-Path $resolvedInstallDir 'build'
    if (Test-Path $buildDir) {
        Remove-Item -Path $buildDir -Recurse -Force
    }

    [Environment]::SetEnvironmentVariable('OPENEMS_INSTALL_PATH', $openemsRoot, 'User')
    [Environment]::SetEnvironmentVariable('ROBI_RCS_HOME', $resolvedInstallDir, 'User')

    $launcherPath = Join-Path $resolvedInstallDir 'Run-RobiRCS.cmd'
    $launcherContent = @"
@echo off
setlocal
set "ROBI_RCS_HOME=%~dp0"
set "OPENEMS_INSTALL_PATH=%ROBI_RCS_HOME%openEMS"
set "PYTHONUTF8=1"
"%ROBI_RCS_HOME%.venv\Scripts\python.exe" "%ROBI_RCS_HOME%main.py"
"@
    $launcherContent.TrimStart() | Set-Content -Path $launcherPath -Encoding ASCII

    $uninstallPath = Join-Path $resolvedInstallDir 'Uninstall-RobiRCS.ps1'
    $uninstallContent = @"

[Environment]::SetEnvironmentVariable('OPENEMS_INSTALL_PATH', `$null, 'User')
[Environment]::SetEnvironmentVariable('ROBI_RCS_HOME', `$null, 'User')

`$desktopShortcut = Join-Path `$env:USERPROFILE 'Desktop\Robi RCS.lnk'
`$startMenuShortcut = Join-Path `$env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Robi RCS.lnk'
if (Test-Path `$desktopShortcut) { Remove-Item `$desktopShortcut -Force }
if (Test-Path `$startMenuShortcut) { Remove-Item `$startMenuShortcut -Force }

`$target = '$resolvedInstallDir'
if (Test-Path `$target) { Remove-Item `$target -Recurse -Force }
"@
    $uninstallContent.Trim() | Set-Content -Path $uninstallPath -Encoding UTF8

    if (-not $NoDesktopShortcut) {
        $desktopShortcut = Join-Path $env:USERPROFILE 'Desktop\Robi RCS.lnk'
        New-Shortcut -ShortcutPath $desktopShortcut -TargetPath $launcherPath -WorkingDirectory $resolvedInstallDir -Description 'Robi RCS indito'
    }

    if (-not $NoStartMenuShortcut) {
        $startMenuDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
        New-Shortcut -ShortcutPath (Join-Path $startMenuDir 'Robi RCS.lnk') -TargetPath $launcherPath -WorkingDirectory $resolvedInstallDir -Description 'Robi RCS indito'
    }

    Write-Step 'Telepites kesz.'
    Write-Step "Indito: $launcherPath"
    Write-Step "openEMS konyvtar: $openemsRoot"

    $installedHealth = Test-InstalledHealth -PythonExe $venvPython -OpenEMSRoot $openemsRoot
    $healthProblems = Get-HealthProblems -Health $installedHealth
    if (-not $installedHealth -or $healthProblems.Count -gt 0) {
        throw "A telepites lefutott, de az utoellenorzes hibat talalt: $($healthProblems -join '; ')"
    }

    $successMessage = @"
A Robi RCS telepitese kesz.

Telepitesi mappa: $resolvedInstallDir
Python: $($installedHealth.python)
openEMS: hasznalhato
"@
    Show-ResultDialog -Title 'Robi RCS telepito' -Message $successMessage.Trim() -Icon 64
    exit 0
}
catch {
    Write-Host "[Robi RCS] HIBA: $($_.Exception.Message)" -ForegroundColor Red
    Show-ResultDialog -Title 'Robi RCS telepito - hiba' -Message $_.Exception.Message -Icon 16
    exit 1
}