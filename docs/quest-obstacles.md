# Co-op W3: souhrnná zpráva o překážkách v questech

Tahle zpráva shrnuje 7 rešerší questů: prolog a Velen, Novigrad, Skellige, endgame, vedlejší obsah, HoS, B&W a mechaniky společné všem questům. Nic se neupravovalo a hra se nespouštěla. Všechny čtyři nahlášené chyby se vešly do níže popsaných tříd:

| Nahlášená chyba | Třída |
|---|---|
| Nesdílené zabíjení | A |
| Nefunkční revive | B |
| Ciri s Geraltovou hlavou | D |
| Esc zamrazí hru | K |

## 1. Třídy příčin a obecné opravy

**A. Smrt nepřítele se k Misu nepřenese (blocker, nahlášeno)**
- **Kde:** všechny questové souboje. Patří sem griffin a drowneři, botchling, Get Junior, divadlo, zahrada Vegelbudů, Reuvenův trezor, elementál v Kaer Trolde, Toad Prince, Ofieri Mage, Imlerith, Caranthir, Eredin, Dettlaff a kontrakty.
- **Proč:** host drží mrtvého nepřítele v seznamu jen asi 4 s (coopEnemies.ws ~776). Potom ReleasePuppet nebo Unsuppress vrátí lokální kopii nepřítele u Misu vlastní AI. Questový graf u Misu přitom čeká na smrt právě tohoto NPC.
- **Oprava:**
  - Trvalá množina „mrtvé u hosta“ (netId + tag/šablona + pozice spawnu), posílaná v každém snapshotu.
  - U Misu skutečný `Kill(..., true, thePlayer)`, i když je NPC questově nesmrtelné. Takové NPC už nikdy nepouštět přes Unsuppress.
  - Když nepřítel uteče, zmizí nebo změní postoj, poslat „pacify/despawn“ místo „release“.
  - Questové bosse neuvolňovat po 80 m ani po 10 s.
  - Pokud Misu kopie nepřítele chybí, spawnout ji z hostovy šablony.
- Pracnost S–M, riziko nízké.

**B. Down a revive se nepřenášejí (blocker, nahlášeno)**
- **Oprava:**
  - Stav „down“ posílat jako samostatnou síťovou zprávu se sekvenčním číslem a potvrzením (ACK).
  - Puppet ležícího hráče přehraje animaci a nabídne revive. Revive proběhne přes síť.
  - Nepřátelé ležícího hráče ignorují. Odpočet do smrti stojí, dokud partner žije. Po konci boje se hráč oživí automaticky.
  - Logiku přesunout do CR4Player, aby pokryla i Ciri.
  - Vypnout ji ve fistfightech a při skriptované porážce (Blood Run).
- Pracnost M, riziko střední.

**C. Questový graf u Misu se zasekne (největší třída)**
- **Kde:** prolog v Kaer Morhen, Imperial Audience, Destination: Skellige, Isle of Mists, Ugly Baby, Through Time and Space, Tedd Deireadh, loď Ofieri, Dead Man's Party, malovaný svět, O'Dimova říše, příjezd do Toussaintu, Země tisíce bajek, Night of Long Fangs.
- **Proč:** synchronizace faktů a deníku jen dopředu neposune uzly, které čekají na scénu, trigger, interakci nebo lokální smrt.
- **Oprava (checkpoint resync):**
  - Host vynutí autosave při změně světa questem, při úspěchu fáze hlavního questu, při konci scény se skokem o víc než 30 m a po zabití bosse.
  - Misu načte přesně tento soubor. Leash stojí, dokud se nenačte.
  - Když host načte save sám, Misu načte stejný soubor (ne „nejnovější“) a jednou se jí dovolí i snížit fakty.
  - Teleport hosta po scéně Misu následuje okamžitě.
- Pracnost M–L, riziko střední (dlouhé loady, save uložený uprostřed Ciri segmentu).

**D. Výměna postavy a vzhled (blocker, nahlášeno)**
- **Misu vzhled:** mechanicky zůstane Geralt. Hlavu a vlasy odmountovat a trvale skrývat. Hra je znovu nasazuje po scéně, holení nebo změně zbroje, proto znovu aplikovat po každé scéně a loadu. Připojit Ciri appearance a puppet u hosta stavět ze šablony Ciri.
- **Host hraje jako Ciri (flashbacky Velen/Novigrad/Lofoten, bitva o KM, Bald Mountain, On Thin Ice, posednutí Vlodimirem):**
  - Poslat šablonu postavy puppetu.
  - Misu přepnout do spectator režimu (skrytá, nesmrtelná, kamera na hostu, leash vypnutý).
  - Jejímu grafu zakázat přepnutí na Ciri.
  - Její postavu nikdy neaplikovat do savu, kde se hraje za Ciri.
- Pracnost M, riziko střední až vysoké (odložený Geraltův inventář).

**E. Zásah od Misu obrátí neutrální NPC proti hostovi (blocker)**
- **Kde:** Vesemir, stráže v Crow's Perch, Zoltan, Lambert a Triss v bitvě o KM, svatebčané, rukojmí, Crach, stráže v Beauclair, ušetřený troll.
- **Oprava:** přeposílat jen zásahy na NPC, která jsou u hosta už nepřátelská. Pravidlo „neutrální se změní na nepřátelské“ zrušit.
- Pracnost S, riziko nízké.

**F. Exkluzivní volby (v dialogu i činem)**
- **Kde:** Whispering Hillock, botchling, Keira, Junior, Triss, Dudu, volby o osudu Ciri, Syanna.
- **Oprava:**
  - V questových dialozích a u objektů, kterými se volí, smí Misu jen přihlížet, pokud host není ve stejném dialogu.
  - Exkluzivní fakty zrcadlit přesně, tedy i směrem dolů.
- Pracnost S–M, riziko nízké.

**G. Questové předměty a stopy**
- **Kde:** lampa, Maska Uroborose, návnada z rakytníku, maska a pozvánka k Vegelbudům, klíče, stužky v Bajkách, poznámky k scavenger hunts.
- **Oprava:**
  - Zrcadlit přidání a odebrání předmětů s tagem Quest od hosta k Misu.
  - Zrcadlit prozkoumané stopy u focus clue entit.
- Pracnost S–M, riziko nízké.

**H. Pohyb: lodě, podzemí, voda**
- **Oprava:**
  - Teleportovat k hostovi i pod 80 m, když k němu nevede navmesh cesta, výškový rozdíl je přes 4 m nebo se Misu 10 s nepřibližuje.
  - Cíl teleportu nikdy nesmí být ve vodě ani bez země pod nohama.
  - Režim lodě: Misu jako pasažér, nebo pauza leashe a teleport na místo přistání.
  - Klávesa „teleport k hostovi“.
  - 3 s nesmrtelnosti po každém teleportu.
- Pracnost M, riziko nízké.

**I. Minihry (fistfighty, závody, Gwent, turnaj)**
- **Oprava:** po detekci minihry se Misu stane divákem. Její zásahy se nepřeposílají, zdraví nepřátel je ×1.0 a down/revive je vypnutý, takže platí vanilla prohra.
- Pracnost S, riziko nízké.

**J. Neviditelní společníci a eskorty**
- **Kde:** Vesemir, Baron, Keira, Johnny, Zoltan, Regis, Syanna, Hjalmar.
- **Oprava:** zrcadlit je jako puppety (pozice + animace). Misu lokální kopie skrýt a zamknout.
- Pracnost M, riziko nízké.

**K. Pauza (Esc, menu, tutoriály), nahlášeno**
- **Oprava:**
  - V co-opu hru nepauzovat: jen zablokovat vstup a hráč je v menu nesmrtelný.
  - Síťový tick běží dál.
  - Když je nastavený flag pauzy, neuvolňovat puppety kvůli starému snapshotu.
  - Tutoriály Misu vypnout.
- Pracnost S–M, riziko střední.

## 2. Blockery, které potřebují vlastní opravu

- **Prolog v Kaer Morhen:** co-op vypnout, Misu se připojí z prvního autosavu v White Orchard.
- **Isle of Mists:** ostrov nemá signposty a trpaslíci ukradnou loď. Vynutit resync při příjezdu i při odchodu.
- **Evil's Soft First Touches:** zajetí na lodi Ofieri a ztroskotání. Misu je po tu dobu spectator na bezpečném místě na pevnině, resync proběhne po ztroskotání, ještě před Ofieri Mage.
- **Blood Run:** skriptovaná porážka od Dettlaffa se srazí s pádem na 1 HP.
- **Bitva o Kaer Morhen:** Misu bomby a Yrden musí zavírat portály, kratší leash, ochrana spojenců.
- **Through Time and Space:** řetěz portálů a poškození prostředím.
- **On Thin Ice:** Caranthirův teleport do moře a přesun do Eredinovy arény. Pád do vody má být down, ne smrt.
- **Bald Mountain:** kouzlo babiček jde zlomit jen Ciri Blinkem, na vrcholu hrozí smrtelný pád.
- **Scenes From a Marriage:** dveře mezi vzpomínkami v malovaném světě a Caretaker, který se zásahy léčí.
- **Dead Man's Party:** posednutí a rvačka u prasat.
- **Konec hry:** fakty o osudu Ciri zrcadlit přesně, od Tedd Deireadh je Misu spectator, po titulcích resync.
- **Odměny:** unikátní Gwent karty, body z Places of Power, mutace a runewordy. Doplnit je do Misu profilu, nebo je vyřadit ze zrcadlení.

## 3. Doporučené pořadí

1. **A + E:** sdílené zabíjení a zrušení pravidla neutrální→nepřátelský. Bylo to nahlášené, je to levné a odblokuje to většinu soubojů.
2. **B + I:** down/revive přes síť, včetně výjimek pro fistfighty a skriptovanou porážku.
3. **K:** Esc bez pauzy.
4. **D, vzhled Misu:** skrýt Geraltovu hlavu.
5. **C + H:** checkpoint resync, při reloadu stejný save jako host, chytřejší leash a režim lodě. Je to nejvíc práce, ale bez toho se neprojde Isle of Mists, Kaer Morhen ani DLC.
6. **D (Ciri segmenty) + F:** spectator při výměně postavy a zámek voleb.
7. **G, J:** questové předměty a společníci.
8. **Blockery ze sekce 2:** v pořadí, v jakém je budete hrát (HoS → Velen → Novigrad → Skellige → endgame → B&W).