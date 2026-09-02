"""The bridge between the Aqua front-end and the Python engine."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import webview

from . import ffmpeg_setup
from .downloader import Engine, split_urls
from .settings import Settings

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class Api:
    def __init__(self):
        self._log: list[str] = []
        self.settings = Settings()
        self.window: "webview.Window | None" = None
        self._lock = threading.Lock()
        self._pending_jobs: dict[int, dict] = {}
        self._pending_logs: list[str] = []
        self._pending_events: list[dict] = []
        self._versions: dict = {"python": sys.version.split()[0],
                                "ytdlp": "checking…", "scdl": "checking…"}
        self._probed = False
        self._installing = False
        self._zoomed = False
        self.engine = Engine(self.settings, on_job=self._on_job, on_log=self._on_log)

    # ------------------------------------------------------------- plumbing
    def attach(self, window):
        self.window = window
        threading.Thread(target=self._prewarm, daemon=True,
                         name="ks-prewarm").start()

    def _prewarm(self):
        try:
            cmd = self.engine.scdl_command()
            if cmd:
                self.engine.scdl_flags(cmd)
        except Exception:
            pass
        try:
            import yt_dlp  # noqa: F401
        except Exception:
            pass

    def _on_job(self, data: dict):
        with self._lock:
            self._pending_jobs[data["id"]] = data

    def _on_log(self, line: str):
        self._log.append(line)
        del self._log[:-800]
        with self._lock:
            self._pending_logs.append(line)

    def _notify(self, kind: str, payload):
        with self._lock:
            self._pending_events.append({"kind": kind, "payload": payload})

    def poll(self) -> dict:
        """Called from JS on a timer. Python never pushes into the WebView —
        that deadlocks pywebview on Windows whenever the user clicks."""
        with self._lock:
            jobs = list(self._pending_jobs.values())
            logs = self._pending_logs[:]
            events = self._pending_events[:]
            self._pending_jobs.clear()
            self._pending_logs.clear()
            self._pending_events.clear()
        return {"jobs": jobs, "logs": logs, "events": events}

    # ------------------------------------------------------------ app state
    def get_state(self) -> dict:
        self._probe_versions()
        return {
            "settings": self.settings.data,
            "jobs": self.engine.snapshot(),
            "log": self._log[-200:],
            "ffmpeg": ffmpeg_setup.find_ffmpeg(),
            "versions": dict(self._versions),
        }

    def _probe_versions(self):
        if self._probed:
            return
        self._probed = True

        def work():
            try:
                import yt_dlp
                self._versions["ytdlp"] = yt_dlp.version.__version__
            except Exception:
                self._versions["ytdlp"] = "not installed"
            try:
                from importlib.metadata import version
                self._versions["scdl"] = version("scdl")
            except Exception:
                self._versions["scdl"] = "not installed"
            self._notify("versions", dict(self._versions))

        threading.Thread(target=work, daemon=True, name="ks-versions").start()

    def save_settings(self, patch: dict) -> dict:
        return self.settings.update(patch or {})

    # --------------------------------------------------------------- queue
    def add_urls(self, text: str) -> dict:
        urls = split_urls(text)
        if not urls:
            return {"ok": False, "error": "That doesn’t look like a link."}

        def work():
            for u in urls:
                try:
                    self.engine.add(u)
                except Exception as exc:
                    self._on_log(f"Could not queue {u}: {exc}")

        threading.Thread(target=work, daemon=True, name="ks-add").start()
        return {"ok": True, "added": len(urls)}

    def cancel(self, job_id):
        threading.Thread(target=lambda: self.engine.cancel(job_id),
                         daemon=True).start()
        return True

    def cancel_all(self):
        threading.Thread(target=self.engine.cancel_all, daemon=True).start()
        return True

    def clear_finished(self):
        self.engine.remove_finished()
        return self.engine.snapshot()

    def retry(self, job_id):
        threading.Thread(target=lambda: self.engine.retry(job_id),
                         daemon=True).start()
        return {"ok": True}

    def read_clipboard(self) -> str:
        try:
            if sys.platform == "win32":
                cmd = ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"]
            elif sys.platform == "darwin":
                cmd = ["pbpaste"]
            else:
                cmd = ["xclip", "-selection", "clipboard", "-o"]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5,
                               creationflags=CREATE_NO_WINDOW)
            if r.returncode == 0:
                return (r.stdout or "").strip()
        except Exception as exc:
            self._on_log(f"Clipboard unavailable: {exc}")
        return ""

    # --------------------------------------------------------------- files
    def choose_folder(self):
        if not self.window:
            return None
        start = self.settings["output_dir"] or str(Path.home())
        try:
            res = self.window.create_file_dialog(
                webview.FOLDER_DIALOG, directory=start, allow_multiple=False)
        except Exception as exc:
            self._on_log(f"Could not open the folder picker: {exc}")
            return None
        if res:
            path = res[0] if isinstance(res, (list, tuple)) else res
            self.settings.update({"output_dir": str(path)})
            return str(path)
        return None

    def open_path(self, path: str = ""):
        target = path or self.settings["output_dir"]
        p = Path(target)
        if not p.exists():
            p = p.parent
        try:
            if sys.platform == "win32":
                os.startfile(str(p))  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
            return True
        except Exception as exc:
            self._on_log(f"Could not open {p}: {exc}")
            return False

    def reveal(self, path: str):
        p = Path(path)
        try:
            if sys.platform == "win32" and p.exists():
                subprocess.Popen(["explorer", "/select,", str(p)])
                return True
            if sys.platform == "darwin" and p.exists():
                subprocess.Popen(["open", "-R", str(p)])
                return True
        except Exception:
            pass
        return self.open_path(str(p.parent))

    # -------------------------------------------------------------- ffmpeg
    def install_ffmpeg(self):
        if self._installing:
            return False
        self._installing = True

        def work():
            try:
                self._notify("ffmpegBusy", True)
                path = ffmpeg_setup.install_ffmpeg(log=self._on_log)
                self._notify("ffmpeg", path)
            except Exception as exc:
                self._on_log(f"ffmpeg install failed: {exc}")
                self._notify("ffmpeg", None)
            finally:
                self._installing = False
                self._notify("ffmpegBusy", False)

        threading.Thread(target=work, daemon=True, name="ks-ffmpeg").start()
        return True

    # -------------------------------------------------------- window chrome
    def _window_op(self, name: str, *args):
        """pywebview marshals window calls onto the UI thread and blocks until
        it answers, so these never run on the thread serving the request."""
        def work():
            try:
                if self.window:
                    getattr(self.window, name)(*args)
            except Exception as exc:
                self._on_log(f"Window {name} failed: {exc}")

        threading.Thread(target=work, daemon=True, name=f"ks-{name}").start()
        return True

    def win_close(self):
        # destroy() can stall on WebView2 teardown, so the exit runs on its own
        # thread — a stuck teardown must not leave the process alive forever.
        def hard_exit():
            time.sleep(1.0)
            os._exit(0)

        def work():
            time.sleep(0.15)  # let the reply reach the page before we go
            try:
                if self.window:
                    self.window.destroy()
            except Exception:
                pass

        threading.Thread(target=hard_exit, daemon=True, name="ks-exit").start()
        threading.Thread(target=work, daemon=True, name="ks-close").start()
        return True

    def win_minimize(self):
        return self._window_op("minimize")

    def win_zoom(self):
        self._zoomed = not self._zoomed
        return self._window_op("maximize" if self._zoomed else "restore")

    def win_resize(self, width, height):
        return self._window_op("resize", max(560, int(width)),
                               max(420, int(height)))
