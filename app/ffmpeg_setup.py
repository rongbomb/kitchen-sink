"""Locate ffmpeg/ffprobe, or fetch a static build into ./bin on first run."""
from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

from .settings import app_dir

WIN_BUILDS = [
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-win64-gpl.zip",
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
]

EXE = ".exe" if sys.platform == "win32" else ""


def bin_dir() -> Path:
    d = app_dir() / "bin"
    d.mkdir(parents=True, exist_ok=True)
    return d


def find_ffmpeg() -> str | None:
    """Return the directory holding ffmpeg, or None."""
    local = bin_dir() / f"ffmpeg{EXE}"
    if local.exists():
        return str(bin_dir())

    which = shutil.which("ffmpeg")
    if which:
        return str(Path(which).parent)

    try:  # pip-installed fallback; ships ffmpeg but not ffprobe
        import imageio_ffmpeg  # type: ignore

        return str(Path(imageio_ffmpeg.get_ffmpeg_exe()).parent)
    except Exception:
        return None


def install_ffmpeg(log=print) -> str | None:
    """Download a static ffmpeg build into ./bin. Returns the directory."""
    existing = find_ffmpeg()
    if existing:
        log(f"ffmpeg already available at {existing}")
        return existing

    if sys.platform != "win32":
        log("Install ffmpeg with your package manager "
            "(brew install ffmpeg / apt install ffmpeg).")
        return None

    import tempfile
    import urllib.request

    dest = bin_dir()
    for url in WIN_BUILDS:
        tmp_path = None
        try:
            log(f"Downloading ffmpeg from {url} ...")
            req = urllib.request.Request(url, headers={"User-Agent": "KitchenSink/1.0"})
            # Streamed to a temp file: an 80 MB read() into memory stalls the
            # process and reports no progress while it runs.
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length") or 0)
                got = 0
                next_report = 0
                with tempfile.NamedTemporaryFile(
                        suffix=".zip", dir=str(dest), delete=False) as tmp:
                    tmp_path = Path(tmp.name)
                    while True:
                        chunk = resp.read(262144)
                        if not chunk:
                            break
                        tmp.write(chunk)
                        got += len(chunk)
                        if got >= next_report:
                            next_report = got + 5 * 1048576
                            if total:
                                log(f"  {got / 1048576:.0f} of "
                                    f"{total / 1048576:.0f} MB")
                            else:
                                log(f"  {got / 1048576:.0f} MB")
            log("Download complete, extracting ...")
            with zipfile.ZipFile(tmp_path) as zf:
                wanted = ("ffmpeg.exe", "ffprobe.exe", "ffplay.exe")
                for member in zf.namelist():
                    name = Path(member).name.lower()
                    if name in wanted:
                        with zf.open(member) as src, open(dest / name, "wb") as out:
                            shutil.copyfileobj(src, out)
                        log(f"  -> bin/{name}")
            if (dest / "ffmpeg.exe").exists():
                log("ffmpeg ready.")
                return str(dest)
        except Exception as exc:  # try the next mirror
            log(f"  failed: {exc}")
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
    log("Could not fetch ffmpeg automatically. "
        "Install it manually and put ffmpeg.exe in the app's bin folder.")
    return None


if __name__ == "__main__":
    ok = install_ffmpeg()
    sys.exit(0 if ok else 1)
