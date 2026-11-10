// Modules: create new sensors, detectors, dialogues and actuators, test them, and decide
// whether they stay private (only on this machine) or are shared with everyone (public).

import { api, clear, debounce, guard, h, refreshCatalog, toast } from "./lib.js";

const KINDS = {
  sensor: "Reads a device: camera, microphone, wearable…",
  detector: "Turns input into information: speech, faces, emotions, gestures…",
  dialogue: "Decides what to say: chatbots, LLMs, dialogue managers…",
  actuator: "Acts in the world: speech, motion, screens, lights…",
};
const ACTIONS = {
  REQUEST: "ask for a result (detectors, dialogues)",
  DO: "perform an action (actuators)",
  ON: "start a continuous activity",
  OFF: "stop it",
};
const md = { list: [], selected: null, view: "list", tab: "code", spec: null, output: null, checks: null, code: null };
let root;

const emptySpec = () => ({ name: "", kind: "detector", description: "", author: "", license: "MIT",
  actions: ["REQUEST"], params: [], requirements: [], credentials: [], share: "private" });

function renderList() {
  const box = root.querySelector("#modules-list");
  clear(box);
  box.append(h("h3", {}, "Modules", h("button", { class: "btn small primary", onclick: () => { md.view = "wizard"; md.spec = emptySpec(); render(); } }, "+ New module")));
  const groups = { private: "Private: only on this machine", public: "Public: shared with everyone", external: "External folders" };
  for (const [visibility, label] of Object.entries(groups)) {
    const items = md.list.filter((m) => m.visibility === visibility);
    if (!items.length && visibility === "external") continue;
    box.append(h("div", { class: "hint", style: { margin: "10px 0 4px" } }, label));
    if (!items.length) box.append(h("div", { class: "hint", style: { paddingLeft: "8px" } }, "none yet"));
    const list = h("div", { class: "list" });
    items.forEach((m) => list.append(h("div", {
      class: "list-item" + (md.view === "detail" && md.selected === m.name ? " active" : ""),
      onclick: () => openModule(m.name),
    }, h("span", { class: "grow" }, m.name), h("span", { class: "pill " + (m.error ? "err" : "ok") }, m.error ? "error" : (m.manifest.kind || "ok")))));
    box.append(list);
  }
  box.append(h("p", { class: "hint", style: { marginTop: "12px" } },
    "Modules are folders in modules/private or modules/public with a harmoni_module.yaml. Once created they can be used as backend: <name> in any services configuration, on ROS 2 and in simulation."));
}

// ----------------------------------------------------------------- wizard
function renderWizard(main) {
  const s = md.spec;
  const update = (rerender = false) => { preview(); if (rerender) renderWizard(main); };
  clear(main);
  const form = h("div", {});
  form.append(h("label", { class: "field" }, h("span", {}, "Name *", h("small", {}, "lowercase, e.g. raised_hand")),
    h("input", { value: s.name, oninput: (e) => { s.name = e.target.value; update(); } })));
  form.append(h("div", { class: "field" }, h("span", { style: { fontWeight: 600, fontSize: "12.5px" } }, "Kind"),
    h("div", { class: "kind-cards", style: { marginTop: "4px" } }, Object.entries(KINDS).map(([kind, doc]) =>
      h("div", { class: "kind-card" + (s.kind === kind ? " active" : ""), onclick: () => {
        s.kind = kind; s.actions = kind === "actuator" ? ["DO"] : ["REQUEST"]; update(true); } },
        h("b", {}, kind), h("small", {}, doc))))));
  form.append(h("label", { class: "field" }, h("span", {}, "Description *"),
    h("textarea", { rows: 2, oninput: (e) => { s.description = e.target.value; update(); } }, s.description)));
  form.append(h("div", { class: "grid-2" },
    h("label", { class: "field" }, h("span", {}, "Author"), h("input", { value: s.author, oninput: (e) => { s.author = e.target.value; update(); } })),
    h("label", { class: "field" }, h("span", {}, "License"), h("input", { value: s.license, oninput: (e) => { s.license = e.target.value; update(); } }))));
  form.append(h("div", { class: "field" }, h("span", { style: { fontWeight: 600, fontSize: "12.5px" } }, "Actions it supports"),
    Object.entries(ACTIONS).map(([action, doc]) => h("label", { class: "row", style: { margin: "3px 0" } },
      h("input", { type: "checkbox", checked: s.actions.includes(action), style: { width: "auto" },
        onchange: (e) => { s.actions = e.target.checked ? [...s.actions, action] : s.actions.filter((a) => a !== action); update(); } }),
      h("b", {}, action), h("span", { class: "hint" }, doc)))));

  const params = h("div", { class: "field" }, h("span", { style: { fontWeight: 600, fontSize: "12.5px", display: "flex", justifyContent: "space-between" } },
    "Parameters", h("button", { class: "btn small", onclick: () => { s.params.push({ name: "", type: "str", default: "", doc: "", required: false }); update(true); } }, "+ Add")));
  if (!s.params.length) params.append(h("div", { class: "hint" }, "Settings given in the services configuration (e.g. model path, threshold, robot IP)."));
  s.params.forEach((p, i) => params.append(h("div", { class: "row param-row", style: { margin: "4px 0" } },
    h("input", { value: p.name, placeholder: "name", oninput: (e) => { p.name = e.target.value; update(); } }),
    h("select", { style: { width: "90px", flex: "none" }, onchange: (e) => { p.type = e.target.value; update(); } },
      ["str", "int", "float", "bool", "list"].map((t) => h("option", { value: t, selected: p.type === t }, t))),
    h("input", { value: p.default ?? "", placeholder: "default", oninput: (e) => { p.default = e.target.value; update(); } }),
    h("input", { value: p.doc, placeholder: "description", oninput: (e) => { p.doc = e.target.value; update(); } }),
    h("button", { class: "btn small icon danger", onclick: () => { s.params.splice(i, 1); update(true); } }, "×"))));
  form.append(params);
  form.append(h("div", { class: "grid-2" },
    h("label", { class: "field" }, h("span", {}, "Python requirements", h("small", {}, "one per line")),
      h("textarea", { rows: 2, class: "code", placeholder: "mediapipe>=0.10", oninput: (e) => { s.requirements = e.target.value.split("\n").filter(Boolean); update(); } }, s.requirements.join("\n"))),
    h("label", { class: "field" }, h("span", {}, "Credentials", h("small", {}, "names in .env")),
      h("textarea", { rows: 2, class: "code", placeholder: "MY_API_KEY", oninput: (e) => { s.credentials = e.target.value.split(/[\n,]/).map((c) => c.trim()).filter(Boolean); update(); } }, s.credentials.join("\n")))));
  form.append(h("div", { class: "field" }, h("span", { style: { fontWeight: 600, fontSize: "12.5px" } }, "Who can use it"),
    h("label", { class: "row", style: { margin: "4px 0" } }, h("input", { type: "radio", name: "share", checked: s.share === "private", style: { width: "auto" }, onchange: () => { s.share = "private"; } }),
      h("span", {}, h("b", {}, "Keep it private"), h("span", { class: "hint" }, " — stays in modules/private on this machine, never committed"))),
    h("label", { class: "row", style: { margin: "4px 0" } }, h("input", { type: "radio", name: "share", checked: s.share === "public", style: { width: "auto" }, onchange: () => { s.share = "public"; } }),
      h("span", {}, h("b", {}, "Share with everyone"), h("span", { class: "hint" }, " — moved to modules/public once its checks pass (tests, README, author, no credentials)")))));
  form.append(h("div", { class: "row" }, h("button", { class: "btn primary", onclick: create }, "Create module"),
    h("button", { class: "btn", onclick: () => { md.view = "list"; render(); } }, "Cancel")));

  main.append(h("div", { class: "wizard" }, h("h2", { style: { marginTop: 0 } }, "New module"),
    h("p", { class: "hint" }, "Describe the module: HARMONI generates a working backend, tests, examples and documentation. You then write only the logic (the TODO parts)."),
    h("div", { class: "wizard-grid" }, form, h("div", {},
      h("div", { class: "card" }, h("header", {}, "backend.py preview"), h("div", { class: "body" },
        h("div", { id: "wizard-errors" }), h("pre", { class: "output", id: "wizard-preview", style: { maxHeight: "560px" } }, "")))))));
  preview();
}

const preview = debounce(async () => {
  const s = md.spec;
  const result = await api("/modules-preview", { method: "POST", body: specBody(s) });
  const errors = document.getElementById("wizard-errors");
  const code = document.getElementById("wizard-preview");
  if (!errors || !code) return;
  clear(errors);
  result.errors.forEach((e) => errors.append(h("div", { class: "issue error", style: { padding: "3px 0" } }, h("span", { class: "lvl" }, "fix"), e)));
  code.textContent = result.backend || "";
}, 300);

function specBody(s) {
  return { name: s.name.trim(), kind: s.kind, description: s.description, author: s.author, license: s.license,
    actions: s.actions, requirements: s.requirements, credentials: s.credentials, visibility: "private",
    params: s.params.filter((p) => p.name).map((p) => ({ ...p, default: p.default === "" ? null : p.default })) };
}

async function create() {
  const s = md.spec;
  const module = await guard(api("/modules", { method: "POST", body: specBody(s) }), `Module ${s.name} created`);
  await refreshCatalog();
  await loadList();
  md.selected = module.name; md.view = "detail"; md.tab = "use";
  if (s.share === "public") {
    md.tab = "checks";
    render();
    await setVisibility("public");
  } else {
    await openModule(module.name);
  }
}

// ----------------------------------------------------------------- module details
async function openModule(name) {
  md.selected = name; md.view = "detail"; md.output = null; md.checks = null;
  md.code = await api(`/modules/${encodeURIComponent(name)}/backend`).catch(() => null);
  render();
}

function renderDetail(main) {
  const m = md.list.find((x) => x.name === md.selected);
  clear(main);
  if (!m) return main.append(h("div", { class: "empty" }, "Module not found."));
  const manifest = m.manifest || {};
  main.append(h("div", { class: "toolbar" },
    h("span", { class: "title" }, m.name), h("span", { class: "pill accent" }, manifest.kind || "module"),
    h("span", { class: "pill " + (m.visibility === "public" ? "ok" : "") }, m.visibility),
    m.error ? h("span", { class: "pill err", title: m.error }, "load error") : h("span", { class: "pill ok" }, "loaded"),
    h("span", { class: "spacer" }),
    m.visibility === "private" ? h("button", { class: "btn primary", onclick: () => setVisibility("public") }, "Share with everyone…") : null,
    m.visibility === "public" ? h("button", { class: "btn", onclick: () => setVisibility("private") }, "Make private") : null));
  const body = h("div", { style: { padding: "14px", maxWidth: "1100px" } });
  body.append(h("p", {}, manifest.description || ""), h("div", { class: "hint" }, m.path));
  if (m.error) body.append(h("pre", { class: "output", style: { color: "var(--err)", marginTop: "8px" } }, m.error));
  body.append(h("div", { class: "seg", style: { margin: "12px 0" } }, ["use", "code", "tests", "checks"].map((t) =>
    h("button", { class: md.tab === t ? "active" : "", onclick: () => { md.tab = t; render(); } }, t[0].toUpperCase() + t.slice(1)))));
  if (md.tab === "code") body.append(renderCode(m));
  if (md.tab === "tests") body.append(renderTests(m));
  if (md.tab === "checks") body.append(renderChecks(m));
  if (md.tab === "use") body.append(renderUse(m));
  main.append(body);
}

function renderCode(m) {
  if (!md.code) return h("div", { class: "hint" }, "No backend file.");
  const area = h("textarea", { class: "code", spellcheck: "false", style: { minHeight: "520px" } }, md.code.text);
  return h("div", {}, h("div", { class: "row", style: { marginBottom: "8px" } }, h("code", {}, md.code.file), h("span", { class: "spacer" }),
    h("button", { class: "btn primary", onclick: async () => {
      await guard(api(`/modules/${encodeURIComponent(m.name)}/backend`, { method: "PUT", body: { text: area.value } }), "Saved and reloaded");
      md.code.text = area.value; await loadList(); await refreshCatalog(); render();
    } }, "Save & reload")), area);
}

function renderTests(m) {
  return h("div", {}, h("div", { class: "row", style: { marginBottom: "8px" } },
    h("button", { class: "btn primary", onclick: async (e) => {
      e.target.disabled = true; e.target.textContent = "Running…";
      md.output = await guard(api(`/modules/${encodeURIComponent(m.name)}/test`, { method: "POST", body: {} })).catch(() => null);
      render();
    } }, "Run the tests"), h("span", { class: "hint" }, "tests/ of the module, in a separate process")),
    md.output ? h("div", {}, h("span", { class: "pill " + (md.output.ok ? "ok" : "err") }, md.output.ok ? "passed" : "failed"),
      h("pre", { class: "output", style: { marginTop: "8px" } }, md.output.output)) : null);
}

function renderChecks(m) {
  const checks = md.checks || m.checks || [];
  return h("div", {},
    h("p", { class: "hint" }, "A module can be shared with everyone only when all the checks pass. Then commit modules/public/", m.name, " and open a pull request."),
    h("div", { class: "row", style: { marginBottom: "8px" } }, h("button", { class: "btn", onclick: async (e) => {
      e.target.disabled = true; e.target.textContent = "Checking…";
      md.checks = (await guard(api(`/modules/${encodeURIComponent(m.name)}/checks`, { method: "POST", body: {} }))).checks;
      render();
    } }, "Run all checks (with tests)")),
    checks.map((c) => h("div", { class: "check " + (c.ok ? "ok" : "ko") }, h("span", { class: "mark" }, c.ok ? "✓" : "✗"),
      h("div", {}, h("div", {}, c.check), !c.ok && c.detail ? h("details", {}, h("summary", {}, "details"), h("pre", { class: "output" }, c.detail)) : null))));
}

function renderUse(m) {
  const service = `${m.name}_default`;
  const action = ((m.manifest || {}).actions || ["REQUEST"])[0];
  const yaml = `  ${service}:\n    backend: ${m.name}\n`;
  const node = JSON.stringify({ type: "ServiceAction", name: `${m.name} ${action}`,
    params: { service, action, input_value: "hello", ...(action === "REQUEST" ? { output_key: `${m.name}/result` } : {}), timeout_s: 30 } }, null, 2);
  const copy = (text) => navigator.clipboard?.writeText(text).then(() => toast("Copied", "ok"));
  return h("div", {},
    h("div", { class: "card" }, h("header", {}, "1. Add it to a services configuration", h("span", { class: "spacer" }),
      h("button", { class: "btn small", onclick: () => copy(yaml) }, "Copy")), h("div", { class: "body" },
      h("p", { class: "hint" }, "Services page → open a configuration → Add a service → backend ", h("code", {}, m.name), ", or paste under services:"),
      h("pre", { class: "output" }, yaml))),
    h("div", { class: "card" }, h("header", {}, "2. Call it from a tree", h("span", { class: "spacer" }),
      h("button", { class: "btn small", onclick: () => copy(node) }, "Copy")), h("div", { class: "body" },
      h("p", { class: "hint" }, "Compose page → add a ServiceAction node with service ", h("code", {}, service), " and action ", h("code", {}, action), ". Example node:"),
      h("pre", { class: "output" }, node))),
    h("div", { class: "card" }, h("header", {}, "3. Write the logic"), h("div", { class: "body" },
      h("p", {}, "Edit the TODO parts on the ", h("a", { href: "#", onclick: (e) => { e.preventDefault(); md.tab = "code"; render(); } }, "Code"),
        " tab, then run the tests. Install its requirements in the ROS 2 container with ", h("code", {}, "./harmoni.sh ros2 modules-install"), "."))));
}

async function setVisibility(visibility) {
  const result = await guard(api(`/modules/${encodeURIComponent(md.selected)}/visibility`, { method: "POST", body: { visibility } }));
  md.checks = result.checks;
  if (result.ok) toast(visibility === "public" ? `${md.selected} is now public: commit modules/public/${md.selected}` : `${md.selected} is now private`, "ok");
  else { toast("Some checks failed: the module stays private", "err"); md.tab = "checks"; }
  await loadList();
  render();
}

function render() {
  renderList();
  const main = root.querySelector("#modules-main");
  if (md.view === "wizard") return renderWizard(main);
  if (md.view === "detail") return renderDetail(main);
  clear(main);
  main.append(h("div", { class: "wizard" }, h("h2", { style: { marginTop: 0 } }, "HARMONI modules"),
    h("p", {}, "A module adds a new capability to HARMONI — a sensor, a detector, a dialogue component or an actuator — without changing the core."),
    h("ol", {}, h("li", {}, "Describe it: HARMONI generates a working skeleton, tests and examples."),
      h("li", {}, "Write the logic in backend.py and run its tests."),
      h("li", {}, "Use it: add it to a services configuration and call it from a tree with ServiceAction."),
      h("li", {}, "Decide: keep it private, or share it with everyone once its checks pass.")),
    h("button", { class: "btn primary", onclick: () => { md.view = "wizard"; md.spec = emptySpec(); render(); } }, "+ New module")));
}

async function loadList() { md.list = await api("/modules"); }

export function initModules(container) {
  root = container;
  container.classList.add("layout-2");
  container.append(h("aside", { class: "col side" }, h("div", { class: "section", id: "modules-list" })),
    h("div", { class: "col", id: "modules-main" }));
  loadList().then(render).catch((e) => toast(e.message, "err"));
}
