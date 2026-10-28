# Avklarte beslutninger — 28. oktober 2026

- Egen integrasjon og egen kortvariant i samme private repo.
- Originalkortets funksjoner videreføres; senere originalendringer vurderes separat.
- HA-målversjon: 2026.10.4.
- Første sensor: Aqara DJT12LM/T1, Zigbee2MQTT, MQTT-topic `zigbee2mqtt/Vibrasjon`, hendelse `movement`.
- Sensorhendelse betyr kontrollbehov, ikke bekreftet fangst.
- Kvittering utføres etter kontroll og fysisk klargjøring.
- Bekreftet fangst gir +1; falsk alarm gir ingen fangst.
- Ett kontrollforløp telles maksimalt én gang, også med flere skjermer.
- Alle feller administreres sentralt uten manuelle hjelpere per felle.
- Tilstand og hendelser lagres på HA-serveren og overlever normal restart.
- Ingen mobilvarsling. Eventuelle varsler i HAs varslingspanel må kunne deaktiveres helt; standard er av.
- Fangstteller per felle og samlet total, med vanlig HA-langtidsstatistikk.
- Ingen historisk omskriving av HA-statistikk ved angring.
- Lesbar hendelseslogg i tillegg til tall, basert på strukturerte hendelser.
- Angre siste fangst finnes bare i integrasjonens administrasjon, med valgt felle, tidspunkt og bekreftelse.
- Angring endrer ingen fysisk klargjørings-/kontrollstatus.
- Arkivering av feller beholder fangsthistorikken og samlet total.

Implementasjonsvalg: standard sperretid er 30 sekunder og kan endres til 0–600 sekunder. Én MQTT-sensor er knyttet til én registrert felle. Feil ved lagring skal ikke publisere en fangst som ikke er skrevet til lagringen. Ingen installasjon i brukerens HA og ingen automatisk merge/publisering som del av utviklingen.
