---
name: Kitchen Sink
description: Mac OS X Aqua desktop shell for a personal audio downloader
colors:
  aqua-blue: "#4a90e2"
  aqua-blue-dark: "#2f6fce"
  aqua-blue-deep: "#1f5bb5"
  selection: "#3b6ea5"
  face: "#ededed"
  face-dark: "#d8d8d8"
  line: "#9a9a9a"
  text: "#101010"
  text-dim: "#6b6b6b"
  window-chrome: "#6d7a8b"
  stripe: "rgba(0,0,0,.045)"
  success: "#28a844"
  error: "#d0342c"
  soundcloud-chip: "#8a4211"
  youtube-chip: "#8c1f1f"
typography:
  ui:
    fontFamily: "Lucida Grande, Lucida Sans Unicode, Lucida Sans, Segoe UI, Tahoma, Geneva, sans-serif"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.35
  mono:
    fontFamily: "Monaco, Andale Mono, Consolas, Courier New, monospace"
    fontSize: "10.5px"
    fontWeight: 400
    lineHeight: 1.45
rounded:
  window: "9px"
  control: "6px"
  chip: "7px"
spacing:
  pane: "9px 12px 10px"
  row-gap: "7px"
  list-item: "5px 0"
components:
  button-default:
    backgroundColor: "{colors.face}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "4px 14px"
  progress-bar:
    backgroundColor: "{colors.aqua-blue}"
    height: "11px"
    rounded: "{rounded.control}"
---

## Overview

Kitchen Sink wears **Mac OS X Aqua (10.1–10.3)** inside a frameless pywebview window. Everything is CSS gradients — no image assets. The interface mode is **Operate**: scanability, native metaphors, and task completion beat expression.

## Colors

| Role | Token | Usage |
| --- | --- | --- |
| Primary action | `aqua-blue` → `aqua-blue-deep` | Progress bars, selected tabs, proxy icon |
| Surface | `face`, `face-dark` | Window body, panes, lists |
| Structure | `line`, `text`, `text-dim` | Borders, labels, secondary copy |
| Status | `success`, `error` | LED, done/error bars and badges |
| Site chips | SC orange, YT red gradients | Queue row provenance |

## Typography

- **UI:** Lucida Grande stack at 11px — title bar 12px bold, status bar 10px.
- **Mono:** Log console and name-format field only.
- **Hierarchy:** Bold row titles; 10px dim subtitles; no kickers or eyebrows above headings.

## Layout

- Column flex: title bar (23px) → top pane → tab view (flex) → status bar (20px).
- URL row + options row + destination row in top pane.
- Queue list: name (flex) | status (126px) | progress (140px).
- Minimum window 600×470; resize grip bottom-right.

## Elevation & Depth

Aqua depth via **inset highlights + bottom shadows**, not floating cards. Sheet dialogs slide from title bar with shade overlay. Buttons use beveled gradients; traffic lights use radial specular dots.

## Shapes

- Window: 9px top radius, 7px bottom.
- Controls, popups, field wells: 6px.
- Progress bars: pill 6px radius.
- Traffic lights: perfect circles 13px.

## Components

- **Traffic lights:** close/min/zoom with hover labels.
- **Popup selects:** native `<select>` with faux arrow chrome.
- **Checkboxes:** Aqua square with gradient box.
- **Queue rows:** alternating `#edf3fe` stripe; site chips; cancel ✕ on active jobs.
- **Progress bar:** barber-pole animation while running; green/red terminal states.
- **Sheet:** modal alert with icon variants info/warn.

## Do's and Don'ts

**Do:** Keep pinstripe backgrounds, blue progress, and Lucida voice consistent. Use sheet dialogs for confirmations. Show site chips and actionable error hints.

**Don't:** Flatten to modern minimal UI, add glass/blur, use gradient text, or replace Aqua scrollbars. Don't use emoji as icons — draw with CSS or text glyphs already in the sheet icons.
