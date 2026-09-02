"""Kitchen Sink download engine: yt-dlp for YouTube (and anything else),
scdl for SoundCloud, ffmpeg for the audio conversion in between."""
from __future__ import annotations

import itertools
import os
import queue
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .ffmpeg_setup import find_ffmpeg

_ids = itertools.count(1)

SOUNDCLOUD_RE = re.compile(r"(^|\.)soundcloud\.com|snd\.sc", re.I)
YOUTUBE_RE = re.compile(r"(^|\.)(youtube\.com|youtu\.be|youtube-nocookie\.com)", re.I)
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)

# codecs that can carry embedded cover art
ART_OK = {"mp3", "m4a", "opus", "flac", "original"}

QUALITY_MAP = {"v0": "0", "320": "320", "256": "256", "192": "192", "128": "128"}

NO_WINDOW = {"creationflags": 0x08000000} if sys.platform == "win32" else {}


def console_python() -> str:
    """pythonw.exe gives a child process no usable stdio, so scdl's output
    never comes back. python.exe from the same environment does."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        console = exe.with_name("python.exe")
        if console.exists():
            return str(console)
    return str(exe)


def classify(url: str) -> str:
    host = re.sub(r"^https?://", "", url).split("/")[0].lower()
    if SOUNDCLOUD_RE.search(host):
        return "soundcloud"
    if YOUTUBE_RE.search(host):
        return "youtube"
    return "other"


def split_urls(text: str) -> list[str]:
    """Pull every URL out of a pasted blob, in order, de-duplicated."""
    seen, out = set(), []
    for m in URL_RE.finditer(text or ""):
        u = m.group(0).rstrip(".,;)]}’\"'")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def human_bytes(n) -> str:
    try:
        n = float(n)
    except (TypeError, ValueError):
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return ""


def human_time(s) -> str:
    try:
        s = int(s)
    except (TypeError, ValueError):
        return ""
    return f"{s // 60}:{s % 60:02d}" if s < 3600 else f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"


@dataclass
class Job:
    url: str
    id: int = field(default_factory=lambda: next(_ids))
    site: str = "other"
    engine: str = "yt-dlp"
    title: str = ""
    status: str = "queued"     # queued|working|done|error|cancelled
    stage: str = "Waiting"
    percent: float = 0.0
    speed: str = ""
    eta: str = ""
    size: str = ""
    message: str = ""
    files: list = field(default_factory=list)
    index: int = 0
    count: int = 0
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)
    _last_push: float = field(default=0.0, repr=False)
    # What yt-dlp actually wrote, before any postprocessor renamed it.
    _raw_files: list = field(default_factory=list, repr=False)

    def dict(self) -> dict:
        return {
            "id": self.id, "url": self.url, "site": self.site, "engine": self.engine,
            "title": self.title or self.url, "status": self.status, "stage": self.stage,
            "percent": round(self.percent, 1), "speed": self.speed, "eta": self.eta,
            "size": self.size, "message": self.message, "files": self.files,
            "index": self.index, "count": self.count,
        }


class Cancelled(Exception):
    pass


class Engine:
    def __init__(self, settings, on_job=None, on_log=None):
        self.settings = settings
        self.on_job = on_job or (lambda j: None)
        self.on_log = on_log or (lambda s: None)
        self.jobs: dict[int, Job] = {}
        self.q: "queue.Queue[Job]" = queue.Queue()
        self.workers: list[threading.Thread] = []
        self._lock = threading.Lock()
        self._scdl_cmd: "list[str] | None | bool" = False   # False = not looked up
        self._scdl_flags: "set[str] | None" = None
        self._spawn_workers()

    # ---------------------------------------------------------------- workers
    def _spawn_workers(self):
        try:
            want = max(1, min(4, int(self.settings.get("concurrency", 1) or 1)))
        except (TypeError, ValueError):
            want = 1
        with self._lock:
            while len(self.workers) < want:
                t = threading.Thread(target=self._loop, daemon=True,
                                     name=f"ks-worker-{len(self.workers)}")
                t.start()
                self.workers.append(t)

    def _loop(self):
        while True:
            job = self.q.get()
            try:
                if job._cancel.is_set():
                    self._finish(job, "cancelled", "Cancelled")
                else:
                    self._run(job)
            except Cancelled:
                self._finish(job, "cancelled", "Cancelled")
            except Exception as exc:
                self.log(f"[{job.id}] {type(exc).__name__}: {exc}")
                self._finish(job, "error", str(exc).strip()[:300] or "Failed")
            finally:
                self.q.task_done()

    # ------------------------------------------------------------------ scdl
    def scdl_command(self) -> "list[str] | None":
        """How to invoke scdl here, or None when it isn't installed."""
        if self._scdl_cmd is not False:
            return self._scdl_cmd

        exe = Path(sys.executable).parent / (
            "scdl.exe" if sys.platform == "win32" else "scdl")
        if exe.exists():
            self._scdl_cmd = [str(exe)]
            return self._scdl_cmd
        try:
            import scdl.scdl  # noqa: F401
        except Exception as exc:
            self.log(f"scdl is not installed ({exc}). "
                     "SoundCloud links will use yt-dlp instead. "
                     "Run tools\\update.bat to install scdl.")
            self._scdl_cmd = None
            return None
        # scdl 3.x names its entry point _main; older releases used main.
        self._scdl_cmd = [console_python(), "-c",
                          "import sys; from scdl import scdl as m; "
                          "sys.argv[0] = 'scdl'; "
                          "(getattr(m, '_main', None) or m.main)()"]
        return self._scdl_cmd

    def scdl_flags(self, cmd: list[str]) -> set:
        """scdl's options move between releases, and an unknown one makes it
        exit before downloading anything. Ask it what it accepts."""
        if self._scdl_flags is not None:
            return self._scdl_flags
        found: set = set()
        try:
            r = subprocess.run(cmd + ["--help"], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=60,
                               **NO_WINDOW)
            for m in re.finditer(r"--[a-zA-Z][\w-]*",
                                 (r.stdout or "") + (r.stderr or "")):
                found.add(m.group(0))
        except Exception as exc:
            self.log(f"Could not read scdl's options ({exc}).")
        self._scdl_flags = found
        return found

    # ------------------------------------------------------------------ api
    def log(self, text: str):
        for line in str(text).rstrip().splitlines():
            if line.strip():
                self.on_log(line.rstrip())

    def push(self, job: Job, throttle: bool = False):
        """Progress callbacks fire many times a second; only state changes are
        worth a round trip to the UI."""
        if throttle:
            now = time.time()
            if now - job._last_push < 0.15:
                return
            job._last_push = now
        self.on_job(job.dict())

    def add(self, url: str) -> dict:
        job = Job(url=url.strip())
        job.site = classify(job.url)
        wants_scdl = (job.site == "soundcloud"
                      and self.settings.get("soundcloud_engine") == "scdl")
        job.engine = "scdl" if wants_scdl and self.scdl_command() else "yt-dlp"
        with self._lock:
            self.jobs[job.id] = job
        self._spawn_workers()
        self.push(job)
        self.q.put(job)
        return job.dict()

    def cancel(self, job_id: int):
        job = self.jobs.get(int(job_id))
        if job and job.status in ("queued", "working"):
            job._cancel.set()
            job.stage = "Cancelling…"
            self.push(job)

    def cancel_all(self):
        for job in list(self.jobs.values()):
            self.cancel(job.id)

    def remove_finished(self):
        with self._lock:
            for jid in [j.id for j in self.jobs.values()
                        if j.status in ("done", "error", "cancelled")]:
                self.jobs.pop(jid, None)

    def retry(self, job_id: int) -> dict | None:
        job = self.jobs.get(int(job_id))
        if not job or job.status not in ("error", "cancelled"):
            return None
        url = job.url
        with self._lock:
            self.jobs.pop(job.id, None)
        return self.add(url)

    def snapshot(self) -> list[dict]:
        return [j.dict() for j in self.jobs.values()]

    # ------------------------------------------------------------- internals
    def _finish(self, job: Job, status: str, message: str = ""):
        job.status = status
        job.stage = {"done": "Complete", "error": "Failed",
                     "cancelled": "Cancelled"}.get(status, status)
        job.message = message
        if status == "done":
            job.percent = 100.0
        job.speed = job.eta = ""
        self.push(job)

    def _outdir(self) -> Path:
        d = Path(self.settings["output_dir"]).expanduser()
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _run(self, job: Job):
        job.status = "working"
        job.stage = "Contacting server…"
        self.push(job)
        if job.engine == "scdl":
            try:
                self._run_scdl(job)
                return
            except Cancelled:
                raise
            except Exception as exc:
                # yt-dlp handles SoundCloud too, so a broken scdl is a detour
                # rather than a dead end.
                self.log(f"scdl failed: {exc}")
                self.log("Trying the same link with yt-dlp instead.")
                job.engine = "yt-dlp"
                job.percent = 0.0
                job.files = []
                job.stage = "Retrying with yt-dlp…"
                self.push(job)
        self._run_ytdlp(job)

    # ------------------------------------------------------------- yt-dlp
    def _ytdlp_opts(self, job: Job) -> dict:
        s = self.settings
        fmt = s["audio_format"]
        outdir = self._outdir()
        # "%(playlist_title&{}/|)s" expands to "Playlist Name/" or to nothing,
        # so the subfolder appears only when the URL really was a playlist.
        sub = "%(playlist_title&{}/|)s" if s.get("playlist_subfolder") else ""
        tmpl = (s.get("name_template") or "%(title)s").strip()
        root = str(outdir).replace("\\", "/").rstrip("/")
        outtmpl = f"{root}/{sub}{tmpl}.%(ext)s"

        pps = []
        if fmt != "original":
            pp = {"key": "FFmpegExtractAudio", "preferredcodec": fmt}
            if fmt == "mp3":
                pp["preferredquality"] = QUALITY_MAP.get(s["audio_quality"], "320")
            pps.append(pp)
        if s.get("embed_metadata"):
            pps.append({"key": "FFmpegMetadata", "add_metadata": True,
                        "add_chapters": True})
        want_art = s.get("embed_thumbnail") and fmt in ART_OK
        if want_art:
            pps.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})

        opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "postprocessors": pps,
            "writethumbnail": bool(want_art),
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "consoletitle": False,
            "noplaylist": s.get("playlist_mode") == "single",
            "ignoreerrors": "only_download",
            "retries": 5,
            "fragment_retries": 5,
            "trim_file_name": 180,
            "windowsfilenames": sys.platform == "win32",
            "progress_hooks": [lambda d: self._hook(job, d)],
            "postprocessor_hooks": [lambda d: self._pp_hook(job, d)],
            "logger": _YdlLogger(self, job),
        }
        items = (s.get("playlist_items") or "").strip()
        if items and s.get("playlist_mode") != "single":
            opts["playlist_items"] = items
        ff = find_ffmpeg()
        if ff:
            opts["ffmpeg_location"] = ff
        if s.get("archive"):
            from .settings import config_dir
            opts["download_archive"] = str(config_dir() / "archive.txt")
        if s.get("write_lyrics"):
            opts["writesubtitles"] = True
            opts["subtitleslangs"] = ["en.*"]
        browser = (s.get("cookies_from_browser") or "").strip()
        if browser:
            opts["cookiesfrombrowser"] = (browser,)
        return opts

    def _hook(self, job: Job, d: dict):
        if job._cancel.is_set():
            raise Cancelled()
        info = d.get("info_dict") or {}
        if info.get("playlist_index"):
            job.index = int(info["playlist_index"])
            job.count = int(info.get("n_entries") or info.get("playlist_count") or 0)
        title = info.get("title") or info.get("track")
        if title:
            job.title = str(title)
        st = d.get("status")
        if st == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            got = d.get("downloaded_bytes") or 0
            job.percent = (got / total * 100) if total else job.percent
            job.stage = "Downloading"
            job.speed = (human_bytes(d.get("speed")) + "/s") if d.get("speed") else ""
            job.eta = human_time(d.get("eta"))
            job.size = human_bytes(total)
        elif st == "finished":
            job.percent = 100.0
            job.stage = "Converting…"
            job.speed = job.eta = ""
            path = d.get("filename") or info.get("filepath")
            if path and path not in job._raw_files:
                job._raw_files.append(path)
        elif st == "error":
            job.stage = "Error"
        self.push(job, throttle=(st == "downloading"))

    def _pp_hook(self, job: Job, d: dict):
        if job._cancel.is_set():
            raise Cancelled()
        name = (d.get("postprocessor") or "").replace("FFmpeg", "")
        if d.get("status") == "started":
            job.stage = {"ExtractAudio": "Converting audio…",
                         "Metadata": "Writing tags…",
                         "EmbedThumbnail": "Embedding artwork…"}.get(
                name, f"{name}…")
            self.push(job)
        elif d.get("status") == "finished":
            fp = (d.get("info_dict") or {}).get("filepath")
            if fp and fp not in job.files:
                job.files.append(fp)

    def _saved_message(self, job: Job) -> str:
        n = len(job.files)
        if job.count > 1:
            return f"{n or job.count} of {job.count} tracks saved"
        return f"{n or 1} file(s) saved"

    def _run_ytdlp(self, job: Job):
        import yt_dlp

        opts = self._ytdlp_opts(job)
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(job.url, download=False, process=False)
                if isinstance(info, dict):
                    job.title = str(info.get("title") or job.title or job.url)
                    if info.get("_type") in ("playlist", "multi_video"):
                        job.count = int(info.get("playlist_count")
                                        or info.get("n_entries") or 0)
                        job.stage = "Reading playlist…"
                    self.push(job)
            except Exception:
                pass  # probing is a nicety, not a requirement

            if job._cancel.is_set():
                raise Cancelled()
            ydl.download([job.url])

        if job._cancel.is_set():
            raise Cancelled()
        # Postprocessor output wins; without one, the raw download is the file.
        if not job.files:
            job.files = list(job._raw_files)
        if not job.files:
            raise RuntimeError("Nothing was saved — the link may be private, "
                               "region-locked, or need cookies")
        self._finish(job, "done", self._saved_message(job))

    # --------------------------------------------------------------- scdl
    def _scdl_argv(self, job: Job, supported: set) -> list[str]:
        s = self.settings
        # -l and --path have been in scdl forever; everything else is offered
        # only when this build advertises it.
        args = ["-l", job.url, "--path", str(self._outdir())]
        skipped = []

        def opt(flag: str, value=None):
            if supported and flag not in supported:
                skipped.append(flag)
                return
            args.append(flag)
            if value is not None:
                args.append(str(value))

        # scdl declares these as "[-c | --force-metadata]", so passing both
        # makes it reject the whole command line.
        if s.get("embed_metadata"):
            opt("--force-metadata")
        else:
            args.append("-c")
        if s.get("embed_thumbnail"):
            opt("--original-art")
        opt("--no-album-tag")

        fmt = s["audio_format"]
        if fmt == "original":
            opt("--original-name" if s.get("sc_original_files") else "--no-original")
        elif fmt == "flac":
            # --flac converts lossless originals; tracks without one still
            # come down as mp3 rather than being skipped entirely.
            opt("--flac")
        elif fmt == "opus":
            opt("--opus")
            opt("--no-original")
        else:  # mp3 / m4a / wav -> take the mp3 stream, convert afterwards
            opt("--onlymp3")
            opt("--no-original")

        if not s.get("playlist_subfolder"):
            opt("--no-playlist-folder")
        if s.get("archive"):
            from .settings import config_dir
            opt("--download-archive", config_dir() / "sc-archive.txt")
        # Always sent: scdl's own default prefixes every file with the track
        # id, which would make SoundCloud names differ from YouTube ones.
        tmpl = (s.get("name_template") or "").strip()
        if tmpl:
            opt("--name-format", tmpl)
        if s.get("sc_auth_token"):
            opt("--auth-token", s["sc_auth_token"])
        if s.get("sc_client_id"):
            opt("--client-id", s["sc_client_id"])

        if skipped:
            self.log("This scdl build doesn't accept " + ", ".join(skipped) +
                     " — continuing without them.")
        return args

    AUDIO_EXT = {".mp3", ".m4a", ".flac", ".wav", ".opus", ".ogg", ".aac", ".aiff"}

    def _scan_audio(self) -> dict:
        """Map every audio file under the output dir to its mtime."""
        out = {}
        root = self._outdir()
        for dirpath, _dirs, names in os.walk(root):
            for n in names:
                if Path(n).suffix.lower() in self.AUDIO_EXT:
                    p = os.path.join(dirpath, n)
                    try:
                        out[p] = os.path.getmtime(p)
                    except OSError:
                        pass
        return out

    def _run_scdl(self, job: Job):
        base = self.scdl_command()
        if not base:
            raise RuntimeError("scdl is not installed")
        argv = self._scdl_argv(job, self.scdl_flags(base))
        before = self._scan_audio()
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        ff = find_ffmpeg()
        if ff:
            env["PATH"] = ff + os.pathsep + env.get("PATH", "")

        self.log("scdl " + " ".join(
            a if " " not in a else f'"{a}"'
            for a in argv if not a.startswith("eyJ")))

        proc = subprocess.Popen(
            base + argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", env=env,
            bufsize=1, **NO_WINDOW)

        job.stage = "Downloading"
        self.push(job)
        pct_re = re.compile(r"(\d{1,3})%")
        title_re = re.compile(r"Downloading\s+(.+?)\s*$", re.I)
        tail: list[str] = []

        assert proc.stdout is not None
        for raw in proc.stdout:
            if job._cancel.is_set():
                proc.terminate()
                raise Cancelled()
            line = raw.rstrip()
            if not line:
                continue
            title = title_re.search(line)
            if title:
                job.title = title.group(1)[:160]
                job.percent = 0.0
            pct = pct_re.search(line)
            if pct:
                job.percent = max(0.0, min(100.0, float(pct.group(1))))
            if "\r" not in raw and not pct:
                self.log(line)
                tail.append(line)
                del tail[:-6]
            self.push(job, throttle=True)

        code = proc.wait()
        if job._cancel.is_set():
            raise Cancelled()
        if code != 0:
            reason = next((t for t in reversed(tail)
                           if re.search(r"error|denied|403|404|not found|"
                                        r"unrecognized|invalid|traceback", t, re.I)),
                          "")
            raise RuntimeError(reason.strip()[:200] if reason
                               else f"scdl exited with code {code}")

        # Whatever is new (or freshly rewritten) in the output tree is ours.
        after = self._scan_audio()
        job.files = sorted(p for p, m in after.items()
                           if p not in before or m > before[p] + 0.5)

        if not job.files and not self.settings.get("archive"):
            # A clean exit that produced nothing usually means scdl bailed on
            # the track quietly. Let the caller fall back to yt-dlp.
            raise RuntimeError("scdl finished without saving anything")

        # convert to the requested container if scdl couldn't produce it
        if self.settings["audio_format"] in ("m4a", "wav"):
            job.stage = "Converting audio…"
            self.push(job)
            self._convert_dir(job, self.settings["audio_format"])
        self._finish(job, "done", self._saved_message(job))

    def _convert_dir(self, job: Job, target: str):
        ff = find_ffmpeg()
        if not ff:
            self.log("ffmpeg not found — leaving files as MP3.")
            return
        exe = str(Path(ff) / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"))
        out = []
        for f in job.files:
            src = Path(f)
            if not src.exists() or src.suffix.lstrip(".") == target:
                out.append(f)
                continue
            dst = src.with_suffix("." + target)
            codec = ["-c:a", "aac", "-b:a", "256k"] if target == "m4a" else \
                    ["-c:a", "pcm_s16le"]
            flags = {"creationflags": 0x08000000} if sys.platform == "win32" else {}
            r = subprocess.run([exe, "-y", "-i", str(src), *codec, str(dst)],
                               capture_output=True, text=True, **flags)
            if r.returncode == 0 and dst.exists():
                try:
                    src.unlink()
                except OSError:
                    pass
                out.append(str(dst))
            else:
                self.log(f"ffmpeg failed on {src.name}")
                out.append(f)
        job.files = out


class _YdlLogger:
    def __init__(self, engine: "Engine", job: Job):
        self.e, self.j = engine, job

    def debug(self, msg):
        if not str(msg).startswith("[debug] "):
            self.e.log(msg)

    def info(self, msg):
        self.e.log(msg)

    def warning(self, msg):
        self.e.log("warning: " + str(msg))

    def error(self, msg):
        self.e.log("error: " + str(msg))
