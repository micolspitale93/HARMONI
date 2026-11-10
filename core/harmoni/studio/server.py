"""HARMONI Studio HTTP server (python standard library only).

JSON API under ``/api``, server-sent events on ``/api/events``, static web app on ``/``.
By default it listens on 127.0.0.1 only: it can read and write files of the repository.
"""

import json
import logging
import mimetypes
import queue
import re
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import yaml

from harmoni import __version__, modules
from harmoni.modules import checks
from harmoni.modules.generator import ModuleSpecError, create_module, normalize_spec, render_backend
from harmoni.services import describe_backends
from harmoni.studio.runs import EventBus, RunManager
from harmoni.studio.workspace import Workspace, WorkspaceError
from harmoni.tree import describe

log = logging.getLogger("harmoni.studio")
STATIC = Path(__file__).resolve().parent / "static"
MAX_BODY = 5 * 1024 * 1024


class HttpError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class Studio:
    """The application: routes requests to the workspace, the runs and the modules"""

    def __init__(self, root):
        self.workspace = Workspace(root)
        self.bus = EventBus()
        self.runs = RunManager(self.workspace, self.bus)
        self.routes = []
        r = self.route
        r("GET", r"/api/info", self.info)
        r("GET", r"/api/palette", lambda req: describe())
        r("GET", r"/api/backends", lambda req: describe_backends())
        r("GET", r"/api/trees", lambda req: self.workspace.list_trees())
        r("GET", r"/api/trees/(?P<name>[^/]+)", lambda req, name: self.workspace.read_tree(name))
        r("PUT", r"/api/trees/(?P<name>[^/]+)", lambda req, name: self.workspace.write_tree(name, req.json()))
        r("POST", r"/api/validate", self.validate)
        r("GET", r"/api/scripts", lambda req: self.workspace.list_scripts())
        r("GET", r"/api/scripts/(?P<name>[^/]+)", lambda req, name: self.workspace.read_script(name))
        r("PUT", r"/api/scripts/(?P<name>[^/]+)", self.write_script)
        r("GET", r"/api/configs", lambda req: self.workspace.list_configs())
        r("GET", r"/api/configs/(?P<config_id>[^/]+)", lambda req, config_id: self.workspace.read_config(config_id))
        r("PUT", r"/api/configs/(?P<config_id>[^/]+)", self.write_config)
        r("POST", r"/api/configs-check", lambda req: self.workspace.check_config_text(req.json().get("text", "")))
        r("POST", r"/api/service-snippet", self.service_snippet)
        r("GET", r"/api/run", lambda req: self.runs.state())
        r("POST", r"/api/run", self.start_run)
        r("POST", r"/api/run/command", self.run_command)
        r("POST", r"/api/run/stop", self.stop_run)
        r("POST", r"/api/ros2/connect", lambda req: self.runs.connect_ros2())
        r("GET", r"/api/modules", self.list_modules)
        r("POST", r"/api/modules", self.create_module)
        r("POST", r"/api/modules-preview", self.preview_module)
        r("GET", r"/api/modules/(?P<name>[^/]+)/backend", self.read_backend)
        r("PUT", r"/api/modules/(?P<name>[^/]+)/backend", self.write_backend)
        r("POST", r"/api/modules/(?P<name>[^/]+)/test", self.test_module)
        r("POST", r"/api/modules/(?P<name>[^/]+)/checks", self.check_module)
        r("POST", r"/api/modules/(?P<name>[^/]+)/visibility", self.module_visibility)

    def route(self, method, pattern, handler):
        self.routes.append((method, re.compile("^" + pattern + "$"), handler))

    def dispatch(self, req):
        for method, pattern, handler in self.routes:
            match = pattern.match(req.path)
            if match and method == req.method:
                return handler(req, **{k: unquote(v) for k, v in match.groupdict().items()})
        raise HttpError(404, f"no route {req.method} {req.path}")

    # --------------------------------------------------------------------- handlers
    def info(self, req):
        return {"version": __version__, "root": str(self.workspace.root),
                "ros2_available": self.runs.ros2.available(), "modules": len(modules.list_modules())}

    def validate(self, req):
        body = req.json()
        return self.workspace.validate_tree(body.get("tree") or {}, body.get("variables") or None)

    def write_script(self, req, name):
        self.workspace.write_script(name, req.json())
        return {"saved": name}

    def write_config(self, req, config_id):
        return self.workspace.write_config(config_id, req.json().get("text", ""))

    def service_snippet(self, req):
        body = req.json()
        service_id = str(body.get("service_id", "")).strip()
        if not re.match(r"^[A-Za-z][A-Za-z0-9_]{0,60}$", service_id):
            raise WorkspaceError("service id: letters, digits and _")
        entry = {"backend": body.get("backend")}
        entry.update({k: v for k, v in (body.get("params") or {}).items() if v not in (None, "")})
        text = yaml.safe_dump({service_id: entry}, sort_keys=False, allow_unicode=True)
        return {"snippet": "".join("  " + line + "\n" for line in text.splitlines())}

    def start_run(self, req):
        body = req.json()
        return self.runs.start_simulation(body.get("tree"), body.get("config"), body.get("variables") or {},
                                          body.get("period_s", 0.2))

    def run_command(self, req):
        self.runs.command(req.json().get("command", ""))
        return {"sent": True}

    def stop_run(self, req):
        self.runs.stop()
        return {"stopped": True}

    def _module(self, name):
        info = modules.get_module(name)
        if info is None:
            raise HttpError(404, f"module '{name}' not found")
        return info

    def list_modules(self, req):
        result = []
        for info in modules.list_modules():
            data = info.to_dict()
            data["checks"] = checks.check_module(info, with_tests=False)
            result.append(data)
        return result

    def preview_module(self, req):
        spec = dict(req.json())
        try:
            return {"backend": render_backend(normalize_spec(spec)), "errors": []}
        except ModuleSpecError as e:
            return {"backend": "", "errors": e.errors}

    def create_module(self, req):
        try:
            folder = create_module(req.json())
        except ModuleSpecError as e:
            raise HttpError(400, "; ".join(e.errors))
        info = self._module(folder.name)
        return info.to_dict()

    def read_backend(self, req, name):
        info = self._module(name)
        entry = info.path / info.manifest.get("backend", "backend.py")
        return {"name": name, "file": entry.name, "text": entry.read_text(encoding="utf-8")}

    def write_backend(self, req, name):
        info = self._module(name)
        text = req.json().get("text", "")
        try:
            compile(text, "backend.py", "exec")
        except SyntaxError as e:
            raise HttpError(400, f"syntax error line {e.lineno}: {e.msg}")
        (info.path / info.manifest.get("backend", "backend.py")).write_text(text, encoding="utf-8")
        modules.forget(name)
        reloaded = self._module(name)
        return reloaded.to_dict()

    def test_module(self, req, name):
        ok, output = checks.run_tests(self._module(name).path)
        return {"ok": ok, "output": output}

    def check_module(self, req, name):
        return {"checks": checks.check_module(self._module(name), with_tests=True)}

    def module_visibility(self, req, name):
        ok, results, path = checks.set_visibility(name, req.json().get("visibility", ""))
        return {"ok": ok, "checks": results, "path": str(path)}


class Request:
    def __init__(self, handler, method):
        parsed = urlparse(handler.path)
        self.method = method
        self.path = parsed.path.rstrip("/") or "/"
        self.handler = handler
        self._body = None

    def json(self):
        if self._body is None:
            length = int(self.handler.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise HttpError(413, "request too large")
            raw = self.handler.rfile.read(length) if length else b"{}"
            try:
                self._body = json.loads(raw.decode("utf-8") or "{}")
            except ValueError:
                raise HttpError(400, "invalid JSON body")
        return self._body


def make_handler(studio: Studio):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "HARMONIStudio/" + __version__

        def log_message(self, fmt, *args):
            log.debug(fmt, *args)

        def _send(self, status, body: bytes, content_type="application/json"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status, data):
            self._send(status, json.dumps(data, default=str).encode("utf-8"))

        def _api(self, method):
            req = Request(self, method)
            try:
                if method in ("POST", "PUT"):
                    req.json()  # read the body before answering, even on errors
                self._json(200, studio.dispatch(req))
            except HttpError as e:
                self._json(e.status, {"error": str(e)})
            except (WorkspaceError, ValueError, KeyError, FileExistsError, RuntimeError) as e:
                self._json(400, {"error": str(e).strip("'\"")})
            except FileNotFoundError as e:
                self._json(404, {"error": f"not found: {e}"})
            except Exception as e:  # noqa: BLE001
                log.error("%s", traceback.format_exc())
                self._json(500, {"error": f"{type(e).__name__}: {e}"})

        def _events(self):
            q = studio.bus.subscribe()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            try:
                for event, data in list(studio.bus.last.items()):
                    self._event(event, data)
                while True:
                    try:
                        event, data = q.get(timeout=15)
                        self._event(event, data)
                    except queue.Empty:
                        self.wfile.write(b": keep-alive\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                studio.bus.unsubscribe(q)

        def _event(self, event, data):
            self.wfile.write(f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n".encode("utf-8"))
            self.wfile.flush()

        def _static(self):
            path = urlparse(self.path).path
            if path in ("", "/"):
                path = "/index.html"
            target = (STATIC / path.lstrip("/")).resolve()
            if STATIC not in target.parents or not target.is_file():
                return self._send(404, b"not found", "text/plain")
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if target.suffix == ".js":
                content_type = "text/javascript"
            self._send(200, target.read_bytes(), content_type + ("; charset=utf-8" if "text" in content_type else ""))

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/api/events":
                return self._events()
            if path.startswith("/api/"):
                return self._api("GET")
            return self._static()

        def do_POST(self):
            self._api("POST")

        def do_PUT(self):
            self._api("PUT")

    return Handler


def make_server(root, host="127.0.0.1", port=8800):
    studio = Studio(root)
    server = ThreadingHTTPServer((host, port), make_handler(studio))
    server.daemon_threads = True
    server.studio = studio
    return server
