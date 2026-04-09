# Windows telepítő

## Gyors használat

1. Dupla kattintás: installer/Install-RobiRCS.cmd
2. Vagy PowerShellből:

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Install-RobiRCS.ps1
```

Ha dupla kattintás után az ablak korábban túl gyorsan bezárult, az új verzió már megáll hiba esetén, és kiírja a log helyét is:

- `%TEMP%\RobiRCSInstaller.log`

## Mit csinál

- bemásolja az alkalmazást a `LocalAppData\Programs\Robi RCS` mappába
- létrehoz egy saját `.venv` környezetet
- telepíti a Robi RCS csomagot
- telepíti a mellékelt openEMS és CSXCAD wheel-eket
- beállítja az `OPENEMS_INSTALL_PATH` user környezeti változót
- létrehoz indító parancsfájlt és Windows shortcutokat

## Python követelmény

A mellékelt openEMS wheel-ek miatt Python 3.13 vagy 3.14 szükséges.

## Leggyakoribb hibák

- Nincs telepítve Python 3.13 vagy 3.14.
- A `py` launcher nincs fent, és a `python` parancs sem található.
- PowerShell indítható, de a script valamilyen lokális policy vagy vállalati védelem miatt leáll.
- A felhasználó gépén az antivírus vagy SmartScreen megfogja a frissen másolt binárisokat.
- A telepítő csomag nincs teljesen kibontva, ezért hiányzik a `openEMS` vagy a `src` könyvtár.