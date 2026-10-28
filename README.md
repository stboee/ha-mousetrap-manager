# Mousetrap Manager

Privat videreutvikling av [Rodent Trap Card](https://github.com/kedube/ha-rodent-traps), med en Home Assistant-integrasjon som holder et felles, varig register over musefeller.

**Første utviklingsversjon: 0.1.0. Målplattform: Home Assistant 2026.10.4.** Testet programvare er ikke det samme som verifisert drift på en fysisk felle; se testplanen nedenfor før ordinær bruk.

## Arbeidsflyt

1. Aqara DJT12LM/T1 publiserer `action: movement` gjennom Zigbee2MQTT.
2. Integrasjonen lagrer én ventende kontrollhendelse. Kortet viser **Må kontrolleres**. Bevegelse alene teller aldri som fangst.
3. Kontroller, tøm ved behov, spenn opp og sett fellen tilbake.
4. Velg **Bekreft fangst** (+1) eller **Falsk alarm** (ingen telling).
5. En konfigurerbar sperretid, som standard 30 sekunder, demper håndteringsbevegelse etter kvittering.

Samme hendelse kan ikke bekreftes to ganger. Dette håndheves på serveren, også fra flere skjermer og etter restart. Ved feilbetjening finnes **Angre siste fangst** under integrasjonens konfigurasjon. Kortet har ingen angreknapp.

**Mobilvarsling brukes ikke.** Valgfrie varsler i Home Assistants innebygde varslingspanel er avslått som standard. De kan aktiveres i integrasjonens innstillinger og kvitteres gjennom vanlig kontrollarbeidsflyt. Nye rystelser mens kontroll venter oppretter ikke flere alarmer.

## Installasjon fra dette private repositoriet

Last ned kildekoden fra den avtalte grenen/versjonen med din egen GitHub-tilgang. Kopier hele mappen:

`custom_components/mousetrap_manager` → `<HA-konfigurasjon>/custom_components/mousetrap_manager`

Ikke bare kopier Python-filene: `frontend`, `translations`, `manifest.json` og `services.yaml` skal følge med. Ingen nøkler eller GitHub-passord skal legges i integrasjonens konfigurasjon.

1. Start Home Assistant på nytt.
2. Legg til **Mousetrap Manager** under Innstillinger → Enheter og tjenester.
3. Åpne integrasjonens konfigurasjon → **Legg til felle**.
4. Velg Aqara-sensorens MQTT-enhet, et fellenavn og nøyaktig MQTT-topic. For den første kjente sensoren er topic `zigbee2mqtt/Vibrasjon`.
5. Legg til denne dashboardressursen som **JavaScript-modul** under Innstillinger → Dashboards → Ressurser (avansert modus kan være nødvendig):

`/mousetrap_manager/mousetrap-manager-card.js?v=0.1.0`

6. Last nettleseren/Companion-appen på nytt og legg til **Mousetrap Manager Card**. Kortvelgeren foreslår registrerte feller automatisk når kortet opprettes. Etter registrering av flere feller kan du velge deres statusentiteter i kortets visuelle editor.

Den private installasjonsmåten gjennom HACS er ikke verifisert. Manuell installasjon krever ingen ekstra hjelper per felle. `hacs.json` beskriver integrasjonen; kortet følger integrasjonspakken.

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

Hendelsesloggen nederst i kortet kan filtreres per felle. Eldre hendelser hentes i sider; hele loggen kopieres ikke inn i sensorattributter eller nettleserlagring.

## Konfigurasjon og korrigering

- **Legg til felle:** navn, MQTT-enhet og eksakt topic. Wildcards er ikke tillatt.
- **Rediger/arkiver felle:** endre navn/topic eller arkiver/reaktiver. Stabil intern felle-ID bevarer registreringene gjennom navneendring. Samme sensor/topic kan ikke opprettes på nytt som en annen felle.
- **Innstillinger:** slå HA-varsler helt av/på; velg sperretid 0–600 sekunder.
- **Angre siste fangst:** velg felle, se registreringstidspunktet og bekreft. Registreringen annulleres i loggen, tellere reduseres én gang, og fellens gjeldende kontrollstatus endres ikke. Hvis en ny fangst har kommet til mens skjemaet var åpent, må du åpne det på nytt.

Angring er en administrativ handling. Det finnes ingen angretjeneste eller knapp i kortet.

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

## Opphav og lisens

Kortgrunnlag: Rodent Trap Card 1.4, Katherine Dubé / `kedube`, commit [`28ff11fce917bb51a2d078b5c62bde40524b686a`](https://github.com/kedube/ha-rodent-traps/commit/28ff11fce917bb51a2d078b5c62bde40524b686a). Se [UPSTREAM.md](docs/UPSTREAM.md). Oppdateringer fra originalprosjektet vurderes som egne saker.

GPL-3.0-or-later, med opprinnelige kildehenvisninger bevart. Se [LICENSE](LICENSE).
