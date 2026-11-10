// Compose: build HRI behavior trees from the HARMONI node palette.

import { api, clear, clone, datalist, debounce, emit, glyph, guard, h, knownServices, on, state, toast } from "./lib.js";
import { renderDiagram, specToDiagram } from "./diagram.js";

const COMPOSITES = new Set(["Sequence", "Selector", "Parallel"]);
const ed = { name: null, doc: null, selected: null, dirty: false, issues: [], view: "outline", filter: "", drag: null };
let root;

// ----------------------------------------------------------------- tree helpers
const nodeAt = (path) => path.reduce((node, i) => node.children[i], ed.doc.root);
function findPath(target, node = ed.doc.root, path = []) {
  if (node === target) return path;
  for (let i = 0; i < (node.children || []).length; i++) {
    const found = findPath(target, node.children[i], path.concat(i));
    if (found) return found;
  }
  return null;
}
const contains = (node, target) => node === target || (node.children || []).some((c) => contains(c, target));
const isComposite = (node) => COMPOSITES.has(node.type);

function newNode(type) {
  const count = JSON.stringify(ed.doc.root).split(`"type":"${type}"`).length;
  const node = { type, name: count > 1 ? `${type} ${count}` : type, params: {} };
  if (COMPOSITES.has(type)) node.children = [];
  return node;
}

function insert(node, targetPath, where) {
  if (targetPath === null || targetPath === undefined) targetPath = [];
  const target = nodeAt(targetPath);
  if (where === "inside") {
    if (!isComposite(target)) return toast("Only Sequence, Selector and Parallel can contain nodes", "err");
    target.children.push(node);
  } else {
    if (!targetPath.length) return toast("The root must stay a single node: drop inside it", "err");
    const parent = nodeAt(targetPath.slice(0, -1));
    const index = targetPath[targetPath.length - 1] + (where === "after" ? 1 : 0);
    parent.children.splice(index, 0, node);
  }
  ed.selected = findPath(node);
  changed();
}

function removeAt(path) {
  if (!path.length) return toast("The root cannot be deleted", "err");
  nodeAt(path.slice(0, -1)).children.splice(path[path.length - 1], 1);
}

function move(fromPath, targetPath, where) {
  const node = nodeAt(fromPath);
  const target = nodeAt(targetPath);
  if (contains(node, target)) return;
  removeAt(fromPath);
  insert(node, findPath(target), where);
}

function addFromPalette(type) {
  if (!ed.doc) return;
  const node = newNode(type);
  const sel = ed.selected ? nodeAt(ed.selected) : ed.doc.root;
  if (isComposite(sel)) insert(node, findPath(sel), "inside");
  else insert(node, findPath(sel), "after");
}

function issuePath(path) {
  const indices = [...String(path).matchAll(/children\[(\d+)\]/g)].map((m) => Number(m[1]));
  return path.startsWith("root") ? indices : null;
}

// ----------------------------------------------------------------- blackboard keys and suggestions
function resolveKeys(templates, params) {
  return (templates || []).map((t) => t.replace(/\{(\w+)\}/g, (_, p) => params[p] ?? ""))
    .filter((k) => k && !k.includes("{")).map((k) => k.replace(/^\//, ""));
}

function keysInTree() {
  const keys = new Set(Object.keys(ed.doc.blackboard || {}));
  (function walk(node) {
    const meta = state.palette[node.type] || {};
    const params = Object.fromEntries(Object.entries(meta.params || {}).map(([k, p]) => [k, (node.params || {})[k] ?? p.default]));
    resolveKeys(meta.writes, params).forEach((k) => keys.add(k));
    resolveKeys(meta.reads, params).forEach((k) => keys.add(k));
    (node.children || []).forEach(walk);
  })(ed.doc.root);
  return [...keys].sort();
}

function castOf(doc) {
  const cast = doc.cast && typeof doc.cast === "object" ? doc.cast : {};
  const agents = Array.isArray(cast.agents) ? cast.agents : [];
  return { cast, agents, roles: agents.map((a) => a.role).filter(Boolean),
           channels: [...new Set(agents.flatMap((a) => Object.keys(a.services || {})))] };
}

function suggestionsFor(paramName) {
  const vars = Object.keys(ed.doc.variables || {}).map((v) => `\${${v}}`);
  if (paramName === "default_role" || paramName === "roles") return datalist("dl-roles", [...castOf(ed.doc).roles, ...vars]);
  if (paramName === "channel") return datalist("dl-channels", [...new Set(["speech", "led", "gesture", ...castOf(ed.doc).channels])]);
  if (paramName === "service") return datalist("dl-services", [...knownServices(), ...vars]);
  if (/key|source|target/.test(paramName)) return datalist("dl-keys", [...keysInTree(), ...vars]);
  return datalist("dl-vars", vars);
}

// ----------------------------------------------------------------- parameter values
function typeOf(decl) {
  const t = String(decl.type || "str");
  if (t.includes("Any")) return "any";
  return t.split("|")[0];
}

function parseValue(text, type) {
  if (text === "") return undefined;
  if (text.startsWith("${") && text.endsWith("}")) return text;
  if (type === "int" || type === "float") return /^-?\d+(\.\d+)?$/.test(text.trim()) ? Number(text) : text;
  if (type === "bool") return text === "true" ? true : text === "false" ? false : text;
  if (type === "list" || type === "dict" || type === "any") {
    try { return JSON.parse(text); } catch { if (type === "any") return text; throw new Error("invalid JSON"); }
  }
  return text;
}

function display(value) {
  if (value === undefined || value === null) return "";
  return typeof value === "object" ? JSON.stringify(value, null, 1) : String(value);
}

function summary(node) {
  const p = node.params || {};
  if (node.type === "ServiceAction") return `${p.action || "REQUEST"} ${p.service || "?"}${p.output_key ? " → " + p.output_key : ""}`;
  if (node.type === "CheckValue") {
    const cond = ["equals", "not_equals", "one_of", "truthy"].find((k) => p[k] !== undefined);
    return `${p.key || "?"} ${cond ? cond.replace("_", " ") + " " + JSON.stringify(p[cond]) : ""}`;
  }
  if (node.type === "GroupScript" || node.type === "DialogueScript") return `${p.script || ""}${p.session && p.session !== "auto" ? " · " + p.session : ""}`;
  if (node.type === "AgentSpeak") return `agent in ${p.agent_key || "bot/agent"} speaks (${p.channel || "speech"})`;
  if (node.type === "AgentsAction") return `${p.action || "DO"} ${display(p.input_value ?? p.input_key ?? "")} → ${p.roles ? p.roles.join(", ") : "all agents"} (${p.channel || "?"})`;
  return Object.entries(p).slice(0, 2).map(([k, v]) => `${k}=${display(v)}`).join(" ");
}

// ----------------------------------------------------------------- rendering
function renderTreeList(container) {
  clear(container);
  container.append(h("h3", {}, "Trees", h("button", { class: "btn small", onclick: newTree }, "+ New")));
  const list = h("div", { class: "list" });
  state.trees.forEach((t) => list.append(h("div", {
    class: "list-item" + (t.name === ed.name ? " active" : ""), title: t.description, onclick: () => openTree(t.name),
  }, h("span", { class: "grow" }, t.title), h("span", { class: "meta" }, t.name))));
  container.append(list);
}

function renderPalette(container) {
  clear(container);
  container.append(h("h3", {}, "Nodes"));
  container.append(h("input", { placeholder: "Search nodes…", value: ed.filter,
    oninput: (e) => { ed.filter = e.target.value.toLowerCase(); renderPalette(container); container.querySelector("input").focus(); } }));
  const groups = {};
  state.paletteList.filter((n) => !n.type.startsWith("Test") && !String(n.doc).startsWith("Deprecated"))
    .filter((n) => !ed.filter || (n.type + " " + n.doc + " " + n.category).toLowerCase().includes(ed.filter))
    .forEach((n) => (groups[n.category] ||= []).push(n));
  for (const [category, nodes] of Object.entries(groups)) {
    const group = h("div", { class: "palette-group" }, h("div", {}, category));
    nodes.forEach((n) => group.append(h("div", {
      class: "palette-item", draggable: "true", title: n.doc + "\n(click to add, or drag into the tree)",
      onclick: () => addFromPalette(n.type),
      ondragstart: (e) => { ed.drag = { newType: n.type }; e.dataTransfer.setData("text/plain", n.type); },
    }, glyph(n.type), n.type, h("small", {}, n.kind === "composite" ? "container" : ""))));
    container.append(group);
  }
  container.append(h("p", { class: "hint" }, "Every HARMONI service is called with ServiceAction: pick the service id and the action. New services come from the Modules page."));
}

function issuesByPath() {
  const map = new Map();
  ed.issues.forEach((i) => {
    const p = issuePath(i.path);
    if (p) map.set(JSON.stringify(p), map.get(JSON.stringify(p)) === "error" ? "error" : i.level);
  });
  return map;
}

function renderOutline(container) {
  clear(container);
  if (!ed.doc) return container.append(h("div", { class: "empty" }, "Open a tree or create a new one."));
  const marks = issuesByPath();
  const build = (node, path) => {
    const key = JSON.stringify(path);
    const level = marks.get(key);
    const row = h("div", {
      class: "node-row" + (key === JSON.stringify(ed.selected) ? " selected" : "") + (level ? ` has-${level}` : ""),
      draggable: path.length ? "true" : "false", "data-path": key,
      onclick: (e) => { e.stopPropagation(); select(path); },
      ondragstart: (e) => { e.stopPropagation(); ed.drag = { path }; e.dataTransfer.setData("text/plain", key); },
      ondragover: (e) => { e.preventDefault(); e.stopPropagation(); markDrop(row, e, node); },
      ondragleave: () => row.classList.remove("drop-before", "drop-after", "drop-inside"),
      ondrop: (e) => { e.preventDefault(); e.stopPropagation(); drop(row, path); },
    }, glyph(node.type), h("span", { class: "name" }, node.name || node.type), h("span", { class: "type" }, node.type),
      h("span", { class: "summary" }, summary(node)));
    const li = h("li", {}, row);
    if (node.children) {
      const ul = h("ul");
      node.children.forEach((c, i) => ul.append(build(c, path.concat(i))));
      if (!node.children.length) ul.append(h("li", { class: "hint", style: { padding: "4px 8px" } }, "empty: drop nodes here"));
      li.append(ul);
    }
    return li;
  };
  container.append(h("ul", {}, build(ed.doc.root, [])));
}

function markDrop(row, event, node) {
  row.classList.remove("drop-before", "drop-after", "drop-inside");
  const rect = row.getBoundingClientRect();
  const y = (event.clientY - rect.top) / rect.height;
  const where = isComposite(node) && y > 0.3 && y < 0.7 ? "inside" : y < 0.5 ? "before" : "after";
  row.dataset.where = where;
  row.classList.add("drop-" + where);
}

function drop(row, path) {
  const where = row.dataset.where || "after";
  row.classList.remove("drop-before", "drop-after", "drop-inside");
  if (!ed.drag) return;
  if (ed.drag.newType) insert(newNode(ed.drag.newType), path, where);
  else move(ed.drag.path, path, where);
  ed.drag = null;
}

function paramInput(node, name, decl) {
  const type = typeOf(decl);
  const value = (node.params || {})[name];
  const set = (v) => {
    node.params ||= {};
    if (v === undefined) delete node.params[name]; else node.params[name] = v;
    changed(false);
  };
  let input;
  if (decl.choices) {
    input = h("select", { onchange: (e) => set(e.target.value || undefined) },
      h("option", { value: "" }, `(default${decl.default !== null ? ": " + decl.default : ""})`),
      decl.choices.map((c) => h("option", { value: c, selected: value === c }, c)));
  } else if (type === "list" || type === "dict") {
    input = h("textarea", { class: "code", rows: 3, placeholder: type === "dict" ? '{"input": "@bot/message"}' : "[]",
      oninput: (e) => { try { set(parseValue(e.target.value, type)); e.target.classList.remove("invalid"); } catch { e.target.classList.add("invalid"); } } },
      display(value));
  } else {
    const list = type === "bool" ? datalist("dl-bool", ["true", "false", ...Object.keys(ed.doc.variables || {}).map((v) => `\${${v}}`)]) : suggestionsFor(name);
    input = h("input", { value: display(value), list, placeholder: decl.default !== null && decl.default !== undefined ? `default: ${display(decl.default)}` : type,
      oninput: (e) => { try { set(parseValue(e.target.value, type)); e.target.classList.remove("invalid"); } catch { e.target.classList.add("invalid"); } } });
  }
  return h("label", { class: "field" },
    h("span", {}, name + (decl.required ? " *" : ""), h("small", {}, type)), input,
    decl.doc ? h("div", { class: "field-doc" }, decl.doc) : null);
}

function renderProperties(container) {
  clear(container);
  if (!ed.doc) return;
  if (ed.selected === null) return renderTreeSettings(container);
  const node = nodeAt(ed.selected);
  const meta = state.palette[node.type] || { params: {}, doc: "Unknown node type" };
  const head = h("div", { class: "section" },
    h("h3", {}, "Node", h("button", { class: "btn small", onclick: () => select(null) }, "Tree settings")),
    h("div", { class: "row", style: { marginBottom: "8px" } }, glyph(node.type), h("b", {}, node.type)),
    h("div", { class: "hint" }, meta.doc),
    h("label", { class: "field", style: { marginTop: "10px" } }, h("span", {}, "Name"),
      h("input", { value: node.name || "", oninput: (e) => { node.name = e.target.value; changed(false); } })));
  container.append(head);
  const params = h("div", { class: "section" }, h("h3", {}, "Parameters"));
  const entries = Object.entries(meta.params || {});
  if (!entries.length) params.append(h("div", { class: "hint" }, "No parameters."));
  entries.forEach(([name, decl]) => params.append(paramInput(node, name, decl)));
  const unknown = Object.keys(node.params || {}).filter((k) => !(meta.params || {})[k]);
  unknown.forEach((k) => params.append(h("div", { class: "hint" }, `Unknown parameter "${k}" `,
    h("button", { class: "btn small danger", onclick: () => { delete node.params[k]; changed(); } }, "remove"))));
  container.append(params);
  const effective = Object.fromEntries(Object.entries(meta.params || {}).map(([k, p]) => [k, (node.params || {})[k] ?? p.default]));
  const reads = resolveKeys(meta.reads, effective), writes = resolveKeys(meta.writes, effective);
  if (reads.length || writes.length) {
    container.append(h("div", { class: "section" }, h("h3", {}, "Blackboard"),
      reads.length ? h("div", {}, "reads ", reads.map((k) => h("code", { style: { marginRight: "6px" } }, k))) : null,
      writes.length ? h("div", {}, "writes ", writes.map((k) => h("code", { style: { marginRight: "6px" } }, k))) : null));
  }
  const path = ed.selected;
  container.append(h("div", { class: "section" }, h("h3", {}, "Actions"), h("div", { class: "row", style: { flexWrap: "wrap" } },
    h("button", { class: "btn small", disabled: !path.length, onclick: () => shift(-1) }, "↑ Up"),
    h("button", { class: "btn small", disabled: !path.length, onclick: () => shift(1) }, "↓ Down"),
    h("button", { class: "btn small", disabled: !path.length, onclick: duplicate }, "Duplicate"),
    h("button", { class: "btn small", onclick: () => wrap("Sequence") }, "Wrap in Sequence"),
    h("button", { class: "btn small", onclick: () => wrap("Selector") }, "Wrap in Selector"),
    h("button", { class: "btn small danger", disabled: !path.length, onclick: deleteSelected }, "Delete"))));
}

function kvEditor(title, obj, onChange, hint) {
  const box = h("div", { class: "section" }, h("h3", {}, title,
    h("button", { class: "btn small", onclick: () => { let n = "name", i = 1; while (n in obj) n = `name${i++}`; obj[n] = ""; onChange(true); } }, "+ Add")));
  if (hint) box.append(h("div", { class: "hint", style: { marginBottom: "6px" } }, hint));
  Object.entries(obj).forEach(([key, value]) => {
    const keyInput = h("input", { value: key, style: { flex: "0 0 40%" },
      onchange: (e) => { const v = obj[key]; delete obj[key]; obj[e.target.value] = v; onChange(true); } });
    const valueInput = h("input", { value: display(value), class: "mono",
      oninput: (e) => { obj[key] = parseValue(e.target.value, "any") ?? ""; onChange(false); } });
    box.append(h("div", { class: "row", style: { marginBottom: "4px" } }, keyInput, valueInput,
      h("button", { class: "btn small icon danger", title: "remove", onclick: () => { delete obj[key]; onChange(true); } }, "×")));
  });
  return box;
}

// The cast: any number of humans and of agents (robots). Agents are addressed by role in the tree;
// their services per channel say which robot realizes them, so conditions only change the cast.
function castEditor(doc) {
  const box = h("div", { class: "section" }, h("h3", {}, "Cast"));
  const hasCast = doc.cast && typeof doc.cast === "object";
  if (!hasCast) {
    box.append(h("div", { class: "hint", style: { marginBottom: "6px" } }, "Who takes part: humans and agents (robots, virtual agents)."),
      h("button", { class: "btn small", onclick: () => { doc.cast = { humans: [], agents: [] }; changed(true); } }, "+ Add a cast"));
    return box;
  }
  const cast = doc.cast;
  const humansText = typeof cast.humans === "string" ? cast.humans : (cast.humans || []).join(", ");
  box.append(h("label", { class: "field" }, h("span", {}, "Humans", h("small", {}, "comma separated, or ${variable}")),
    h("input", { value: humansText, list: datalist("dl-vars", Object.keys(doc.variables || {}).map((v) => `\${${v}}`)),
      oninput: (e) => { const v = e.target.value; cast.humans = v.trim().startsWith("${") ? v.trim() : v.split(",").map((x) => x.trim()).filter(Boolean); changed(false); } }),
    h("div", { class: "field-doc" }, "The script session and $USERNAME1, $USERNAME2… follow these names.")));
  cast.agents ||= [];
  box.append(h("div", { class: "row", style: { justifyContent: "space-between", margin: "4px 0" } },
    h("b", { style: { fontSize: "12.5px" } }, `Agents (${cast.agents.length})`),
    h("button", { class: "btn small", onclick: () => { cast.agents.push({ role: `Agent${cast.agents.length + 1}`, name: "", robot: "", services: { speech: "" } }); changed(true); } }, "+ Agent")));
  const services = datalist("dl-services", knownServices());
  cast.agents.forEach((agent, i) => {
    agent.services ||= {};
    const card = h("div", { class: "card", style: { padding: "8px", marginBottom: "8px" } },
      h("div", { class: "grid-2" },
        h("label", { class: "field" }, h("span", {}, "Role *"), h("input", { value: agent.role || "", oninput: (e) => { agent.role = e.target.value; changed(false); } })),
        h("label", { class: "field" }, h("span", {}, "Name"), h("input", { value: agent.name || "", oninput: (e) => { agent.name = e.target.value; changed(false); } }))),
      h("label", { class: "field" }, h("span", {}, "Robot"), h("input", { value: agent.robot || "", placeholder: "Furhat, NAO, Pepper, virtual…", oninput: (e) => { agent.robot = e.target.value; changed(false); } })),
      h("div", { style: { fontSize: "12.5px", fontWeight: 600, margin: "2px 0 4px" } }, "Services by channel"),
      Object.entries(agent.services).map(([channel, service]) => h("div", { class: "row", style: { marginBottom: "4px" } },
        h("input", { value: channel, style: { flex: "0 0 32%" }, list: datalist("dl-channel-names", ["speech", "led", "gesture", "gaze", "face"]),
          onchange: (e) => { const s = agent.services[channel]; delete agent.services[channel]; agent.services[e.target.value] = s; changed(true); } }),
        h("input", { value: service, list: services, placeholder: "service id", oninput: (e) => { agent.services[channel] = e.target.value; changed(false); } }),
        h("button", { class: "btn small icon danger", title: "remove", onclick: () => { delete agent.services[channel]; changed(true); } }, "×"))),
      h("div", { class: "row" },
        h("button", { class: "btn small", onclick: () => { let c = "channel", n = 1; while (c in agent.services) c = `channel${n++}`; agent.services[c] = ""; changed(true); } }, "+ Channel"),
        h("span", { class: "spacer" }),
        h("button", { class: "btn small danger", onclick: () => { cast.agents.splice(i, 1); changed(true); } }, "Remove agent")));
    box.append(card);
  });
  box.append(h("div", { class: "hint" }, "Leaves address agents by role (AgentSpeak, AgentsAction). Configurations and the Run page can override the cast, e.g. to swap which robot plays which role."));
  return box;
}

function renderTreeSettings(container) {
  const doc = ed.doc;
  container.append(h("div", { class: "section" }, h("h3", {}, "Tree settings"),
    h("label", { class: "field" }, h("span", {}, "Name"), h("input", { value: doc.name || "", oninput: (e) => { doc.name = e.target.value; changed(false); } })),
    h("label", { class: "field" }, h("span", {}, "Description"),
      h("textarea", { rows: 3, oninput: (e) => { doc.description = e.target.value; changed(false); } }, doc.description || "")),
    h("label", { class: "field" }, h("span", {}, "Stop when", h("small", {}, "blackboard key")),
      h("input", { value: doc.stop_when || "", list: datalist("dl-keys", keysInTree()), placeholder: "e.g. scene/finished",
        oninput: (e) => { if (e.target.value) doc.stop_when = e.target.value; else delete doc.stop_when; changed(false); } }),
      h("div", { class: "field-doc" }, "The runner stops when this value becomes true."))));
  doc.variables ||= {};
  container.append(kvEditor("Variables", doc.variables, (rerender) => changed(rerender),
    "Use them in parameters as ${name}; they can be overridden by configurations and on the Run page."));
  container.append(castEditor(doc));
  doc.blackboard ||= {};
  container.append(kvEditor("Initial blackboard", doc.blackboard, (rerender) => changed(rerender)));
  container.append(h("div", { class: "section hint" }, "Select a node to edit it. Shortcuts: Delete, Ctrl+D duplicate, Alt+↑/↓ move, Ctrl+S save."));
}

function renderIssues(container) {
  clear(container);
  if (!ed.doc) return;
  if (!ed.issues.length) return container.append(h("div", { class: "issue" }, h("span", { class: "lvl", style: { color: "var(--ok)" } }, "valid"), "No problems found."));
  ed.issues.forEach((i) => container.append(h("div", { class: `issue ${i.level}`, onclick: () => { const p = issuePath(i.path); if (p) select(p); } },
    h("span", { class: "lvl" }, i.level), h("span", {}, i.message), h("span", { class: "path" }, i.path))));
}

function renderCenter() {
  const body = root.querySelector("#compose-body");
  clear(body);
  if (ed.view === "diagram" && ed.doc) {
    const wrap = h("div", { class: "diagram-wrap" });
    body.append(wrap);
    renderDiagram(wrap, specToDiagram(ed.doc.root), { selected: ed.selected, onSelect: select, scale: "fit" });
  } else {
    const outline = h("div", { class: "outline", onclick: () => select(null) });
    body.append(outline);
    renderOutline(outline);
  }
}

function renderToolbar() {
  const bar = root.querySelector("#compose-toolbar");
  clear(bar);
  bar.append(
    h("span", { class: "title" }, ed.doc ? (ed.doc.name || ed.name) : "Compose"),
    ed.name ? h("span", { class: "pill" }, ed.name + (ed.dirty ? " • unsaved" : "")) : null,
    ed.doc ? h("span", { class: "pill " + (ed.issues.some((i) => i.level === "error") ? "err" : "ok") },
      ed.issues.some((i) => i.level === "error") ? "invalid" : "valid") : null,
    h("span", { class: "spacer" }),
    h("div", { class: "seg" },
      h("button", { class: ed.view === "outline" ? "active" : "", onclick: () => { ed.view = "outline"; renderAll(); } }, "Outline"),
      h("button", { class: ed.view === "diagram" ? "active" : "", onclick: () => { ed.view = "diagram"; renderAll(); } }, "Diagram")),
    h("button", { class: "btn", disabled: !ed.doc, onclick: saveAs }, "Save as…"),
    h("button", { class: "btn primary", disabled: !ed.doc, onclick: save }, "Save"),
    h("button", { class: "btn", disabled: !ed.name, title: "Run this tree on the Run page", onclick: () => emit("run-tree", ed.name) }, "▶ Run"),
  );
}

function renderAll() {
  renderToolbar();
  renderTreeList(root.querySelector("#compose-trees"));
  renderCenter();
  renderIssues(root.querySelector("#compose-issues"));
  renderProperties(root.querySelector("#compose-props"));
}

// ----------------------------------------------------------------- actions
function select(path) {
  ed.selected = path;
  renderCenter();
  renderProperties(root.querySelector("#compose-props"));
}

const validate = debounce(async () => {
  if (!ed.doc) return;
  try {
    const result = await api("/validate", { method: "POST", body: { tree: ed.doc } });
    ed.issues = result.issues;
  } catch (e) { ed.issues = [{ level: "error", path: "", message: e.message }]; }
  renderToolbar();
  renderIssues(root.querySelector("#compose-issues"));
  renderCenter();
}, 300);

function changed(rerenderProps = true) {
  ed.dirty = true;
  renderToolbar();
  renderCenter();
  if (rerenderProps) renderProperties(root.querySelector("#compose-props"));
  validate();
}

function shift(delta) {
  const path = ed.selected;
  const parent = nodeAt(path.slice(0, -1));
  const i = path[path.length - 1], j = i + delta;
  if (j < 0 || j >= parent.children.length) return;
  [parent.children[i], parent.children[j]] = [parent.children[j], parent.children[i]];
  ed.selected = path.slice(0, -1).concat(j);
  changed();
}

function duplicate() {
  const copy = clone(nodeAt(ed.selected));
  copy.name = (copy.name || copy.type) + " copy";
  insert(copy, ed.selected, "after");
}

function wrap(type) {
  const path = ed.selected;
  const node = nodeAt(path);
  const wrapper = { type, name: type, params: {}, children: [node] };
  if (!path.length) ed.doc.root = wrapper;
  else nodeAt(path.slice(0, -1)).children[path[path.length - 1]] = wrapper;
  ed.selected = findPath(wrapper);
  changed();
}

function deleteSelected() {
  if (!ed.selected || !ed.selected.length) return;
  removeAt(ed.selected);
  ed.selected = ed.selected.length > 1 ? ed.selected.slice(0, -1) : null;
  changed();
}

async function openTree(name) {
  if (ed.dirty && !confirm("Discard the unsaved changes?")) return;
  ed.doc = await guard(api(`/trees/${encodeURIComponent(name)}`));
  ed.name = name; ed.selected = null; ed.dirty = false; ed.issues = [];
  renderAll();
  validate();
}

async function save() {
  if (!ed.doc) return;
  const result = await guard(api(`/trees/${encodeURIComponent(ed.name)}`, { method: "PUT", body: ed.doc }));
  ed.issues = result.issues; ed.dirty = false;
  toast(result.valid ? `Saved ${ed.name}` : `Saved ${ed.name} (with errors)`, result.valid ? "ok" : "err");
  await reloadTrees();
}

async function saveAs() {
  let name = prompt("File name of the tree", ed.name || "my_interaction.json");
  if (!name) return;
  if (!name.endsWith(".json")) name += ".json";
  ed.name = name;
  await save();
}

async function newTree() {
  if (ed.dirty && !confirm("Discard the unsaved changes?")) return;
  let name = prompt("File name of the new tree", "my_interaction.json");
  if (!name) return;
  if (!name.endsWith(".json")) name += ".json";
  ed.name = name;
  ed.doc = { harmoni_tree: 1, name: name.replace(/\.json$/, ""), description: "", variables: {},
             root: { type: "Sequence", name: "Main", params: {}, children: [] } };
  ed.selected = []; ed.dirty = true; ed.issues = [];
  renderAll();
  validate();
}

async function reloadTrees() {
  state.trees = await api("/trees");
  renderTreeList(root.querySelector("#compose-trees"));
  renderToolbar();
  emit("trees-changed");
}

export function initCompose(container) {
  root = container;
  container.classList.add("layout-3");
  container.append(
    h("aside", { class: "col side" }, h("div", { class: "section", id: "compose-trees" }), h("div", { class: "section", id: "compose-palette" })),
    h("div", { class: "col", style: { display: "flex", flexDirection: "column" } },
      h("div", { class: "toolbar", id: "compose-toolbar" }),
      h("div", { id: "compose-body", style: { flex: 1, overflow: "auto", display: "flex", flexDirection: "column" } }),
      h("div", { class: "issues", id: "compose-issues" })),
    h("aside", { class: "col side-right", id: "compose-props" }),
  );
  on("catalog", () => { renderPalette(container.querySelector("#compose-palette")); renderAll(); });
  on("open-tree", (name) => openTree(name));
  document.addEventListener("keydown", (e) => {
    if (!container.classList.contains("active") || !ed.doc) return;
    const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName);
    if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); save(); }
    if (typing) return;
    if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); deleteSelected(); }
    if ((e.ctrlKey || e.metaKey) && e.key === "d" && ed.selected && ed.selected.length) { e.preventDefault(); duplicate(); }
    if (e.altKey && e.key === "ArrowUp" && ed.selected && ed.selected.length) { e.preventDefault(); shift(-1); }
    if (e.altKey && e.key === "ArrowDown" && ed.selected && ed.selected.length) { e.preventDefault(); shift(1); }
  });
  window.addEventListener("beforeunload", (e) => { if (ed.dirty) { e.preventDefault(); e.returnValue = ""; } });
}

export function openTreeIfNone() {
  if (!ed.doc && state.trees.length) openTree(state.trees[0].name);
}
