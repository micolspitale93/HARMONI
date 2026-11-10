"""Tree file format: variables, validation, building"""

import os

import pytest

from harmoni.tree import BuildContext, TreeSpecError, build_tree, describe, load_spec, resolve_spec, services_used, validate


def tree(root, **extra):
    spec = {"harmoni_tree": 1, "name": "T", "root": root}
    spec.update(extra)
    return spec


def leaf(type_, name="n", **params):
    return {"type": type_, "name": name, "params": params}


def errors(spec):
    return [str(i) for i in validate(spec) if i.level == "error"]


def warnings(spec):
    return [str(i) for i in validate(spec) if i.level == "warning"]


def test_group_interaction_tree_is_valid(trees_dir):
    issues = validate(load_spec(os.path.join(trees_dir, "group_interaction.json")))
    assert issues == []


def test_services_used(trees_dir):
    assert set(services_used(load_spec(os.path.join(trees_dir, "group_interaction.json")))) == {
        "bot_default", "stt_default", "speaker_furhat", "speaker_nao"}


def test_unknown_type():
    assert any("unknown node type 'Nope'" in e for e in errors(tree({"type": "Nope", "name": "x"})))


def test_missing_required_param():
    assert any("required parameter" in e for e in errors(tree(leaf("CheckValue"))))


def test_unknown_param():
    assert any("unknown parameter" in e for e in errors(tree(leaf("CheckValue", key="a", colour="red"))))


def test_wrong_param_type():
    assert any("expected float" in e for e in errors(tree(leaf("Wait", seconds="soon"))))


def test_int_accepted_for_float_but_not_bool():
    assert errors(tree(leaf("Wait", seconds=2))) == []
    assert errors(tree(leaf("Wait", seconds=True))) != []


def test_choices():
    assert any("must be one of" in e for e in errors(tree(leaf("ServiceAction", service="s", action="JUMP"))))


def test_composite_needs_children_and_leaf_cannot_have_them():
    assert any("needs at least one child" in e for e in errors(tree({"type": "Sequence", "name": "s"})))
    bad_leaf = dict(leaf("SetValue", key="a", value=1), children=[leaf("SetValue", key="b", value=1)])
    assert any("cannot have children" in e for e in errors(tree(bad_leaf)))


def test_reads_without_writer_is_a_warning():
    spec = tree(leaf("CheckValue", key="nobody/writes", equals=1))
    assert errors(spec) == []
    assert any("no node writes it" in w for w in warnings(spec))


def test_initial_blackboard_counts_as_writer():
    spec = tree(leaf("CheckValue", key="a/b", equals=1), blackboard={"a/b": 1})
    assert warnings(spec) == []


def test_variables_keep_type_and_interpolate():
    spec = tree(leaf("Wait", name="wait ${who}", seconds="${s}"), variables={"s": 1.5, "who": "Manny"})
    resolved, issues = resolve_spec(spec)
    assert issues == []
    assert resolved["root"]["params"]["seconds"] == 1.5
    assert resolved["root"]["name"] == "wait Manny"


def test_variable_overrides_and_undefined_variables():
    spec = tree(leaf("Wait", seconds="${s}"), variables={"s": 1})
    resolved, _ = resolve_spec(spec, {"s": 3})
    assert resolved["root"]["params"]["seconds"] == 3
    assert any("undefined variable" in e for e in errors(tree(leaf("Wait", seconds="${nope}"))))


def test_unsupported_version():
    assert any("unsupported format version" in e for e in errors(dict(tree(leaf("Wait", seconds=1)), harmoni_tree=99)))


def test_build_raises_on_errors():
    with pytest.raises(TreeSpecError) as e:
        build_tree(tree({"type": "Nope", "name": "x"}))
    assert e.value.issues


def test_build_composites_and_initial_values():
    from tests.conftest import bb_get

    spec = tree({"type": "Parallel", "name": "p", "params": {"policy": "one"},
                 "children": [leaf("SetValue", key="a", value=1), leaf("CheckValue", name="c", key="a", equals=1)]},
                blackboard={"init/x": 5})
    root, resolved, warnings_ = build_tree(spec, BuildContext())
    assert root.name == "p" and len(root.children) == 2
    assert bb_get("init/x") == 5


def test_load_yaml(tmp_path):
    path = tmp_path / "t.yaml"
    path.write_text("harmoni_tree: 1\nname: Y\nroot: {type: Wait, name: w, params: {seconds: 1}}\n")
    spec = load_spec(str(path))
    assert spec["name"] == "Y" and spec["_base_dir"] == str(tmp_path)


def test_describe_palette_is_complete():
    palette = {d["type"]: d for d in describe()}
    assert {"Sequence", "Selector", "Parallel", "ServiceAction", "CheckValue", "GroupScript"} <= set(palette)
    service = palette["ServiceAction"]
    assert service["params"]["service"]["required"] is True
    assert "{output_key}" in service["writes"]
