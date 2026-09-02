/* Kitchen Sink — front-end controller. Talks to Python over loopback HTTP. */
(function () {
  "use strict";

  const $  = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));

  let api = null;
  let settings = {};
  const jobs = new Map();
  let ready = false;
  let booted = false;
  let goBusy = false;

  /* ============================== transport ============================= */
  /* pywebview's bridge starts an OS thread per call and answers with a
     blocking evaluate_js: on a timer it buries the process in threads, and on
     close it waits forever for a reply from a webview that is already gone.
     Nothing here touches it — every call goes to the loopback HTTP server.  */
  const TOKEN = window.KS_TOKEN || "";
  const LIVE = location.protocol === "http:" && TOKEN && TOKEN.indexOf("__") !== 0;

  function apiGet(path) {
    return fetch(path, { headers: { "X-KS-Token": TOKEN } }).then((r) => r.json());
  }

  function apiPost(name, body) {
    return fetch("/api/" + name, {
      method: "POST",
      headers: { "X-KS-Token": TOKEN, "Content-Type": "application/json" },
      body: JSON.stringify(body || {})
    }).then((r) => r.json()).then((r) => {
      if (r && r.ok === false) throw new Error(r.error || "Request failed");
      return r ? r.result : null;
    });
  }

  const SERVER = {
    get_state: () => apiGet("/api/state"),
    poll: () => apiGet("/api/poll"),
    add_urls: (text) => apiPost("add_urls", { text }),
    save_settings: (patch) => apiPost("save_settings", { patch }),
    cancel: (job_id) => apiPost("cancel", { job_id }),
    cancel_all: () => apiPost("cancel_all"),
    clear_finished: () => apiPost("clear_finished"),
    retry: (job_id) => apiPost("retry", { job_id }),
    read_clipboard: () => apiPost("read_clipboard"),
    install_ffmpeg: () => apiPost("install_ffmpeg"),
    open_path: (path) => apiPost("open_path", { path: path || "" }),
    reveal: (path) => apiPost("reveal", { path }),
    choose_folder: () => apiPost("choose_folder"),
    win_close: () => apiPost("win_close"),
    win_minimize: () => apiPost("win_minimize"),
    win_zoom: () => apiPost("win_zoom"),
    win_resize: (w, h) => apiPost("win_resize", { width: w, height: h })
  };

  /* ============================ demo fallback ============================ */
  /* Lets you open web/index.html in a browser to look at the design without
     running Python. Never used when the real app is running.               */
  const DEMO = {
    get_state: () => Promise.resolve({
      settings: {
        output_dir: "C:\\Users\\you\\Music\\Kitchen Sink", audio_format: "mp3",
        audio_quality: "320", embed_thumbnail: true, embed_metadata: true,
        soundcloud_engine: "scdl", sc_auth_token: "", sc_client_id: "",
        sc_original_files: true, name_template: "%(title)s",
        playlist_subfolder: true, playlist_mode: "all", playlist_items: "",
        concurrency: 1, archive: false,
        cookies_from_browser: "", write_lyrics: false, sound_effects: true
      },
      jobs: [
        { id: 1, title: "Aphex Twin — Avril 14th", site: "youtube", engine: "yt-dlp",
          status: "working", stage: "Downloading", percent: 63, speed: "1.8 MB/s",
          eta: "0:09", size: "8.4 MB", url: "https://youtu.be/…", files: [],
          index: 0, count: 0, message: "" },
        { id: 2, title: "Burial — Untrue (full LP)", site: "soundcloud", engine: "scdl",
          status: "working", stage: "Converting audio…", percent: 100, speed: "",
          eta: "", size: "", url: "https://soundcloud.com/…", files: [],
          index: 4, count: 13, message: "" },
        { id: 3, title: "Boards of Canada — Roygbiv", site: "youtube", engine: "yt-dlp",
          status: "done", stage: "Complete", percent: 100, speed: "", eta: "",
          size: "5.1 MB", url: "https://youtu.be/…", files: ["x.mp3"],
          index: 0, count: 0, message: "1 file(s) saved" },
        { id: 4, title: "private-set-2003.wav", site: "soundcloud", engine: "scdl",
          status: "error", stage: "Failed", percent: 0, speed: "", eta: "", size: "",
          url: "https://soundcloud.com/…", files: [], index: 0, count: 0,
          message: "403 — track requires an OAuth token" }
      ],
      log: ["[youtube] Extracting URL…", "[info] Downloading 1 format(s): 251",
            "[ExtractAudio] Destination: Roygbiv.mp3", "scdl -l https://soundcloud.com/… --onlymp3"],
      ffmpeg: "C:\\Users\\you\\Desktop\\Kitchen Sink\\bin",
      versions: { python: "3.12.4", ytdlp: "2026.08.19", scdl: "2.13.0" },
      platform: "win32", home: "C:\\Users\\you"
    }),
    add_urls: () => Promise.resolve({ ok: true, added: 1 }),
    save_settings: (p) => Promise.resolve(p),
    cancel: () => Promise.resolve(true), cancel_all: () => Promise.resolve(true),
    clear_finished: () => Promise.resolve([]), retry: () => Promise.resolve({ ok: true }),
    read_clipboard: () => Promise.resolve("https://youtu.be/demo"),
    poll: () => Promise.resolve({ jobs: [], logs: [], events: [] }), choose_folder: () => Promise.resolve(null),
    open_path: () => Promise.resolve(true), reveal: () => Promise.resolve(true),
    install_ffmpeg: () => Promise.resolve(true),
    win_close: () => window.close(), win_minimize: () => {}, win_zoom: () => {},
    win_resize: () => {}
  };

  /* ================================ sound =============================== */
  let actx = null;
  function blip(kind) {
    if (!settings.sound_effects) return;
    try {
      actx = actx || new (window.AudioContext || window.webkitAudioContext)();
      const notes = kind === "error" ? [392, 262] : [784, 1047, 1319];
      notes.forEach((f, i) => {
        const o = actx.createOscillator(), g = actx.createGain();
        o.type = "sine"; o.frequency.value = f;
        const t = actx.currentTime + i * 0.075;
        g.gain.setValueAtTime(0.0001, t);
        g.gain.exponentialRampToValueAtTime(0.055, t + 0.012);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.2);
        o.connect(g); g.connect(actx.destination);
        o.start(t); o.stop(t + 0.22);
      });
    } catch (e) { /* no audio device; never mind */ }
  }

  /* ================================ sheet =============================== */
  let sheetResolve = null;
  function sheet(opts) {
    $("#sheet-title").textContent = opts.title || "";
    $("#sheet-msg").innerHTML = opts.message || "";
    $("#sheet-extra").innerHTML = opts.extra || "";
    $("#sheet-icon").className = "sheet-icon " + (opts.icon || "info");
    $("#sheet-ok").textContent = opts.ok || "OK";
    $("#sheet-cancel").style.display = opts.cancel === false ? "none" : "";
    $("#sheet-cancel").textContent = opts.cancelLabel || "Cancel";
    $("#sheet").classList.add("on");
    $("#shade").classList.add("on");
    return new Promise((res) => { sheetResolve = res; });
  }
  function closeSheet(val) {
    $("#sheet").classList.remove("on");
    $("#shade").classList.remove("on");
    if (sheetResolve) { sheetResolve(val); sheetResolve = null; }
  }
  $("#sheet-ok").onclick = () => closeSheet(true);
  $("#sheet-cancel").onclick = () => closeSheet(false);

  /* =============================== status =============================== */
  function setStatus(text, led) {
    $("#status").textContent = text;
    $("#led").className = "status-led" + (led ? " " + led : "");
  }

  function refreshCounts() {
    const all = Array.from(jobs.values());
    const busy = all.filter((j) => j.status === "working" || j.status === "queued").length;
    const done = all.filter((j) => j.status === "done").length;
    const bad  = all.filter((j) => j.status === "error").length;
    $("#counts").textContent = all.length
      ? `${all.length} item${all.length > 1 ? "s" : ""} · ${done} done` +
        (bad ? ` · ${bad} failed` : "")
      : "";
    if (busy) setStatus(`Downloading — ${busy} in progress…`, "busy");
    else if (bad) setStatus("Finished with errors.", "err");
    else if (done) setStatus("All downloads complete.", "ok");
    else setStatus("Ready.", "");
    $("#queue-empty").style.display = all.length ? "none" : "";
    const failed = all.filter((j) => j.status === "error");
    const retryBtn = $("#btn-retry");
    if (retryBtn) {
      retryBtn.disabled = failed.length === 0;
      retryBtn.title = failed.length
        ? `Retry ${failed.length} failed download${failed.length > 1 ? "s" : ""}`
        : "Retry failed downloads";
    }
  }

  /* ============================== rendering ============================= */
  function siteChip(job) {
    if (job.site === "soundcloud") return '<span class="chip sc">SoundCloud</span>';
    if (job.site === "youtube")    return '<span class="chip yt">YouTube</span>';
    return '<span class="chip">Web</span>';
  }

  function rowHTML(job) {
    const cancellable = job.status === "queued" || job.status === "working";
    const retryable = job.status === "error" || job.status === "cancelled";
    const barCls =
      job.status === "done" ? "bar done" :
      job.status === "error" ? "bar err" :
      job.status === "working" ? "bar run" : "bar";
    const indet = job.status === "working" && job.percent >= 99.9 &&
                  /Convert|tag|artwork|Embed/i.test(job.stage || "");
    const sub = job.count > 1 ? `Track ${job.index || 1} of ${job.count} · ` : "";
    const meta = [job.speed, job.eta && "ETA " + job.eta, job.size]
                   .filter(Boolean).join(" · ");
    const hint = job.status === "error" && /403|oauth|token/i.test(job.message || "")
      ? " · add OAuth token in Preferences"
      : job.status === "error" && /bot|sign in|cookie/i.test(job.message || "")
      ? " · try Cookies from in Preferences"
      : "";
    return `
      <div class="name">
        <b title="${esc(job.title)}">${esc(job.title)}</b>
        <small>${siteChip(job)}${esc(sub)}${esc(job.message || job.url)}${esc(hint)}</small>
      </div>
      <div class="status">
        ${cancellable ? '<button class="xbtn" data-cancel="' + job.id + '" title="Cancel">&#10005;</button>' : ""}
        ${retryable ? '<button class="retrybtn" data-retry="' + job.id + '" title="Retry">&#8635;</button>' : ""}
        <span class="badge">${esc(job.stage || job.status)}</span>
      </div>
      <div class="prog">
        <div class="${barCls}${indet ? " indet" : ""}"><i style="width:${job.percent}%"></i></div>
        <div class="meta">${esc(meta)}</div>
      </div>`;
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function upsert(job, deferCounts) {
    const prev = jobs.get(job.id);
    jobs.set(job.id, job);
    let el = document.getElementById("job-" + job.id);
    if (!el) {
      el = document.createElement("div");
      el.id = "job-" + job.id;
      el.className = "item";
      // keep the empty-state placeholder last so :nth-child striping is right
      $("#queue").insertBefore(el, $("#queue-empty"));
    }
    el.className = "item " + job.status;
    el.innerHTML = rowHTML(job);
    if (job.files && job.files.length) {
      el.querySelector(".name").style.cursor = "default";
      el.querySelector(".name").ondblclick = () => api.reveal(job.files[0]);
    }
    if (prev && prev.status !== job.status) {
      if (job.status === "done") blip("done");
      if (job.status === "error") blip("error");
    }
    if (!deferCounts) refreshCounts();
  }

  function upsertMany(list) {
    (list || []).forEach((j) => upsert(j, true));
    refreshCounts();
  }

  function addLog(line, deferScroll) {
    const pre = $("#log");
    pre.textContent += (pre.textContent ? "\n" : "") + line;
    if (pre.textContent.length > 120000) pre.textContent = pre.textContent.slice(-90000);
    if (!deferScroll) pre.scrollTop = pre.scrollHeight;
  }

  function addLogs(lines) {
    (lines || []).forEach((l) => addLog(l, true));
    const pre = $("#log");
    pre.scrollTop = pre.scrollHeight;
  }

  /* =========================== settings binding ========================= */
  const BINDINGS = [
    ["#fmt",        "audio_format",         "value"],
    ["#quality",    "audio_quality",        "value"],
    ["#art",        "embed_thumbnail",      "checked"],
    ["#tags",       "embed_metadata",       "checked"],
    ["#sc-engine",  "soundcloud_engine",    "value"],
    ["#sc-token",   "sc_auth_token",        "value"],
    ["#sc-client",  "sc_client_id",         "value"],
    ["#sc-original","sc_original_files",    "checked"],
    ["#tmpl",       "name_template",        "value"],
    ["#sub",        "playlist_subfolder",   "checked"],
    ["#pl-mode",    "playlist_mode",        "value"],
    ["#pl-items",   "playlist_items",       "value"],
    ["#archive",    "archive",              "checked"],
    ["#lyrics",     "write_lyrics",         "checked"],
    ["#conc",       "concurrency",          "value"],
    ["#cookies",    "cookies_from_browser", "value"],
    ["#sfx",        "sound_effects",        "checked"]
  ];

  function applySettings(s) {
    settings = s || {};
    BINDINGS.forEach(([sel, key, prop]) => {
      const el = $(sel);
      if (!el) return;
      const v = settings[key];
      el[prop] = prop === "checked" ? !!v : (v == null ? "" : String(v));
    });
    $("#dest").textContent = settings.output_dir || "";
    $("#dest").title = settings.output_dir || "";
    const showQ = settings.audio_format === "mp3";
    $("#lbl-quality").style.visibility = showQ ? "" : "hidden";
    $("#wrap-quality").style.visibility = showQ ? "" : "hidden";
  }

  function wireSettings() {
    BINDINGS.forEach(([sel, key, prop]) => {
      const el = $(sel);
      if (!el) return;
      const handler = () => {
        let v = el[prop];
        if (key === "concurrency") v = parseInt(v, 10) || 1;
        settings[key] = v;
        api.save_settings({ [key]: v });
        if (key === "audio_format") applySettings(settings);
      };
      el.addEventListener("change", handler);
      if (prop === "value" && el.tagName === "INPUT") {
        let t; el.addEventListener("input", () => { clearTimeout(t); t = setTimeout(handler, 400); });
      }
    });
  }

  /* ============================== ffmpeg ================================ */
  function setFfmpeg(path) {
    const el = $("#ff-state");
    if (path) {
      el.className = "ffmpeg-state ok";
      el.textContent = "found";
      el.title = path;
      $("#btn-ffmpeg").textContent = "Reinstall…";
    } else {
      el.className = "ffmpeg-state bad";
      el.textContent = "not found";
      el.title = "";
      $("#btn-ffmpeg").textContent = "Install ffmpeg…";
    }
  }

  /* ============================== actions =============================== */
  async function pasteUrl() {
    const text = await api.read_clipboard();
    if (!text) {
      await sheet({
        title: "Clipboard is empty",
        message: "Copy a YouTube or SoundCloud link first, then try Paste again.",
        icon: "warn", cancel: false
      });
      return;
    }
    $("#url").value = text.trim();
    if (/https?:\/\//i.test(text)) go();
    else $("#url").focus();
  }

  async function retryFailed() {
    const failed = Array.from(jobs.values()).filter((j) => j.status === "error");
    if (!failed.length) return;
    for (const j of failed) await api.retry(j.id);
  }

  async function go() {
    if (!booted) {
      setStatus("Still starting…", "busy");
      return;
    }
    if (goBusy) return;
    const box = $("#url");
    const text = box.value.trim();
    if (!text) { box.focus(); return; }

    goBusy = true;
    $("#btn-go").disabled = true;
    setStatus("Queuing…", "busy");
    try {
      const res = await withTimeout(api.add_urls(text), 8000, "Queue");
      if (res && res.ok === false) {
        await sheet({ title: "That’s not a link", message: esc(res.error),
                      icon: "warn", cancel: false });
        return;
      }
      box.value = "";
      switchTab("queue");
      setStatus("Queued.", "busy");
    } catch (err) {
      addLog("Could not queue link: " + (err && err.message ? err.message : err));
      setStatus("Could not queue — see Log.", "err");
    } finally {
      goBusy = false;
      $("#btn-go").disabled = false;
      refreshCounts();
    }
  }

  function switchTab(name) {
    $$(".tab").forEach((t) => t.classList.toggle("selected", t.dataset.tab === name));
    $$(".tabpanel").forEach((p) => p.classList.toggle("active", p.dataset.panel === name));
  }

  function wireUI() {
    $("#btn-go").onclick = go;
    $("#btn-paste").onclick = pasteUrl;
    $("#url").addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); go(); }
    });
    // Wait until the paste has landed in the field, and until boot finishes,
    // before auto-starting.
    $("#url").addEventListener("paste", () => {
      requestAnimationFrame(() => requestAnimationFrame(() => {
        if (!booted) return;
        const v = $("#url").value.trim();
        if (/^https?:\/\//i.test(v)) go();
      }));
    });

    $("#btn-choose").onclick = async () => {
      const p = await api.choose_folder();
      if (p) { settings.output_dir = p; $("#dest").textContent = p; $("#dest").title = p; }
    };
    $("#dest").onclick = () => api.open_path("");
    $("#btn-open").onclick = () => api.open_path("");
    $("#btn-stop").onclick = () => api.cancel_all();
    $("#btn-retry").onclick = retryFailed;
    $("#btn-clear").onclick = async () => {
      await api.clear_finished();
      Array.from(jobs.values())
        .filter((j) => ["done", "error", "cancelled"].includes(j.status))
        .forEach((j) => {
          jobs.delete(j.id);
          const el = document.getElementById("job-" + j.id);
          if (el) el.remove();
        });
      refreshCounts();
    };
    $("#btn-clearlog").onclick = () => { $("#log").textContent = ""; };

    $("#queue").addEventListener("click", (e) => {
      const b = e.target.closest("[data-cancel]");
      if (b) { api.cancel(parseInt(b.dataset.cancel, 10)); return; }
      const r = e.target.closest("[data-retry]");
      if (r) api.retry(parseInt(r.dataset.retry, 10));
    });

    $$(".tab").forEach((t) => { t.onclick = () => switchTab(t.dataset.tab); });

    $("#btn-ffmpeg").onclick = async () => {
      const ok = await sheet({
        title: "Install ffmpeg?",
        message: "Kitchen Sink will download a static ffmpeg build (about 80&nbsp;MB) " +
                 "into its own <b>bin</b> folder. Nothing is installed system-wide.",
        icon: "", ok: "Install"
      });
      if (!ok) return;
      switchTab("log");
      api.install_ffmpeg();
    };

    $("#btn-about").onclick = () => sheet({
      title: "Kitchen Sink 1.0",
      message: "A personal YouTube &amp; SoundCloud audio downloader.<br>" +
               "Powered by yt-dlp, scdl and ffmpeg.",
      icon: "info", cancel: false
    });

    $("#btn-close").onclick = () => { try { api.win_close(); } catch (e) {} };
    $("#btn-min").onclick   = () => { try { api.win_minimize(); } catch (e) {} };
    $("#btn-zoom").onclick  = () => { try { api.win_zoom(); } catch (e) {} };
    $("#titlebar").addEventListener("dblclick", (e) => {
      if (!e.target.closest("button")) { try { api.win_zoom(); } catch (err) {} }
    });

    /* Resize grip — one bridge call on release, not while dragging. */
    const grip = $("#grip");
    grip.addEventListener("mousedown", (e) => {
      e.preventDefault();
      const x0 = e.screenX, y0 = e.screenY;
      const w0 = window.outerWidth || window.innerWidth;
      const h0 = window.outerHeight || window.innerHeight;
      const up = (ev) => {
        try {
          api.win_resize(w0 + (ev.screenX - x0), h0 + (ev.screenY - y0));
        } catch (err) { /* no bridge yet */ }
        window.removeEventListener("mousemove", move);
        window.removeEventListener("mouseup", up);
      };
      const move = (ev) => ev.preventDefault();
      window.addEventListener("mousemove", move);
      window.addEventListener("mouseup", up);
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && $("#sheet").classList.contains("on")) closeSheet(false);
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "w") api.win_close();
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "l") $("#url").select();
      if ((e.ctrlKey || e.metaKey) && e.key === ",") switchTab("prefs");
    });

    /* drag a link onto the window */
    let dragDepth = 0;
    const dropHint = $("#drop-hint");
    const showDrop = (on) => {
      if (dropHint) dropHint.classList.toggle("on", on);
      document.body.classList.toggle("drag-over", on);
    };
    document.addEventListener("dragenter", (e) => {
      e.preventDefault();
      dragDepth++;
      showDrop(true);
    });
    document.addEventListener("dragleave", (e) => {
      e.preventDefault();
      dragDepth = Math.max(0, dragDepth - 1);
      if (dragDepth === 0) showDrop(false);
    });
    document.addEventListener("dragover", (e) => e.preventDefault());
    document.addEventListener("drop", (e) => {
      e.preventDefault();
      dragDepth = 0;
      showDrop(false);
      const t = e.dataTransfer.getData("text/uri-list") ||
                e.dataTransfer.getData("text/plain") ||
                e.dataTransfer.getData("text");
      if (t) { $("#url").value = t.trim(); go(); }
    });
  }

  /* ================================ boot ================================ */
  function showVersions(v) {
    $("#versions").textContent =
      `yt-dlp ${v.ytdlp} · scdl ${v.scdl} · Python ${v.python}`;
  }

  function applyPoll(data) {
    if (!data) return;
    if (data.jobs && data.jobs.length) upsertMany(data.jobs);
    if (data.logs && data.logs.length) addLogs(data.logs);
    (data.events || []).forEach((ev) => {
      if (ev.kind === "versions") showVersions(ev.payload || {});
      if (ev.kind === "ffmpeg") setFfmpeg(ev.payload);
      if (ev.kind === "ffmpegBusy") {
        if (ev.payload) setStatus("Installing ffmpeg…", "busy");
        else refreshCounts();
      }
    });
  }

  // Self-scheduling instead of setInterval, so a slow reply can never stack
  // requests on top of one another.
  function startPolling() {
    if (!LIVE) return;
    const tick = () => {
      Promise.resolve(api.poll())
        .then(applyPoll)
        .catch(() => {})
        .then(() => setTimeout(tick, 200));
    };
    tick();
  }

  function withTimeout(value, ms, label) {
    return Promise.race([
      Promise.resolve(value),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error(label + " timed out")), ms))
    ]);
  }

  async function boot() {
    if (ready) return;
    ready = true;
    api = LIVE ? SERVER : DEMO;
    if (!LIVE) booted = true;

    // Wire the interface before touching Python, so the window stays usable
    // even if the engine is slow to answer or never answers at all.
    wireUI();
    wireSettings();
    setStatus("Starting…", "busy");
    $("#url").focus();

    let st = null;
    try {
      st = await withTimeout(api.get_state(), 20000, "Startup");
    } catch (err) {
      setStatus("The engine didn’t respond — see the Log tab.", "err");
      addLog("Startup problem: " + (err && err.message ? err.message : err));
      addLog("The window still works. Try closing and reopening Kitchen Sink, " +
             "or run setup.bat again.");
      booted = true;
      startPolling();
      return;
    }

    try {
      applySettings(st.settings);
      upsertMany(st.jobs);
      addLogs(st.log);
      setFfmpeg(st.ffmpeg);
      showVersions(st.versions || {});
      refreshCounts();
      booted = true;
      setStatus("Ready.", "");
      startPolling();
    } catch (err) {
      addLog("Interface error: " + (err && err.message ? err.message : err));
      booted = true;
      setStatus("Ready.", "");
      startPolling();
    }

    if (!st.ffmpeg) {
      setTimeout(async () => {
        const ok = await sheet({
          title: "ffmpeg isn’t installed yet",
          message: "Kitchen Sink needs ffmpeg to convert audio and embed artwork. " +
                   "Shall I download it into the app’s own folder now? (~80&nbsp;MB)",
          icon: "warn", ok: "Download", cancelLabel: "Later"
        });
        if (ok) { switchTab("log"); api.install_ffmpeg(); }
      }, 500);
    }
  }

  if (LIVE) {
    // Startup no longer waits on the bridge — the data comes over HTTP.
    boot();
  } else {
    // web/index.html opened straight in a browser: fall back to demo data.
    document.addEventListener("DOMContentLoaded", () => setTimeout(boot, 1500));
    if (document.readyState !== "loading") setTimeout(boot, 1500);
  }
})();
