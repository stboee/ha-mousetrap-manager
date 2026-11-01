# Avklarte beslutninger — oppdatert 1. november 2026

- Egen integrasjon og egen kortvariant i samme repo. Repositoriet var opprinnelig privat og er nå offentlig (bekreftet via GitHub 1. november).
- Egen variant: relevante originalfunksjoner videreføres etter avklaring; senere originalendringer vurderes separat.
- HA-målversjon: 2026.10.4.
- Første sensor: Aqara DJT12LM/T1, Zigbee2MQTT, MQTT-topic `zigbee2mqtt/Vibrasjon`, hendelse `movement`.
- Sensorhendelse betyr kontrollbehov, ikke bekreftet fangst.
- Kvittering utføres etter kontroll og fysisk klargjøring.
- Bekreftet fangst gir +1; falsk alarm gir ingen fangst.
- Ett kontrollforløp telles maksimalt én gang, også med flere skjermer.
- Alle feller administreres sentralt uten manuelle hjelpere per felle.
- Tilstand og hendelser lagres på HA-serveren og overlever normal restart.
- Ingen mobilvarsling. Eventuelle varsler i HAs varslingspanel må kunne deaktiveres helt; standard er av.
- Snap-fangstteller per felle og Snap-teller, med vanlig HA-langtidsstatistikk. Ingen felles Snap-/Victor-total.
- Ingen historisk omskriving av HA-statistikk ved angring.
- Lesbar hendelseslogg i tillegg til tall, basert på strukturerte hendelser.
- Angre siste fangst finnes bare i integrasjonens administrasjon, med valgt felle, tidspunkt og bekreftelse.
- Angring endrer ingen fysisk klargjørings-/kontrollstatus.
- Arkivering av feller beholder fangsthistorikken og samlet total.

Implementasjonsvalg: standard sperretid er 30 sekunder og kan endres til 0–600 sekunder. Én MQTT-sensor er knyttet til én registrert felle. Feil ved lagring skal ikke publisere en fangst som ikke er skrevet til lagringen.

Arbeidsmåte avklart etter første implementering: videre endringer kan gjøres direkte i `main`, med tag og release ved nye versjoner. Installasjon i brukerens HA skjer separat. Vanlige kodeendringer publiserer ikke automatisk en release; publisering utløses uttrykkelig gjennom `release-request.json` eller manuell kjøring av Release-workflowen. HACS kan bruke det offentlige repositoriet som egendefinert integrasjon; HACS støtter ikke private repositorier.

## Avklart for 0.2.0

- Bruk `mdi:rodent`, med lisens og lokalt medfølgende brand-bilder. Magnific-illustrasjonen brukes ikke.
- Aktiv overvåking: oppspent felle uten mus. Kontrollbehov: utløst felle med kontrollsymbol, uten bekreftet fangst i tegningen.
- Åtealder og åtebyttetidspunkt lagres per felle. Visningen kan slås av per felle. Ukjent startdato skal ikke erstattes med installasjonsdatoen.
- Åtebytteknappen ligger med kontrollhandlingene og finnes også på enhetssiden; den skal ikke stå permanent fremme på kortet.
- Åtebytte kvitterer ikke kontroll eller inspeksjon. Brukeren klargjør fellen og velger etterpå Bekreft fangst eller Falsk alarm.
- Inspeksjonsintervall velges per felle, med 0 som av. Før første inspeksjon regnes fristen fra registrering av fellen; senere fra sist inspeksjon.
- Bekreft fangst og Falsk alarm registrerer også inspeksjon. Inspeksjon omfatter kontroll av åtet, men nullstiller ikke åtealder.
- Periodisk inspeksjon får egen knapp når fristen er passert. Ved bevegelse brukes de vanlige kontrollknappene. Ingen inspeksjonshandling skal kunne omgå ventende kontroll.
- Inspeksjon og åtebytte logges med tidspunkter; aldre og frister oppdateres på serveren hvert minutt uten åpent kort.
- Varsler: hovedbryter for full deaktivering, eget valg for bevegelse, og inspeksjonsvarsler per felle. Nye inspeksjonsvarsler er av som standard. Ingen mobilvarsling.
- Siste sensorkontakt må bygge på Zigbee2MQTT `last_seen`. MQTT-mottak, HA-oppdatering eller restart må ikke oppfattes som ny Zigbee-kontakt. Retained-rapport kan gjenopprette sitt faktiske kontakttidspunkt, men ikke utløse kontroll.
- Eksisterende v1-lagring oppgraderes additivt med samme felle-ID-er, hendelser, fangster og ventende kontroll. Tidligere kvitteringer beholder sin faktiske inspeksjonstid.

## Victor-gjenoppretting – 0.2.1

- Brukeren har bedt om et valgfritt automatisk reload når den eksisterende Victor-integrasjonen har vært utilgjengelig en stund.
- Aktivering, valgt Victor-konfigurasjonsoppføring, ventetid, minste intervall og forsøksgrense styres i Mousetrap Manager. Standard: av, 20 minutters venting, 60 minutter mellom forsøk og 3 forsøk per feilperiode.
- Overvåk den eksisterende oppføringens HA-entiteter. Ingen ny API-klient, innlogging eller kopi av Victor-entitetene opprettes.
- All observert entitetsstatus må være utilgjengelig for en lastet oppføring; én felle med gammel rapportering utløser ikke reload av en ellers fungerende konto.
- Oppstart, pågående inn-/utlasting, ny innlogging, HAs egne setup-retry-forsøk og manuell deaktivering respekteres. Oppstart medfører ny observasjonstid.
- Antall forsøk og siste reload-tidspunkt lagres før handlingen. Gyldig gjenoppretting nullstiller antall forsøk, mens sperretiden beholdes. Manuell nullstilling av forsøksantall finnes i konfigurasjonen.
- Diagnostikkstatus og HA-logg viser handlingene. Ingen nye varsler eller mobilvarsler legges til.

## Felles oppsett og Victor-visning – 0.3.0

- Brukeren godkjente Victor M1-utkast 2 og ga uttrykkelig startbeskjed etter diskusjonen.
- Integrasjonen eier oppsett, terskler, frister, statusprioritering og tilgjengelige handlinger. Kortet viser dette og formidler handlinger.
- Ett felles kortoppsett, per-felle-overstyring, automatisk visning av nye aktive feller og skjuling av arkiverte. Minimal YAML består bare av korttypen. Eldre lokale kortvalg fases ut med synlig forklaring.
- Bare snap og Victor M1. Andre originaltyper og deres frontendlogikk tas ut. Original runtime beholdes urørt som referanse.
- Victor bruker eksisterende enhet og kildeentiteter. Ingen ny API-klient, innlogging, dupliserte fangsttellere, historisk import eller ny langtidsstatistikk.
- Ingen felles Snap-/Victor-sum, og ingen ny sum for Victor. Snap beholder eksisterende fangster/statistikk; Victor viser kildeverdier per felle.
- Victor får vedlikehold for åte og inspeksjon. Inspeksjon logges, omfatter åtet og endrer ikke Victor-fangst, telleverk eller kildestatus. Ingen Bekreft fangst/Falsk alarm for Victor.
- Normal Victor-status er Ingen fangst meldt. Manglende/ukjent/utilgjengelig kilde skal ikke fremstilles som normalstatus.
- Godkjent grafikk: tydelig frontfasong, store statusmarkeringer og stor tekst øverst. Ingen liten grå forklaring under fellen.
- Gammel kontakt bygger på faktisk last_seen/last_report_date. Den skilles fra utilgjengelig kilde og utløser ikke automatisk Victor-reload alene. Konfigurerbare terskler og valgfrie HA-varsler, helt avslått som standard. Ingen mobilvarsling.
- Tidligere lagring videreføres additivt med stabile felle-ID-er; Snap-historikk, ventende kontroll og vedlikehold beholdes.
