import { fixtureUrl, openPage } from "./lib.mjs";

export default async function run(browser) {
  const page = await openPage(browser, fixtureUrl, { viewport: { width: 390, height: 844 } });
  const lines = await page.evaluate(async () => {
    const out = [];
    const check = (name, value, expected) => out.push(JSON.stringify(value) === JSON.stringify(expected)
      ? `ok   ${name}` : `FAIL ${name}: expected ${JSON.stringify(expected)} got ${JSON.stringify(value)}`);
    const now = new Date().toISOString();
    const state = (value, attrs = {}) => ({ state: String(value), attributes: attrs, last_changed: now, last_updated: now });
    const attrs = { mousetrap_manager: true, trap_id: "trap-a", trap_name: "Loft", source_device_id: "source", catch_count: 0,
      last_catch: null, last_movement: now, pending_event_id: "movement-1", revision: 1 };
    let calls = [], ws = [];
    let resolveCall;
    const hass = {
      devices: { source: { id: "source", name: "Vibrasjon", manufacturer: "Aqara", model: "DJT12LM" } },
      entities: {
        "sensor.battery": { entity_id: "sensor.battery", device_id: "source", original_name: "Battery" },
        "sensor.linkquality": { entity_id: "sensor.linkquality", device_id: "source", original_name: "Linkquality" },
      },
      states: {
        "sensor.trap": state("pending", attrs), "sensor.battery": state(100, { device_class: "battery", unit_of_measurement: "%" }),
        "sensor.linkquality": state(70), "sensor.total": state(12, { mousetrap_manager_total: true }),
      },
      callService: (...args) => { calls.push(args); return new Promise((r) => { resolveCall = r; }); },
      callWS: async (msg) => { ws.push(msg); return { events: [{ id: "one", trap_id: "trap-a", name: "<img src=x onerror=alert(1)>", type: "movement", at: now }], next_cursor: null }; },
    };
    const Card = customElements.get("mousetrap-manager-card");
    check("managed traps are discovered without helpers", Card.getStubConfig(hass).traps, [{ manager: "sensor.trap" }]);
    const card = document.createElement("mousetrap-manager-card");
    card.setConfig({ title: "Musefeller", traps: [{ manager: "sensor.trap" }] });
    document.body.appendChild(card); card.hass = hass;
    const q = (s) => card.shadowRoot.querySelector(s);
    const chip = () => q(".tile-head .chip-text").textContent;
    check("movement shows check-needed, not caught", chip(), "Må kontrolleres");
    check("movement does not increment displayed captures", q(".m-strikes .m-value").textContent, "0");
    check("managed tile reads source battery", q(".m-battery .m-value").textContent, "100%");
    check("managed tile uses capture terminology", q(".m-strikes .m-label").textContent, "Fangster");
    check("lifetime total includes archived/undisplayed traps", q(".summary").textContent.includes("Samlet fangst: 12"), true);
    check("only normal acknowledgement buttons appear", [...card.shadowRoot.querySelectorAll(".act")].map((x) => x.textContent.trim()), ["Bekreft fangst", "Falsk alarm"]);
    check("undo is absent from the card", card.shadowRoot.textContent.toLowerCase().includes("angre"), false);
    q(".act").click(); q(".act").click();
    await new Promise((r) => setTimeout(r, 10));
    check("double click sends one capture command", calls.length, 1);
    check("capture command pins the displayed episode", calls[0].slice(0, 3), ["mousetrap_manager", "confirm_catch", { trap_id: "trap-a", event_id: "movement-1" }]);
    resolveCall(); await new Promise((r) => setTimeout(r, 10));
    hass.states = { ...hass.states, "sensor.trap": state("monitoring", { ...attrs, catch_count: 1, last_catch: now, pending_event_id: null, revision: 2 }) };
    card.hass = { ...hass };
    check("server update clears acknowledgement buttons", card.shadowRoot.querySelectorAll(".act").length, 0);
    check("monitoring does not claim physical arming", chip(), "Overvåking aktiv");
    const sourceStates = hass.states;
    hass.states = { ...hass.states, "sensor.battery": state("unavailable"), "sensor.linkquality": state("unavailable") };
    card.hass = { ...hass };
    check("virtual state cannot hide an unavailable physical sensor", chip(), "Offline");
    hass.states = sourceStates; card.hass = { ...hass };
    const journal = q(".manager-journal"); journal.open = true;
    await new Promise((r) => setTimeout(r, 60));
    check("journal is fetched from the server", ws.some((m) => m.type === "mousetrap_manager/journal"), true);
    check("journal escapes trap names", q(".journal-events").querySelector("img"), null);
    check("journal renders prose", q(".journal-events").textContent.includes("Bevegelse registrert"), true);
    q(".journal-controls select").value = "trap-a";
    q(".journal-controls select").dispatchEvent(new Event("change"));
    await new Promise((r) => setTimeout(r, 10));
    check("journal filter requests a specific trap", ws[ws.length - 1].trap_id, "trap-a");
    const width = q(".tile").getBoundingClientRect();
    check("managed phone tile fits viewport", width.right <= window.innerWidth, true);
    const maintenance = { ...attrs, pending_event_id: null, show_bait_age: true, bait_age_days: 12,
      bait_event_id: "bait-1", last_inspection: now, inspection_age_days: 8, inspection_interval_days: 7,
      inspection_event_id: "inspection-1", inspection_due: true, last_sensor_contact: new Date(Date.now() - 7200000).toISOString() };
    hass.states = { ...hass.states, "sensor.trap": state("monitoring", maintenance) }; card.hass = { ...hass };
    check("scheduled inspection is visible without movement", chip(), "Tid for inspeksjon");
    check("bait age uses the server's number of days", q(".m-bait_age .m-value").textContent, "12 dager");
    check("inspection age is independent of bait age", q(".m-inspection_age .m-value").textContent, "8 dager");
    check("sensor contact is visible", !!q(".m-sensor_contact [data-since]"), true);
    check("scheduled inspection has contextual actions", [...card.shadowRoot.querySelectorAll(".act")].map((x) => x.textContent.trim()), ["Inspeksjon utført", "Åte byttet"]);
    q(".act").click(); await new Promise((r) => setTimeout(r, 5));
    check("inspection command pins the displayed inspection", calls[calls.length - 1].slice(0, 3), ["mousetrap_manager", "inspection_completed", { trap_id: "trap-a", event_id: "inspection-1" }]);
    resolveCall(); await new Promise((r) => setTimeout(r, 5));
    hass.states = { ...hass.states, "sensor.trap": state("pending", { ...maintenance, pending_event_id: "movement-2" }) }; card.hass = { ...hass };
    check("movement takes precedence over inspection deadline", chip(), "Må kontrolleres");
    check("bait replacement appears with acknowledgement buttons", [...card.shadowRoot.querySelectorAll(".act")].map((x) => x.textContent.trim()), ["Bekreft fangst", "Falsk alarm", "Åte byttet"]);
    check("pending illustration has a question badge", !!q(".scene .badge-check"), true);
    check("pending illustration never claims a caught mouse", q(".scene .mouse, .scene .victim"), null);
    card.shadowRoot.querySelectorAll(".act")[2].click(); await new Promise((r) => setTimeout(r, 5));
    check("bait command pins the displayed bait change", calls[calls.length - 1].slice(0, 3), ["mousetrap_manager", "bait_replaced", { trap_id: "trap-a", event_id: "bait-1" }]);
    resolveCall(); await new Promise((r) => setTimeout(r, 5));
    hass.states = { ...hass.states, "sensor.trap": state("monitoring", { ...maintenance, inspection_due: false, last_sensor_contact: null }) }; card.hass = { ...hass };
    check("monitoring illustration contains no mouse", q(".scene .mouse, .scene .victim"), null);
    check("monitoring illustration is still set", !!q(".scene .holddown"), true);
    check("maintenance buttons are hidden during normal monitoring", card.shadowRoot.querySelectorAll(".act").length, 0);
    check("HA state updates cannot invent sensor contact", q(".m-sensor_contact .m-value").textContent, "Ukjent");
    hass.states = { ...hass.states, "sensor.trap": state("pending", { ...maintenance, pending_event_id: "movement-2", show_bait_age: false }) }; card.hass = { ...hass };
    check("bait age visibility is configurable per trap", q(".m-bait_age"), null);
    check("hidden bait age also hides its action", [...card.shadowRoot.querySelectorAll(".act")].map((x) => x.textContent.trim()), ["Bekreft fangst", "Falsk alarm"]);
    check("maintenance readings fit a phone viewport", q(".tile").getBoundingClientRect().right <= window.innerWidth, true);
    hass.states = { ...hass.states, "sensor.trap": state("unavailable", attrs) }; card.hass = { ...hass };
    check("unavailable manager never reports monitoring active", chip(), "Status ukjent");
    card.remove();
    return out;
  });
  return { lines, errors: page.errors };
}
