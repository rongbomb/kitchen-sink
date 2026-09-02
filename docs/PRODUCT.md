# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Python 3.9+ desktop shell (pywebview + WebView2 on Windows), vanilla HTML/CSS/JS front end, yt-dlp + scdl + ffmpeg engine. No bundler; UI opens from `web/index.html`.

## Users

Sam and other music listeners who want a personal, offline library from YouTube and SoundCloud — not a streaming replacement, but a quiet tool for grabbing tracks they already have rights to listen to privately.

## Product Purpose

Paste or drop links, pick format and quality, and queue downloads with live progress. Success means files land tagged, with artwork, in a chosen folder — without touching system Python or PATH.

## Positioning

Dual-engine routing: scdl for SoundCloud originals and richer tags; yt-dlp for everything else — in a single Aqua-styled desktop window that feels like a Mac OS X utility, not a browser tab or CLI wrapper.

## Operating Context

Runs locally on Windows (primary), with paths for macOS/Linux. First run via `setup.bat`; updates via `tools\update.bat` when YouTube breaks. Preferences live in `%APPDATA%\KitchenSink\settings.json`.

## Capabilities and Constraints

- YouTube, SoundCloud, playlists, albums, user pages, likes (with OAuth token)
- Formats: MP3, AAC/M4A, Opus, FLAC, WAV, Original
- Queue with concurrency 1–4, archive skip, cookie import for bot checks
- Frameless Aqua window with drag-resize, traffic lights, sheet dialogs
- Personal use scope; no redistribution features

## Brand Commitments

Name: **Kitchen Sink**. Voice: plain, helpful, slightly nostalgic (Aqua era). Visual: Mac OS X 10.1–10.3 Aqua — pinstripes, traffic lights, Lucida Grande, blue progress bars. Do not modernize into flat Material or glassmorphism unless explicitly requested.

## Evidence on Hand

Working codebase: `app/downloader.py`, `web/aqua.css`, README with troubleshooting. Demo data in `web/app.js` for browser-only preview.

## Product Principles

1. **Local-first** — private venv, bundled ffmpeg, no cloud accounts required.
2. **Honest errors** — failures explain themselves in the log; UI surfaces actionable recovery.
3. **Queue clarity** — always show what's running, what's waiting, and what finished.
4. **Respect the source** — prefer original uploads on SoundCloud when allowed; embed real metadata.
5. **Stay out of the way** — paste-and-go defaults; power settings tucked in Preferences.

## Accessibility & Inclusion

Keyboard shortcuts for paste, focus URL, preferences, close. Visible focus rings on interactive controls. Respect `prefers-reduced-motion` for progress animations and sheet transitions.
