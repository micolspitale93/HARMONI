"""python -m harmoni.studio [--host 127.0.0.1] [--port 8800] [--root <HARMONI repository>]"""

import argparse
import logging
import os
import sys
import webbrowser

from harmoni.modules import harmoni_root
from harmoni.studio.server import make_server


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m harmoni.studio", description="HARMONI Studio")
    parser.add_argument("--host", default="127.0.0.1",
                        help="address to listen on (default 127.0.0.1: only this computer)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("HARMONI_STUDIO_PORT", 8800)))
    parser.add_argument("--root", default=str(harmoni_root()), help="HARMONI repository")
    parser.add_argument("--open", action="store_true", help="open the browser")
    args = parser.parse_args(argv)
    os.environ["HARMONI_ROOT"] = os.path.abspath(args.root)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    server = make_server(args.root, args.host, args.port)
    url = f"http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{server.server_port}"
    print(f"HARMONI Studio on {url}  (repository: {os.path.abspath(args.root)}, Ctrl+C to stop)", flush=True)
    if args.host == "0.0.0.0":
        print("WARNING: Studio is reachable from the network and can edit files of the repository", flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.studio.runs.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
