# RCS szimulációs szoftverterv openEMS motorral

## 1. A szoftver célja és fő funkciói

### 1.1 Cél
A cél egy egyablakos, Qt6/Python alapú, mérnöki felhasználásra készült RCS szimulációs alkalmazás megtervezése, amely az openEMS elektromágneses solverre épül, és a végfelhasználó számára teljesen GUI-alapon használható. A felhasználónak ne kelljen Python, Octave vagy openEMS scriptet írnia; minden szükséges paraméter grafikus űrlapokon, varázslókon, előre definiált sablonokon és validált mezőkön keresztül legyen beállítható.

### 1.2 Elsődleges felhasználási esetek
- 3D geometria importálása fájlból és fizikai ellenőrzése.
- Monostatikus és bistatikus RCS számítás frekvenciasöprésben.
- Több beesési szög, több polarizáció és több anyagkonfiguráció futtatása.
- Fizikailag konzisztens automatikus szimulációs domén- és mesh-generálás.
- Interaktív eredménymegjelenítés 2D és 3D nézetekben.
- Tudományos és mérnöki exportformátumok támogatása.
- Reprodukálható projektmentés teljes metaadattal.

### 1.3 Nem funkcionális célok
- Fizikai helyesség elsőbbsége a vizuális kényelemmel szemben.
- Stabil működés különböző méretskálájú és topológiájú objektumokon.
- Közérthető, de szakmailag pontos hiba- és figyelmeztetési rendszer.
- Moduláris architektúra, amely később bővíthető optimalizációval, batch futtatással, GPU gyorsítással.

## 2. Fizikai modell és számítási módszer

### 2.1 Alapmodell
Az alkalmazás az openEMS időtartománybeli elektromágneses megoldóját használja. Az openEMS FDTD/FIT jellegű diszkretizációs megközelítéssel dolgozik strukturált rácson, anyagtérképpel és abszorbeáló peremfeltételekkel. A szórási probléma megoldásának alapja:

- adott 3D célgeometria,
- definiált anyagmodell(ek),
- beeső síkhullám vagy annak openEMS-ben reprezentálható ekvivalens gerjesztése,
- abszorbeáló peremfeltételekkel lezárt szimulációs tér,
- időtartományi mezőszámítás,
- frekvenciatartományi utófeldolgozás,
- szórt távoli tér számítása, majd ebből RCS meghatározása.

### 2.2 RCS definíció
A szoftver az RCS-t az alábbi standard alakban kezeli:

$$
\sigma(\theta,\phi,f) = 4\pi R^2 \frac{|E_s(\theta,\phi,f)|^2}{|E_i(f)|^2}
$$

ahol:
- $E_s$ a távoli szórt elektromos tér amplitúdója,
- $E_i$ a beeső tér referencia-amplitúdója,
- $R$ a megfigyelési távolság a távoli tér formulában,
- $\sigma$ az RCS $[m^2]$ egységben.

Monostatikus esetben a megfigyelési irány megegyezik a beesési irány ellentettjével. Bistatikus esetben a megfigyelési irány külön paraméterezett.

### 2.3 Anyagmodellek
Az alkalmazás első verzióban az alábbi anyagmodelltípusokat kezeli:
- PEC.
- Jó vezető, véges vezetőképességgel.
- Veszteséges dielektrikum: $\varepsilon_r$, $\mu_r$, $\sigma$, $\tan\delta$.
- Egyszerű radarabszorbens anyag sablon, parametrizált veszteségi profillal.
- Izotróp általános közeg.
- Opcionálisan anizotróp közeg, ha az openEMS adott leképezésben stabilan támogatja.

Az anizotrópia és disperszív modellek csak akkor legyenek bekapcsolhatók a GUI-ban, ha a backend validáltan és dokumentáltan kezeli őket; ellenkező esetben a rendszer ezt haladó vagy kísérleti funkcióként jelöli.

### 2.4 Szimulációs tartomány
A célobjektum köré olyan szórási tér kerül definiálásra, amely:
- elég nagy a közel-térből távoli-térbe történő korrekt utófeldolgozáshoz,
- nem metszi a PML-t a releváns szórt mező maximumok környezetében,
- figyelembe veszi a legnagyobb hullámhosszt és a gerjesztés irányát,
- minimalizálja a felesleges memória- és időigényt.

## 3. openEMS-alapú szimulációs pipeline teljes lépésről lépésre

### 3.1 Projekt létrehozása
1. Új projekt inicializálása.
2. Alapértelmezett egységek és numerikus beállítások betöltése.
3. Projekt metaadatok inicializálása: verzió, dátum, openEMS verzió, solver preset.

### 3.2 Geometria import
1. Fájlkiválasztás: STL elsődleges, majd OBJ, OFF, PLY, STEP opcionálisan konverziós lánccal.
2. Geometria parse és normalizálás.
3. Triangle mesh tisztítás:
   - duplikált csúcsok törlése,
   - degenerate háromszögek szűrése,
   - hibás normálok jelzése,
   - nyitott felületek és non-manifold élek detektálása.
4. Bounding box számítás.
5. Topológiai validáció.
6. Preview megjelenítés.

### 3.3 Mértékegység és skála meghatározása
1. Importált fájl implicit egységének ellenőrzése.
2. Automatikus heuristika: tipikus méretskála alapján egységjavaslat.
3. Felhasználói megerősítés: mm, cm, m.
4. Uniform scale faktor alkalmazása.
5. Frissített bounding box és méretek kiírása.

### 3.4 Anyag- és gerjesztési konfiguráció
1. Anyagmodell kiválasztása.
2. Anyagparaméterek validálása és egységesítése.
3. Frekvenciatartomány megadása.
4. Gerjesztés típusa és polarizáció beállítása.
5. Monostatikus vagy bistatikus mód kiválasztása.
6. Megfigyelési síkok és szögsorozatok megadása.

### 3.5 Automatikus box és mesh generálás
1. Legnagyobb frekvenciából minimális hullámhossz számítása.
2. Alaprácsfelbontás számítása $\lambda_{min}/N$ szabállyal.
3. Lokális finomítás generálása geometrián, éleken, kis rádiuszokon és anyaghatárok mentén.
4. PML régió beépítése.
5. Boxméret meghatározása célobjektum + szabad tér margó alapján.
6. CFL időlépés becslése.
7. Memória- és futásidőbecslés.
8. Figyelmeztetés, ha a feladat túl nagy vagy alulmintavételezett.

### 3.6 openEMS input generálás
1. CSXCAD geometriai reprezentáció előállítása.
2. Material assignment létrehozása.
3. Mesh lines / grid definíció előállítása.
4. Boundary condition beállítása.
5. Excitation definíció létrehozása.
6. Near-field / far-field mintafelületek kijelölése.
7. Solver input fájlok generálása reprodukálható formában.

### 3.7 Solver futtatás
1. Paraméterellenőrzés és preflight check.
2. Ideiglenes munkakönyvtár létrehozása.
3. openEMS futtatása subprocess-en keresztül.
4. STDOUT/STDERR és solver log folyamatos olvasása.
5. Progress model frissítése.
6. Sikertelen futás esetén diagnosztika és újrafuttatási javaslat.

### 3.8 Utófeldolgozás
1. Mezőadatok beolvasása.
2. Frekvenciatartományi transzformáció, ha szükséges.
3. Szórt tér leválasztása a teljes mezőből.
4. Near-to-far-field transzformáció.
5. RCS számítás frekvencia- és szögfüggésben.
6. Co-pol és cross-pol komponensek képzése.
7. Felületi vagy geometriai vetített intenzitástérkép származtatása.

### 3.9 Vizualizáció és export
1. 2D grafikonok létrehozása.
2. 3D mező- és felületnézetek előállítása.
3. Időfüggő animációs frame-ek elkészítése.
4. Export csomag létrehozása.
5. Projekt állapot mentése.

## 4. A bemeneti adatok teljes listája

### 4.1 Geometria és projekt
- Geometriafájl útvonala.
- Geometriaformátum.
- Egység: mm, cm, m.
- Skálázási faktor.
- Forgatás és kezdeti orientáció.
- Opcionális pozicionálás a koordinátarendszerben.
- Projekt neve, leírása, verziócímke.

### 4.2 Geometriai feldolgozási paraméterek
- Felületjavítás engedélyezése.
- Kis elemek automatikus eltávolításának küszöbe.
- Nyitott felület figyelmeztetés vagy tiltás.
- Vízálló geometria követelmény szintje.

### 4.3 Anyagparaméterek
- Anyagmodell típusa.
- $\varepsilon_r$.
- $\mu_r$.
- $\sigma$ [S/m].
- $\tan\delta$.
- Diszperziós paraméterek, ha támogatott.
- Anizotróp tenzor komponensek, ha támogatott.
- Anyagpreset neve.

### 4.4 Frekvenciaparaméterek
- Kezdő frekvencia.
- Végfrekvencia.
- Mintapontok száma.
- Sweep típus: lineáris vagy logaritmikus.
- Referenciafrekvencia a vizualizációhoz.

### 4.5 Gerjesztési paraméterek
- Beesési irány.
- Azimuth szög.
- Elevation szög.
- Polarizáció: lineáris X/Y/tetszőleges, RHCP, LHCP.
- E tér orientáció.
- H tér orientáció.
- Forrásamplitúdó.
- Gerjesztés típusa: impulzus, Gaussian pulse, harmonikus.
- Fázis referencia.

### 4.6 RCS specifikus paraméterek
- Monostatikus vagy bistatikus mód.
- Megfigyelési szögtartomány.
- Megfigyelési sík: azimuth sweep, elevation sweep, tetszőleges sík.
- Távoli tér referencia távolság.
- Co-pol / cross-pol komponensszámítás engedélyezése.
- Többszög-sorozat futtatás engedélyezése.

### 4.7 Mesh és numerikus paraméterek
- Automatikus mesh engedélyezése.
- Alap mesh finomsági preset: coarse, normal, fine, expert.
- Cél cellaszám hullámhosszonként.
- Minimális cellaméret.
- Maximális cellanövekedési arány.
- Lokális finomítás erőssége.
- PML vastagság cellában.
- Időlépésszorzó vagy CFL safety factor.
- Maximális memóriahasználat.

### 4.8 Export és megjelenítés
- Eredményfájlok mappája.
- Exportformátumok.
- Animáció fps.
- Időablak vagy fázislépésszám.
- Színskála típusa.
- Log részletességi szintje.

## 5. Az automatikus mesh és box generálás logikája

### 5.1 Cél
Az automatikus mesh-generátor célja, hogy a felhasználónak ne kelljen mezőszintű numerikus részletekkel foglalkoznia, de az eredmény továbbra is fizikailag helyes maradjon. A rendszer ezért javaslatot készít, nem vakon állít be mindent. Minden automatikus döntéshez indoklás és minőségi jelző társul.

### 5.2 Box méretezési stratégia
Legyen a geometria befoglaló mérete:

$$
L_x, L_y, L_z
$$

és a maximális frekvenciából számolt minimális hullámhossz:

$$
\lambda_{min} = \frac{c}{f_{max}\sqrt{\varepsilon_{r,max}\mu_{r,max}}}
$$

Javasolt szabad tér margó a célobjektum és a PML belső határa között:
- általános esetben legalább $0.3\lambda_{min}$ és inkább $0.5\lambda_{min}$,
- erős rezonáns vagy hosszúkás geometriánál $0.75\lambda_{min}$,
- bistatikus széles szögtartománynál a kritikus irányokban adaptívan növelt margó.

Alap box:

$$
Box_x = L_x + 2M_x, \quad Box_y = L_y + 2M_y, \quad Box_z = L_z + 2M_z
$$

ahol $M_i$ irányfüggő margó, amely a beesési irány és a szórási szögmező szerint módosulhat.

### 5.3 Alaprácsfelbontás
Kiinduló szabály:
- levegőben legalább 15-20 cella a legrövidebb hullámhosszon,
- nagy kontrasztú anyagban effektív hullámhossz alapján inkább 20-30 cella,
- erősen görbült vagy kis részletű geometrián további lokális finomítás.

Alap cellaméret:

$$
\Delta_{base} = \min\left(\frac{\lambda_{min}}{N_\lambda}, \frac{r_{min}}{N_r}, \frac{t_{min}}{N_t}\right)
$$

ahol:
- $N_\lambda$ tipikusan 15-25,
- $r_{min}$ a legkisebb lokális görbületi sugár becslése,
- $t_{min}$ a legkisebb releváns geometriai részlet,
- $N_r$ és $N_t$ tipikusan 3-6.

### 5.4 Adaptív finomítási szabályok
Automatikus lokális finomítás szükséges:
- élek és csúcsok környezetében,
- kis rádiuszú görbületeknél,
- vékony rétegeknél,
- anyaghatároknál,
- nagy mezőgradiensű zónákban, ha előzetes becslés rendelkezésre áll.

A finomítás logikája:
1. Geometriai feature extraction.
2. Feature importance score számítása.
3. Lokális célcella-méret hozzárendelése.
4. Strukturált mesh-re való leképzés smoothinggal.
5. Mesh grading korlátozása, hogy a szomszédos cellák méretaránya ne legyen túl nagy.

Javasolt mesh grading feltétel:
- szomszédos cellaméretek aránya ne legyen nagyobb 1.2-1.4 értéknél.

### 5.5 PML és peremfeltétel illesztés
Default peremfeltétel: minden oldalon PML.

PML méretezés:
- 8-12 cella normál esetben,
- nagy sávszélesség vagy sekély beesés esetén 12-16 cella.

A rendszer ellenőrzi:
- a célobjektum és PML közötti minimális távolságot,
- hogy finom mesh-e közvetlenül a PML határig ér-e,
- a PML kezdete előtt van-e elegendő homogén régió.

### 5.6 CFL stabilitás és időlépés
Az időlépést a rendszer automatikusan számolja a strukturált rács alapján:

$$
\Delta t \leq S \cdot \frac{1}{c\sqrt{\frac{1}{\Delta x^2}+\frac{1}{\Delta y^2}+\frac{1}{\Delta z^2}}}
$$

ahol $S$ a safety factor, tipikusan 0.9 vagy konzervatívabb érték.

### 5.7 Minőségértékelés és figyelmeztetések
A mesh generátor minden futás előtt minősítést ad:
- zöld: numerikusan várhatóan stabil és megfelelő.
- sárga: futtatható, de a pontosság korlátozott lehet.
- piros: várhatóan instabil, pontatlan vagy erőforrásigényben irreális.

Konkrét figyelmeztetések:
- túl kevés cella a legrövidebb hullámhosszon,
- túl kicsi PML távolság,
- túl nagy aspect ratio a cellák között,
- túl vékony geometriai elem nem reprezentálható,
- memóriaigény meghaladja a felhasználó limitjét,
- nagyon magas rezonanciafaktor várható, finomabb mesh javasolt.

## 6. A GUI részletes felépítése és képernyőelrendezése

### 6.1 Főablak elrendezés
Az alkalmazás egyablakos, dockolható panelekből álló felépítésű.

Javasolt layout:
- bal felső: állandó 3D preview panel,
- jobb felső és közép: nagy eredménypanel tabokkal,
- bal alsó vagy jobb oldali keskeny sáv: paraméterpanel szekciókra bontva,
- alsó teljes szélességben: log / státusz / figyelmeztetés panel,
- felső toolbar: projekt, import, futtatás, mentés, export,
- alsó status bar: rövid állapot, memória, solver állapot, progress.

### 6.2 Preview panel
Funkciók:
- 3D objektum megjelenítése.
- Orbit rotate, pan, zoom.
- Tengelyek megjelenítése.
- Bounding box ki-be kapcsolás.
- Fő méretek annotálása: X, Y, Z kiterjedés.
- Felületnormál ellenőrzés nézet.
- Árnyalás, wireframe, feature-edge overlay.

Információs overlay:
- objektumnév,
- egység,
- teljes méret,
- becsült felületi háromszögszám,
- topológiai állapot.

### 6.3 Paraméterpanel
Accordion vagy tab szekciók:

1. Geometria
- fájl kiválasztása,
- egység,
- scale,
- orientáció,
- javítási opciók.

2. Anyag
- preset lista,
- egyedi paramétermezők,
- anyagmagyarázó tooltippek.

3. Frekvencia
- start,
- stop,
- samples,
- sweep típus,
- referenciafrekvencia.

4. Gerjesztés
- monostatic / bistatic kapcsoló,
- azimuth,
- elevation,
- polarizáció,
- amplitúdó,
- gerjesztési forma.

5. Mesh és domén
- automatikus mesh kapcsoló,
- preset,
- expert override mezők,
- memória limit,
- PML preset.

6. Eredmény és export
- export célmappa,
- grafikonformátumok,
- mezőexport,
- animáció paraméterei,
- auto-save opciók.

Minden mezőhöz tartozik:
- validációs állapot,
- tooltip,
- ajánlott tartomány,
- alapértelmezett érték visszaállító ikon.

### 6.4 Eredménypanel tabstruktúra
Tabok:
- Geometria
- Mesh
- Futási állapot
- RCS vs frekvencia
- Polarizáció
- 3D RCS térkép
- 2D animáció
- 3D animáció
- Exportálás
- Napló/Hibák

### 6.5 Log és állapotpanel
Nézetek:
- rövid eseménynapló,
- részletes technikai log,
- figyelmeztetések,
- hibák,
- numerikus összefoglaló.

Példák:
- Geometry imported: watertight = false, 2 open edges detected.
- Mesh quality warning: 9.8 cells per wavelength at 18 GHz. Recommended minimum is 15.
- Estimated RAM: 28.4 GB, exceeds configured limit of 16 GB.

### 6.6 Fő vezérlőelemek
- Szimuláció indítása.
- Szünet / megszakítás.
- Mentés.
- Projekt mentése.
- Projekt betöltése.
- Eredmények exportálása.
- Animáció exportálása.
- Diagnosztika futtatása.

## 7. A fő felhasználói folyamat a fájlbetöltéstől az exportig

1. A felhasználó új projektet nyit.
2. Betölti a 3D geometriát.
3. A rendszer preview-ban megjeleníti, kiszámolja a bounding boxot, és egységmegerősítést kér.
4. A felhasználó kiválasztja vagy módosítja az anyagmodellt.
5. Beállítja a frekvenciasávot és a gerjesztést.
6. A szoftver automatikusan javasolja a mesh-t és a boxot.
7. A felhasználó megtekinti a Mesh tabban az automatikus hálót és a diagnosztikát.
8. A rendszer preflight ellenőrzést végez.
9. A felhasználó elindítja a szimulációt.
10. A futás közben látszik a progress, log és becsült hátralévő idő.
11. Futás után megjelennek az RCS grafikonok, polarizációs eredmények, 3D térképek, animációk.
12. A felhasználó interaktívan elemez, majd exportálja a szükséges adatokat.
13. A projekt teljes állapota elmenthető reprodukálható formában.

## 8. Eredmények és vizualizációk részletes terve

### 8.1 RCS vs frekvencia
Interaktív 2D grafikon:
- x tengely: frekvencia,
- y tengely: RCS $[m^2]$ vagy opcionálisan dBsm,
- több görbe támogatás,
- legendával polarizáció vagy szög szerint,
- crosshair kurzor,
- adatpont export,
- log/lin tengelykapcsoló.

### 8.2 Polarizációs eredmények
Megjelenítések:
- co-pol és cross-pol görbék,
- polar plot adott frekvencián,
- szórásdiagram szögfüggéssel,
- frekvenciaszelet választó.

### 8.3 Mesh nézet
- 3D structured mesh overlay.
- Szeletelt nézetek XY, XZ, YZ síkban.
- Lokális cellaméret színkódolással.
- Anyaghatár overlay.
- Kritikus cellák kiemelése.

### 8.4 3D RCS / visszaverési intenzitás térkép
Megjegyzés: az RCS fizikailag távoli téri mennyiség, ezért a geometriára vetített felületi színtérkép nem közvetlenül az RCS lokális definíciója, hanem egy származtatott vizualizáció. A GUI ezt egyértelműen címkézi például így:
- Surface scattering intensity proxy,
- Equivalent induced current magnitude,
- Backscatter contribution map.

Így elkerülhető a fizikailag félrevezető megjelenítés.

Támogatott felületi mennyiségek:
- indukált felületi áram sűrűség becslése,
- lokális visszaszórási hozzájárulás proxy,
- felületi E/H mező amplitúdó,
- reflektivitási indikátor választott frekvencián.

### 8.5 Futási állapot nézet
- pipeline lépések listája,
- aktuális lépés kiemelése,
- százalékos progress,
- hátralévő idő becslés,
- aktuális memória és lemezhasználat,
- solver iteráció/step kijelzés.

## 9. Animációk fizikai és vizuális megvalósítása

### 9.1 2D időfüggő animáció
Fizikai alap:
- valós időtartományi mezőadatok mintasíkban,
- vagy adott frekvenciás harmonikus mezőből fázissöpréses rekonstruált animáció.

Ajánlott megoldás:
- kiválasztható vágósíkban $E$ vagy $H$ mező komponensek megjelenítése,
- a beeső, szórt és teljes tér külön kapcsolható,
- időcsúszka vagy fázisszög csúszka.

Vizualizáció:
- színtérképes amplitúdó,
- opcionális kontúrok,
- objektum kontúr overlay,
- lejátszás/szünet/tekerés.

### 9.2 3D időfüggő animáció
Forrása:
- ritkított 3D mezőminták a szimulációs tartományban,
- izofelületek vagy szeletek,
- idő- vagy fázisfüggő frame generálás.

Megjeleníthető elemek:
- hullámfront szeletek,
- szórt mező amplitúdó felhő,
- objektum környezetében volumetrikus vagy szeletelt megjelenítés,
- reflexió és interferencia mintázat.

Fizikai korlát:
- a teljes 3D időanimáció extrém adatigényű lehet; a szoftver ezért preview és full export módot kínál.

### 9.3 Export
- MP4 H.264 ffmpeg-gel.
- GIF rövidebb demonstrációkhoz.
- Frame sorozat PNG-be.

## 10. Hibakezelés, validáció és naplózás

### 10.1 Validációs szintek
1. UI-szintű azonnali mezővalidáció.
2. Projekt-szintű konzisztenciaellenőrzés.
3. Numerikus preflight check.
4. Solver-futás közbeni monitorozás.
5. Post-run eredmény-megbízhatósági ellenőrzés.

### 10.2 Tipikus hibák és kezelésük
- Nem olvasható geometria: importhiba üzenet és formátumjavaslat.
- Nyitott vagy hibás háló: javítási lehetőség vagy futás tiltása.
- Hiányzó egység: kötelező megerősítés.
- Fizikailag irreális anyagparaméter: piros validáció.
- Túl durva mesh: sárga/piros figyelmeztetés.
- Túl nagy memóriaigény: becslés és alternatív javaslat.
- Solver divergence vagy idő előtti leállás: diagnosztikai összefoglaló.
- Gyanús eredmény: például negatív vagy zajdominált szakaszok esetén figyelmeztetés.

### 10.3 Naplózás
Log szintek:
- INFO,
- WARNING,
- ERROR,
- DEBUG,
- PHYSICS-CHECK.

Minden fontos log mellé metaadat:
- timestamp,
- pipeline lépés,
- modul neve,
- súlyosság,
- opcionális javasolt teendő.

## 11. Mentési/export formátumok

### 11.1 Projektfájl
Javasolt saját formátum: `.rcsproj`.

Tartalma:
- JSON vagy YAML alapú projektleíró,
- relatív vagy abszolút geometriahivatkozások,
- anyag-, mesh-, gerjesztés- és exportbeállítások,
- openEMS input generálási metaadat,
- verzió és kompatibilitási információ.

### 11.2 Numerikus eredmények
- CSV egyszerű görbékhez.
- JSON metaadatokhoz és kisebb adatcsomagokhoz.
- HDF5 nagy mezőadatokhoz és összetett strukturált eredményekhez.
- MAT opcionálisan MATLAB/Octave kompatibilitáshoz.

### 11.3 Grafikon és kép export
- PNG.
- SVG.
- PDF.

### 11.4 3D tudományos export
- VTK.
- VTU.
- HDF5.

### 11.5 Animáció export
- MP4.
- GIF.
- PNG sequence.

## 12. Moduláris szoftverarchitektúra

### 12.1 Rétegek
1. Presentation layer.
2. Application orchestration layer.
3. Domain / physics layer.
4. Infrastructure / I/O layer.

### 12.2 Fő komponensek

#### A. Fájlbetöltő és geometriafeldolgozó modul
Felelősség:
- 3D fájlok importja,
- topológiai tisztítás,
- mesh feature extraction,
- preview mesh előállítása.

#### B. Mértékegység és méretkezelő modul
Felelősség:
- egységkonverzió,
- skálázás,
- fizikai dimenziók egységes belső SI reprezentációja.

#### C. Anyagmodell-kezelő
Felelősség:
- preset könyvtár,
- paramétervalidáció,
- openEMS kompatibilis anyagleképezés.

#### D. Automatikus mesh és szimulációs box generátor
Felelősség:
- bounding box elemzés,
- lokális jellemzők felismerése,
- rács- és PML ajánlás,
- numerikus minőségbecslés.

#### E. openEMS input generátor
Felelősség:
- CSXCAD és solver input előállítás,
- gerjesztés és NF2FF konfiguráció,
- munkakönyvtár struktúra létrehozása.

#### F. Solver orchestration / futtatáskezelő
Felelősség:
- openEMS indítás,
- párhuzamos futások koordinációja,
- progress események,
- megszakítás és újraindítás.

#### G. Progress és log rendszer
Felelősség:
- pipeline állapotkövetés,
- log aggregáció,
- UI felé események szolgáltatása.

#### H. Utófeldolgozó RCS számító modul
Felelősség:
- mezőadatok betöltése,
- NF2FF számítás,
- RCS görbék, polarizációs bontás,
- minőségellenőrzés.

#### I. 2D/3D vizualizációs modul
Felelősség:
- grafikonok,
- 3D geometriák és mezők,
- kurzor alapú lekérdezés,
- többnézetes szinkronizálás.

#### J. Animáció generáló modul
Felelősség:
- frame generálás,
- preview és HQ render,
- ffmpeg export.

#### K. Export és fájlkezelő modul
Felelősség:
- állománystruktúra,
- exportpipeline,
- projektmentés és betöltés.

#### L. GUI vezérlőréteg
Felelősség:
- state binding,
- felhasználói műveletek orchestrationje,
- aszinkron műveletek és thread-safe UI frissítés.

## 13. Javasolt technológiai stack

### 13.1 Mag stack
- GUI: PySide6 (Qt6).
- Alkalmazásnyelv: Python 3.11 vagy újabb.
- Szimulációvezérlés: Python wrapper és openEMS parancssoros futtatás.
- Geometriafeldolgozás: trimesh, pyvista, numpy.
- STEP támogatás: pythonocc-core vagy CAD Assistant / gmsh alapú konverziós pipeline.
- 3D megjelenítés: PyVista + Qt interop, opcionálisan VTK natív widget.
- 2D grafikonok: PyQtGraph elsődlegesen, Matplotlib exporthoz opcionálisan.
- Adatformátumok: HDF5 h5py-vel, JSON.
- Animáció: ffmpeg integráció.
- Háttérfeladatok: Qt threads / QThreadPool / concurrent.futures.

### 13.2 Miért PySide6
- A felhasználó korábbi tapasztalata szerint jól működött.
- Modern Qt6 widget és docking támogatás.
- Stabil natív desktop érzet Windows alatt.
- Jó integráció PyVista/VTK és grafikon komponensekkel.

### 13.3 Miért PyVista/VTK
- Erős 3D tudományos megjelenítés.
- VTK export és tudományos formátumtámogatás.
- Könnyű mesh, slice és scalar field vizualizáció.

### 13.4 openEMS interfész stratégia
Elsődleges ajánlás:
- Python-orientált orchestration,
- openEMS input generálás dedikált Python modulból,
- szükség esetén Octave kompatibilis köztes generátor csak ott, ahol openEMS Python API hiányos.

## 14. Teljes adatfolyam a bemenettől a megjelenítésig

1. User Input Layer:
   - geometria,
   - anyag,
   - frekvencia,
   - gerjesztés,
   - export.

2. Validation Layer:
   - formai ellenőrzés,
   - fizikai ellenőrzés,
   - numerikus becslés.

3. Geometry Processing Layer:
   - import,
   - repair,
   - bbox,
   - feature extraction.

4. Simulation Preparation Layer:
   - egységkonverzió,
   - mesh,
   - domén,
   - PML,
   - source,
   - NF2FF setup.

5. Solver Execution Layer:
   - openEMS input,
   - run,
   - monitor.

6. Postprocessing Layer:
   - mezőbeolvasás,
   - RCS számítás,
   - derived data.

7. Visualization Layer:
   - 2D chart,
   - 3D scene,
   - animation timeline.

8. Export Layer:
   - images,
   - tables,
   - scientific files,
   - project state.

## 15. Pszedókód vagy komponensszintű működési vázlat

```text
MainWindow
  ├─ ProjectController
  ├─ GeometryPreviewWidget
  ├─ ParameterPanel
  ├─ ResultsWorkspace
  ├─ LogPanel
  └─ StatusBarController

ProjectController.load_geometry(path):
  geometry = GeometryImporter.load(path)
  geometry = GeometryRepair.clean(geometry)
  bbox = GeometryAnalyzer.compute_bbox(geometry)
  units = UnitResolver.resolve_with_user_confirmation(geometry, bbox)
  scaled_geometry = UnitConverter.apply_scale(geometry, units)
  preview_model = PreviewBuilder.build(scaled_geometry)
  ui.preview.show(preview_model)
  ui.parameters.seed_defaults_from_geometry(bbox)

ProjectController.prepare_simulation(config):
  ValidationService.validate_ui_config(config)
  feature_map = GeometryAnalyzer.extract_features(config.geometry)
  domain = DomainGenerator.propose(config.geometry, config.frequency, config.excitation)
  mesh = MeshGenerator.generate(config.geometry, feature_map, config.materials, domain, config.frequency)
  quality = MeshQualityEvaluator.evaluate(mesh, domain, config)
  if quality.blocking_issues:
      ui.show_blocking_issues(quality)
      return
  sim_input = OpenEMSInputBuilder.build(config, domain, mesh)
  ui.mesh_view.show(mesh)
  return sim_input

ProjectController.run_simulation(sim_input):
  run = SolverRunner.start(sim_input)
  while run.active:
      event = run.poll_event()
      ui.progress.update(event)
      ui.log.append(event)
  results = PostProcessor.collect(run.output_dir)
  rcs_data = RCSProcessor.compute(results)
  visual_data = VisualizationMapper.build(results, rcs_data)
  ui.results.present(rcs_data, visual_data)

ProjectController.export(selection):
  ExportManager.export(selection, current_project, current_results)
```

## 16. Olyan megoldások, amelyek biztosítják, hogy az eredmények fizikailag helyesek és numerikusan stabilak legyenek

### 16.1 Fizikai helyesség biztosítása
- Minden belső számítás SI egységekben történik.
- A GUI-ban megadott egységeket azonnal SI-re konvertáljuk.
- Az anyagparaméterekből effektív hullámhossz számítódik, és ezt használjuk a mesh ajánláshoz.
- A geometriára vetített színtérképeket nem nevezzük félrevezetően RCS-nek, ha valójában csak lokális proxy mennyiségek.
- Monostatikus és bistatikus definíciók szigorúan elkülönülnek.
- A polarizációs bázis egyértelműen dokumentált: incident frame, scattering frame, co-pol, cross-pol transzformáció.

### 16.2 Numerikus stabilitás biztosítása
- CFL feltétel automatikus ellenőrzése.
- Cella/hullámhossz minimum követelmény.
- Mesh grading korlátozása.
- PML minimális vastagság és távolság ellenőrzése.
- Nagy kontrasztú anyagoknál konzervatívabb mesh ajánlás.
- Nagyon vékony elemek esetén explicit jelzés: resolved / under-resolved / unresolved.
- Futás után energiakonvergencia és maradék oszcilláció vizsgálat.

### 16.3 Eredmény-megbízhatósági becslés
A rendszer minden eredményhez confidence jelzőt adhat:
- Mesh adequacy index.
- Domain adequacy index.
- PML risk index.
- Frequency resolution index.
- Runtime convergence score.

Az eredményoldalon rövid összefoglaló:
- Physics quality: Good / Acceptable / Low confidence.

### 16.4 Referencia és regressziós tesztek
A fejlesztés során kötelező referenciaesetek:
- PEC gömb Mie-régióban ismert referenciaértékekkel.
- Laplemez normál beesésben.
- Henger különböző polarizációkkal.
- Egyszerű diëlektromos test validáció irodalmi adattal.

Ezekből automatikus validációs csomag épül, amely minden release-nél fut.

## 17. Javaslat a későbbi bővíthetőségre

### 17.1 Funkcionális bővítések
- Több beesési szög batch futtatás.
- Paramétersöprés és DOE.
- Optimalizációs mód: minimális RCS keresés.
- Többtestes jelenetek.
- Réteges vagy kompozit anyagmodellek.
- Radarabszorbens anyag könyvtár.

### 17.2 Teljesítménybővítések
- Többfutásos párhuzamos scheduler.
- Távoli gépen futtatás.
- Klaszter vagy HPC integráció.
- GPU gyorsítás, ha a solver vagy utófeldolgozás támogatja.
- HDF5 chunking és lazy loading nagy mezőadatokra.

### 17.3 UX bővítések
- Project wizard kezdőknek.
- Expert mode haladó paraméterekkel.
- Eredmény-összehasonlító nézet két futás között.
- Automatikus riportgenerálás PDF-be.

## Ajánlott implementációs megjegyzések

### MVP határ
Az első megvalósítható, de szakmailag értelmes verzió tartalmazza:
- STL/OBJ import,
- egységkezelés,
- PEC és veszteséges dielektrikum,
- monostatikus RCS frekvenciasöprés,
- automatikus mesh/domain,
- RCS vs frekvencia grafikon,
- 3D preview,
- log és progress rendszer,
- projektmentés,
- alap export.

### Második fázis
- bistatikus mód,
- polarizációs bontás,
- fejlett 3D mezőtérképek,
- 2D/3D animáció,
- STEP pipeline,
- batch futtatás.

### Harmadik fázis
- optimalizáció,
- fejlett anyagmodellek,
- HPC/GPU,
- validációs dashboard,
- intelligens automatikus preset-ajánló.
