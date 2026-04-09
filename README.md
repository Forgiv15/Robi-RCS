# Robi RCS

Desktop alkalmazás univerzális RCS szimulációhoz Qt6/Python alapon, openEMS orientált workflow-val.

## Indítás

```powershell
python -m pip install -e .
python main.py
```

Vagy Windows alatt közvetlenül:

```powershell
Run-RobiRCS.cmd
```

Ha a kibontott projektmappaban nincs helyi `.venv`, a `Run-RobiRCS.cmd` most automatikusan megprobal atvaltani a telepitett `LocalAppData\Programs\Robi RCS` peldanyra.

## Tesztelés

```powershell
python -m unittest discover -s tests -v
```

## Windows telepítő

Készítettem egy helyi Windows telepítőt is, amely a mellékelt openEMS csomagot és a Python wheel-eket automatikusan telepíti:

```powershell
installer\Install-RobiRCS.cmd
```

Részletek: installer/README.md

Az installer most már akkor is ad visszajelzést, ha minden szükséges komponens már telepítve van, és a GUI-ban külön környezetellenőrzés is látható a főablakban.

## Megjegyzés

Az alkalmazás GUI-ja és a teljes előkészítési pipeline helyben futtatható. A tényleges openEMS solver futtatáshoz külön telepített openEMS/CSXCAD Python környezet vagy külső parancs szükséges.

Részletes teszt- és openEMS futtatási lépések: docs/testing_and_openems.md
