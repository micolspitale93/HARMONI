"""HARMONI Studio API, against a real server on a temporary copy of the workspace"""

import json
import shutil
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from harmoni import modules
from harmoni.services import base
from harmoni.studio.server import make_server

CORE = Path(__file__).resolve().parents[1]
REPO = CORE.parent


@pytest.fixture
def studio(tmp_path, monkeypatch):
    shutil.copytree(CORE / "trees", tmp_path / "core" / "trees")
    shutil.copytree(REPO / "ros2" / "config", tmp_path / "ros2" / "config")
    monkeypatch.setenv("HARMONI_ROOT", str(tmp_path))
    monkeypatch.delenv("HARMONI_MODULE_PATH", raising=False)
    server = make_server(tmp_path, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", tmp_path
    server.studio.runs.stop()
    server.shutdown()
    for name in [n for n, cls in base._BACKENDS.items() if (cls.backend_info or {}).get("module")]:
        base._BACKENDS.pop(name)
        modules.forget(name)
    for name in list(sys.modules):
        if name.startswith("harmoni_modules."):
            del sys.modules[name]


def call(url, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_info_palette_backends(studio):
    url, root = studio
    status, info = call(url + "/api/info")
    assert status == 200 and info["root"] == str(root)
    _, palette = call(url + "/api/palette")
    assert {"Sequence", "ServiceAction", "GroupScript"} <= {n["type"] for n in palette}
    _, backends = call(url + "/api/backends")
    assert {"assistant", "azure_diarization", "furhat", "nao_http", "mock"} <= {b["name"] for b in backends}


def test_trees_read_write_validate(studio):
    url, root = studio
    _, trees = call(url + "/api/trees")
    assert "group_interaction.json" in [t["name"] for t in trees]
    _, tree = call(url + "/api/trees/group_interaction.json")
    tree["name"] = "Edited"
    status, result = call(url + "/api/trees/edited.json", "PUT", tree)
    assert status == 200 and result["valid"] and "bot_default" in result["services"]
    assert json.loads((root / "core" / "trees" / "edited.json").read_text())["name"] == "Edited"
    status, result = call(url + "/api/validate", "POST", {"tree": {"harmoni_tree": 1, "root": {"type": "Nope"}}})
    assert status == 200 and not result["valid"]


@pytest.mark.parametrize("name", ["../evil.json", "evil.txt", "..%2Fevil.json"])
def test_invalid_names_are_rejected(studio, name):
    url, _ = studio
    status, _ = call(url + "/api/trees/" + name, "PUT", {"harmoni_tree": 1})
    assert status in (400, 404)


def test_scripts(studio):
    url, _ = studio
    _, scripts = call(url + "/api/scripts")
    assert "group_interaction.json" in scripts
    _, script = call(url + "/api/scripts/group_interaction.json")
    assert {"1session", "2session", "3session"} <= set(script)
    assert call(url + "/api/scripts/new.json", "PUT", {"1session": [{"utterance": "Hi", "agent": "Mover", "nlp": 0}]})[0] == 200
    assert call(url + "/api/scripts/bad.json", "PUT", {"1session": [{"agent": "Mover"}]})[0] == 400


def test_configs(studio):
    url, root = studio
    _, configs = call(url + "/api/configs")
    ids = [c["id"] for c in configs]
    assert "core:group_interaction.mock.yaml" in ids and "ros2:group_interaction_mock.yaml" in ids
    status, config = call(url + "/api/configs/ros2:group_interaction_mock.yaml")
    assert status == 200 and "services:" in config["text"]
    assert [i for i in config["issues"] if i["level"] == "error"] == []
    _, checked = call(url + "/api/configs-check", "POST", {"text": "services:\n  x: {backend: teleport}\n"})
    assert any("unknown backend" in i["message"] for i in checked["issues"])
    assert call(url + "/api/configs/core:broken.yaml", "PUT", {"text": "services: [unclosed"})[0] == 400
    _, snippet = call(url + "/api/service-snippet", "POST",
                      {"service_id": "speaker_furhat", "backend": "furhat", "params": {"robot_ip": "1.2.3.4", "voice": ""}})
    assert snippet["snippet"] == "  speaker_furhat:\n    backend: furhat\n    robot_ip: 1.2.3.4\n"


def test_simulation_run_streams_snapshots(studio):
    url, _ = studio
    events = []

    def listen():
        with urllib.request.urlopen(url + "/api/events", timeout=60) as response:
            for line in response:
                line = line.decode().strip()
                if line.startswith("event:"):
                    events.append(line.split(":", 1)[1].strip())
                if len(events) > 20:
                    return

    threading.Thread(target=listen, daemon=True).start()
    status, _ = call(url + "/api/run", "POST", {"tree": "group_interaction.json",
                                                "config": "core:group_interaction.mock.yaml",
                                                "variables": {"max_scenes": 5}, "period_s": 0.01})
    assert status == 200
    for _ in range(500):
        _, state = call(url + "/api/run")
        snapshot = state.get("snapshot") or {}
        if snapshot.get("state") == "finished":
            break
        time.sleep(0.02)
    assert snapshot["state"] == "finished" and snapshot["source"] == "simulation"
    assert any("Furhat says" in entry["message"] for entry in state["log"])
    assert "snapshot" in events
    assert call(url + "/api/run/command", "POST", {"command": "pause"})[0] == 400  # nothing running


def test_simulation_with_bad_config(studio):
    url, _ = studio
    status, error = call(url + "/api/run", "POST", {"tree": "group_interaction.json", "config": "core:missing.yaml"})
    assert status == 404


def test_ros2_connect_without_rclpy(studio):
    url, _ = studio
    status, error = call(url + "/api/ros2/connect", "POST", {})
    assert status == 400 and "rclpy" in error["error"]


def test_modules_lifecycle(studio):
    url, root = studio
    spec = {"name": "wave_detector", "kind": "detector", "description": "Detects waving", "author": "",
            "actions": ["REQUEST"], "params": [{"name": "fps", "type": "int", "default": 10}]}
    _, preview = call(url + "/api/modules-preview", "POST", dict(spec, name="Bad Name"))
    assert preview["errors"]
    _, preview = call(url + "/api/modules-preview", "POST", spec)
    assert "class WaveDetectorBackend" in preview["backend"] and not preview["errors"]
    assert not (root / "modules" / "private" / "wave_detector").exists()  # preview writes nothing

    status, created = call(url + "/api/modules", "POST", spec)
    assert status == 200 and created["loaded"] and created["backends"] == ["wave_detector"]
    assert call(url + "/api/modules", "POST", spec)[0] == 400  # duplicate
    _, listed = call(url + "/api/modules")
    module = {m["name"]: m for m in listed}["wave_detector"]
    assert module["visibility"] == "private" and module["checks"]
    _, backends = call(url + "/api/backends")
    assert "wave_detector" in {b["name"] for b in backends}

    _, code = call(url + "/api/modules/wave_detector/backend")
    assert call(url + "/api/modules/wave_detector/backend", "PUT", {"text": "def broken(:"})[0] == 400
    edited = code["text"].replace('"input": data}', '"input": data, "waving": True}')
    status, reloaded = call(url + "/api/modules/wave_detector/backend", "PUT", {"text": edited})
    assert status == 200 and reloaded["loaded"]

    _, tested = call(url + "/api/modules/wave_detector/test", "POST", {})
    assert tested["ok"], tested["output"]
    # without author it cannot become public yet
    _, result = call(url + "/api/modules/wave_detector/visibility", "POST", {"visibility": "public"})
    failed = {c["check"] for c in result["checks"] if not c["ok"]}
    assert not result["ok"] and "manifest has a author" in failed
    folder = root / "modules" / "private" / "wave_detector"
    (folder / "README.md").write_text((folder / "README.md").read_text().replace("TODO", "Me"))
    manifest = folder / "harmoni_module.yaml"
    manifest.write_text(manifest.read_text().replace("author: ''", "author: Me"))
    modules.forget("wave_detector")
    _, result = call(url + "/api/modules/wave_detector/visibility", "POST", {"visibility": "public"})
    assert result["ok"], result["checks"]
    assert (root / "modules" / "public" / "wave_detector" / "backend.py").is_file()
