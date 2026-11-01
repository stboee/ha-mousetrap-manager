# Mousetrap Manager

Videreutvikling av [Rodent Trap Card](https://github.com/kedube/ha-rodent-traps), med en Home Assistant-integrasjon som holder et felles, varig register over musefeller.

**Utviklingsversjon: 0.2.1. Målplattform: Home Assistant 2026.10.4.** Testet programvare er ikke det samme som verifisert drift på en fysisk felle; se testplanen nedenfor før ordinær bruk.

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
3. Åpne integrasjonens konfigurasjon → **Legg til felle**.
4. Velg Aqara-sensorens MQTT-enhet, et fellenavn og nøyaktig MQTT-topic. For den første kjente sensoren er topic `zigbee2mqtt/Vibrasjon`.
5. Legg til denne dashboardressursen som **JavaScript-modul** under Innstillinger → Dashboards → Ressurser (avansert modus kan være nødvendig):

`/mousetrap_manager/mousetrap-manager-card.js?v=0.2.1`

6. Last nettleseren/Companion-appen på nytt og legg til **Mousetrap Manager Card**. Kortvelgeren foreslår registrerte feller automatisk når kortet opprettes. Etter registrering av flere feller kan du velge deres statusentiteter i kortets visuelle editor.

Ingen ekstra hjelpere per felle trengs. `hacs.json` beskriver integrasjonen; kortet følger integrasjonspakken.

### Oppgradering fra 0.1.0 eller 0.2.0

Oppdater gjennom HACS eller erstatt hele integrasjonsmappen med den nye versjonen. Behold integrasjonen og `.storage`-dataene; ikke slett oppsettet. Start HA på nytt, endre dashboardressursens versjon til `?v=0.2.1` og last nettleseren/appen på nytt. Registrerte feller, ventende kontroll og fangsthistorikk videreføres. Tidligere fangstbekreftelser og falske alarmer gir sitt faktiske tidspunkt som siste inspeksjon. Åtebyttehistorikk og sensorkontakt blir stående som ukjent til de registreres.

## Kort

Én registrert felle, med statusentiteten som integrasjonen opprettet (eksempel-ID):

```yaml
type: custom:mousetrap-manager-card
title: Musefeller
traps:
  - manager: sensor.loft_status
```

Flere registrerte feller:

```yaml
type: custom:mousetrap-manager-card
title: Musefeller
sort: status
traps:
  - manager: sensor.loft_status
  - manager: sensor.garasje_status
```

Kortet viderefører originalens layout, illustrasjoner, animasjoner, signal- og batterivisning, vanlige entitetsroller, knapphandlinger, tema og tilgjengelighet. Originalens eldre smartfeller kan fortsatt konfigureres med de eksisterende rollene. Se [originalens dokumentasjon](docs/upstream/README.md) for disse rollene, med typen endret til `custom:mousetrap-manager-card`.

For registrerte vibrasjonsfeller kommer batteri og signal fra den valgte sensoren. **Overvåking aktiv** beskriver programvarens tilstand; sensoren kan ikke bevise at fellen fysisk er spent. Samlet fangst fra registeret inkluderer også arkiverte feller. Originalkortets sum av viste feller kan vises i tillegg; eldre smartfeller konfigurert direkte i kortet føres ikke automatisk inn i vårt fangstregister.

Aktiv overvåking viser en oppspent felle uten mus. Bevegelse viser en utløst felle med et spørsmålstegn, uten å tegne inn en bekreftet fangst. Integrasjonens lys- og mørkeikon bruker `mdi:rodent` og leveres lokalt i `brand/`.

Hendelsesloggen nederst i kortet kan filtreres per felle. Eldre hendelser hentes i sider; hele loggen kopieres ikke inn i sensorattributter eller nettleserlagring.

## Konfigurasjon og korrigering

- **Legg til felle:** navn, MQTT-enhet, eksakt topic, visning av åtealder og inspeksjonsinnstillinger. Wildcards er ikke tillatt.
- **Rediger/arkiver felle:** endre navn/topic eller arkiver/reaktiver. Stabil intern felle-ID bevarer registreringene gjennom navneendring. Samme sensor/topic kan ikke opprettes på nytt som en annen felle.
- **Innstillinger og varsler:** hovedbryter for alle HA-varsler, eget valg for bevegelsesvarsler og sperretid 0–600 sekunder. For bare inspeksjonsvarsler: slå hovedbryteren på, bevegelsesvarsler av, og inspeksjonsvarsel på for ønskede feller.
- **Angre siste fangst:** velg felle, se registreringstidspunktet og bekreft. Registreringen annulleres i loggen, tellere reduseres én gang, og fellens gjeldende kontrollstatus endres ikke. Hvis en ny fangst har kommet til mens skjemaet var åpent, må du åpne det på nytt.

Angring er en administrativ handling. Det finnes ingen angretjeneste eller knapp i kortet.

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

Hver felle får entiteten **Siste sensorkontakt**, og kortet viser hvor lenge det er siden kontakten. Kilden er Zigbee2MQTTs `last_seen`, som må aktiveres der, eksempelvis:

```yaml
advanced:
  last_seen: ISO_8601
```

Se [Zigbee2MQTTs innstillinger](https://www.zigbee2mqtt.io/guide/configuration/all-settings.html). Legg valget inn i en eventuell eksisterende `advanced`-seksjon. Meldinger uten gyldig `last_seen` gir ikke et oppdiktet kontakttidspunkt. Batteri- og andre rapporter kan oppdatere kontakt uten bevegelse. Gamle meldinger og retained-meldinger bruker sitt opprinnelige tidspunkt; retained bevegelse utløser aldri en ny kontroll. Vanlig HA-oppdatering eller restart teller ikke som sensorkontakt.

Siste sensorkontakt og siste bevegelse er forskjellige opplysninger. Kontakttidspunktet beviser heller ikke at fellen er mekanisk armert. Det settes ingen ny, vilkårlig frist for frakobling av en sovende batterisensor.

## Victor – automatisk gjenoppretting

Dette er et valgfritt tillegg for en **eksisterende Victor Smart-Kill-integrasjon**. Det oppretter ingen ny Victor-tilkobling og krever ingen ekstra innlogging. Funksjonen er avslått som standard og kjører på HA-serveren uten åpent dashboard.

Åpne **Mousetrap Manager → Konfigurer → Victor – automatisk gjenoppretting**:

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

Fangstteller per felle og samlet teller er numeriske sensorer med `state_class: total`. De kan gå ned ved angring. Med Recorder aktiv og sensorene inkludert i opptaket kan HA samle langtidsstatistikk. En angring påvirker statistikken når den utføres; vi omskriver ikke tidligere statistikkperioder.

Detaljloggen lagres i vårt register uavhengig av Recorders vanlige historikkopprydding. Ingen automatisk sletting av fangsthendelser er konfigurert i denne versjonen. Ta vanlig HA-sikkerhetskopi som inkluderer konfigurasjonsmappen og `.storage`. En sikkerhetskopi av bare dette Git-repositoriet inneholder ikke fellenes driftsdata. Fjerning av selve integrasjonen er en annen handling enn å arkivere en felle; behold sikkerhetskopi ved reinstallasjon.

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

Kjør gjerne med `CHROME_PATH` satt til en installert Chromium. Originalens tester av modell, rendering, tilgjengelighet, editor og interaksjon er videreført. Testene av originalprosjektets publiseringsrutine ligger som referanse i `docs/upstream/tests`, siden vår versjon ikke bruker automatisk utgivelse.

`scripts/derive_card.py` dokumenterer den opprinnelige avledningen fra den låste originalfilen. Begge leverte kopier av vår kortfil skal være identiske: `dist/mousetrap-manager-card.js` og filen i integrasjonens `frontend`-mappe. Originalfilen i `dist/rodent-trap-card.js` beholdes uendret som sammenligningsgrunnlag.

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

Kortgrunnlag: Rodent Trap Card 1.4, Katherine Dubé / `kedube`, commit [`28ff11fce917bb51a2d078b5c62bde40524b686a`](https://github.com/kedube/ha-rodent-traps/commit/28ff11fce917bb51a2d078b5c62bde40524b686a). Se [UPSTREAM.md](docs/UPSTREAM.md). Oppdateringer fra originalprosjektet vurderes som egne saker.

GPL-3.0-or-later, med opprinnelige kildehenvisninger bevart. Se [LICENSE](LICENSE).

Integrasjonsikonet er `mdi:rodent`, opprinnelig kreditert Google i Pictogrammers' Material Design Icons 7.4.47. Det beholder Apache 2.0-lisensen; kilde, lisenstekst og merknader følger med i integrasjonens `brand/`-mappe. De vedlagte Magnific-illustrasjonene brukes ikke.

## Utvikling og publisering fra main

Videre endringer kan gjøres direkte i `main`. Tests-workflowen validerer endringene. For å publisere en ny versjon oppdateres integrasjonens og kortets versjon sammen med releasenotatene, og deretter `release-request.json` som en uttrykkelig publiseringsbestilling. Release-workflowen venter på beståtte tester for nøyaktig samme commit, bygger et installasjonsarkiv med SHA-256-kontrollsum, og oppretter tag og release. Den kan også kjøres manuelt fra Actions. Eksisterende versjonstagger overskrives ikke.
