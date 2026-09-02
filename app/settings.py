"""Kitchen Sink - persistent preferences."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP_NAME = "Kitchen Sink"


def app_dir() -> Path:
    """Directory the app was installed into."""
    return Path(__file__).resolve().parent.parent


def config_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        d = Path(base) / "KitchenSink"
    elif sys.platform == "darwin":
        d = Path.home() / "Library" / "Application Support" / "KitchenSink"
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        d = Path(base) / "kitchensink"
    d.mkdir(parents=True, exist_ok=True)
    return d


def default_music_dir() -> str:
    for candidate in (Path.home() / "Music" / "Kitchen Sink", Path.home() / "Downloads"):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return str(candidate)
        except OSError:
            continue
    return str(Path.home())


DEFAULTS = {
    "output_dir": "",
    "audio_format": "mp3",          # mp3 | m4a | opus | flac | wav | original
    "audio_quality": "320",         # 320 | 256 | 192 | 128 | v0
    "embed_thumbnail": True,
    "embed_metadata": True,
    "write_lyrics": False,
    "soundcloud_engine": "scdl",    # scdl | yt-dlp
    "sc_auth_token": "",
    "sc_client_id": "",
    "sc_original_files": True,      # prefer original uploads when available
    "name_template": "%(title)s",
    "playlist_subfolder": True,
    "playlist_mode": "all",         # all | single (when a link carries both)
    "playlist_items": "",           # yt-dlp range, e.g. "1-10" or "3,7,9"
    "concurrency": 1,
    "archive": False,               # skip anything already downloaded
    "cookies_from_browser": "",     # "", chrome, firefox, edge, brave...
    "sound_effects": True,
}


class Settings:
    def __init__(self) -> None:
        self.path = config_dir() / "settings.json"
        self.data = dict(DEFAULTS)
        self.data["output_dir"] = default_music_dir()
        self.load()

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for k, v in raw.items():
                if k in DEFAULTS:
                    self.data[k] = v
        except (OSError, ValueError):
            pass
        if not self.data.get("output_dir"):
            self.data["output_dir"] = default_music_dir()

    def save(self) -> None:
        try:
            self.path.write_text(
                json.dumps(self.data, indent=2), encoding="utf-8"
            )
        except OSError:
            pass

    def update(self, patch: dict) -> dict:
        for k, v in (patch or {}).items():
            if k in DEFAULTS:
                self.data[k] = v
        self.save()
        return self.data

    def __getitem__(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def get(self, key, fallback=None):
        return self.data.get(key, fallback)
