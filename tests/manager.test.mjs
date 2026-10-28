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
    hass.states = { ...hass.states, "sensor.trap": state("unavailable", attrs) }; card.hass = { ...hass };
    check("unavailable manager never reports monitoring active", chip(), "Status ukjent");
    card.remove();
    return out;
  });
  return { lines, errors: page.errors };
}
