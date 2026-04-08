# Robi RCS tesztelés és openEMS futtatás

## 1. Alap ellenőrzés

1. Aktiváld a virtuális környezetet.
2. Telepítsd a csomagot editable módban.
3. Futtasd az automatizált teszteket.

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m unittest discover -s tests -v
```

Ha a helyi fejlesztői repóból indítod, használd ezt is:

```powershell
Run-RobiRCS.cmd
```

## 2. GUI smoke test

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -c "from pathlib import Path; import sys; sys.path.insert(0, str(Path('src').resolve())); from PySide6.QtWidgets import QApplication; from robi_rcs.ui.main_window import MainWindow; app = QApplication([]); window = MainWindow(); print(window.windowTitle())"
```

Ha a kimenet `Robi RCS`, akkor a GUI létrehozható headless módban is.

## 3. Valós openEMS környezet beállítása

Az alkalmazás a Solver panel `openEMS python` mezőjében olyan `python.exe` útvonalat vár, amelyből ez működik:

```powershell
<openems-python.exe> -c "import openEMS, CSXCAD; print('ok')"
```

Ha ez nem sikerül, a program diagnosztikát ad, és szintetikus eredményre vált vissza.

Az új installer ezt automatikusan megcsinálja a mellékelt openEMS könyvtárból, és beállítja az `OPENEMS_INSTALL_PATH` környezeti változót is.

## 4. Ajánlott openEMS ellenőrzés kézzel

```powershell
<openems-python.exe> -c "import openEMS, CSXCAD, importlib.util; print(importlib.util.find_spec('openEMS').origin); print(importlib.util.find_spec('CSXCAD').origin)"
```

## 5. Valós solver futtatás a GUI-ból

1. Indítsd el a programot: `python main.py`
2. Tölts be egy STL/OBJ/PLY/STEP geometriát.
3. Ellenőrizd a `Mesh / Solver` panelen:
   - `openEMS python`: a működő openEMS-es Python útvonala
   - `Csak input`: kikapcsolva
   - `Cél futásidő [perc]`: a kívánt cél, például 10-120
4. Nyomd meg a `Diagnosztika` gombot.
5. Ha nincs blocking issue, indítsd a `Szimuláció indítása` műveletet.
6. A futás után a `Run directory` log sorból megkapod a generált openEMS job mappát.

## 6. Input generálás solver futtatás nélkül

Ha előbb csak az openEMS inputot akarod ellenőrizni:

1. Kapcsold be a `Csak input` opciót.
2. Futtasd a szimulációt.
3. A logban megjelenő run mappában ott lesz:
   - `job.json`
   - `run_openems_job.py`
   - a konvertált geometriafájl

Ez hasznos, ha előbb a külső openEMS környezetben akarod manuálisan futtatni a generált scriptet.

## 7. Manuális futtatás a generált job könyvtárból

```powershell
cd <run-directory>
<openems-python.exe> run_openems_job.py
```

Siker esetén létrejön a `result.json`, és a GUI ugyanebből a struktúrából is tud dolgozni.

## 8. Export ellenőrzése

A `Eredmények exportálása` művelet a megadott output könyvtárba többféle fájlt ír:

- numerikus CSV/JSON/HDF5
- `summary.json` és `summary.txt`
- `surface_proxy.vtp`
- plot képek és szöveges diagnosztikai dumpok a `plots/` mappában

## 9. Tipikus hibák

- `openEMS és CSXCAD nem importálható együtt`: rossz Python környezet van megadva.
- `Preflight hiba`: a geometria/frekvencia/memória beállítás blokkoló problémát tartalmaz.
- `Animáció export hiba` MP4 esetén: általában hiányzó ffmpeg backend.