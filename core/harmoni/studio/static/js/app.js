// HARMONI Studio entry point: pages and shared catalog.

import { api, emit, on, refreshCatalog, state, toast } from "./lib.js";
import { initCompose, openTreeIfNone } from "./compose.js";
import { initScripts } from "./scripts.js";
import { initServices } from "./services.js";
import { initRun } from "./run.js";
import { initModules } from "./modules.js";

function showPage(name) {
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.page === name));
  document.querySelectorAll(".page").forEach((p) => p.classList.toggle("active", p.id === `page-${name}`));
  if (location.hash !== `#${name}`) history.replaceState(null, "", `#${name}`);
  emit(`page:${name}`);
}

async function main() {
  document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => showPage(b.dataset.page)));
  try {
    state.info = await api("/info");
  } catch (e) {
    toast("Cannot reach the Studio server: " + e.message, "err");
    return;
  }
  const ros = document.getElementById("ros-pill");
  ros.textContent = state.info.ros2_available ? "ROS 2 available" : "ROS 2: not here";
  ros.className = "pill " + (state.info.ros2_available ? "ok" : "");
  ros.title = state.info.ros2_available ? "Studio runs where rclpy is available: it can monitor ROS 2 trees"
    : "Simulation only. Run ./harmoni.sh ros2 studio to monitor trees running on ROS 2";

  initCompose(document.getElementById("page-compose"));
  initScripts(document.getElementById("page-scripts"));
  initServices(document.getElementById("page-services"));
  initRun(document.getElementById("page-run"));
  initModules(document.getElementById("page-modules"));
  on("run-tree", () => showPage("run"));
  on("run-config", () => showPage("run"));

  await refreshCatalog();
  openTreeIfNone();
  const pages = ["compose", "scripts", "services", "run", "modules"];
  const fromHash = () => {
    const name = (location.hash || "#compose").slice(1);
    showPage(pages.includes(name) ? name : "compose");
  };
  window.addEventListener("hashchange", fromHash); // links, back and forward
  fromHash();
}

main();
