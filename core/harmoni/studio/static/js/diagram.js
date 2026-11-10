// Top-down SVG drawing of a behavior tree, with the live status of every node.
// Input nodes: {name, type, status?, message?, children?}

const SVG = "http://www.w3.org/2000/svg";
const W = 168, H = 48, GAP_X = 14, GAP_Y = 54, PAD = 12;
const COMPOSITES = new Set(["Sequence", "Selector", "Parallel"]);
const ICON = { Sequence: "→", Selector: "?", Parallel: "⇉" };

function s(tag, attrs = {}, text) {
  const el = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (text !== undefined) el.textContent = text;
  return el;
}

function measure(node) {
  const children = node.children || [];
  if (!children.length) return (node._w = W);
  const sum = children.reduce((acc, c) => acc + measure(c), 0) + GAP_X * (children.length - 1);
  return (node._w = Math.max(W, sum));
}

function place(node, x, y, path, out) {
  node._x = x + node._w / 2 - W / 2;
  node._y = y;
  node._path = path;
  out.push(node);
  let cx = x;
  (node.children || []).forEach((child, i) => {
    place(child, cx, y + H + GAP_Y, path.concat(i), out);
    cx += child._w + GAP_X;
  });
}

function truncate(text, n) {
  text = String(text || "");
  return text.length > n ? text.slice(0, n - 1) + "…" : text;
}

// scale: a number, or "fit" to fit the width of the container (never enlarging)
export function renderDiagram(container, root, { selected = null, onSelect = null, scale = 1 } = {}) {
  container.replaceChildren();
  if (!root) return;
  const tree = JSON.parse(JSON.stringify(root));
  measure(tree);
  const nodes = [];
  place(tree, PAD, PAD, [], nodes);
  const depth = Math.max(...nodes.map((n) => n._y)) + H + PAD;
  const width = tree._w + PAD * 2;
  if (scale === "fit") scale = Math.max(0.62, Math.min(1, (container.clientWidth - 32) / width));
  const svg = s("svg", { class: "diagram", width: width * scale, height: depth * scale, viewBox: `0 0 ${width} ${depth}` });
  for (const node of nodes) {
    for (const child of node.children || []) {
      const x1 = node._x + W / 2, y1 = node._y + H, x2 = child._x + W / 2, y2 = child._y;
      const my = (y1 + y2) / 2;
      svg.append(s("path", { class: "edge", d: `M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}` }));
    }
  }
  const key = selected ? JSON.stringify(selected) : null;
  for (const node of nodes) {
    const composite = COMPOSITES.has(node.type);
    const g = s("g", { class: "node" + (key === JSON.stringify(node._path) ? " selected" : ""),
      transform: `translate(${node._x},${node._y})` });
    g.append(s("rect", { class: `box ${composite ? "composite" : ""} ${node.status || ""}`, width: W, height: H, rx: 8 }));
    const label = (composite ? (ICON[node.type] || "") + " " : "") + truncate(node.name, 22);
    g.append(s("text", { x: 10, y: 19, "font-weight": 600 }, label));
    g.append(s("text", { x: 10, y: 36, class: "sub" }, truncate(node.message || node.type, 28)));
    const title = s("title");
    title.textContent = `${node.name} (${node.type})${node.status ? " " + node.status : ""}${node.message ? "\n" + node.message : ""}`;
    g.append(title);
    if (onSelect) g.addEventListener("click", () => onSelect(node._path));
    svg.append(g);
  }
  container.append(svg);
}

// Convert a tree file node into the structure used by the diagram (no status).
export function specToDiagram(node) {
  if (!node) return null;
  const params = node.params || {};
  const message = params.service ? `${params.action || "REQUEST"} ${params.service}` : (params.key ? params.key : node.type);
  return { name: node.name || node.type, type: node.type, message,
           children: (node.children || []).map(specToDiagram) };
}
