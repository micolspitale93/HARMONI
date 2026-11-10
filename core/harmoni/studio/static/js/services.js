// Services: which backend (module) serves each service id, with its parameters.
// The YAML text is edited directly so that comments and anchors are preserved.

import { api, clear, debounce, emit, guard, h, on, refreshCatalog, state, toast } from "./lib.js";

const sv = { id: null, text: "", parsed: null, issues: [], dirty: false, backend: null };
let root;

function renderList() {
  const container = root.querySelector("#services-list");
  clear(container);
  container.append(h("h3", {}, "Configurations", h("button", { class: "btn small", onclick: newConfig }, "+ New")));
  for (const place of ["ros2", "core"]) {
    container.append(h("div", { class: "hint", style: { margin: "8px 0 4px" } },
      place === "ros2" ? "ROS 2 (ros2/config)" : "Simulation (core/trees)"));
    const list = h("div", { class: "list" });
    state.configs.filter((c) => c.place === place).forEach((c) => list.append(h("div", {
      class: "list-item" + (c.id === sv.id ? " active" : ""), onclick: () => open(c.id),
    }, h("span", { class: "grow" }, c.name), h("span", { class: "meta" }, `${(c.services || []).length} services`))));
    container.append(list);
  }
}

function renderEditor() {
  const main = root.querySelector("#services-main");
  clear(main);
  if (sv.id === null) return main.append(h("div", { class: "empty" }, "Open a configuration or create a new one."));
  const textarea = h("textarea", { class: "code", spellcheck: "false", style: { flex: 1, minHeight: "420px", border: 0, borderRadius: 0, padding: "12px 14px" },
    oninput: (e) => { sv.text = e.target.value; sv.dirty = true; check(); renderToolbar(); } }, sv.text);
  main.append(h("div", { class: "toolbar", id: "services-toolbar" }), textarea);
  renderToolbar();
}

function renderToolbar() {
  const bar = root.querySelector("#services-toolbar");
  if (!bar) return;
  clear(bar);
  const errors = sv.issues.filter((i) => i.level === "error").length;
  bar.append(h("span", { class: "title" }, sv.id), sv.dirty ? h("span", { class: "pill warn" }, "unsaved") : null,
    h("span", { class: "pill " + (errors ? "err" : "ok") }, errors ? `${errors} error(s)` : "valid"),
    h("span", { class: "spacer" }),
    h("button", { class: "btn", onclick: () => emit("run-config", sv.id), title: "Use this configuration on the Run page" }, "▶ Run with it"),
    h("button", { class: "btn primary", onclick: save }, "Save"));
}

function renderSide() {
  const side = root.querySelector("#services-side");
  clear(side);
  if (sv.id === null) return;
  const issues = h("div", { class: "section" }, h("h3", {}, "Checks"));
  if (!sv.issues.length) issues.append(h("div", { class: "hint" }, "Backends, parameters and tree are consistent."));
  sv.issues.forEach((i) => issues.append(h("div", { class: `issue ${i.level}`, style: { padding: "4px 0" } },
    h("span", { class: "lvl" }, i.level), h("span", {}, h("code", {}, i.path), " ", i.message))));
  side.append(issues);
  const services = (sv.parsed && sv.parsed.services) || {};
  const box = h("div", { class: "section" }, h("h3", {}, "Services"));
  Object.entries(services).forEach(([id, params]) => {
    const backend = state.backends.find((b) => b.name === (params || {}).backend);
    box.append(h("div", { class: "list-item", style: { cursor: "default" } }, h("b", { class: "grow" }, id),
      h("span", { class: "pill " + (backend ? "accent" : "err") }, (params || {}).backend || "?"),
      backend ? h("span", { class: "meta" }, backend.kind) : null));
  });
  side.append(box);
  side.append(renderAddService());
}

function renderAddService() {
  const box = h("div", { class: "section" }, h("h3", {}, "Add a service"));
  const backend = state.backends.find((b) => b.name === sv.backend) || state.backends[0];
  if (!backend) return box;
  sv.backend = backend.name;
  const values = {};
  const id = h("input", { value: `${backend.kind === "actuator" ? "speaker" : backend.name}_default` });
  box.append(h("label", { class: "field" }, h("span", {}, "Backend"),
    h("select", { onchange: (e) => { sv.backend = e.target.value; renderSide(); } },
      ["sensor", "detector", "dialogue", "actuator", "service"].map((kind) => {
        const items = state.backends.filter((b) => b.kind === kind);
        return items.length ? h("optgroup", { label: kind }, items.map((b) => h("option", { value: b.name, selected: b.name === backend.name },
          b.name + (b.module ? " (module)" : "")))) : null;
      })),
    h("div", { class: "field-doc" }, backend.doc)));
  box.append(h("label", { class: "field" }, h("span", {}, "Service id", h("small", {}, "used by the trees")), id));
  Object.entries(backend.params || {}).forEach(([name, decl]) => {
    const input = h("input", { placeholder: decl.default !== null && decl.default !== undefined ? `default: ${JSON.stringify(decl.default)}` : decl.type,
      oninput: (e) => { values[name] = e.target.value; } });
    box.append(h("label", { class: "field" }, h("span", {}, name + (decl.required ? " *" : ""), h("small", {}, decl.type)), input,
      decl.doc ? h("div", { class: "field-doc" }, decl.doc) : null));
  });
  if ((backend.credentials || []).length) {
    box.append(h("div", { class: "hint", style: { marginBottom: "8px" } }, "Needs in .env: ", backend.credentials.map((c) => h("code", { style: { marginRight: "4px" } }, c))));
  }
  box.append(h("button", { class: "btn", onclick: async () => {
    const params = {};
    for (const [name, raw] of Object.entries(values)) {
      if (raw === "") continue;
      const type = (backend.params[name] || {}).type || "str";
      try { params[name] = type === "str" ? raw : JSON.parse(raw); } catch { params[name] = raw; }
    }
    const { snippet } = await guard(api("/service-snippet", { method: "POST", body: { service_id: id.value, backend: backend.name, params } }));
    insertSnippet(snippet);
  } }, "Insert into the configuration"));
  return box;
}

function insertSnippet(snippet) {
  const lines = sv.text.split("\n");
  let start = lines.findIndex((l) => /^services:\s*(#.*)?$/.test(l));
  if (start === -1) {
    sv.text = sv.text.replace(/\s*$/, "\n") + "services:\n" + snippet;
  } else {
    let end = lines.length;
    for (let i = start + 1; i < lines.length; i++) if (/^\S/.test(lines[i]) && !lines[i].startsWith("#")) { end = i; break; }
    while (end > start + 1 && lines[end - 1].trim() === "") end--;
    lines.splice(end, 0, snippet.replace(/\n$/, ""));
    sv.text = lines.join("\n");
  }
  sv.dirty = true;
  renderEditor();
  check();
}

const check = debounce(async () => {
  const result = await api("/configs-check", { method: "POST", body: { text: sv.text } });
  sv.parsed = result.parsed; sv.issues = result.issues;
  renderToolbar(); renderSide();
}, 350);

async function open(id) {
  if (sv.dirty && !confirm("Discard the unsaved changes?")) return;
  const config = await guard(api(`/configs/${encodeURIComponent(id)}`));
  Object.assign(sv, { id, text: config.text, parsed: config.parsed, issues: config.issues, dirty: false });
  renderList(); renderEditor(); renderSide();
}

async function newConfig() {
  const place = (prompt("Where? 'ros2' (ros2/config, used by ROS 2) or 'core' (core/trees, simulation only)", "ros2") || "").trim();
  if (!["ros2", "core"].includes(place)) return place && toast("Type ros2 or core", "err");
  let name = prompt("File name of the configuration", "my_setup.yaml");
  if (!name) return;
  if (!/\.ya?ml$/.test(name)) name += ".yaml";
  Object.assign(sv, { id: `${place}:${name}`, dirty: true, issues: [], parsed: null,
    text: `# HARMONI services configuration\nparticipants: &participants "Sarah, Jane"\n\ntree:\n  file: core/trees/group_interaction.json\n  variables:\n    user_names: *participants\n\nservices:\n` });
  renderList(); renderEditor(); check();
}

async function save() {
  const result = await guard(api(`/configs/${encodeURIComponent(sv.id)}`, { method: "PUT", body: { text: sv.text } }), `Saved ${sv.id}`);
  sv.issues = result.issues; sv.dirty = false;
  await refreshCatalog();
  renderList(); renderToolbar(); renderSide();
}

export function initServices(container) {
  root = container;
  container.classList.add("layout-3");
  container.append(h("aside", { class: "col side" }, h("div", { class: "section", id: "services-list" })),
    h("div", { class: "col", id: "services-main", style: { display: "flex", flexDirection: "column" } }),
    h("aside", { class: "col side-right", id: "services-side" }));
  on("catalog", () => { renderList(); if (sv.id) renderSide(); else renderEditor(); });
  renderEditor();
}
