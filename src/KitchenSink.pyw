#!/usr/bin/env python3
"""Kitchen Sink — a YouTube & SoundCloud audio downloader wearing Aqua.

Run me with:  pythonw src/KitchenSink.pyw  (or double-click "Kitchen Sink.bat")
"""
from __future__ import annotations

import os
import sys
import traceback

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)


def _log_path() -> str:
    try:
        from app.settings import config_dir
        return os.path.join(str(config_dir()), "error.log")
    except Exception:
        return os.path.join(BASE, "error.log")


def _report(title: str, msg: str, detail: str = "") -> None:
    """pythonw.exe has no console, so a crash is invisible without this."""
    if detail:
        try:
            with open(_log_path(), "a", encoding="utf-8") as fh:
                fh.write(detail + "\n")
        except OSError:
            pass
        msg = f"{msg}\n\nDetails were written to:\n{_log_path()}"
    try:
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror(title, msg)
        root.destroy()
    except Exception:
        print(f"{title}: {msg}", file=sys.stderr)


def _missing(name: str, pip_name: str | None = None) -> None:
    pip_name = pip_name or name
    _report("Kitchen Sink",
            f"Kitchen Sink needs the '{pip_name}' package.\n\n"
            f"Run setup.bat (Windows) or:\n"
            f"    {sys.executable} -m pip install {pip_name}\n")
    sys.exit(1)


try:
    import webview
except ImportError:
    _missing("webview", "pywebview")


def _start(window_kwargs: dict) -> None:
    """Try the Edge WebView2 backend, then whatever pywebview can find."""
    attempts = []
    if sys.platform == "win32":
        attempts.append(dict(window_kwargs, gui="edgechromium"))
    attempts.append(window_kwargs)

    errors = []
    for kwargs in attempts:
        try:
            webview.start(**kwargs)
            return
        except Exception:
            errors.append(traceback.format_exc())

    _report(
        "Kitchen Sink could not open its window",
        "The app window failed to start.\n\n"
        "On Windows this is almost always a missing Edge WebView2 runtime.\n"
        "Install it from:\n"
        "https://developer.microsoft.com/microsoft-edge/webview2/\n\n"
        "If that is already installed, run setup.bat again to repair the "
        "environment.",
        "\n\n".join(errors))
    sys.exit(1)


def main() -> None:
    from app.api import Api
    from app import server

    api = Api()
    web_dir = os.path.join(BASE, "web")
    index = os.path.join(web_dir, "index.html")
    if not os.path.exists(index):
        _report("Kitchen Sink",
                f"The interface files are missing:\n{index}\n\n"
                "Re-extract the zip so the 'web' folder sits next to "
                "KitchenSink.pyw.")
        sys.exit(1)

    # Served over loopback rather than opened as file:// — see app/server.py
    # for why the JS bridge cannot carry the interface's traffic.
    url = server.start(api, web_dir)

    # No js_api on purpose. pywebview introspects it with a recursive dir()
    # walk, which reaches api.window -> window.native and reads WebView2 COM
    # properties off the UI thread until the recursion limit blows. Nothing
    # needs the bridge any more; window dragging is injected separately.
    window = webview.create_window(
        "Kitchen Sink",
        url=url,
        width=700,
        height=640,
        min_size=(600, 470),
        frameless=True,
        easy_drag=False,
        resizable=True,
        background_color="#6D7A8B",
        text_select=False,
    )
    api.attach(window)

    _start({"debug": bool(os.environ.get("KITCHEN_SINK_DEBUG"))})


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        _report("Kitchen Sink crashed",
                "Kitchen Sink hit an unexpected error while starting.",
                traceback.format_exc())
        sys.exit(1)
