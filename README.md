# Mousetrap Manager

Mousetrap Manager er en Home Assistant-integrasjon for overvåking og historikk for musefeller.

**Versjon 2026.11.26. Testet med Home Assistant 2026.10.4 og 2026.11.2.**

## Arbeidsflyt

1. Aqara DJT12LM/T1 publiserer `action: movement` gjennom Zigbee2MQTT.
2. Integrasjonen lagrer én ventende kontrollhendelse. Kortet viser **Må kontrolleres**. Bevegelse alene teller aldri som fangst.
3. Kontroller, tøm ved behov, spenn opp og sett fellen tilbake.
4. Velg **Bekreft fangst** (+1) eller **Falsk alarm** (ingen telling).
5. En konfigurerbar sperretid, som standard 30 sekunder, demper håndteringsbevegelse etter kvittering.

Samme hendelse kan ikke bekreftes to ganger. Dette håndheves på serveren, også fra flere skjermer og etter restart. Ved feilbetjening finnes **Angre siste fangst** under integrasjonens konfigurasjon. Kortet har ingen angreknapp.

**Mobilvarsling brukes ikke.** Valgfrie varsler i Home Assistants innebygde varslingspanel er avslått som standard. Hovedbryteren kan slå alle varsler helt av. Bevegelsesvarsler kan slås av separat, slik at bare periodiske inspeksjonsvarsler brukes. Nye rystelser mens kontroll venter oppretter ikke flere alarmer.

## Installasjon med HACS

Repositoriet er offentlig og kan legges til som et egendefinert HACS-repositorium. Det er ikke nødvendig at det ligger i HACS' standardliste.

1. Åpne HACS → menyen ⋮ → **Egendefinerte repositorier / Custom repositories**.
2. Legg til `https://github.com/stboee/ha-mousetrap-manager` med type **Integrasjon / Integration**.
3. Finn Mousetrap Manager i HACS og last ned ønsket release. Kortet følger med integrasjonen.
4. Start Home Assistant på nytt og følg oppsettet nedenfor.

HACS støtter ikke private repositorier. Hvis en egen kopi gjøres privat, må den installeres manuelt.

## Manuell installasjon

Den publiserte releasen tilbyr et ferdig installasjonsarkiv. Pakk det ut i en midlertidig mappe og kopier hele `mousetrap_manager` til `<HA-konfigurasjon>/custom_components/`. Full kildekode er også tilgjengelig i GitHubs kildearkiver.

Alternativt lastes kildekoden fra ønsket versjon. Kopier hele mappen:

`custom_components/mousetrap_manager` → `<HA-konfigurasjon>/custom_components/mousetrap_manager`

Ikke bare kopier Python-filene: `frontend`, `translations`, `manifest.json` og `services.yaml` skal følge med. Ingen nøkler eller GitHub-passord skal legges i integrasjonens konfigurasjon.

## Første oppsett

1. Start Home Assistant på nytt etter installasjon.
2. Legg til **Mousetrap Manager** under Innstillinger → Enheter og tjenester.
3. Åpne integrasjonens konfigurasjon → **Feller → Legg til klappfelle**.
4. Velg Aqara-sensorens MQTT-enhet, et fellenavn og nøyaktig MQTT-topic. For den første kjente sensoren er topic `zigbee2mqtt/Vibrasjon`.
5. Legg til denne dashboardressursen som **JavaScript-modul** under Innstillinger → Dashboards → Ressurser (avansert modus kan være nødvendig):

`/mousetrap_manager/mousetrap-manager-card.js?v=2026.11.26`

6. Last nettleseren/Companion-appen på nytt og legg til **Mousetrap Manager Card**. Kortet finner alle aktive feller automatisk, også feller som legges til senere.

Ingen ekstra hjelpere per felle trengs. `hacs.json` beskriver integrasjonen; kortet følger integrasjonspakken.

### Oppgradering fra 0.1.x–0.5.x

Oppdater gjennom HACS eller erstatt hele integrasjonsmappen med den nye versjonen. Behold integrasjonen og `.storage`-dataene; ikke slett oppsettet. Start HA på nytt, endre dashboardressursens versjon til `?v=2026.11.26` og last nettleseren/appen på nytt. Registrerte feller, ventende kontroll og fangsthistorikk videreføres. Tidligere arkiverte feller vises som **Sesongpause**. Fra denne utgivelsen bruker vi versjonsformatet `ÅÅÅÅ.MM.DD` basert på publiseringsdatoen. Tidligere fangstbekreftelser og falske alarmer gir sitt faktiske tidspunkt som siste inspeksjon. Ved oppgradering fra 0.1.x er åtebytte og sensorkontakt ukjent til de registreres. Tidspunkter og vedlikehold som allerede er registrert i 0.2.x beholdes.

## Kort og felles oppsett

```yaml
type: custom:mousetrap-manager-card
```

Feller i bruk vises automatisk i fullvisningen, med tydelig merking av testfeller. Under **Kort og tilsyn → Fullvisning** velger du tittel, sortering, maksimalt antall kolonner, oppsummering, illustrasjoner og verdier. Under hver felle kan du beholde felles visning eller gi fellen egne innstillinger. Layouten tilpasser seg skjermbredden. Et tomt plasseringsfelt bruker kildeenhetens HA-område.

Tidligere YAML-valg for navn, roller, handlinger, visning og et fast `traps`-utvalg brukes ikke lenger. Eksisterende kort viser en forklaring og følger det sentrale oppsettet; forenkle YAML som ovenfor. Dette er en bevisst endring fra 0.3.0. HAs egne `grid_options` og `visibility` kan brukes i tillegg til korttype og visningsmodus. Fullvisning og tilsyn kan brukes samtidig; øvrige visningsvalg styres i integrasjonen. Flere ulike oppsettsprofiler støttes ikke nå. Fullvisningen støtter klappfeller og Victor M1.

Store statusoverskrifter og tydelige symboler står øverst. Aktiv overvåking viser en oppspent snap-felle uten mus. Bevegelse viser en utløst felle med spørsmålstegn. **Overvåking aktiv** betyr at programvaren overvåker; vibrasjonssensoren kan ikke bevise fysisk armering. Integrasjonens ikon bruker lokalt medfølgende `mdi:rodent`.

**Felleillustrasjon** velges ved registrering eller under **Konfigurer → Feller → Velg og administrer felle → Navn, sensor og vedlikehold**.

- **Klassisk klappfelle** – dagens illustrasjon og standard for eksisterende feller.
- **Rapp 2** – mørk, innkapslet klappfelle.
- **Biltema Giljotin** – lys giljotinfelle med ventilasjonsspor og metallfjær.

Valget gjelder bare utseendet og lagres per felle i integrasjonen. Det vises likt på PC og mobil. Alle tre overvåkes som vibrasjonsfeller med de samme kontrollhandlingene. Du kan bytte illustrasjon uten å opprette fellen på nytt; felle-ID, fangster, åtehistorikk, inspeksjon og ventende kontroll beholdes. Hver modell har bilder for overvåking, kontrollbehov, inspeksjon og utilgjengelig sensor. Statusen står fortsatt med stor tekst i kortets topp. Victor M1 beholder sin egen grafikk. De nye SVG-illustrasjonene er tegnet etter produktbildene som formreferanser; fotografiene distribueres ikke.

Oppsummeringen holder felletypene adskilt og viser bare registerets **Snap-fangster**, inkludert registrerte driftsfangster fra feller på sesongpause eller feller fjernet med historikk. Hver Victor-felle viser sine egne kildeverdier. Det beregnes ingen felles Snap-/Victor-sum eller ny Victor-sum.

Hendelsesloggen har **Driftslogg** og **Testlogg**. Begge kan filtreres per felle, også for feller som er fjernet med historikken i behold. Den lagres på serveren, ikke i nettleseren. Vedlikehold ligger sammenfoldet i normaltilstand og vises med kontrollhandlingene når det trengs.

## Kompakt tilsynskort på startsiden

Fra 0.4.0 har samme customkort to visninger. **Fullvisning** beholdes på Musefeller-fanen. **Tilsyn** er en liten liste uten felleillustrasjoner, måleverdier, kvitteringsknapper eller hendelseslogg. Den viser bare feller som trenger oppmerksomhet, med navn og konkrete årsaker. Ett trykk åpner fullvisningen. Den passer i én murverkskolonne.

1. Oppdater hele integrasjonen til 2026.11.26 og start HA på nytt. Bruk ressursen med `?v=2026.11.26`, og last nettleseren/appen på nytt. Fjern eventuelle eldre ressursoppføringer som laster en annen kopi av samme kort.
2. Åpne **Konfigurer → Kort og tilsyn → Tilsyn på startsiden**. Velg hvilke årsaker som skal vises. Standard: meldt Victor-fangst, ventende snap-kontroll, inspeksjonsfrist og utilgjengelig kilde/ukjent Victor-status. Gammel/ukjent sensorkontakt og lavt batteri kan slås på separat og bruker de eksisterende tersklene.
3. Legg inn adressestien til din Musefeller-fane, for eksempel `/lovelace/musefeller` eller `/dashboard-hjem/musefeller`. Bruk stien fra din egen adresse; en ny fane opprettes ikke automatisk. Tomt felt er tillatt under oppsett og gir en forklaring i kortet.
4. Legg til et nytt **Mousetrap Manager**-kort på startsiden. Velg **Tilsyn på startsiden** i korteditoren. Editorens standardvalg setter opp HAs betingede synlighet med den faktiske tilsynsentiteten. Andre synlighetsbetingelser beholdes.

Integrasjonen oppretter én felles binærsensor **Mousetrap Manager Tilsyn nødvendig** automatisk. Standard-ID er `binary_sensor.mousetrap_manager_tilsyn_nodvendig`; bruk ID-en som vises i korteditoren hvis du har omdøpt entiteten. Ingen hjelpere eller lister per felle må vedlikeholdes. Ordinære feller i bruk tas med automatisk. Feller på sesongpause og testfeller holdes utenfor.

Ved YAML-oppsett brukes:

```yaml
type: custom:mousetrap-manager-card
mode: attention
visibility:
  - condition: state
    entity: binary_sensor.mousetrap_manager_tilsyn_nodvendig
    state_not: "off"
```

Denne synlighetsbetingelsen fjerner hele kortet fra HA-layouten ved normal drift. Bruk **ikke av**, slik at `unknown` og `unavailable` fortsatt viser en feil. Det er ikke tilstrekkelig å bruke en betingelse som bare viser kortet når sensoren er `on`. Det er HAs betingede synlighet som sørger for at kortets plass i murverk fjernes. Uten denne betingelsen kan kortet brukes som en alltid synlig, kompakt statusvisning. Normalstatus kan vises i editoren for å gjøre kortet redigerbart.

Fullvisningen bruker fortsatt:

```yaml
type: custom:mousetrap-manager-card
```

Fangst prioriteres før kontrollbehov, deretter inspeksjon og kilde-/helseproblemer. En felle med flere årsaker får én rad med alle årsakene og telles én gang. Antallet er **feller som trenger tilsyn**, ikke en ny fangsttotal. Tilsynsvalgene er uavhengige av HA-varsler og mobilvarsling; eksisterende varsler forblir avslått som standard.

Tilsynsstatus, ferdige tekster, sortering og årsaksvalg beregnes i integrasjonen. Kortet filtrerer ikke feller eller tolker sensorer selv. Hvis tilsynsentiteten er borte, utilgjengelig, gjenopprettet eller har et ukjent dataformat, viser kortet en feil fremfor å bruke gamle fangstopplysninger. Native synlighetsbetingelser som du legger til selv kan begrense når kortet er synlig.

Korteditoren viser nå versjonsnummeret. For teknisk kontroll kan `customElements.get("mousetrap-manager-card").getVersion()` kjøres i nettleserkonsollen.

## Victor Smart-Kill Wi-Fi M1

Installer og konfigurer [Victor-integrasjonen](https://github.com/toreamun/victorsmartkill-homeassistant) først. Velg deretter **Mousetrap Manager → Konfigurer → Feller → Legg til Victor M1**, og velg eksisterende Victor-enhet. Entitetene finnes automatisk via kildeintegrasjonens stabile identifikatorer, også etter omdøping av entitets-ID. Bruk **Victor-entiteter (avansert)** under den enkelte fellen hvis en eldre variant trenger manuelle kilder.

Kortet leser eksisterende `capture`, `kills_present`, `total_kills`, `last_kill_date`, `last_report_date`, `battery_level` og `wireless_network_rssi`. Temperatur, escapes og retreats brukes ikke. Kildeverdiene kopieres ikke til nye tellersensorer, og det lages ingen ny API-klient eller innlogging. Gammel Victor-fangsthistorikk importeres ikke. Ingen ekstra langtidsstatistikk tilrettelegges for Victor.

Normalstatus er **Ingen fangst meldt**; dette beviser ikke fysisk armering. **Fangst meldt** følger Victor-kilden. **Inspeksjon utført** og **Åte byttet** registrerer bare vårt vedlikehold og endrer verken fangststatus eller teller hos Victor. Kortet tilbyr derfor ikke Bekreft fangst/Falsk alarm for Victor. Vedlikeholdsentitetene samles på en egen registerenhet med kobling til eksisterende Victor-enhet; kildeentitetene beholdes. HA 2026.10 har separate enhetsoppføringer per integrasjon.

De godkjente M1-illustrasjonene viser normaltilstand, meldt fangst, inspeksjonsfrist og utilgjengelig kilde. Ukjent kildestatus vises som ukjent, aldri som ingen fangst.

## Innstillinger

| Meny | Hva den styrer |
|---|---|
| **Feller** | Registrering, oppsett per felle, sesongpause, test, fjerning og angring av siste driftsfangst. |
| **Varsler i Home Assistant** | Hovedbryter og felles standarder for varselpanelet. Hovedbryteren er av som standard. |
| **Kort og tilsyn** | Felles oppsett for fullvisningen og årsaker og lenke for tilsyn på startsiden. |
| **Driftsinnstillinger** | Sperretid for nye vibrasjoner, felles grenser for batteri og kontakt og gjenoppretting av Victor. |

Under **Feller → Velg og administrer felle** ligger fellens inspeksjonsintervall og valg for åtealder under **Navn, sensor og vedlikehold**. Under **Varsler for denne fellen** kan du velge **Følg felles standard**, **På** eller **Av** for hver varslingstype. Tidligere lagrede inspeksjonsvarsler beholdes som valg for den enkelte fellen. Testfeller og feller på sesongpause vises ikke i tilsynskortet og gir ikke HA-varsler. Vibrasjonsovervåking i ordinær drift kan gi kontrollbehov i kortene selv om HA-varselet for bevegelse er av.

### Sesongpause, test og fjerning

| Handling | Virkning |
|---|---|
| **Sett på sesongpause** | Stanser oppfølging og skjuler fellen fra kortene. Oppsett og historikk beholdes. Avklar eventuell ventende kontroll først. |
| **Ta i bruk igjen** | Klargjør fellen før du bekrefter. Inspeksjon registreres, og eventuell ny frist regnes fra klargjøringen. Kryss av hvis du også byttet åte. |
| **Gjør til testfelle** | Nye hendelser går til testloggen. Tidligere driftshistorikk beholdes som standard. Du kan velge å flytte hele den gamle loggen til test hvis den bare inneholder prøver. |
| **Ta i ordinær bruk** | Nye hendelser registreres i driftsloggen. Tidligere testhendelser forblir tilgjengelige i testloggen. |
| **Nullstill testfelle** | Sletter testhendelser og nullstiller testfangster, kontrollstatus og registrert vedlikehold. Oppsett og eventuell tidligere driftshistorikk beholdes. |
| **Fjern felle, behold historikk** | Fjerner fellen fra oppsettet og frigjør kilden til gjenbruk. Tidligere hendelser og fangster er fortsatt tilgjengelige i logg og teller. |
| **Slett felle og historikk** | Sletter hendelsene i Mousetrap Manager. Fellens bekreftede driftsfangster trekkes fra den samlede klappfelletelleren. Dialogen viser antallet før bekreftelse. |

Sletting og nullstilling gjelder lagringen i Mousetrap Manager. Eksisterende data i Home Assistant Recorder, Zigbee2MQTT og Victor-integrasjonen håndteres av de respektive systemene. Victor-fangster kommer fra Victor-integrasjonen og kan ikke nullstilles gjennom Mousetrap Manager.

**Angre siste driftsfangst** under **Feller** krever bekreftelse av den aktuelle registreringen. Telleren reduseres én gang, og det logges at fangsten ble annullert. Gjeldende kontrollstatus beholdes.

## Åte og periodisk inspeksjon

Hver felle får egne entiteter for **Åtealder**, **Åte sist byttet**, **Sist inspisert**, **Tid siden inspeksjon**, **Neste inspeksjon** og **Inspeksjon nødvendig**. Aldre er antall hele 24-timersdøgn. Tidspunktene lagres i UTC og vises av HA i lokal tid. Ukjent dato vises som ukjent, ikke som nytt åte eller nylig inspisert felle.

- Velg **Vis åtealder i kortet** per felle. Dette skjuler/viser åtealderen og den tilhørende kortknappen; lagrede data beholdes.
- **Åte byttet** vises sammen med kontrollhandlingene ved bevegelse eller påkrevd periodisk inspeksjon. Handlingen nullstiller åtealderen og logges, men kvitterer ikke bevegelse eller inspeksjon. Klargjør fellen og kvitter kontrollen etterpå.
- **Inspeksjonsintervall** velges per felle i dager. `0` slår av den periodiske fristen. Før første registrerte inspeksjon regnes fristen fra fellens registreringstidspunkt; deretter fra siste inspeksjon.
- Når fristen passeres, vises **Tid for inspeksjon** og knappen **Inspeksjon utført**. Knappen registrerer at fellen og åtet er inspisert og fellen klargjort. Åtealderen endres ikke.
- Ved ventende bevegelse brukes **Bekreft fangst** eller **Falsk alarm**. Begge registrerer også inspeksjon, fjerner inspeksjonsvarselet og starter neste periode. En egen inspeksjonsknapp kan ikke omgå den ventende kontrollen.
- **Åte byttet** og **Inspeksjon utført** finnes også som knappeentiteter på fellens enhetsside. Ingen av dem gir fangst. Arkiverte feller overvåkes ikke for inspeksjonsfrist.

En bakgrunnsoppdatering i HA kontrollerer frister og aldre hvert minutt, uavhengig av kortet. Inspeksjonsvarsling er avslått som standard og velges per felle. Ett stabilt varsel opprettes per overskredet frist; det kommer ikke et nytt ved hver bakgrunnsoppdatering. En avvist melding blir ikke gjenopprettet ved neste minutt, men en HA-restart kan gjenopprette det samme uavklarte varselet.

## Siste sensorkontakt

Hver snap-felle får entiteten **Siste sensorkontakt**. Victor bruker sin eksisterende **Last report date**. Kortet viser hvor gammel kontakten er. For snap-feller er kilden Zigbee2MQTTs `last_seen`, som må aktiveres der, eksempelvis:

```yaml
advanced:
  last_seen: ISO_8601
```

Se [Zigbee2MQTTs innstillinger](https://www.zigbee2mqtt.io/guide/configuration/all-settings.html). Legg valget inn i en eventuell eksisterende `advanced`-seksjon. Meldinger uten gyldig `last_seen` gir ikke et oppdiktet kontakttidspunkt. Batteri- og andre rapporter kan oppdatere kontakt uten bevegelse. Gamle meldinger og retained-meldinger bruker sitt opprinnelige tidspunkt; retained bevegelse utløser aldri en ny kontroll. Vanlig HA-oppdatering eller restart teller ikke som sensorkontakt.

Siste sensorkontakt og siste bevegelse er forskjellige opplysninger. Kontakttidspunktet beviser heller ikke at fellen er mekanisk armert. **Driftsinnstillinger → Felles grenser for batteri og sensorkontakt** har terskler for gammel kontakt (standard 24 timer) og overskredet kontaktfrist (72 timer). 0 slår den aktuelle terskelen av. Velg realistiske verdier for sensorens rapporteringsintervall. Gammel rapportering merkes separat fra en kildeintegrasjon som faktisk er utilgjengelig. Batteriterskelen er som standard 20 %. Per-felle-overstyring er mulig. Varsler for kontakt og batteri kan velges under **Varsler i Home Assistant** eller for den enkelte fellen, med felles hovedbryter som overstyrer.

## Victor – automatisk gjenoppretting

Dette er et valgfritt tillegg for en **eksisterende Victor Smart-Kill-integrasjon**. Det oppretter ingen ny Victor-tilkobling og krever ingen ekstra innlogging. Funksjonen er avslått som standard og kjører på HA-serveren uten åpent dashboard.

Åpne **Mousetrap Manager → Konfigurer → Driftsinnstillinger → Victor – automatisk gjenoppretting**:

1. Velg den eksisterende Victor-integrasjonen/kontoen og aktiver funksjonen.
2. Velg hvor lenge den skal være sammenhengende utilgjengelig før reload. Standard er **20 minutter**, område 1–1440 minutter.
3. Velg minste tid mellom reload-forsøk. Standard er **60 minutter**, område 5–1440 minutter.
4. Velg maksimalt antall forsøk per feilperiode. Standard er **3**, område 1–10.

Kontrollen ser på entitetene som faktisk tilhører den valgte Victor-oppføringen i HAs entitetsregister. En lastet oppføring må ha observerte, aktive entiteter som alle er `unavailable`. En kjent fungerende entitet gjør at oppføringen regnes som tilgjengelig. Én utilgjengelig felle eller gammelt `last_report_date` alene utløser derfor ikke reload. `unknown`, manglende entiteter og gjenopprettede plassholdere er ikke tilstrekkelig bevis på en feil. En oppføring med status `setup_error` kan også forsøkes gjenopprettet etter ventetiden.

Ved ny innlogging, deaktivering, manuell utlasting, pågående oppstart/utlasting eller HAs egne `setup_retry`-forsøk griper funksjonen ikke inn. Etter HA-oppstart begynner observasjonstiden på nytt. Forsøksantall og tidspunkt for siste forsøk lagres før reload og bevares ved restart, slik at restart eller endring av andre innstillinger ikke omgår forsøksgrensen eller sperretiden.

En faktisk tilgjengelig entitet nullstiller forsøksantallet for feilperioden; sperretiden siden siste reload beholdes. Hvis forsøksgrensen er nådd mens feilen fortsetter, stopper automatiske reload-forsøk. Du kan velge **Nullstill lagret antall forsøk** i samme skjema for en ny forsøksrunde. Dette nullstiller ikke sperretiden. En pågående reload får fullføre dersom Mousetrap Manager lastes om eller funksjonen deaktiveres.

Diagnostikkentiteten **Victor automatisk gjenoppretting** viser status, antall forsøk, siste forsøk og resultat. Faktiske reload-forsøk og feil skrives også i HA-loggen. Ingen mobilvarsler eller nye HA-varsler opprettes av denne funksjonen. Reload kan hjelpe en hengende forbindelse; et pågående eksternt driftsavbrudd eller ugyldig innlogging må fortsatt løses ved kilden.

## Lagring, historikk og statistikk

Integrasjonen skriver registeret gjennom Home Assistants `Store` til `.storage/mousetrap_manager.<entry-id>`. Lagret kontrollstatus, sperretid, fangster og annulleringer leses før entitetene opprettes. Integrasjonen kjører uten åpne dashboards. Alle skjermer leser samme HA-entiteter.

Snap-fangstteller per felle og Snap-telleren er numeriske sensorer med `state_class: total`. De kan gå ned ved angring. Med Recorder aktiv og sensorene inkludert i opptaket kan HA samle langtidsstatistikk. En angring, sletting eller flytting av eldre driftsfangster til test kan gi et fall i grafen på endringstidspunktet. Tidligere statistikkperioder i Recorder beholdes. Testfangster vises per testfelle i fullvisningen og inngår ikke i de ordinære fangsttellerne.

**Klappfeller i bruk** og **Victor-feller i bruk** er egne sensorer med `state_class: measurement`. De teller ordinære feller som er satt ut, også om en kilde midlertidig er utilgjengelig. Recorder bygger statistikk over antall aktive feller fra oppgraderingen.

Detaljloggen lagres i vårt register uavhengig av Recorders vanlige historikkopprydding. Ingen automatisk sletting av fangsthendelser er konfigurert i denne versjonen. Ta vanlig HA-sikkerhetskopi som inkluderer konfigurasjonsmappen og `.storage`. En sikkerhetskopi av bare dette Git-repositoriet inneholder ikke fellenes driftsdata. Fjerning av selve integrasjonen er en annen handling enn å sette en felle på sesongpause; behold sikkerhetskopi ved reinstallasjon.

## Sensorstøtte og grenser

Første registreringsvei bruker Zigbee2MQTT/MQTT med `action: movement`, verifisert mot den kjente Aqara DJT12LM/T1-datamodellen. `shake` og `triple_strike` tolkes ikke automatisk som fangsthendelser. Retained MQTT-handlinger ignoreres for å unngå gamle alarmer etter tilkobling.

En melding som oppstår mens Home Assistant/MQTT er ute av drift kan gå tapt. Dette er overvåking av en mekanisk felle, ikke en garanti for registrering av enhver fysisk utløsning. Dørslag kan utløse en vibrasjonssensor; plassering og følsomhet må prøves fysisk.

## Utvikling og tester

Backend, med Python 3.14:

```sh
python -m pip install homeassistant==2026.10.4 paho-mqtt==2.1.0 pytest pytest-asyncio
python -m pytest -q
```

Frontend:

```sh
npm ci
npx playwright install chromium
npm test
```

Kjør gjerne med `CHROME_PATH` satt til en installert Chromium. Frontendtestene dekker også kompakt tilsyn, synlighet, feilstatus og editorens oppsett av native HA-betingelser. De dekker protokollen mot integrasjonen, blandet Snap-/Victor-visning, automatisk visning av feller og sesongpause, handlinger, kildelesing, mobilbredde, logg og syntaks.

Begge leverte kopier av kortfilen skal være identiske: `dist/mousetrap-manager-card.js` og filen i integrasjonens `frontend`-mappe.

## Fysisk akseptansetest før ordinær bruk

1. Kontroller at varsling står av, og at en testbevegelse bare gir **Må kontrolleres**, med teller 0.
2. Kontroller samme hendelse samtidig på PC og mobil.
3. Kvitter falsk alarm etter klargjøring: ingen fangst, ingen ny alarm under sperretiden.
4. Utløs en ny test, bekreft fangst og prøv dobbelttrykk/fra begge skjermer: bare +1.
5. Start HA på nytt med kontroll ventende, og senere med en bekreftet fangst: kontroller at begge tilstander gjenopprettes.
6. Angre testfangsten gjennom konfigurasjonen: total tilbake, annullering i loggen.
7. Verifiser sensortilkobling, batteri, rekkevidde og respons på en faktisk utløsning av fellen.
8. Registrer åtebytte med kontroll ventende: åtealder blir 0, kontrollen står fortsatt. Kvitter falsk alarm etter klargjøring: siste inspeksjon oppdateres, fangstteller står.
9. Sett et passende inspeksjonsintervall. Kontroller neste frist og at gjennomført inspeksjon flytter den. Kontroller at valgfritt inspeksjonsvarsel kan brukes med bevegelsesvarsler avslått.
10. Aktiver `last_seen` i Zigbee2MQTT. Kontroller at kortet viser kontaktalder, og at restart uten ny Zigbee-kontakt ikke gjør tidspunktet nytt.
11. For valgfri Victor-gjenoppretting: kontroller valgt konto, terskler og diagnostikkstatus. Bekreft ved neste reelle feil at korte avbrudd får rette seg selv, og at bare valgt Victor-oppføring lastes på nytt etter terskelen.

## Opphav og lisens

Opphav til de klassiske klappfellebildene og deler av testoppsettet: Rodent Trap Card 1.4, Katherine Dubé / `kedube`, commit [`28ff11fce917bb51a2d078b5c62bde40524b686a`](https://github.com/kedube/ha-rodent-traps/commit/28ff11fce917bb51a2d078b5c62bde40524b686a). Se [UPSTREAM.md](docs/UPSTREAM.md).

GPL-3.0-or-later, med opprinnelige kildehenvisninger bevart. Se [LICENSE](LICENSE).

Integrasjonsikonet er `mdi:rodent`, opprinnelig kreditert Google i Pictogrammers' Material Design Icons 7.4.47. Det beholder Apache 2.0-lisensen; kilde, lisenstekst og merknader følger med i integrasjonens `brand/`-mappe. De vedlagte Magnific-illustrasjonene brukes ikke.

## Utvikling og publisering fra main

Videre endringer kan gjøres direkte i `main`. Tests-workflowen validerer endringene. For å publisere en ny versjon oppdateres integrasjonens og kortets versjon sammen med releasenotatene, og deretter `release-request.json` som en uttrykkelig publiseringsbestilling. Release-workflowen venter på beståtte tester for nøyaktig samme commit, bygger et installasjonsarkiv med SHA-256-kontrollsum, og oppretter tag og release. Den kan også kjøres manuelt fra Actions. Eksisterende versjonstagger overskrives ikke.
