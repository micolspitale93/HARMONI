"""HARMONI modules: new sensors, detectors, dialogues and actuators, added without touching the core.

A module is a folder with a manifest ``harmoni_module.yaml`` and a python file registering one
(or more) service backends with ``@register_backend`` (it may also register tree leaves)::

    modules/
    ├── public/<name>/      shared with everyone: committed to the HARMONI repository
    └── private/<name>/     only on this machine: ignored by git

More folders can be added with the environment variable ``HARMONI_MODULE_PATH`` (``:`` separated),
e.g. a git repository shared by a team. Modules are created by
:func:`harmoni.modules.generator.create_module` (or the HARMONI Studio "Modules" page) and are then
usable as ``backend: <name>`` in service configurations, on ROS 2 and in simulation.
"""

import importlib.util
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

log = logging.getLogger("harmoni.modules")

MANIFEST = "harmoni_module.yaml"
VISIBILITIES = ("private", "public")


def harmoni_root() -> Path:
    """Root of the HARMONI repository (HARMONI_ROOT, or the folder that contains core/)"""
    env = os.environ.get("HARMONI_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3]


def modules_dir(visibility: str) -> Path:
    if visibility not in VISIBILITIES:
        raise ValueError(f"visibility must be one of {VISIBILITIES}")
    return harmoni_root() / "modules" / visibility


def search_paths() -> List[Path]:
    paths = [modules_dir("public"), modules_dir("private")]
    for extra in os.environ.get("HARMONI_MODULE_PATH", "").split(os.pathsep):
        if extra.strip():
            paths.append(Path(extra.strip()))
    return paths


@dataclass
class ModuleInfo:
    name: str
    path: Path
    manifest: dict
    visibility: str
    loaded: bool = False
    error: str = ""
    backends: List[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "name": self.name,
            "path": str(self.path),
            "visibility": self.visibility,
            "loaded": self.loaded,
            "error": self.error,
            "backends": self.backends,
            "manifest": self.manifest,
        }


_MODULES: Dict[str, ModuleInfo] = {}


def read_manifest(path: Path) -> dict:
    with open(path / MANIFEST, "r", encoding="utf-8") as f:
        manifest = yaml.safe_load(f) or {}
    if not isinstance(manifest, dict) or not manifest.get("name"):
        raise ValueError(f"{path / MANIFEST}: 'name' is required")
    return manifest


def discover() -> List[ModuleInfo]:
    """Find the modules in the search paths (without importing them)"""
    found = []
    for base in search_paths():
        if not base.is_dir():
            continue
        visibility = base.name if base.name in VISIBILITIES and base.parent.name == "modules" else "external"
        for path in sorted(p for p in base.iterdir() if (p / MANIFEST).is_file()):
            try:
                manifest = read_manifest(path)
            except Exception as e:  # noqa: BLE001
                found.append(ModuleInfo(path.name, path, {}, visibility, error=str(e)))
                continue
            found.append(ModuleInfo(manifest["name"], path, manifest, visibility))
    return found


def _import_module(info: ModuleInfo):
    from harmoni.services.base import _BACKENDS

    before = set(_BACKENDS)
    entry = info.path / info.manifest.get("backend", "backend.py")
    module_name = f"harmoni_modules.{info.name}"
    spec = importlib.util.spec_from_file_location(module_name, entry)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    info.backends = sorted(set(_BACKENDS) - before) or [
        name for name, cls in _BACKENDS.items() if getattr(cls, "__module__", "") == module_name]
    for name in info.backends:
        _BACKENDS[name].backend_info["module"] = info.name


def load_modules(reload: bool = False) -> List[ModuleInfo]:
    """Import every module found (once). A broken module is reported, never raised."""
    for info in discover():
        known = _MODULES.get(info.name)
        if known is not None and not reload and known.path == info.path and (known.loaded or known.error):
            continue
        if info.error:
            _MODULES[info.name] = info
            continue
        try:
            _import_module(info)
            info.loaded = True
        except Exception as e:  # noqa: BLE001 - a broken module must not break HARMONI
            info.error = f"{type(e).__name__}: {e}"
            log.warning("module %s not loaded: %s", info.name, info.error)
        _MODULES[info.name] = info
    return list(_MODULES.values())


def list_modules() -> List[ModuleInfo]:
    load_modules()
    present = {info.path for info in discover()}
    return [m for m in _MODULES.values() if m.path in present]


def get_module(name: str) -> Optional[ModuleInfo]:
    for info in list_modules():
        if info.name == name:
            return info
    return None


def forget(name: str):
    _MODULES.pop(name, None)
