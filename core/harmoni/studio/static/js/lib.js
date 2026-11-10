// Shared helpers: DOM creation, API calls, notifications, application state.

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") el.className = value;
    else if (key === "style" && typeof value === "object") Object.assign(el.style, value);
    else if (key.startsWith("on")) el.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === "value") el.value = value;
    else if (value === true) el.setAttribute(key, "");
    else el.setAttribute(key, value);
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

export function clear(el) {
  while (el.firstChild) el.removeChild(el.firstChild);
  return el;
}

export async function api(path, { method = "GET", body } = {}) {
  const response = await fetch("/api" + path, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await response.json(); } catch { data = null; }
  if (!response.ok) throw new Error((data && data.error) || `${response.status} ${response.statusText}`);
  return data;
}

export function toast(message, kind = "") {
  const el = h("div", { class: `toast ${kind}` }, message);
  document.getElementById("toasts").append(el);
  setTimeout(() => el.remove(), kind === "err" ? 7000 : 3500);
}

export async function guard(promise, okMessage) {
  try {
    const result = await promise;
    if (okMessage) toast(okMessage, "ok");
    return result;
  } catch (e) {
    toast(e.message, "err");
    throw e;
  }
}

export function debounce(fn, ms = 300) {
  let timer;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
}

export const clone = (value) => JSON.parse(JSON.stringify(value));

// ----------------------------------------------------------------- application state
export const state = {
  palette: {},        // type -> node type description
  paletteList: [],
  backends: [],
  configs: [],
  trees: [],
  info: {},
  listeners: {},
};

export function on(event, fn) { (state.listeners[event] ||= []).push(fn); }
export function emit(event, data) { (state.listeners[event] || []).forEach((fn) => fn(data)); }

export async function refreshCatalog() {
  const [palette, backends, configs, trees] = await Promise.all([
    api("/palette"), api("/backends"), api("/configs"), api("/trees"),
  ]);
  state.paletteList = palette;
  state.palette = Object.fromEntries(palette.map((n) => [n.type, n]));
  state.backends = backends;
  state.configs = configs;
  state.trees = trees;
  emit("catalog");
}

// Service ids known from the configurations and from the modules (for suggestions)
export function knownServices() {
  const ids = new Set();
  state.configs.forEach((c) => (c.services || []).forEach((s) => ids.add(s)));
  state.backends.filter((b) => b.module).forEach((b) => ids.add(`${b.name}_default`));
  return [...ids].sort();
}

export const GLYPHS = {
  Sequence: "→", Selector: "?", Parallel: "⇉", ServiceAction: "◆", CheckValue: "◇", SetValue: "=",
  CopyValue: "⧉", Wait: "⏱", GroupScript: "S", ScriptedTurn: "T", OrchestratorDecision: "D",
  DialogueScript: "S", AgentSpeak: "◉", AgentsAction: "⁂", LogUtterance: "✎",
};

export function glyph(type) {
  const meta = state.palette[type] || {};
  const category = (meta.category || "general").replace(/\s+/g, "-");
  return h("span", { class: `glyph ${category}`, title: `${type} (${meta.category || ""})` },
    GLYPHS[type] || (type || "?")[0]);
}

export function datalist(id, values) {
  let el = document.getElementById(id);
  if (!el) { el = h("datalist", { id }); document.body.append(el); }
  clear(el);
  values.forEach((v) => el.append(h("option", { value: v })));
  return id;
}
