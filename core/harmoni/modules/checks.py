"""Checks run before a module is shared with everyone, and visibility changes."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

import yaml

from harmoni.modules import MANIFEST, ModuleInfo, forget, get_module, modules_dir, read_manifest

SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), "OpenAI-like API key"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
    (re.compile(r"""(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*["'][A-Za-z0-9_\-/+=]{16,}["']"""),
     "hard-coded credential"),
]
TEXT_SUFFIXES = {".py", ".yaml", ".yml", ".json", ".md", ".txt", ".cfg", ".toml", ".sh"}


def run_tests(path: Path, timeout: int = 300):
    """Run the tests of a module in a separate process. Returns (ok, output)."""
    tests = Path(path) / "tests"
    if not tests.is_dir():
        return False, "no tests/ folder"
    env = dict(os.environ)
    core_dir = Path(__file__).resolve().parents[2]  # the core/ folder of this HARMONI
    env["PYTHONPATH"] = os.pathsep.join([str(core_dir), env.get("PYTHONPATH", "")])
    try:
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(tests)],
                              cwd=str(path), env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"tests did not finish in {timeout} s"
    return proc.returncode == 0, (proc.stdout + proc.stderr)[-6000:]


def find_secrets(path: Path) -> List[str]:
    found = []
    for file in sorted(Path(path).rglob("*")):
        if not file.is_file() or file.suffix not in TEXT_SUFFIXES or "__pycache__" in file.parts:
            continue
        text = file.read_text(encoding="utf-8", errors="replace")
        for pattern, what in SECRET_PATTERNS:
            if pattern.search(text):
                found.append(f"{file.relative_to(path)}: {what}")
    return found


def check_module(info: ModuleInfo, with_tests: bool = True) -> List[dict]:
    """Checks required to share a module with everyone. Each: {check, ok, detail}."""
    manifest = info.manifest or {}
    results = []

    def add(check, ok, detail=""):
        results.append({"check": check, "ok": bool(ok), "detail": detail})

    add("loads without errors", info.loaded and not info.error, info.error)
    for key in ("description", "author", "license"):
        add(f"manifest has a {key}", bool(str(manifest.get(key, "")).strip()), "edit harmoni_module.yaml")
    readme = info.path / "README.md"
    add("README describes the module", readme.is_file() and "TODO" not in readme.read_text(encoding="utf-8"),
        "README.md must exist and contain no TODO")
    secrets = find_secrets(info.path)
    add("no credentials in the files", not secrets, "; ".join(secrets) or "credentials must come from .env")
    if with_tests:
        ok, output = run_tests(info.path)
        add("tests pass", ok, output)
    return results


def set_visibility(name: str, visibility: str, with_tests: bool = True):
    """Move a module between modules/private and modules/public.

    Making a module public requires every check of :func:`check_module` to pass.
    Returns (ok, checks, new path).
    """
    info = get_module(name)
    if info is None:
        raise KeyError(f"module '{name}' not found")
    if info.visibility == visibility:
        return True, [], info.path
    if info.visibility not in ("private", "public"):
        raise ValueError(f"module '{name}' is in an external folder ({info.path}): move it by hand")
    checks = []
    if visibility == "public":
        checks = check_module(info, with_tests=with_tests)
        if not all(c["ok"] for c in checks):
            return False, checks, info.path
    target = modules_dir(visibility) / info.path.name
    if target.exists():
        raise FileExistsError(f"{target} already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(info.path), str(target))
    manifest = read_manifest(target)
    manifest["visibility"] = visibility
    (target / MANIFEST).write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    forget(name)
    return True, checks, target
