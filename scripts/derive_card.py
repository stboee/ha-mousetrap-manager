"""Documented one-time derivation from the pinned upstream card.

Kept so the fork's initial changes can be reproduced and reviewed. Later upstream
changes are separate work; this script never downloads or updates upstream.
"""

from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / "dist/rodent-trap-card.js").read_text()


def replace(old, new):
    global source
    if old not in source:
        raise RuntimeError(f"Missing upstream anchor: {old[:100]}")
    source = source.replace(old, new)


replace('const VERSION = "1.4";', 'const VERSION = "0.1.0";')
replace('"rodent-trap-card"', '"mousetrap-manager-card"')
replace('"rodent-trap-card-editor"', '"mousetrap-manager-card-editor"')
replace('name: "Rodent Trap Card",', 'name: "Mousetrap Manager Card",')
replace("@layer rodent-trap-card", "@layer mousetrap-manager-card")
replace(
    "@container (max-width: 180px) {",
    """@container (min-width: 181px) and (max-width: 200px) {
  .metric { padding-left: 4px; padding-right: 4px; }
  .metric .m-value { font-size: 12px; }
}
@container (max-width: 180px) {""",
)
replace('const TRAP_KEYS = ["device",', 'const TRAP_KEYS = ["manager", "device",')
replace('const TRAP_ONLY_KEYS = ["device",', 'const TRAP_ONLY_KEYS = ["manager", "device",')
replace('const TRAP_FORM_KEYS = ["device",', 'const TRAP_FORM_KEYS = ["manager", "device",')
replace('    device: "Device",', '    manager: "Mousetrap Manager status entity",\n    device: "Device",')
replace(
    '    { name: "device", selector:',
    '    { name: "manager", selector: entitySel(["sensor"]) },\n    { name: "device", selector:',
)
replace(
    "  function resolveTrap(hass, trap, cfg, index) {",
    """  function resolveTrap(hass, trap, cfg, index) {
    const managerEntity = trap.manager;
    const managerState = managerEntity && hass && hass.states ? hass.states[managerEntity] : null;
    const managed = managerEntity ? { ...(managerState ? managerState.attributes : {}), state: managerState ? managerState.state : "unavailable", entity: managerEntity } : null;
    if (managed) {
      trap = { ...trap, device: managed.source_device_id || trap.device,
        name: trap.name || managed.trap_name, kill: false, armed: false, rearm: false,
        strikes: { entity: managerEntity, attribute: "catch_count" },
        last_strike: { entity: managerEntity, attribute: "last_catch" } };
    }""",
)
replace("      refs,\n      watch: Array.from(watch),", "      refs,\n      managed,\n      watch: Array.from(watch),")
replace(
    "    return m;\n  }\n\n  const errorText",
    """    if (t.managed) {
      const a = t.managed;
      m.manager = a;
      m.primary = a.entity;
      const physicalStates = m.watch.filter((id) => id !== a.entity).map((id) => hass.states[id]).filter(Boolean);
      if (physicalStates.length && physicalStates.every((s) => s.state === "unavailable")) m.online = false;
      m.kill = false;
      m.rearm = null;
      m.armKnown = false;
      m.actions = [];
      delete m.holds.kill;
      delete m.holds.trap;
      if (a.state === "pending" && a.pending_event_id) {
        m.status = "check";
        m.label = "M\\u00e5 kontrolleres";
        m.scene = "sprung";
        for (const [service, name] of [["confirm_catch", "Bekreft fangst"], ["false_alarm", "Falsk alarm"]]) {
          m.actions.push(makeAction(hass, { action: "mousetrap_manager." + service, name,
            data: { trap_id: a.trap_id, event_id: a.pending_event_id } }, false));
        }
      } else if (a.state === "archived") {
        m.status = "unknown"; m.label = "Arkivert"; m.scene = "idle";
      } else if (a.state !== "monitoring") {
        m.status = "unknown"; m.label = "Status ukjent"; m.scene = "idle";
      } else {
        m.status = m.online === false ? "offline" : warnings.length ? "warn" : "ok";
        m.label = m.status === "ok" ? "Overv\\u00e5king aktiv" : m.status === "offline" ? "Offline" : warnings[0];
        m.scene = m.online === false ? "offline" : "armed";
      }
    }
    return m;
  }

  const errorText""",
)
replace(
    "  function renderBanner(m) {",
    """  function renderBanner(m) {
    if (m.manager && m.manager.state === "pending") return `<div class="banner b-check">${ICONS.bell}<div><div class="b-title">M\\u00e5 kontrolleres</div><div class="b-sub">Kontroller, t\\u00f8m og klargj\\u00f8r fellen f\\u00f8r du kvitterer. Bevegelse er ikke bekreftet fangst.</div></div></div>`;
    if (m.manager && m.manager.state === "monitoring" && Date.parse(m.manager.cooldown_until) > Date.now()) return `<div class="hint">Kort h\\u00e5ndteringspause etter kvittering.</div>`;""",
)
replace(
    "word : METRIC_LABELS[key], cls, hold, busy)",
    'word : (m.manager && key === "strikes" ? "Fangster" : m.manager && key === "last_strike" ? "Siste fangst" : METRIC_LABELS[key]), cls, hold, busy)',
)
replace("  function renderSummary(models) {", "  function renderSummary(models, globalTotal) {")
replace(
    '    return chips.join("");\n  }\n\n  // ---------------------------------------------------------------------------\n  // Styles',
    """    const managedPending = models.filter((m) => m.manager && m.manager.state === "pending").length;
    if (managedPending) chips.push(chip("s-check", `${managedPending} m\\u00e5 kontrolleres`));
    if (globalTotal !== undefined && globalTotal !== null) chips.push(chip("total", `Samlet fangst: ${globalTotal}`));
    return chips.join("");
  }

  // ---------------------------------------------------------------------------
  // Styles""",
)
replace(
    "        const html = renderSummary(current);",
    """        const totals = Object.values(this._hass.states || {}).filter((s) => s.attributes && s.attributes.mousetrap_manager_total);
        const globalTotal = current.some((m) => m.manager) && totals.length ? toNum(totals[0].state, null) : undefined;
        const html = renderSummary(current, globalTotal);""",
)
replace(
    "    _update(force = false) {\n      const cfg",
    """    _update(force = false) {
      this._refreshJournal();
      const cfg""",
)
replace(
    '            <div class="sr-only" role="status"></div>`;',
    """            <div class="sr-only" role="status"></div>
            <details class="manager-journal" style="padding:12px" hidden><summary>Hendelseslogg</summary><div class="journal-controls"></div><div class="journal-events" aria-live="polite"></div></details>`;""",
)
replace(
    '      this._live = wrap.querySelector(".sr-only");',
    """      this._live = wrap.querySelector(".sr-only");
      this._journal = wrap.querySelector(".manager-journal");
      this._journalSig = null;
      this._journalRequest = (this._journalRequest || 0) + 1;
      this._journal.addEventListener("toggle", () => this._refreshJournal(true));""",
)
replace(
    "    /** True when none of the trap's entities",
    """    _refreshJournal(force = false) {
      if (!this._journal || !this._hass) return;
      const states = Object.values(this._hass.states || {}).filter((s) => s.attributes && s.attributes.mousetrap_manager);
      const enabled = this._config.traps.some((t) => t.manager);
      this._journal.hidden = !enabled;
      if (!enabled || !this._journal.open) return;
      const sig = JSON.stringify(states.map((s) => [s.entity_id, s.attributes.revision]));
      if (!force && sig === this._journalSig) return;
      this._journalSig = sig;
      const controls = this._journal.querySelector(".journal-controls");
      if (!controls.children.length) {
        const select = document.createElement("select");
        select.setAttribute("aria-label", "Filtrer hendelseslogg etter felle");
        const all = document.createElement("option"); all.value = ""; all.textContent = "Alle feller"; select.appendChild(all);
        states.forEach((s) => { const o = document.createElement("option"); o.value = s.attributes.trap_id; o.textContent = s.attributes.trap_name; select.appendChild(o); });
        select.addEventListener("change", () => this._loadJournal()); controls.appendChild(select);
      }
      this._loadJournal();
    }

    async _loadJournal(before) {
      const request = ++this._journalRequest;
      const out = this._journal.querySelector(".journal-events");
      const filter = this._journal.querySelector("select");
      const msg = { type: "mousetrap_manager/journal", limit: 50 };
      if (filter && filter.value) msg.trap_id = filter.value;
      if (before) msg.before = before;
      try {
        const result = await this._hass.callWS(msg);
        if (request !== this._journalRequest || !this.isConnected) return;
        if (!before) out.textContent = "";
        const old = out.querySelector("button"); if (old) old.remove();
        const labels = { registered: "Felle registrert", movement: "Bevegelse registrert. M\\u00e5 kontrolleres.",
          capture_confirmed: "Fangst bekreftet. Fellen er klargjort.", false_alarm: "Falsk alarm. Fellen er klargjort.",
          capture_voided: "Siste fangst annullert.", archived: "Felle arkivert.", reactivated: "Felle aktivert igjen.", renamed: "Felle omd\\u00f8pt." };
        result.events.forEach((e) => { const row = document.createElement("p"); row.textContent = new Date(e.at).toLocaleString() + " - " + e.name + ": " + (labels[e.type] || e.type); out.appendChild(row); });
        if (!out.children.length) out.textContent = "Ingen hendelser.";
        if (result.next_cursor) { const more = document.createElement("button"); more.textContent = "Vis eldre"; more.addEventListener("click", () => this._loadJournal(result.next_cursor)); out.appendChild(more); }
      } catch (e) {
        if (request === this._journalRequest) out.textContent = "Kunne ikke hente hendelsesloggen: " + callError(e);
      }
    }

    /** True when none of the trap's entities""",
)
replace(
    "  function discoverTraps(hass) {",
    """  function discoverTraps(hass) {
    const managed = Object.entries(hass && hass.states ? hass.states : {}).filter(([, s]) => s.attributes && s.attributes.mousetrap_manager && s.state !== "archived");
    if (managed.length) return managed.map(([id]) => ({ manager: id }));""",
)
replace(
    "  function entitySuggestion(hass, entityId) {",
    """  function entitySuggestion(hass, entityId) {
    const state = hass && hass.states ? hass.states[entityId] : null;
    if (state && state.attributes && state.attributes.mousetrap_manager) return { config: { type: `custom:${CARD_TAG}`, traps: [{ manager: entityId }] } };""",
)

destination = root / "custom_components/mousetrap_manager/frontend/mousetrap-manager-card.js"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(source)
(root / "dist/mousetrap-manager-card.js").write_text(source)

# Keep upstream regression suites, adapted to the independent custom-element name.
for path in list((root / "tests").glob("*")) + [root / "demo/index.html"]:
    if path.is_file():
        text = path.read_text().replace("rodent-trap-card", "mousetrap-manager-card")
        if path.name == "lib.mjs":
            text = text.replace('root + "dist/', 'root + "custom_components/mousetrap_manager/frontend/')
        elif path.name == "fixture.html" or path.parent.name == "demo":
            text = text.replace("../dist/", "../custom_components/mousetrap_manager/frontend/")
        path.write_text(text)
