from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = REPO_ROOT / "runs"
VISUALIZER_DIR = REPO_ROOT / "visualizer"
SHOWCASE_HOST = "127.0.0.1"
SHOWCASE_PORT = 4317


def showcase_state() -> dict:
    active_states = sorted(
        RUNS_DIR.glob("*/state.json"), key=lambda path: path.stat().st_mtime, reverse=True
    )
    if active_states:
        state = json.loads(active_states[0].read_text())
        return {
            "phase": _phase_for(state),
            "run_id": state["run_id"],
            "timelines": state.get("timelines", []),
            "scoreboard": state.get("scoreboard", []),
            "winner": state.get("winner"),
            "postmortem": state.get("postmortem", ""),
        }

    result_path = RUNS_DIR / "last_result.json"
    if result_path.exists():
        result = json.loads(result_path.read_text())
        return {"phase": "collapsed", **result}

    return {
        "phase": "ready",
        "run_id": None,
        "timelines": [],
        "scoreboard": [],
        "winner": None,
        "postmortem": "",
    }


def save_result(state: dict, winner: str, postmortem: str) -> None:
    payload = {
        "run_id": state["run_id"],
        "timelines": state.get("timelines", []),
        "scoreboard": state.get("scoreboard", []),
        "winner": winner,
        "postmortem": postmortem,
    }
    RUNS_DIR.mkdir(exist_ok=True)
    (RUNS_DIR / "last_result.json").write_text(json.dumps(payload, indent=2) + "\n")


def save_scoreboard(state: dict, scoreboard: list[dict]) -> None:
    state["scoreboard"] = scoreboard
    state_path = RUNS_DIR / state["run_id"] / "state.json"
    state_path.write_text(json.dumps(state, indent=2) + "\n")


def launch_showcase() -> str:
    url = f"http://{SHOWCASE_HOST}:{SHOWCASE_PORT}"
    if not _server_running():
        subprocess.Popen(
            [sys.executable, str(REPO_ROOT / "scripts" / "showcase.py")],
            cwd=REPO_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        for _ in range(20):
            if _server_running():
                break
            time.sleep(0.1)
    if not _server_running():
        raise RuntimeError("Everett's visualizer could not start on port 4317")
    webbrowser.open(url)
    return url


def serve_showcase() -> None:
    server = ThreadingHTTPServer((SHOWCASE_HOST, SHOWCASE_PORT), ShowcaseHandler)
    server.serve_forever()


class ShowcaseHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(VISUALIZER_DIR), **kwargs)

    def do_GET(self) -> None:
        request_path = urlparse(self.path).path
        if request_path == "/api/state":
            self._send_json(showcase_state())
            return
        if request_path.startswith("/vendor/"):
            self._send_three_build_file(request_path)
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        request_path = urlparse(self.path).path
        if request_path == "/api/state":
            self._send_headers("application/json", 0)
            return
        if request_path.startswith("/vendor/"):
            path = self._three_build_path(request_path)
            if path is None or not path.exists():
                self.send_error(HTTPStatus.NOT_FOUND, "Three.js build file was not found")
                return
            self._send_headers("text/javascript", path.stat().st_size)
            return
        super().do_HEAD()

    def log_message(self, format: str, *args) -> None:
        return

    def _send_json(self, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self._send_headers("application/json", len(body))
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Three.js has not been installed")
            return
        body = path.read_bytes()
        self._send_headers("text/javascript", len(body))
        self.wfile.write(body)

    def _send_three_build_file(self, request_path: str) -> None:
        path = self._three_build_path(request_path)
        if path is None or not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Three.js build file was not found")
            return
        self._send_file(path)

    def _three_build_path(self, request_path: str) -> Path | None:
        filename = Path(request_path).name
        if not filename.endswith(".js") or filename != request_path.removeprefix("/vendor/"):
            return None
        return VISUALIZER_DIR / "node_modules" / "three" / "build" / filename

    def _send_headers(self, content_type: str, content_length: int) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(content_length))
        self.end_headers()


def _phase_for(state: dict) -> str:
    statuses = {timeline.get("status") for timeline in state.get("timelines", [])}
    if state.get("winner"):
        return "collapsed"
    if state.get("scoreboard"):
        return "judged"
    if statuses & {"running"}:
        return "exploring"
    return "forked"


def _server_running() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.1)
        return connection.connect_ex((SHOWCASE_HOST, SHOWCASE_PORT)) == 0
