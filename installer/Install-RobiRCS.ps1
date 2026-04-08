param(
    [string]$InstallDir = "${env:LOCALAPPDATA}\Programs\Robi RCS",
    [string]$PythonExe = "",
    [switch]$NoDesktopShortcut,
    [switch]$NoStartMenuShortcut
)

$ErrorActionPreference = 'Stop'

function Write-Step([string]$Message) {
    Write-Host "[Robi RCS] $Message"
}

function Resolve-PythonExe {
    param([string]$UserPythonExe)

    if ($UserPythonExe) {
        if (-not (Test-Path $UserPythonExe)) {
            throw "A megadott Python nem található: $UserPythonExe"
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

    throw 'Python 3.13 vagy 3.14 szükséges az installer futtatásához.'
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

$repoRoot = Split-Path -Parent $PSScriptRoot
$resolvedInstallDir = [System.IO.Path]::GetFullPath($InstallDir)
$pythonExe = Resolve-PythonExe -UserPythonExe $PythonExe
$venvDir = Join-Path $resolvedInstallDir '.venv'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'
$openemsRoot = Join-Path $resolvedInstallDir 'openEMS'

Write-Step "Telepítési cél: $resolvedInstallDir"
Write-Step "Python: $pythonExe"

New-Item -ItemType Directory -Force -Path $resolvedInstallDir | Out-Null

$copyItems = @('main.py', 'pyproject.toml', 'README.md', 'docs', 'src', 'openEMS', 'Run-RobiRCS.cmd')
foreach ($item in $copyItems) {
    $source = Join-Path $repoRoot $item
    if (-not (Test-Path $source)) {
        throw "Hiányzó telepítési forrás: $source"
    }
    $destination = Join-Path $resolvedInstallDir $item
    if (Test-Path $destination) {
        Remove-Item -Path $destination -Recurse -Force
    }
    Copy-Item -Path $source -Destination $destination -Recurse -Force
}

Write-Step 'Virtuális környezet létrehozása'
& $pythonExe -m venv $venvDir

Write-Step 'pip frissítése'
& $venvPython -m pip install --upgrade pip

Write-Step 'Robi RCS csomag telepítése'
& $venvPython -m pip install $resolvedInstallDir

$cpTag = & $venvPython -c "import sys; print(f'cp{sys.version_info.major}{sys.version_info.minor}')"
$cpTag = $cpTag.Trim()
$csxWheel = Get-ChildItem -Path (Join-Path $openemsRoot 'python') -Filter "csxcad-*-$cpTag-$cpTag-win_amd64.whl" | Select-Object -First 1
$openemsWheel = Get-ChildItem -Path (Join-Path $openemsRoot 'python') -Filter "openems-*-$cpTag-$cpTag-win_amd64.whl" | Select-Object -First 1

if (-not $csxWheel -or -not $openemsWheel) {
    throw "Nem található kompatibilis openEMS wheel a $cpTag ABI-hoz."
}

Write-Step 'openEMS Python bindingek telepítése'
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
    New-Shortcut -ShortcutPath $desktopShortcut -TargetPath $launcherPath -WorkingDirectory $resolvedInstallDir -Description 'Robi RCS indító'
}

if (-not $NoStartMenuShortcut) {
    $startMenuDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
    New-Shortcut -ShortcutPath (Join-Path $startMenuDir 'Robi RCS.lnk') -TargetPath $launcherPath -WorkingDirectory $resolvedInstallDir -Description 'Robi RCS indító'
}

Write-Step 'Telepítés kész.'
Write-Step "Indító: $launcherPath"
Write-Step "openEMS könyvtár: $openemsRoot"