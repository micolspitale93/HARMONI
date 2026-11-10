// Run: simulate a tree in-process, or monitor/command a tree running on ROS 2.
// Studio only observes snapshots and sends commands between ticks: it is never in the control loop.

import { api, clear, guard, h, on, state, toast } from "./lib.js";
import { renderDiagram } from "./diagram.js";

const rn = { tree: null, config: null, variables: {}, period: 0.3, snapshot: null, log: [], transcript: [],
             last: {}, mode: "simulation", running: false, scale: "fit" };
let root;

function lastTree() { return state.trees.find((t) => t.name === rn.tree) ? rn.tree : (state.trees[0] || {}).name; }

async function loadVariables() {
  if (!rn.tree) return;
  try {
    const tree = await api(`/trees/${encodeURIComponent(rn.tree)}`);
    rn.variables = Object.assign({}, tree.variables || {});
  } catch { rn.variables = {}; }
  renderControls();
}

function renderControls() {
  const box = root.querySelector("#run-controls");
  clear(box);
  rn.tree = lastTree();
  const configs = state.configs.filter((c) => (c.services || []).length);
  if (!rn.config || !configs.find((c) => c.id === rn.config)) rn.config = (configs.find((c) => /mock/.test(c.id)) || configs[0] || {}).id;
  const sim = rn.mode === "simulation";
  box.append(
    h("div", { class: "section" }, h("h3", {}, "Source"),
      h("div", { class: "seg" },
        h("button", { class: sim ? "active" : "", onclick: () => { rn.mode = "simulation"; renderControls(); } }, "Simulation"),
        h("button", { class: !sim ? "active" : "", disabled: !state.info.ros2_available,
          title: state.info.ros2_available ? "Monitor the tree running on ROS 2" : "Run Studio in the ROS 2 container to enable it",
          onclick: () => { rn.mode = "ros2"; renderControls(); } }, "ROS 2 live")),
      h("p", { class: "hint" }, sim
        ? "The tree runs inside Studio with the backends of the configuration (mock ones need no robot or key)."
        : "Studio follows /harmoni/tree/status and sends commands on /harmoni/tree/command. Start the tree with ./harmoni.sh ros2 run …")),
  );
  if (sim) {
    box.append(h("div", { class: "section" }, h("h3", {}, "What to run"),
      h("label", { class: "field" }, h("span", {}, "Tree"),
        h("select", { onchange: (e) => { rn.tree = e.target.value; loadVariables(); } },
          state.trees.map((t) => h("option", { value: t.name, selected: t.name === rn.tree }, `${t.title} (${t.name})`)))),
      h("label", { class: "field" }, h("span", {}, "Services", h("small", {}, "configuration")),
        h("select", { onchange: (e) => { rn.config = e.target.value; } },
          configs.map((c) => h("option", { value: c.id, selected: c.id === rn.config }, c.id)))),
      h("label", { class: "field" }, h("span", {}, "Tick period", h("small", {}, "seconds")),
        h("input", { value: rn.period, oninput: (e) => { rn.period = Number(e.target.value) || 0.3; } }))));
    const vars = h("div", { class: "section" }, h("h3", {}, "Variables"));
    if (!Object.keys(rn.variables).length) vars.append(h("div", { class: "hint" }, "This tree has no variables."));
    Object.entries(rn.variables).forEach(([k, v]) => vars.append(h("div", { class: "row", style: { marginBottom: "4px" } },
      h("code", { style: { flex: "0 0 45%", overflow: "hidden", textOverflow: "ellipsis" } }, k),
      h("input", { value: typeof v === "object" ? JSON.stringify(v) : String(v), class: "mono",
        oninput: (e) => { let val = e.target.value; try { val = JSON.parse(val); } catch { /* keep text */ } rn.variables[k] = val; } }))));
    box.append(vars);
  }
  box.append(h("div", { class: "section" }, h("h3", {}, "Control"), h("div", { class: "row", style: { flexWrap: "wrap" } },
    sim ? h("button", { class: "btn primary", onclick: start }, rn.running ? "Restart" : "▶ Start")
        : h("button", { class: "btn primary", onclick: connectRos }, "Connect"),
    h("button", { class: "btn", onclick: () => command("pause") }, "Pause"),
    h("button", { class: "btn", onclick: () => command("resume") }, "Resume"),
    h("button", { class: "btn", onclick: () => command("reload"), title: "Re-read the tree file (after an edit)" }, "Reload"),
    h("button", { class: "btn danger", onclick: stop }, "Stop"))));
}

function renderLive() {
  const snap = rn.snapshot;
  const status = root.querySelector("#run-status");
  clear(status);
  status.append(h("span", { class: "title" }, snap ? snap.tree : "Nothing running"));
  if (snap) {
    const cls = { running: "run", finished: "ok", error: "err", paused: "warn", stopped: "" }[snap.state] || "";
    status.append(h("span", { class: `pill ${cls}` }, snap.state), h("span", { class: "pill" }, `tick ${snap.tick}`),
      h("span", { class: "pill accent" }, snap.source || rn.mode));
    if (snap.error) status.append(h("span", { class: "pill err", title: snap.error }, snap.error.slice(0, 80)));
  }
  status.append(h("span", { class: "spacer" }),
    h("button", { class: "btn small", title: "zoom out", onclick: () => zoom(-0.15) }, "−"),
    h("button", { class: "btn small" + (rn.scale === "fit" ? " active" : ""), title: "fit to width", onclick: () => { rn.scale = "fit"; renderLive(); } }, "Fit"),
    h("button", { class: "btn small", title: "zoom in", onclick: () => zoom(0.15) }, "+"));
  const diagram = root.querySelector("#run-diagram");
  if (snap && snap.root) renderDiagram(diagram, snap.root, { scale: rn.scale });
  else { clear(diagram); diagram.append(h("div", { class: "empty" }, "Start a simulation, or connect to ROS 2, to see the tree live.")); }

  const transcript = root.querySelector("#run-transcript");
  clear(transcript);
  if (!rn.transcript.length) transcript.append(h("div", { class: "hint" }, "What people and robots say appears here."));
  rn.transcript.slice(-40).forEach((t) => transcript.append(h("div", { class: "bubble " + (t.robot ? "robot" : "") },
    h("span", { class: "who" }, t.who), t.text)));
  transcript.scrollTop = transcript.scrollHeight;

  const bb = root.querySelector("#run-blackboard");
  clear(bb);
  const table = h("table", { class: "kv" });
  Object.entries((snap && snap.blackboard) || {}).forEach(([k, v]) =>
    table.append(h("tr", {}, h("td", {}, k), h("td", {}, typeof v === "object" ? JSON.stringify(v) : String(v)))));
  bb.append(table);

  const log = root.querySelector("#run-log");
  clear(log);
  rn.log.slice(-150).forEach((l) => log.append(h("div", {}, h("span", { class: "src" }, l.source), " ", l.message)));
  log.scrollTop = log.scrollHeight;
}

function zoom(delta) {
  const svg = root.querySelector("#run-diagram svg");
  const current = rn.scale === "fit" && svg ? svg.width.baseVal.value / svg.viewBox.baseVal.width : (rn.scale === "fit" ? 1 : rn.scale);
  rn.scale = Math.max(0.3, Math.min(1.8, current + delta));
  renderLive();
}

// The transcript is derived from the blackboard: new transcriptions and new robot sentences.
function updateTranscript(snap) {
  const bb = snap.blackboard || {};
  const said = bb["/stt/result"];
  if (said && said !== rn.last.stt) {
    const match = String(said).match(/^([^:]{1,40}):\s*(.*)$/s);
    rn.transcript.push({ who: match ? match[1] : "participant", text: match ? match[2] : said, robot: false });
  }
  rn.last.stt = said;
  const message = bb["/bot/message"];
  const key = `${snap.tick}:${message}`;
  if (message && bb["/bot/speak"] && message !== rn.last.message && !rn.last.keys?.has(key)) {
    const agent = bb["/bot/agent"] && bb["/bot/agent"] !== "null" ? bb["/bot/agent"] : (bb["/scene/agent"] || "robot");
    rn.transcript.push({ who: agent, text: message, robot: true });
  }
  rn.last.message = message;
}

async function start() {
  if (!rn.tree || !rn.config) return toast("Choose a tree and a services configuration", "err");
  rn.transcript = []; rn.log = []; rn.last = {}; rn.snapshot = null;
  renderLive();
  await guard(api("/run", { method: "POST", body: { tree: rn.tree, config: rn.config, variables: rn.variables, period_s: rn.period } }));
  rn.running = true;
  renderControls();
}

async function connectRos() {
  rn.transcript = []; rn.log = []; rn.last = {}; rn.snapshot = null;
  await guard(api("/ros2/connect", { method: "POST", body: {} }), "Connected to ROS 2");
}

async function command(cmd) { await guard(api("/run/command", { method: "POST", body: { command: cmd } }), `Sent ${cmd}`); }
async function stop() { await guard(api("/run/stop", { method: "POST", body: {} })); rn.running = false; renderControls(); }

function connectEvents() {
  const source = new EventSource("/api/events");
  source.addEventListener("snapshot", (e) => {
    const snap = JSON.parse(e.data);
    rn.snapshot = snap;
    updateTranscript(snap);
    const pill = document.getElementById("run-pill");
    pill.textContent = `${snap.state} · tick ${snap.tick}`;
    pill.className = "pill " + ({ running: "run", finished: "ok", error: "err", paused: "warn" }[snap.state] || "");
    if (root.classList.contains("active")) renderLive();
  });
  source.addEventListener("log", (e) => { rn.log.push(JSON.parse(e.data)); if (root.classList.contains("active")) renderLive(); });
  source.addEventListener("state", (e) => { const s = JSON.parse(e.data); rn.running = !!s.running; });
  source.onerror = () => { document.getElementById("run-pill").textContent = "disconnected"; };
}

export function initRun(container) {
  root = container;
  container.classList.add("layout-run");
  container.append(
    h("div", { class: "col", style: { display: "flex", flexDirection: "column" } },
      h("div", { class: "toolbar", id: "run-status" }),
      h("div", { class: "diagram-wrap", id: "run-diagram", style: { flex: "1 1 55%", minHeight: "220px" } }),
      h("div", { class: "run-panels" },
        h("div", { class: "card" }, h("header", {}, "Conversation"),
          h("div", { class: "body transcript", id: "run-transcript" })),
        h("div", { class: "card" }, h("header", {}, "Service activity"),
          h("div", { class: "body log", id: "run-log" })))),
    h("aside", { class: "col side-right" },
      h("div", { id: "run-controls" }),
      h("div", { class: "section" }, h("h3", {}, "Blackboard"), h("div", { id: "run-blackboard" }))));
  on("catalog", () => { renderControls(); if (!Object.keys(rn.variables).length) loadVariables(); });
  on("run-tree", (name) => { rn.tree = name; rn.mode = "simulation"; loadVariables(); });
  on("run-config", (id) => { rn.config = id; rn.mode = "simulation"; renderControls(); });
  on("page:run", () => renderLive());
  api("/run").then((s) => { rn.snapshot = s.snapshot; rn.log = s.log || []; rn.running = s.running; renderLive(); });
  connectEvents();
  renderLive();
}
