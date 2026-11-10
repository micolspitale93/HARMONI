"""Module system: generation, discovery, loading, checks, visibility"""

import json
import shutil
import sys

import pytest

from harmoni import modules
from harmoni.constants import ActionType
from harmoni.modules.checks import check_module, find_secrets, set_visibility
from harmoni.modules.generator import ModuleSpecError, create_module, normalize_spec
from harmoni.services import base, create_backend, describe_backends
from harmoni.tree import describe

SPEC = {
    "name": "raised_hand",
    "kind": "detector",
    "description": "Detects a raised hand in the camera image",
    "author": "HARMONI team",
    "actions": ["REQUEST"],
    "params": [{"name": "threshold", "type": "float", "default": "0.5", "doc": "detection threshold"},
               {"name": "camera", "type": "str", "default": "default"}],
    "requirements": ["mediapipe>=0.10"],
    "credentials": ["HAND_API_KEY"],
}


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv("HARMONI_ROOT", str(tmp_path))
    monkeypatch.delenv("HARMONI_MODULE_PATH", raising=False)
    yield tmp_path
    for name in [n for n, cls in base._BACKENDS.items() if (cls.backend_info or {}).get("module")]:
        base._BACKENDS.pop(name)
        modules.forget(name)
    for name in list(sys.modules):
        if name.startswith("harmoni_modules."):
            del sys.modules[name]


def test_spec_validation():
    with pytest.raises(ModuleSpecError) as e:
        normalize_spec({"name": "Bad Name", "kind": "teleporter", "params": [{"name": "class"}],
                        "credentials": ["lowercase"], "visibility": "secret"})
    text = str(e.value)
    for expected in ("name:", "kind:", "description:", "params[0].name", "credentials:", "visibility:"):
        assert expected in text
    with pytest.raises(ModuleSpecError):
        normalize_spec(dict(SPEC, name="furhat"))  # an existing backend


def test_defaults_are_coerced_and_actions_defaulted():
    s = normalize_spec(dict(SPEC, actions=[], kind="actuator"))
    assert s["actions"] == ["DO"]
    assert s["params"][0]["default"] == 0.5


def test_create_load_and_use_a_module(root):
    folder = create_module(SPEC)
    assert folder == root / "modules" / "private" / "raised_hand"
    for name in ("harmoni_module.yaml", "backend.py", "tests/test_raised_hand.py", "example_tree.json",
                 "example_config.yaml", "requirements.txt", "README.md"):
        assert (folder / name).is_file(), name
    info = {m.name: m for m in modules.list_modules()}["raised_hand"]
    assert info.loaded and info.backends == ["raised_hand"] and info.visibility == "private"
    backend = create_backend("raised_hand", "raised_hand_default", {"threshold": 0.7})
    assert backend.threshold == 0.7
    result = backend.handle(ActionType.REQUEST, "frame")
    assert result.ok and json.loads(result.message)["input"] == "frame"
    assert not backend.handle(ActionType.DO, "x").ok
    described = {b["name"]: b for b in describe_backends()}["raised_hand"]
    assert described["module"] == "raised_hand" and described["credentials"] == ["HAND_API_KEY"]
    assert described["params"]["threshold"]["type"] == "float"


def test_generated_tests_pass(root):
    from harmoni.modules.checks import run_tests

    ok, output = run_tests(create_module(dict(SPEC, actions=["REQUEST", "DO", "ON", "OFF"])))
    assert ok, output


def test_duplicate_module(root):
    create_module(SPEC)
    with pytest.raises(ModuleSpecError):
        create_module(dict(SPEC, visibility="public"))


def test_broken_module_is_reported_not_raised(root):
    folder = create_module(SPEC)
    (folder / "backend.py").write_text("raise RuntimeError('broken on purpose')")
    modules.forget("raised_hand")
    info = {m.name: m for m in modules.load_modules()}["raised_hand"]
    assert not info.loaded and "broken on purpose" in info.error
    assert describe()  # the palette still works


def test_secrets_are_detected(root):
    folder = create_module(SPEC)
    assert find_secrets(folder) == []
    (folder / "backend.py").write_text((folder / "backend.py").read_text() + '\nAPI_KEY = "sk-abcdefghijklmnopqrstuvwxyz123456"\n')
    assert find_secrets(folder)


def test_publish_requires_checks_then_moves(root):
    create_module(dict(SPEC, author=""))
    ok, checks, path = set_visibility("raised_hand", "public", with_tests=False)
    failed = {c["check"] for c in checks if not c["ok"]}
    assert not ok and "manifest has a author" in failed and path.parent.name == "private"
    # complete the module, then publish
    readme = path / "README.md"
    readme.write_text(readme.read_text().replace("TODO", "HARMONI team"))
    manifest = path / "harmoni_module.yaml"
    manifest.write_text(manifest.read_text().replace("author: ''", "author: HARMONI team"))
    modules.forget("raised_hand")
    ok, checks, path = set_visibility("raised_hand", "public", with_tests=True)
    assert ok, checks
    assert path == root / "modules" / "public" / "raised_hand"
    assert {m.name: m for m in modules.list_modules()}["raised_hand"].visibility == "public"
    # and back to private, without checks
    ok, _, path = set_visibility("raised_hand", "private")
    assert ok and path.parent.name == "private"


def test_external_module_path(root, tmp_path_factory, monkeypatch):
    team = tmp_path_factory.mktemp("team_modules")
    folder = create_module(dict(SPEC, name="team_sensor", kind="sensor"))
    shutil.move(str(folder), str(team / "team_sensor"))
    modules.forget("team_sensor")
    monkeypatch.setenv("HARMONI_MODULE_PATH", str(team))
    info = {m.name: m for m in modules.list_modules()}["team_sensor"]
    assert info.visibility == "external" and info.loaded
