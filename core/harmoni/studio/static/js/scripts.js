// Scripts: the scenes of scripted dialogues (used by the GroupScript leaf).

import { api, clear, datalist, guard, h, toast } from "./lib.js";

const sc = { name: null, script: null, session: null, dirty: false };
let root;

function renderList(container, names) {
  clear(container);
  container.append(h("h3", {}, "Scripts", h("button", { class: "btn small", onclick: newScript }, "+ New")));
  const list = h("div", { class: "list" });
  names.forEach((n) => list.append(h("div", { class: "list-item" + (n === sc.name ? " active" : ""), onclick: () => open(n) },
    h("span", { class: "grow" }, n))));
  container.append(list);
  container.append(h("p", { class: "hint" },
    "A script has one list of scenes per session (e.g. 1session, 2session…). Scripted scenes are said as written by their robot; ",
    "LLM scenes let the orchestrator decide. $USERNAME1, $USERNAME2… are replaced by the participants' names."));
}

function render() {
  const main = root.querySelector("#scripts-main");
  clear(main);
  if (!sc.script) return main.append(h("div", { class: "empty" }, "Open a script or create a new one."));
  const sessions = Object.keys(sc.script);
  if (!sc.session || !sc.script[sc.session]) sc.session = sessions[0];
  main.append(h("div", { class: "toolbar" },
    h("span", { class: "title" }, sc.name), sc.dirty ? h("span", { class: "pill warn" }, "unsaved") : null,
    h("div", { class: "seg" }, sessions.map((s) => h("button", { class: s === sc.session ? "active" : "",
      onclick: () => { sc.session = s; render(); } }, s))),
    h("button", { class: "btn small", onclick: addSession }, "+ Session"),
    h("span", { class: "spacer" }),
    h("button", { class: "btn", onclick: () => addScene(sc.script[sc.session].length) }, "+ Scene"),
    h("button", { class: "btn primary", onclick: save }, "Save")));
  const scenes = sc.script[sc.session] || [];
  const agents = datalist("dl-agents", ["Mover", "Opposer"]);
  const table = h("table", { class: "grid" }, h("thead", {}, h("tr", {},
    h("th", { style: { width: "40px" } }, "#"), h("th", { style: { width: "140px" } }, "Robot"),
    h("th", { style: { width: "130px" } }, "Who decides"), h("th", {}, "Utterance"), h("th", { style: { width: "120px" } }, ""))));
  const body = h("tbody");
  scenes.forEach((scene, i) => {
    const touch = () => { sc.dirty = true; render(); };
    body.append(h("tr", {},
      h("td", {}, String(i)),
      h("td", {}, h("input", { value: scene.agent || "", list: agents, oninput: (e) => { scene.agent = e.target.value; sc.dirty = true; } })),
      h("td", {}, h("select", { onchange: (e) => { scene.nlp = Number(e.target.value); touch(); } },
        h("option", { value: 0, selected: scene.nlp === 0 }, "Script"), h("option", { value: 1, selected: scene.nlp !== 0 }, "LLM"))),
      h("td", {}, h("textarea", { rows: 2, placeholder: scene.nlp === 0 ? "What the robot says" : "(the LLM decides; optional note)",
        oninput: (e) => { scene.utterance = e.target.value; sc.dirty = true; } }, scene.utterance || "")),
      h("td", {}, h("div", { class: "row" },
        h("button", { class: "btn small icon", title: "move up", onclick: () => swap(i, i - 1) }, "↑"),
        h("button", { class: "btn small icon", title: "move down", onclick: () => swap(i, i + 1) }, "↓"),
        h("button", { class: "btn small icon", title: "insert after", onclick: () => addScene(i + 1) }, "+"),
        h("button", { class: "btn small icon danger", title: "delete", onclick: () => { scenes.splice(i, 1); touch(); } }, "×")))));
  });
  table.append(body);
  main.append(h("div", { style: { padding: "12px 14px" } }, table,
    h("p", { class: "hint" }, `${scenes.length} scenes. The last scene is the closing one: it is said when the interaction ends.`)));
}

function swap(i, j) {
  const scenes = sc.script[sc.session];
  if (j < 0 || j >= scenes.length) return;
  [scenes[i], scenes[j]] = [scenes[j], scenes[i]];
  sc.dirty = true; render();
}

function addScene(index) {
  sc.script[sc.session].splice(index, 0, { id: index, utterance: "", agent: "Mover", nlp: 1, gesture: "" });
  sc.dirty = true; render();
}

function addSession() {
  const name = prompt("Session name (e.g. 2session for two participants)");
  if (!name) return;
  sc.script[name] = JSON.parse(JSON.stringify(sc.script[sc.session] || []));
  sc.session = name; sc.dirty = true; render();
}

async function open(name) {
  if (sc.dirty && !confirm("Discard the unsaved changes?")) return;
  sc.script = await guard(api(`/scripts/${encodeURIComponent(name)}`));
  sc.name = name; sc.session = null; sc.dirty = false;
  await refresh();
}

async function newScript() {
  let name = prompt("File name of the new script", "my_script.json");
  if (!name) return;
  if (!name.endsWith(".json")) name += ".json";
  sc.name = name; sc.dirty = true; sc.session = "1session";
  sc.script = { "1session": [
    { id: 0, utterance: "Hi $USERNAME1, I am a robot. Nice to meet you!", agent: "Mover", nlp: 0, gesture: "" },
    { id: 1, utterance: "", agent: "Mover", nlp: 1, gesture: "" },
    { id: 2, utterance: "Thank you, see you next time!", agent: "Mover", nlp: 0, gesture: "" }] };
  render();
}

async function save() {
  sc.script[sc.session].forEach((scene, i) => { scene.id = i; });
  await guard(api(`/scripts/${encodeURIComponent(sc.name)}`, { method: "PUT", body: sc.script }), `Saved ${sc.name}`);
  sc.dirty = false;
  await refresh();
}

async function refresh() {
  renderList(root.querySelector("#scripts-list"), await api("/scripts"));
  render();
}

export function initScripts(container) {
  root = container;
  container.classList.add("layout-2");
  container.append(h("aside", { class: "col side" }, h("div", { class: "section", id: "scripts-list" })),
    h("div", { class: "col", id: "scripts-main" }));
  refresh().catch((e) => toast(e.message, "err"));
}
