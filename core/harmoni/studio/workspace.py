"""Files edited by HARMONI Studio: tree files, dialogue scripts and service configurations.

Only files inside these folders can be read or written:

- trees:   ``core/trees/*.json``
- scripts: ``core/trees/scripts/*.json``
- configs: ``core/trees/*.yaml`` (simulation) and ``ros2/config/*.yaml`` (ROS 2)
"""

import json
import re
from pathlib import Path

import yaml

from harmoni.config import parse_config
from harmoni.services import available_backends
from harmoni.tree.cast import Cast, merge_cast
from harmoni.tree.spec import has_errors, load_spec, resolve_spec, services_used, validate

NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,80}$")
CONFIG_PLACES = {"core": ("core", "trees"), "ros2": ("ros2", "config")}


class WorkspaceError(ValueError):
    pass


def check_name(name, suffixes):
    if not NAME_RE.match(name or "") or ".." in name:
        raise WorkspaceError(f"invalid file name '{name}'")
    if not name.endswith(suffixes):
        raise WorkspaceError(f"'{name}' must end with {' or '.join(suffixes)}")
    return name


class Workspace:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.trees_dir = self.root / "core" / "trees"
        self.scripts_dir = self.trees_dir / "scripts"

    # ------------------------------------------------------------------ trees
    def list_trees(self):
        trees = []
        for path in sorted(self.trees_dir.glob("*.json")):
            try:
                spec = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                spec = {}
            cast = spec.get("cast") if isinstance(spec.get("cast"), dict) else {}
            trees.append({"name": path.name, "title": spec.get("name", path.stem),
                          "description": spec.get("description", ""),
                          "roles": [a.get("role") for a in cast.get("agents") or [] if isinstance(a, dict)]})
        return trees

    def tree_path(self, name):
        return self.trees_dir / check_name(name, (".json",))

    def read_tree(self, name):
        path = self.tree_path(name)
        if not path.is_file():
            raise FileNotFoundError(name)
        return json.loads(path.read_text(encoding="utf-8"))

    def write_tree(self, name, spec):
        if not isinstance(spec, dict):
            raise WorkspaceError("a tree must be a JSON object")
        clean = {k: v for k, v in spec.items() if not k.startswith("_")}
        path = self.tree_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(clean, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return self.validate_tree(clean)

    def validate_tree(self, spec, variables=None):
        spec = dict(spec)
        spec["_base_dir"] = str(self.trees_dir)
        resolved, issues = resolve_spec(spec, variables)
        issues += validate(resolved, resolved=True)
        return {
            "issues": [{"level": i.level, "path": i.path, "message": i.message} for i in issues],
            "valid": not has_errors(issues),
            "services": services_used(spec),
        }

    # ------------------------------------------------------------------ scripts
    def list_scripts(self):
        return [p.name for p in sorted(self.scripts_dir.glob("*.json"))]

    def read_script(self, name):
        return json.loads((self.scripts_dir / check_name(name, (".json",))).read_text(encoding="utf-8"))

    def write_script(self, name, script):
        if not isinstance(script, dict) or not all(isinstance(v, list) for v in script.values()):
            raise WorkspaceError("a script maps session names to lists of scenes")
        for session, scenes in script.items():
            for i, scene in enumerate(scenes):
                if not isinstance(scene, dict) or "utterance" not in scene or scene.get("nlp") not in (0, 1):
                    raise WorkspaceError(f"{session}[{i}]: a scene needs 'utterance' and 'nlp' (0 or 1)")
        path = self.scripts_dir / check_name(name, (".json",))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(script, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # ------------------------------------------------------------------ service configurations
    def _config_path(self, config_id):
        place, _, name = str(config_id).partition(":")
        if place not in CONFIG_PLACES:
            raise WorkspaceError(f"unknown configuration '{config_id}' (use core:<file> or ros2:<file>)")
        return self.root.joinpath(*CONFIG_PLACES[place]) / check_name(name, (".yaml", ".yml"))

    def list_configs(self):
        configs = []
        for place, parts in CONFIG_PLACES.items():
            for path in sorted(self.root.joinpath(*parts).glob("*.y*ml")):
                info = {"id": f"{place}:{path.name}", "place": place, "name": path.name}
                try:
                    parsed = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                    info["services"] = list((parsed.get("services") or {}).keys())
                    info["tree"] = (parsed.get("tree") or {}).get("file", "")
                except yaml.YAMLError:
                    info["services"], info["tree"] = [], ""
                configs.append(info)
        return configs

    def read_config(self, config_id):
        path = self._config_path(config_id)
        if not path.is_file():
            raise FileNotFoundError(config_id)
        text = path.read_text(encoding="utf-8")
        return {"id": config_id, "text": text, **self.check_config_text(text, config_id)}

    def write_config(self, config_id, text):
        result = self.check_config_text(text, config_id)
        if result["parsed"] is None:
            raise WorkspaceError("; ".join(i["message"] for i in result["issues"]))
        path = self._config_path(config_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return result

    def check_config_text(self, text, config_id=None):
        """Parse a service configuration (resolving ``extends``) and check backends, parameters and tree"""
        issues = []
        path = str(self._config_path(config_id)) if config_id else None
        try:
            parsed = parse_config(text, path)
        except (yaml.YAMLError, ValueError, OSError) as e:
            return {"parsed": None, "issues": [{"level": "error", "path": "yaml", "message": str(e)}]}
        backends = available_backends()
        services = parsed.get("services") or {}
        for service_id, params in services.items():
            params = params or {}
            name = params.get("backend")
            if name not in backends:
                issues.append({"level": "error", "path": f"services.{service_id}",
                               "message": f"unknown backend '{name}'"})
                continue
            declared = (getattr(backends[name], "backend_info", {}) or {}).get("params", {})
            for key in params:
                if key not in ("backend", "subscribe") and declared and key not in declared:
                    issues.append({"level": "warning", "path": f"services.{service_id}.{key}",
                                   "message": f"'{name}' does not declare this parameter"})
            for key, decl in declared.items():
                if decl.required and params.get(key) in (None, "") and not params.get("mockup"):
                    issues.append({"level": "warning", "path": f"services.{service_id}.{key}",
                                   "message": "required parameter is empty"})
        tree_file = (parsed.get("tree") or {}).get("file")
        if tree_file:
            tree_path = self.root / tree_file
            if not tree_path.is_file():
                issues.append({"level": "error", "path": "tree.file", "message": f"{tree_file} not found"})
            else:
                try:
                    for service_id in services_used(load_spec(str(tree_path)), (parsed.get("tree") or {}).get("cast")):
                        if service_id not in services:
                            issues.append({"level": "warning", "path": "services",
                                           "message": f"the tree calls '{service_id}', which is not configured"})
                except Exception as e:  # noqa: BLE001
                    issues.append({"level": "error", "path": "tree.file", "message": str(e)})
        parsed.pop("_extends", None)
        return {"parsed": parsed, "issues": issues}

    def run_defaults(self, tree, config_id=None, cast=None, variables=None):
        """Effective variables and cast of a tree run with a configuration (and run-time overrides)"""
        spec = load_spec(str(self.tree_path(tree)))
        config_tree = {}
        if config_id:
            config_tree = (self.read_config(config_id)["parsed"] or {}).get("tree") or {}
        merged_variables = dict(config_tree.get("variables") or {})
        merged_variables.update(variables or {})
        merged_cast = merge_cast(config_tree.get("cast"), cast) if config_tree.get("cast") else cast
        resolved, _ = resolve_spec(spec, merged_variables, merged_cast)
        return {
            "variables": resolved.get("variables") or {},
            "cast": Cast.from_spec(resolved.get("cast")).to_dict(),
            "config_variables": merged_variables,
            "config_cast": merged_cast,
        }
