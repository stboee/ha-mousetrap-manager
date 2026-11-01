/*!
 * Mousetrap Manager. Snap illustration derived from Rodent Trap Card by Katherine Dube.
 * https://github.com/kedube/ha-rodent-traps
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
(() => {
  "use strict";
  const VERSION = "0.4.0";
  const CARD_TAG = "mousetrap-manager-card";
  const EDITOR_TAG = "mousetrap-manager-card-editor";
  const esc = (s) => String(s === undefined || s === null ? "" : s).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
  const unknown = (s) => s === undefined || s === null || ["unknown", "unavailable", ""].includes(String(s));
  const internalPath = (v) => typeof v === "string" && /^\/(?!\/)/.test(v) && !/[\\\x00-\x20\x7f]/.test(v);
  const attentionEntity = (hass) => Object.entries(hass && hass.states || {}).find((p) => p[1].attributes.mousetrap_manager_attention);
  const attentionCondition = (entity) => ({condition:"state",entity,state_not:"off"});
  const isAttentionCondition = (c, entity) => c && c.condition === "state" && c.entity === entity && c.state_not === "off" && Object.keys(c).length === 3;
  const events = {
    registered: "Felle registrert", renamed: "Felle omd\u00f8pt", archived: "Felle arkivert", reactivated: "Felle tatt i bruk igjen",
    movement: "Bevegelse registrert", capture_confirmed: "Fangst bekreftet", false_alarm: "Falsk alarm kvittert",
    capture_voided: "Siste fangst angret", bait_replaced: "\u00c5te byttet", inspection_completed: "Inspeksjon utf\u00f8rt; \u00e5tet er inspisert",
  };
  const CSS = `
:host {display:block;color:var(--primary-text-color,#182532);font-family:var(--paper-font-body1_-_font-family,system-ui,sans-serif)}
*{box-sizing:border-box}ha-card{display:block;background:var(--ha-card-background,var(--card-background-color,#fff));border-radius:var(--ha-card-border-radius,14px);border:1px solid var(--divider-color,#dadfe4);padding:16px;overflow:hidden}
h2{margin:0 0 12px;font-size:22px}.summary{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px;font-size:15px}.summary span{padding:5px 9px;border:1px solid var(--divider-color,#dadfe4);border-radius:8px}
.grid{--cols:3;display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(max(min(100%,270px),calc((100% - (var(--cols) - 1)*14px)/var(--cols))),1fr))}
.tile{min-width:0;border:2px solid var(--status);border-radius:15px;overflow:hidden;background:var(--ha-card-background,var(--card-background-color,#fff))}
.tile-head{background:var(--status);color:#fff;padding:13px 15px;overflow-wrap:anywhere}.name{font-size:18px;font-weight:600;line-height:1.3}.location{font-size:14px;margin-top:2px}.status{font-size:22px;line-height:1.2;font-weight:750;margin-top:9px}.warnings{font-size:14px;margin:8px 0 0;line-height:1.4}
.scene{display:block;width:100%;height:150px;object-fit:contain;padding:5px 8px;background:#f8fafb}.metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;padding:14px}.metric{text-align:left;background:transparent;color:inherit;border:0;border-radius:5px;padding:0;min-width:0;font:inherit}.metric[data-entity]{cursor:pointer}.m-label{font-size:13px;line-height:1.3;display:block}.m-value{font-size:17px;font-weight:650;line-height:1.5;display:block;overflow-wrap:anywhere}
button,select{font:inherit;color:inherit}button{min-height:44px;padding:8px 12px;cursor:pointer;background:var(--secondary-background-color,#f0f3f6);border:1px solid var(--divider-color,#c6cdd4);border-radius:9px}button:disabled{opacity:.5;cursor:wait}button:focus-visible,summary:focus-visible,select:focus-visible{outline:3px solid var(--primary-color,#03a9f4);outline-offset:2px}
.actions{display:flex;flex-wrap:wrap;gap:8px;padding:0 14px 14px}.maintenance{margin:0 14px 14px}.maintenance summary{cursor:pointer;min-height:36px;padding:7px 0}.maintenance .actions{padding:8px 0 0}.message{padding:0 14px 14px;margin:0;overflow-wrap:anywhere}.message:empty{display:none}.empty{padding:12px 0;font-size:16px;line-height:1.5}
.manager-journal{margin-top:18px;border-top:1px solid var(--divider-color,#dadfe4);padding-top:12px}.manager-journal>summary{font-size:17px;font-weight:600;cursor:pointer;padding:5px 0}.journal-controls{display:flex;gap:8px;margin:10px 0}.journal-controls select{max-width:100%;min-height:44px;background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#ccc);border-radius:6px;padding:6px}.journal-events{padding-left:22px;font-size:14px;line-height:1.5}.journal-events li{padding:4px 0;overflow-wrap:anywhere}.journal-error{overflow-wrap:anywhere}
.tile.animate.capture{animation:attention 2.4s ease-in-out 3}@keyframes attention{50%{border-color:#f09aa8}}@media(prefers-reduced-motion:reduce){.tile.animate.capture{animation:none}}@media(max-width:340px){ha-card{padding:10px}.metrics{gap:8px;padding:10px}.status{font-size:20px}}
[hidden]{display:none!important}.attention-card{padding:0}.attention-content{display:block;padding:12px 14px;color:inherit;text-decoration:none}.attention-content h2{font-size:18px;margin:0 0 3px}.attention-content p{margin:0;line-height:1.4}.attention-summary{font-size:14px}.attention-items{padding:0;margin:8px 0 0;list-style:none}.attention-row{display:flex;gap:10px;padding:7px 0;border-top:1px solid var(--divider-color,#dadfe4);min-width:0}.attention-row>div{min-width:0}.attention-mark{flex:none;width:22px;align-self:flex-start;--mdc-icon-size:22px}.attention-name{display:block;font-size:16px;overflow-wrap:anywhere}.attention-reason{display:block;font-size:14px;line-height:1.4;overflow-wrap:anywhere}.attention-open{display:block;margin-top:8px;font-size:14px;font-weight:600;color:var(--primary-color,#0277bd)}.attention-link:focus-visible{outline:3px solid var(--primary-color,#03a9f4);outline-offset:-3px}.attention-error{border-left:5px solid #986000}.attention-hint{padding-top:8px;font-size:14px}
`;

  function metricText(hass, metric) {
    const state = metric.entity_id && hass.states[metric.entity_id];
    const value = metric.entity_id ? state && !state.attributes.restored && state.state : metric.value;
    if (unknown(value) || value === false) return "Ukjent";
    if (metric.format === "days") return value + (Number(value) === 1 ? " dag" : " dager");
    if (metric.format === "timestamp") {
      const date = new Date(value);
      if (metric.key === "contact" && Number.isFinite(date.getTime())) {
        const minutes = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60000));
        if (minutes >= 1440) return Math.floor(minutes / 1440) + " dager siden";
        if (minutes >= 60) return Math.floor(minutes / 60) + " t siden";
        return minutes ? minutes + " min siden" : "Nettopp";
      }
      return Number.isFinite(date.getTime()) ? date.toLocaleString(hass.locale && hass.locale.language || "nb", {day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit"}) : "Ukjent";
    }
    const unit = state && state.attributes.unit_of_measurement;
    return String(value) + (unit ? (unit === "%" ? "%" : " " + unit) : "");
  }

  class MousetrapManagerCard extends HTMLElement {
    constructor() {
      super(); this.attachShadow({mode:"open"}); this._busy = new Set(); this._messages = new Map(); this._journalRequest = 0;
      this.shadowRoot.innerHTML = `<style>${CSS}</style><ha-card class="full-card"><div class="overview"></div><div class="grid"></div><details class="manager-journal"><summary>Hendelseslogg</summary><div class="journal-controls"><select aria-label="Velg felle i hendelsesloggen"></select><button class="refresh">Oppdater</button></div><p class="journal-error" role="status"></p><ol class="journal-events"></ol><button class="more" hidden>Vis eldre</button></details></ha-card><ha-card class="attention-card" hidden></ha-card>`;
      const journal = this.shadowRoot.querySelector(".manager-journal");
      journal.addEventListener("toggle", () => { if (journal.open) this._loadJournal(); });
      this.shadowRoot.querySelector("select").addEventListener("change", () => this._loadJournal());
      this.shadowRoot.querySelector(".refresh").addEventListener("click", () => this._loadJournal());
      this.shadowRoot.querySelector(".more").addEventListener("click", () => this._loadJournal(this._cursor));
    }
    connectedCallback() { if (!this._timer) this._timer = setInterval(() => this._render(),60000); }
    disconnectedCallback() { clearInterval(this._timer); this._timer = null; ++this._journalRequest; }
    set preview(value) { this._preview = !!value; this._render(); }
    static getVersion() { return VERSION; }
    static getConfigElement() { return document.createElement(EDITOR_TAG); }
    static getStubConfig() { return {type:"custom:" + CARD_TAG}; }
    setConfig(config) {
      if (!config || typeof config !== "object") throw new Error("Ugyldig kortoppsett");
      this._mode = config.mode || "full";
      if (!["full","attention"].includes(this._mode)) throw new Error("Visningsmodus m\u00e5 v\u00e6re full eller attention");
      this._legacy = Object.keys(config).some((k) => !["type","mode","grid_options","visibility","view_layout","layout_options"].includes(k));
      this._render();
    }
    set hass(hass) { this._hass = hass; this._render(); }
    getCardSize() { return this._mode === "attention" ? Math.max(1,Math.ceil(this.getBoundingClientRect().height / 50)) : 5; }
    getGridOptions() { return {columns:12,min_columns:6,rows:"auto"}; }
    _render() {
      if (!this._hass) return;
      if (this._mode === "attention") { this._renderAttention(); return; }
      this.shadowRoot.querySelector(".full-card").hidden = false;
      this.shadowRoot.querySelector(".attention-card").hidden = true;
      const states = Object.entries(this._hass.states || {});
      const setup = states.find((p) => p[1].attributes.mousetrap_manager_dashboard && !unknown(p[1].state));
      const settings = setup ? setup[1].attributes.display : {};
      const allTraps = states.filter((p) => p[1].attributes.mousetrap_manager);
      const traps = allTraps.filter((p) => !p[1].attributes.archived && p[1].state !== "archived");
      this._traps = traps;
      const overview = this.shadowRoot.querySelector(".overview");
      if (!setup) {
        overview.innerHTML = '<p class="empty">Kortoppsettet er utilgjengelig. Kontroller at Mousetrap Manager er oppdatert og lastet.</p>';
        this.shadowRoot.querySelector(".grid").innerHTML = ""; this._markup = null; return;
      }
      const model = traps.map(([entity, st], index) => {
        const a = st.attributes;
        const p = !unknown(st.state) && a.presentation ? a.presentation : {type:a.presentation && a.presentation.type || "snap",name:a.trap_name || "Musefelle",status:"unknown",label:"Status ukjent",scene:"unavailable",color:"#495465",priority:3,metrics:[],actions:[],show_scene:true};
        return {entity, a, p, index};
      });
      if (settings.sort === "name") model.sort((a,b) => a.p.name.localeCompare(b.p.name,"nb"));
      if (settings.sort === "status") model.sort((a,b) => a.p.priority - b.p.priority || a.index - b.index);
      const total = states.find((p) => p[1].attributes.mousetrap_manager_total);
      overview.innerHTML = (settings.title ? `<h2>${esc(settings.title)}</h2>` : "") +
        (settings.show_summary ? `<div class="summary"><span>${model.filter((m) => m.p.type === "snap").length} snap-feller</span><span>${model.filter((m) => m.p.type === "victor").length} Victor-feller</span>${total ? `<span>Snap-fangster: ${esc(unknown(total[1].state) ? "Ukjent" : total[1].state)}</span>` : ""}</div>` : "") +
        (this._legacy ? '<p>Visningsvalg styres n\u00e5 i integrasjonen. Kortets YAML kan forenkles til bare type.</p>' : "");
      const grid = this.shadowRoot.querySelector(".grid");
      grid.style.setProperty("--cols", Math.min(6, Math.max(1, Number(settings.columns) || 3)));
      // Keep focus and open maintenance menus through ordinary HA state updates.
      const opened = new Set(Array.from(grid.querySelectorAll(".maintenance[open]")).map((d) => d.closest(".tile").dataset.id));
      const active = this.shadowRoot.activeElement;
      const focusKey = active && active.dataset.focus;
      const markup = model.map((m) => this._tile(m, opened.has(m.a.trap_id))).join("") || '<p class="empty">Ingen aktive feller. Legg til feller under integrasjonens innstillinger.</p>';
      if (markup !== this._markup) { grid.innerHTML = markup; this._markup = markup; }
      grid.querySelectorAll("button[data-service]").forEach((b) => b.onclick = () => this._action(b));
      grid.querySelectorAll("[data-entity]").forEach((b) => b.onclick = () => this.dispatchEvent(new CustomEvent("hass-more-info", {detail:{entityId:b.dataset.entity},bubbles:true,composed:true})));
      if (focusKey) {
        const next = Array.from(grid.querySelectorAll("[data-focus]")).find((e) => e.dataset.focus === focusKey);
        if (next) next.focus({preventScroll:true});
      }
      const select = this.shadowRoot.querySelector("select");
      const selected = select.value;
      const options = '<option value="">Alle feller</option>' + allTraps.map(([id,st]) => `<option value="${esc(st.attributes.trap_id)}">${esc(st.attributes.trap_name)}</option>`).join("");
      if (select.innerHTML !== options) { select.innerHTML = options; select.value = selected; }
    }
    _attentionHTML(markup) {
      if (this._attentionMarkup === markup) return;
      const card = this.shadowRoot.querySelector(".attention-card");
      const previousLink = card.querySelector(".attention-link");
      const focused = !!previousLink && this.shadowRoot.activeElement === previousLink;
      card.innerHTML = markup; this._attentionMarkup = markup;
      this.dispatchEvent(new CustomEvent("card-size-changed",{bubbles:true,composed:true}));
      if (focused && card.querySelector(".attention-link")) card.querySelector(".attention-link").focus({preventScroll:true});
    }
    _renderAttention() {
      const card = this.shadowRoot.querySelector(".attention-card");
      this.shadowRoot.querySelector(".full-card").hidden = true;
      const entry = attentionEntity(this._hass);
      const state = entry && entry[1];
      const a = state && state.attributes;
      const loaded = state && !unknown(state.state) && !a.restored && a.schema_version === 1 &&
        typeof a.title === "string" && typeof a.summary === "string" && Number.isInteger(a.count) && a.count >= 0 &&
        Array.isArray(a.items) && a.items.every((i) => i && typeof i.name === "string" && typeof i.reason_text === "string");
      // HA visibility removes the whole card from masonry; normal data stays editable in previews.
      card.hidden = false;
      if (!loaded) {
        this._attentionHTML('<div class="attention-content attention-error" role="status"><h2>Musefeller \u2013 status ukjent</h2><p>Tilsynsstatus er utilgjengelig. Kontroller at integrasjonen og kortet er oppdatert og lastet.</p></div>');
        return;
      }
      // The integration supplies rows, order, severity and prose. No client-side trap filtering.
      const rows = a.items.map((item) => {
        const color = /^#[a-fA-F0-9]{6}$/.test(item.color) ? item.color : "#495465";
        return `<li class="attention-row"><span class="attention-mark" style="color:${color}" aria-hidden="true"><svg viewBox="0 0 24 24" width="22" height="22"><circle cx="12" cy="12" r="7" fill="currentColor"/></svg></span><div><strong class="attention-name">${esc(item.name)}</strong><span class="attention-reason">${esc(item.reason_text)}</span></div></li>`;
      }).join("");
      const body = `<header><h2>${esc(a.title)}</h2><p class="attention-summary">${esc(a.summary)}</p></header><ul class="attention-items">${rows}</ul>`;
      const path = internalPath(a.navigation_path) ? a.navigation_path : null;
      this._attentionHTML(path ? `<a class="attention-content attention-link" href="${esc(path)}">${body}<span class="attention-open">\u00c5pne musefeller \u2192</span></a>` : `<div class="attention-content">${body}<p class="attention-hint">Velg adressen til fullvisningen under integrasjonens Tilsynsvisning.</p></div>`);
    }
    _tile(m, opened) {
      const p = m.p, id = m.a.trap_id;
      const type = p.type === "victor" ? "victor-m1" : "snap";
      const scene = ["normal","capture","inspection","unavailable","pending"].includes(p.scene) ? p.scene : "unavailable";
      const color = /^#[a-fA-F0-9]{6}$/.test(p.color) ? p.color : "#495465";
      const actions = (p.actions || []).map((a) => ({...a, contextual:a.contextual !== false}));
      const buttons = (list) => list.map((a) => `<button class="act" data-service="${esc(a.service)}" data-trap="${esc(id)}" data-event="${esc(a.event_id)}" data-focus="${esc(id + a.service)}"${this._busy.has(id) ? " disabled" : ""}>${esc(a.label)}</button>`).join("");
      return `<article class="tile ${esc(p.status)}${p.animations ? " animate" : ""}" data-id="${esc(id)}" style="--status:${color}" aria-label="${esc(p.name)}"><header class="tile-head"><div class="name">${esc(p.name)}</div>${p.location ? `<div class="location">${esc(p.location)}</div>` : ""}<div class="status">${esc(p.label)}</div>${p.warnings && p.warnings.length ? `<p class="warnings">${p.warnings.map(esc).join(" \u00b7 ")}</p>` : ""}</header>${p.show_scene ? `<img class="scene" src="/mousetrap_manager/images/${type}-${scene}.svg?v=${VERSION}" alt="" loading="lazy">` : ""}<div class="metrics">${(p.metrics || []).map((metric) => `<${metric.entity_id ? "button" : "div"} class="metric m-${esc(metric.key)}"${metric.entity_id ? ` data-entity="${esc(metric.entity_id)}" data-focus="${esc(id + metric.key)}"` : ""}><span class="m-label">${esc(metric.label)}</span><span class="m-value">${esc(metricText(this._hass,metric))}</span></${metric.entity_id ? "button" : "div"}>`).join("")}</div>${actions.some((a) => a.contextual) ? `<div class="actions">${buttons(actions.filter((a) => a.contextual))}</div>` : ""}${actions.some((a) => !a.contextual) ? `<details class="maintenance"${opened ? " open" : ""}><summary>Vedlikehold</summary><div class="actions">${buttons(actions.filter((a) => !a.contextual))}</div></details>` : ""}<p class="message" role="status">${esc(this._messages.get(id) || "")}</p></article>`;
    }
    async _action(button) {
      const id = button.dataset.trap;
      if (this._busy.has(id)) return;
      const service = button.dataset.service;
      if (!["confirm_catch","false_alarm","bait_replaced","inspection_completed"].includes(service)) return;
      this._busy.add(id); this._messages.delete(id); this._render();
      try {
        await this._hass.callService("mousetrap_manager", service, {trap_id:id,event_id:button.dataset.event});
        this._messages.set(id,"Registrert");
      } catch (e) { this._messages.set(id,"Kunne ikke lagre: " + (e.message || String(e))); }
      finally { this._busy.delete(id); this._render(); }
    }
    async _loadJournal(before) {
      if (!this._hass || !this._hass.callWS) return;
      const request = ++this._journalRequest;
      const error = this.shadowRoot.querySelector(".journal-error");
      const selected = this.shadowRoot.querySelector("select").value;
      const msg = {type:"mousetrap_manager/journal",limit:30};
      if (selected) msg.trap_id = selected;
      if (before) msg.before = before;
      error.textContent = "Laster hendelser\u2026";
      try {
        const result = await this._hass.callWS(msg);
        if (request !== this._journalRequest) return;
        const list = this.shadowRoot.querySelector(".journal-events");
        if (!before) list.textContent = "";
        (result.events || []).forEach((event) => {
          const li = document.createElement("li");
          li.textContent = new Date(event.at).toLocaleString("nb") + " \u00b7 " + event.name + ": " + (events[event.type] || event.type);
          list.appendChild(li);
        });
        this._cursor = result.next_cursor;
        this.shadowRoot.querySelector(".more").hidden = !this._cursor;
        error.textContent = list.children.length ? "" : "Ingen hendelser";
      } catch (e) { if (request === this._journalRequest) error.textContent = "Kunne ikke hente logg: " + (e.message || String(e)); }
    }
  }
  class MousetrapManagerEditor extends HTMLElement {
    setConfig(config) { this._config = {...config}; this._render(); }
    set hass(hass) { this._hass = hass; this._render(); }
    _change(mode, onlyAttention) {
      const entry = attentionEntity(this._hass);
      const entity = entry && entry[0];
      const config = {...this._config, mode};
      const current = config.visibility || [];
      if (entity && Array.isArray(current)) {
        const conditions = current.filter((c) => !isAttentionCondition(c,entity));
        if (onlyAttention) conditions.push(attentionCondition(entity));
        if (conditions.length) config.visibility = conditions;
        else delete config.visibility;
      }
      this._config = config;
      this.dispatchEvent(new CustomEvent("config-changed",{detail:{config},bubbles:true,composed:true}));
      this._render();
    }
    _render() {
      if (!this.shadowRoot) this.attachShadow({mode:"open"});
      const config = this._config || {};
      const mode = config.mode || "full";
      const entry = attentionEntity(this._hass);
      const entity = entry && entry[0];
      const onlyAttention = !!(entity && Array.isArray(config.visibility) && config.visibility.some((c) => isAttentionCondition(c,entity)));
      const key = JSON.stringify([mode,entity,onlyAttention]);
      if (this._editorKey === key) return;
      this._editorKey = key;
      this.shadowRoot.innerHTML = `<style>:host{display:block;font:inherit}label{display:block;margin:12px 0}select{display:block;font:inherit;padding:8px;margin-top:6px}input{margin-right:8px}p{line-height:1.5}code{overflow-wrap:anywhere}</style><p><b>Mousetrap Manager v${VERSION}</b></p><label>Visning<select><option value="full">Fullvisning</option><option value="attention">Tilsyn p\u00e5 startsiden</option></select></label><label><input type="checkbox"${onlyAttention ? " checked" : ""}${entity ? "" : " disabled"}>Vis bare n\u00e5r tilsyn er n\u00f8dvendig</label><p>Ved valg av Tilsyn settes betinget synlighet automatisk. Ukjent eller utilgjengelig tilsynsstatus forblir synlig. Andre synlighetsbetingelser beholdes.</p><p>Navn, \u00e5rsaker, terskler og adressen til fullvisningen styres under <b>Innstillinger \u2192 Enheter og tjenester \u2192 Mousetrap Manager \u2192 Konfigurer</b>.</p>${entity ? `<p>Tilsynsentitet: <code>${esc(entity)}</code></p>` : '<p>Tilsynsentiteten er ikke tilgjengelig. Oppdater og last integrasjonen for \u00e5 sette betinget synlighet.</p>'}`;
      const select = this.shadowRoot.querySelector("select");
      select.value = mode;
      select.onchange = () => this._change(select.value,select.value === "attention");
      this.shadowRoot.querySelector("input").onchange = (e) => this._change(mode,e.target.checked);
    }
  }
  if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG,MousetrapManagerCard);
  if (!customElements.get(EDITOR_TAG)) customElements.define(EDITOR_TAG,MousetrapManagerEditor);
  window.customCards = window.customCards || [];
  window.customCards.push({type:CARD_TAG,name:"Mousetrap Manager",description:"Fullvisning eller kompakt tilsyn for snap- og Victor-feller",preview:true});
})();
