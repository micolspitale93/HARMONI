// Run: simulate a tree in-process, or monitor/command a tree running on ROS 2.
// Studio only observes snapshots and sends commands between ticks: it is never in the control loop.
// Everything shown here is generic: the cast (any number of humans and agents) and the
// conversation log come from the snapshots, not from keys of a particular interaction.

import { api, clear, guard, h, on, state, toast } from "./lib.js";
import { renderDiagram } from "./diagram.js";

const rn = { tree: null, config: null, variables: {}, cast: { humans: [], agents: [] }, period: 0.3,
             snapshot: null, log: [], mode: "simulation", running: false, scale: "fit" };
let root;

function lastTree() { return state.trees.find((t) => t.name === rn.tree) ? rn.tree : (state.trees[0] || {}).name; }

function configServices() {
  const config = state.configs.find((c) => c.id === rn.config);
  return (config && config.services) || [];
}

// Variables and cast of the tree as configured (the configuration overrides the tree file)
async function loadDefaults() {
  if (!rn.tree) return;
  try {
    const d = await api("/run/defaults", { method: "POST", body: { tree: rn.tree, config: rn.config } });
    rn.variables = d.variables || {};
    rn.cast = d.cast || { humans: [], agents: [] };
  } catch (e) { toast(e.message, "err"); }
  renderControls();
}

function castControls() {
  const box = h("div", { class: "section" }, h("h3", {}, "Cast of this run"));
  box.append(h("label", { class: "field" }, h("span", {}, `Humans (${rn.cast.humans.length})`, h("small", {}, "comma separated")),
    h("input", { value: rn.cast.humans.join(", "), "data-cast": "humans",
      oninput: (e) => { rn.cast.humans = e.target.value.split(",").map((x) => x.trim()).filter(Boolean); } })));
  const services = configServices();
  if (!rn.cast.agents.length) box.append(h("div", { class: "hint" }, "This tree has no agents in its cast."));
  rn.cast.agents.forEach((agent) => {
    const row = h("div", { class: "card", style: { padding: "6px 8px", marginBottom: "6px" } },
      h("div", { class: "row" }, h("b", {}, agent.role), h("span", { class: "hint" }, [agent.name, agent.robot].filter(Boolean).join(" · "))));
    Object.entries(agent.services || {}).forEach(([channel, service]) => row.append(h("div", { class: "row", style: { marginTop: "4px" } },
      h("span", { class: "hint", style: { flex: "0 0 30%" } }, channel),
      h("select", { "data-agent": agent.role, "data-channel": channel, onchange: (e) => { agent.services[channel] = e.target.value; } },
        [...new Set([service, ...services])].map((s) => h("option", { value: s, selected: s === service }, s + (services.includes(s) ? "" : " (not configured)")))))));
    box.append(row);
  });
  box.append(h("div", { class: "hint" }, "Changes apply to the next Start, without editing the tree or the configuration."));
  return box;
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
        ? "The tree runs inside Studio with the services, variables and cast of the configuration (mock services need no robot or key)."
        : "Studio follows /harmoni/tree/status and sends commands on /harmoni/tree/command. Start the tree with ./harmoni.sh ros2 run …")),
  );
  if (sim) {
    box.append(h("div", { class: "section" }, h("h3", {}, "What to run"),
      h("label", { class: "field" }, h("span", {}, "Tree"),
        h("select", { "data-select": "tree", onchange: (e) => { rn.tree = e.target.value; loadDefaults(); } },
          state.trees.map((t) => h("option", { value: t.name, selected: t.name === rn.tree }, `${t.title} (${t.name})`)))),
      h("label", { class: "field" }, h("span", {}, "Configuration", h("small", {}, "services, variables, cast")),
        h("select", { "data-select": "config", onchange: (e) => { rn.config = e.target.value; loadDefaults(); } },
          configs.map((c) => h("option", { value: c.id, selected: c.id === rn.config }, c.id)))),
      h("label", { class: "field" }, h("span", {}, "Tick period", h("small", {}, "seconds")),
        h("input", { value: rn.period, "data-period": "", oninput: (e) => { rn.period = Number(e.target.value) || 0.3; } }))));
    box.append(castControls());
    const vars = h("div", { class: "section" }, h("h3", {}, "Variables"));
    if (!Object.keys(rn.variables).length) vars.append(h("div", { class: "hint" }, "This tree has no variables."));
    Object.entries(rn.variables).forEach(([k, v]) => vars.append(h("div", { class: "row", style: { marginBottom: "4px" } },
      h("code", { style: { flex: "0 0 45%", overflow: "hidden", textOverflow: "ellipsis" } }, k),
      h("input", { value: typeof v === "object" ? JSON.stringify(v) : String(v), class: "mono", "data-var": k,
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

function conversationOf(snap) { return ((snap && snap.blackboard) || {})["/conversation"] || []; }

function renderConversation() {
  const box = root.querySelector("#run-transcript");
  clear(box);
  const turns = conversationOf(rn.snapshot);
  if (!turns.length) return box.append(h("div", { class: "hint" }, "Who says what appears here: humans on the left, agents on the right."));
  turns.slice(-60).forEach((t) => box.append(h("div", { class: "bubble " + (t.kind === "agent" ? "robot" : t.kind === "event" ? "event" : "") },
    h("span", { class: "who" }, t.kind === "event" ? "·" : t.speaker, t.role && t.role !== t.speaker ? ` (${t.role})` : "", t.to ? ` → ${t.to}` : ""),
    t.text)));
  box.scrollTop = box.scrollHeight;
}

// Turns per participant: everyone in the cast is listed, also who has not spoken yet
function renderParticipation() {
  const box = root.querySelector("#run-participation");
  clear(box);
  const snap = rn.snapshot;
  const cast = (snap && snap.cast) || rn.cast;
  const counts = {};
  conversationOf(snap).forEach((t) => { if (t.kind !== "event") counts[t.speaker] = (counts[t.speaker] || 0) + 1; });
  const rows = [
    ...cast.humans.map((name) => ({ name, kind: "human", n: counts[name] || 0 })),
    ...cast.agents.map((a) => ({ name: a.name || a.role, label: a.name ? `${a.name} (${a.role})` : a.role, kind: "agent", n: counts[a.name || a.role] || 0 })),
  ];
  Object.keys(counts).filter((name) => !rows.find((r) => r.name === name)).forEach((name) => rows.push({ name, kind: "human", n: counts[name], unknown: true }));
  if (!rows.length) return box.append(h("div", { class: "hint" }, "No cast."));
  const max = Math.max(1, ...rows.map((r) => r.n));
  rows.forEach((r) => box.append(h("div", { class: "part-row", "data-participant": r.name },
    h("span", { class: "part-name", title: r.unknown ? "not in the cast" : "" }, r.label || r.name, r.unknown ? " ?" : ""),
    h("span", { class: "part-bar" }, h("span", { class: `part-fill ${r.kind}`, style: { width: `${(100 * r.n) / max}%` } })),
    h("span", { class: "part-n" }, String(r.n)))));
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
    if (snap.cast) status.append(h("span", { class: "pill" }, `${snap.cast.humans.length} humans · ${snap.cast.agents.length} agents`));
    if (snap.error) status.append(h("span", { class: "pill err", title: snap.error }, snap.error.slice(0, 80)));
  }
  status.append(h("span", { class: "spacer" }),
    h("button", { class: "btn small", title: "zoom out", onclick: () => zoom(-0.15) }, "−"),
    h("button", { class: "btn small" + (rn.scale === "fit" ? " active" : ""), title: "fit to width", onclick: () => { rn.scale = "fit"; renderLive(); } }, "Fit"),
    h("button", { class: "btn small", title: "zoom in", onclick: () => zoom(0.15) }, "+"));
  const diagram = root.querySelector("#run-diagram");
  if (snap && snap.root) renderDiagram(diagram, snap.root, { scale: rn.scale });
  else { clear(diagram); diagram.append(h("div", { class: "empty" }, "Start a simulation, or connect to ROS 2, to see the tree live.")); }

  renderConversation();
  renderParticipation();

  const bb = root.querySelector("#run-blackboard");
  clear(bb);
  const table = h("table", { class: "kv" });
  Object.entries((snap && snap.blackboard) || {}).filter(([k]) => k !== "/conversation" && !k.startsWith("/cast/")).forEach(([k, v]) =>
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

async function start() {
  if (!rn.tree || !rn.config) return toast("Choose a tree and a configuration", "err");
  rn.log = []; rn.snapshot = null;
  renderLive();
  await guard(api("/run", { method: "POST", body: { tree: rn.tree, config: rn.config, variables: rn.variables,
                                                     cast: rn.cast, period_s: rn.period } }));
  rn.running = true;
  renderControls();
}

async function connectRos() {
  rn.log = []; rn.snapshot = null;
  await guard(api("/ros2/connect", { method: "POST", body: {} }), "Connected to ROS 2");
}

async function command(cmd) { await guard(api("/run/command", { method: "POST", body: { command: cmd } }), `Sent ${cmd}`); }
async function stop() { await guard(api("/run/stop", { method: "POST", body: {} })); rn.running = false; renderControls(); }

function connectEvents() {
  const source = new EventSource("/api/events");
  source.addEventListener("snapshot", (e) => {
    const snap = JSON.parse(e.data);
    rn.snapshot = snap;
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
      h("div", { class: "diagram-wrap", id: "run-diagram", style: { flex: "1 1 50%", minHeight: "220px" } }),
      h("div", { class: "run-panels" },
        h("div", { class: "card" }, h("header", {}, "Conversation"),
          h("div", { class: "body transcript", id: "run-transcript" })),
        h("div", { class: "card" }, h("header", {}, "Participation", h("span", { class: "hint", style: { fontWeight: 400 } }, "turns")),
          h("div", { class: "body", id: "run-participation" })),
        h("div", { class: "card" }, h("header", {}, "Service activity"),
          h("div", { class: "body log", id: "run-log" })))),
    h("aside", { class: "col side-right" },
      h("div", { id: "run-controls" }),
      h("div", { class: "section" }, h("h3", {}, "Blackboard"), h("div", { id: "run-blackboard" }))));
  on("catalog", () => { renderControls(); loadDefaults(); });
  on("run-tree", (name) => { rn.tree = name; rn.mode = "simulation"; loadDefaults(); });
  on("run-config", (id) => { rn.config = id; rn.mode = "simulation"; loadDefaults(); });
  on("page:run", () => renderLive());
  api("/run").then((s) => { rn.snapshot = s.snapshot; rn.log = s.log || []; rn.running = s.running; renderLive(); });
  connectEvents();
  renderLive();
}
