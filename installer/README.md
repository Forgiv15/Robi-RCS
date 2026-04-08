# Windows telepítő

## Gyors használat

1. Dupla kattintás: installer/Install-RobiRCS.cmd
2. Vagy PowerShellből:

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Install-RobiRCS.ps1
```

## Mit csinál

- bemásolja az alkalmazást a `LocalAppData\Programs\Robi RCS` mappába
- létrehoz egy saját `.venv` környezetet
- telepíti a Robi RCS csomagot
- telepíti a mellékelt openEMS és CSXCAD wheel-eket
- beállítja az `OPENEMS_INSTALL_PATH` user környezeti változót
- létrehoz indító parancsfájlt és Windows shortcutokat

## Python követelmény

A mellékelt openEMS wheel-ek miatt Python 3.13 vagy 3.14 szükséges.