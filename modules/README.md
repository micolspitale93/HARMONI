# HARMONI modules

New sensors, detectors, dialogues and actuators, added without touching the core.

- `public/`: modules shared with everyone (committed to the repository)
- `private/`: modules that stay on your machine (ignored by git)

Create one with HARMONI Studio (`./harmoni.sh studio`, page *Modules*) or in python with
`harmoni.modules.generator.create_module`. Every module is a folder with a `harmoni_module.yaml`
manifest, a `backend.py`, tests and examples; once created it can be used as `backend: <name>` in the
service configurations (ROS 2 and simulation) and called from trees with a `ServiceAction` leaf.

A module becomes public (moved from `private/` to `public/`) only when its checks pass: it loads, its
tests pass, its README and manifest are complete and it contains no credentials. Then open a pull request.
Team modules can live in their own git repository: add its folder to `HARMONI_MODULE_PATH`.
