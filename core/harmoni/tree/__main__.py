"""Command line tools for HARMONI tree files (no ROS needed).

    python -m harmoni.tree validate TREE [--set name=value ...]
    python -m harmoni.tree describe                      # node palette (JSON), for authoring tools
    python -m harmoni.tree services TREE                 # services the tree calls
    python -m harmoni.tree simulate TREE --services SERVICES.yaml [--set name=value] [--max-ticks N]

``simulate`` runs the tree in-process: each service of SERVICES.yaml is a backend
(``mock`` for canned answers, or a real one such as ``furhat``/``assistant``).
"""

import argparse
import json
import logging
import sys

import yaml

from harmoni.tree import BuildContext, ClientRegistry, LocalServiceClient, TreeRunner, describe
from harmoni.tree.spec import has_errors, load_spec, resolve_spec, services_used, validate


def _variables(pairs):
    variables = {}
    for pair in pairs or []:
        name, _, value = pair.partition("=")
        try:
            variables[name] = yaml.safe_load(value)  # numbers, booleans
        except yaml.YAMLError:
            variables[name] = value
    return variables


def cmd_validate(args):
    spec = load_spec(args.tree)
    resolved, issues = resolve_spec(spec, _variables(args.set))
    issues += validate(resolved, resolved=True)
    for issue in issues:
        print(issue)
    if has_errors(issues):
        print(f"{args.tree}: INVALID")
        return 1
    print(f"{args.tree}: OK ({len(issues)} warning(s))")
    return 0


def cmd_describe(args):
    print(json.dumps(describe(), indent=2, default=str))
    return 0


def cmd_services(args):
    for service in services_used(load_spec(args.tree)):
        print(service)
    return 0


def make_local_clients(services_file):
    from harmoni.services import create_backend

    with open(services_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    clients = {}
    for service_id, params in (config.get("services") or {}).items():
        params = dict(params)
        backend = create_backend(params.pop("backend"), service_id, params)
        backend.setup()
        clients[service_id] = LocalServiceClient(backend)
    return ClientRegistry(clients)


def cmd_simulate(args):
    logging.basicConfig(level=logging.INFO, format="%(name)-28s %(message)s")
    clients = make_local_clients(args.services)
    runner = TreeRunner(args.tree, BuildContext(client_for=clients), _variables(args.set), period_s=args.period)
    try:
        state = runner.run(max_ticks=args.max_ticks)
    finally:
        runner.shutdown()
        clients.shutdown()
    print(f"simulation ended: {state} after {runner.tree.count if runner.tree else 0} ticks {runner.error}")
    return 0 if state in ("finished", "running", "stopped") else 1


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m harmoni.tree", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("validate", help="check a tree file")
    p.add_argument("tree")
    p.add_argument("--set", action="append", metavar="NAME=VALUE", help="override a tree variable")
    p.set_defaults(func=cmd_validate)
    p = sub.add_parser("describe", help="print the node palette as JSON")
    p.set_defaults(func=cmd_describe)
    p = sub.add_parser("services", help="list the services called by a tree")
    p.add_argument("tree")
    p.set_defaults(func=cmd_services)
    p = sub.add_parser("simulate", help="run a tree in-process with local service backends")
    p.add_argument("tree")
    p.add_argument("--services", required=True, help="YAML file with a 'services' section")
    p.add_argument("--set", action="append", metavar="NAME=VALUE", help="override a tree variable")
    p.add_argument("--max-ticks", type=int, default=2000)
    p.add_argument("--period", type=float, default=0.01, help="seconds between ticks")
    p.set_defaults(func=cmd_simulate)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
