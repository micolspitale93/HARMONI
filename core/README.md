# HARMONI core

ROS-independent part of HARMONI 2.0 (python 3.8+, depends only on `py_trees` and `pyyaml`):

- `harmoni/tree`: tree file format (JSON/YAML), validation, builder, runner, snapshots, CLI
- `harmoni/leaves`: leaves usable in tree files (`ServiceAction`, conditions, group interaction)
- `harmoni/services`: service backends (`assistant`, `azure_diarization`, `furhat`, `nao_http`, `mock`)
- `trees/`: tree files, their scripts and mock services
- `tests/`: unit tests (`python3 -m pytest`)

```bash
cd core
python3 -m harmoni.tree validate trees/group_interaction.json
python3 -m harmoni.tree describe                     # node palette for authoring tools (JSON)
python3 -m harmoni.tree simulate trees/group_interaction.json --services trees/group_interaction.mock.yaml
pip install -e ".[assistant,azure,furhat]"           # optional: install with the cloud/robot SDKs
```

The ROS 2 nodes in `../ros2` run these trees and backends. See `doc/overview/HARMONI-2-Architecture.md`.
