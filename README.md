# Kitchen Sink

A personal YouTube & SoundCloud audio downloader, wearing Mac OS X Aqua.

Runs as a real desktop window (no browser tab), built on **yt-dlp**, **scdl**
and **ffmpeg**.

---

## Setup — once

1. Make sure **Python 3.9+** is installed and on your PATH.
   <https://www.python.org/downloads/windows/> — tick *"Add python.exe to PATH"*.
2. Optional but recommended: install **Git**, so scdl can be pulled straight
   from `github.com/scdl-org/scdl`. Without it the setup falls back to the
   PyPI release of scdl automatically.
3. Double-click **`setup.bat`**.

It creates a private `.venv` next to the app, installs everything, and
downloads a static ffmpeg build into `.\bin`. Nothing touches your system
Python or your PATH.

## Running it

Double-click **`Kitchen Sink.bat`**.

Right-click it → *Send to* → *Desktop (create shortcut)* if you want it
somewhere handier. Change the shortcut's icon to taste.

## When a download suddenly stops working

Run **`update.bat`**. YouTube changes its player regularly and yt-dlp ships
fixes within a day or two — 95% of failures are just a stale yt-dlp.

---

## Using it

Paste a link and press **Download** (or just hit Return — pasting a bare URL
into the empty field starts it automatically). Click **Paste** to pull a link
from the clipboard. You can also drag a link from your browser straight onto
the window — a drop overlay appears while you hover.

Failed downloads show a **↻** retry on each row, or use **Retry Failed** in
the queue footer. Error hints point you to OAuth tokens or browser cookies
when that's likely the fix.

Paste several links at once and it queues all of them. Playlists, albums,
user pages and SoundCloud likes all work.

| Control | What it does |
| --- | --- |
| **Format** | MP3, AAC/M4A, Opus, FLAC, WAV, or *Original* (no re-encode) |
| **Quality** | MP3 bitrate; VBR V0 is the best-sounding option |
| **Artwork / Tags** | Embeds cover art and metadata into the file |
| **Save to** | Where files land. Click the path to open it in Explorer |
| **Queue** | Live progress; **✕** cancels one, *Stop All* cancels everything |
| **Log** | Raw yt-dlp / scdl output — this is where errors explain themselves |

Double-click a finished row to reveal the file in Explorer.

### Which engine handles what

* **YouTube** (and anything else) → yt-dlp.
* **SoundCloud** → scdl by default, because it grabs the **original uploaded
  file** when the artist allowed downloads, and writes better tags. Switch it
  to yt-dlp in Preferences if you'd rather have consistent behaviour.

If scdl is missing, out of date, or fails on a track, the download is retried
automatically with yt-dlp rather than failing. The Log tab says when this
happens and why.

### Playlists

Playlist and album links download every track by default, with live "Track 3
of 20" progress on the queue row.

Preferences → **Playlists** controls two things:

| Setting | What it does |
| --- | --- |
| **A link with a playlist** | A YouTube URL can point at one video *and* a playlist. Choose whether that downloads everything or just the one track. |
| **Tracks** | Limit the range. Empty means all; `1-10` takes the first ten; `3,7,9` takes those three. |

### SoundCloud OAuth token

Only needed for private links, Go+ tracks, or your own likes. In your browser,
sign in to SoundCloud, open DevTools → Application → Cookies → `soundcloud.com`
→ copy the value of **`oauth_token`**, and paste it into Preferences.

### Name format

Uses yt-dlp's template syntax. Some useful ones:

```
%(title)s                          Song Title
%(artist,uploader)s - %(title)s    Artist - Song Title
%(playlist_index)02d. %(title)s    01. Song Title
%(upload_date>%Y)s - %(title)s     2003 - Song Title
```

---

## Layout

```
Kitchen Sink\
  Kitchen Sink.bat     ← launch
  setup.bat            ← first-time install
  update.bat           ← refresh yt-dlp / scdl
  KitchenSink.pyw      ← entry point
  app\                 ← Python: settings, engine, ffmpeg, JS bridge
  web\                 ← the Aqua interface (index.html, aqua.css, app.js)
  bin\                 ← ffmpeg.exe / ffprobe.exe (created by setup)
  .venv\               ← private Python environment (created by setup)
```

Preferences live in `%APPDATA%\KitchenSink\settings.json`.

You can open `web\index.html` in any browser to look at the interface on its
own — it falls back to sample data when Python isn't behind it.

---

## Troubleshooting

**Nothing happens when I double-click `Kitchen Sink.bat`.**
Run `setup.bat` from a Command Prompt so you can read the error. If it
complains about `pythonnet`, install the
[Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe).

**The window opens blank / white.**
WebView2 is missing. It ships with Windows 11 and current Windows 10, but you
can install the Evergreen runtime from
<https://developer.microsoft.com/microsoft-edge/webview2/>.

**"ffmpeg not found".**
Preferences → *Install ffmpeg…*, or drop `ffmpeg.exe` and `ffprobe.exe` into
the `bin` folder yourself.

**A YouTube video says "Sign in to confirm you're not a bot".**
Preferences → *Cookies from* → pick the browser you're signed into YouTube
with. Close that browser first — it locks its cookie database.

**scdl says 403 on a SoundCloud track.**
It needs your OAuth token (see above), or the track genuinely isn't
downloadable.

---

## A note on scope

This is built for personal use — your own library, your own listening. Grabbing
audio you don't have the rights to redistribute is between you and the terms of
service of the site you got it from.
