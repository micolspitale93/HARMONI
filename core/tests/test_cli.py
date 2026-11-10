"""python -m harmoni.tree"""

import json
import os

from harmoni.tree.__main__ import main


def test_validate_ok_and_invalid(trees_dir, tmp_path, capsys):
    assert main(["validate", os.path.join(trees_dir, "group_interaction.json")]) == 0
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"harmoni_tree": 1, "root": {"type": "Nope", "name": "x"}}))
    assert main(["validate", str(bad)]) == 1
    assert "unknown node type" in capsys.readouterr().out


def test_describe_outputs_json(capsys):
    main(["describe"])
    assert any(n["type"] == "ServiceAction" for n in json.loads(capsys.readouterr().out))


def test_simulate_mock_group_interaction(trees_dir, capsys):
    code = main(["simulate", os.path.join(trees_dir, "group_interaction.json"),
                 "--services", os.path.join(trees_dir, "group_interaction.mock.yaml"),
                 "--set", "max_scenes=6", "--period", "0"])
    assert code == 0
    assert "simulation ended: finished" in capsys.readouterr().out
