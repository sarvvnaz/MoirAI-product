// ─────────────────────────────────────────────────────────────
// MoirAI study extension — configuration (single place to edit)
// ─────────────────────────────────────────────────────────────
// Backend origin. Must match the "externally_connectable" entry in
// manifest.json — the study page can only reach this extension from an
// origin listed there, and the extension only fetches from here.
const API_BASE = "https://moirai.telab.ir";

// Hosts where the participant is *supposed* to be during the study
// (the study web app itself). Any other site triggers the reminder.
// Both study domains are listed so an old install keeps working; localhost
// stays for development. Keep this in sync with API_BASE and the manifest —
// all three name the domain, and a mismatch silently stops the extension
// from ever connecting.
const ALLOWED_HOSTS = [
  "moirai.telab.ir",
  "moirai-fastapi.chbkn.dev",
  "localhost",
  "127.0.0.1",
];

// Minimum time between two overlays, so rapid tab switching doesn't spam.
const OVERLAY_COOLDOWN_MS = 8000;

// How long the overlay stays visible.
const OVERLAY_DURATION_MS = 5000;

// ─────────────────────────────────────────────────────────────
// State kept in chrome.storage.local (survives service-worker restarts):
//   eftAccessToken   – participant JWT (set via CONNECT_EFT_USER)
//   studyActive      – true only between SESSION_STARTED / SESSION_ENDED
//   reminderDataUrl  – prefetched image as data URL (instant overlay)
//   reminderCue      – prefetched text cue
//   lastOverlayAt    – cooldown timestamp
// ─────────────────────────────────────────────────────────────

function isAllowedMoirAI(url = "") {
  try {
    const host = new URL(url).hostname;
    return ALLOWED_HOSTS.some((h) => host === h || host.endsWith("." + h));
  } catch {
    return false;
  }
}

function canInject(url = "") {
  return url.startsWith("http://") || url.startsWith("https://");
}

async function getState(keys) {
  return await chrome.storage.local.get(keys);
}

// ── Prefetch the participant's reminder SET (up to 3 images) and cache
//    them as data URLs. Overlays rotate through the set so reminders don't
//    repeat back-to-back. ──
async function blobToDataUrl(blob) {
  return await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

async function prefetchReminder() {
  const { eftAccessToken } = await getState("eftAccessToken");
  if (!eftAccessToken) {
    console.warn("[moirai] prefetch skipped: not connected");
    return false;
  }

  try {
    const res = await fetch(`${API_BASE}/api/extension/reminder-set`, {
      headers: { Authorization: `Bearer ${eftAccessToken}` },
    });
    if (!res.ok) throw new Error(`reminder-set ${res.status}`);
    const data = await res.json();

    // Cache BOTH arms of the design. Which one a given overlay shows is
    // decided at trigger time, so both have to be ready in advance — a
    // network fetch between the disengagement and the reminder would put a
    // visible delay exactly where the measurement happens.
    async function cacheAssets(list) {
      const out = [];
      for (const asset of list || []) {
        let imageUrl = asset.image_url || "";
        if (!imageUrl) continue;
        if (imageUrl.startsWith("/")) imageUrl = `${API_BASE}${imageUrl}`;
        try {
          const imgRes = await fetch(imageUrl);
          if (!imgRes.ok) continue;
          out.push({
            dataUrl: await blobToDataUrl(await imgRes.blob()),
            cue: asset.cue || "",
          });
        } catch {
          /* skip broken asset */
        }
      }
      return out;
    }

    // `assets` is already restricted by the backend to this participant's
    // fixed study arm. Do not choose or randomise the arm in the extension.
    const cached = await cacheAssets(data.assets || []);
    const arm = data.study_group === "control" ? "neutral" : "personalized";

    if (cached.length === 0) throw new Error("no assets cached");

    await chrome.storage.local.set({
      reminderAssets: cached,
      studyArm: arm,
      reminderRotation: 0,
    });
    console.log(
      `[moirai] ${cached.length} reminder(s) cached for arm ${arm}`
    );
    return true;
  } catch (e) {
    console.warn("[moirai] prefetch failed:", e.message);
    return false;
  }
}

// Next reminder to show, and which condition it belongs to.
//
// Between-subjects: the backend fixes the participant's arm and only returns
// that arm's images. Rotate through those images and report the server's arm.
async function nextReminder() {
  const { reminderAssets, reminderRotation, studyArm } = await getState([
    "reminderAssets",
    "reminderRotation",
    "studyArm",
  ]);

  if (!reminderAssets || reminderAssets.length === 0) return null;

  const idx = (reminderRotation || 0) % reminderAssets.length;
  await chrome.storage.local.set({ reminderRotation: idx + 1 });
  return {
    ...reminderAssets[idx],
    condition: studyArm === "neutral" ? "neutral" : "personalized",
  };
}

async function researchPost(path, body) {
  const { eftAccessToken } = await getState("eftAccessToken");
  if (!eftAccessToken) return null;
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${eftAccessToken}`,
    },
    body: JSON.stringify(body || {}),
  });
  return res.ok ? await res.json() : null;
}

// Stamps reminder_shown_timestamp on the latest open trigger row. The
// frontend creates the tab_switch row on focus-lost, which normally lands
// first; retry once in case this overlay won the race.
// `condition` is which arm was actually rendered. It must be passed through
// to the server: it is the only record of what the participant really saw,
// and the whole personalized-vs-generic comparison is built on it.
async function logReminderShown(condition) {
  try {
    const body = { condition: condition || "personalized" };
    let out = await researchPost("/api/research/event/reminder-shown", body);
    if (!out || out.ok === false) {
      await new Promise((r) => setTimeout(r, 2000));
      out = await researchPost("/api/research/event/reminder-shown", body);
    }
    console.log("[moirai] reminder-shown stamped:", JSON.stringify(out));
  } catch (e) {
    console.warn("[moirai] could not log reminder_shown:", e.message);
  }
}

function renderOverlay(dataUrl, cue, durationMs) {
  const oldOverlay = document.getElementById("__moirai_reminder_overlay");
  if (oldOverlay) oldOverlay.remove();

  const host = document.createElement("div");
  host.id = "__moirai_reminder_overlay";

  Object.assign(host.style, {
    position: "fixed",
    inset: "0",
    zIndex: "2147483647",
    background: "rgba(33, 25, 81, 0.92)", // palette navy
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "20px",
  });

  const img = document.createElement("img");
  img.src = dataUrl;
  img.alt = "Reminder";
  Object.assign(img.style, {
    maxWidth: "60vw",
    maxHeight: "60vh",
    borderRadius: "16px",
    boxShadow: "0 20px 80px rgba(0,0,0,0.45)",
  });
  host.appendChild(img);

  if (cue) {
    const text = document.createElement("div");
    text.textContent = cue;
    Object.assign(text.style, {
      maxWidth: "70vw",
      color: "#F0F3FF", // palette lavender
      fontSize: "22px",
      lineHeight: "1.9",
      textAlign: "center",
      direction: "rtl",
      fontFamily: "Tahoma, 'Segoe UI', sans-serif",
      textShadow: "0 2px 12px rgba(0,0,0,0.6)",
    });
    host.appendChild(text);
  }

  // "Return to study" button → clicked_return in the research data.
  const btn = document.createElement("button");
  btn.textContent = "برگرد به مطالعه ↩";
  Object.assign(btn.style, {
    marginTop: "6px",
    padding: "12px 28px",
    fontSize: "17px",
    fontFamily: "Tahoma, 'Segoe UI', sans-serif",
    color: "#211951",
    background: "#15F5BA", // palette mint
    border: "none",
    borderRadius: "12px",
    cursor: "pointer",
    boxShadow: "0 8px 30px rgba(21,245,186,0.35)",
  });
  btn.addEventListener("click", () => {
    try {
      chrome.runtime.sendMessage({ action: "RETURN_TO_STUDY" });
    } catch (e) {
      /* extension context unavailable — ignore */
    }
    host.remove();
  });
  host.appendChild(btn);

  (document.body || document.documentElement).appendChild(host);
  setTimeout(() => host.remove(), durationMs);
}

// Poll the backend: is a study session active for the connected user?
// Reliability rule: on any fetch problem, fall back to the LAST KNOWN state
// (and finally to the locally-stored studyActive flag set by the website
// message) — a transient hiccup must never silently disable reminders.
async function isStudyActive() {
  const { eftAccessToken, studyActive, lastKnownActive } = await getState([
    "eftAccessToken", "studyActive", "lastKnownActive",
  ]);
  if (!eftAccessToken) {
    console.log("[moirai] gate: not connected (no token)");
    return false;
  }
  try {
    const res = await fetch(`${API_BASE}/api/extension/status`, {
      headers: { Authorization: `Bearer ${eftAccessToken}` },
    });
    if (res.ok) {
      const data = await res.json();
      const active = !!data.study_active;
      await chrome.storage.local.set({ lastKnownActive: active });
      return active;
    }
    console.log("[moirai] gate: status HTTP", res.status, "— using fallback");
  } catch (e) {
    console.log("[moirai] gate: status fetch failed:", e.message,
      "— using fallback");
  }
  // Fallback chain: last successful backend answer → website message flag.
  if (typeof lastKnownActive === "boolean") return lastKnownActive;
  return !!studyActive;
}

async function showOverlayIfNotAllowed(tab) {
  if (!tab || !tab.id) return;

  const url = tab.url || "";
  if (isAllowedMoirAI(url)) {
    console.log("[moirai] on study site — no overlay");
    return;
  }
  if (!canInject(url)) {
    console.log("[moirai] cannot inject into:", url || "(empty/chrome page)");
    return;
  }

  // Gate on the BACKEND session flag (source of truth, no message needed).
  const active = await isStudyActive();
  if (!active) {
    console.log("[moirai] gate: study session not active — no overlay");
    return;
  }

  const { lastOverlayAt } = await getState("lastOverlayAt");
  const now = Date.now();
  if (lastOverlayAt && now - lastOverlayAt < OVERLAY_COOLDOWN_MS) {
    console.log("[moirai] overlay suppressed by cooldown");
    return;
  }
  await chrome.storage.local.set({ lastOverlayAt: now });

  try {
    // Use the prefetched cache — instant, no network at trigger time.
    let reminder = await nextReminder();
    if (!reminder) {
      console.log("[moirai] no cache yet — fetching now");
      await prefetchReminder();
      reminder = await nextReminder();
    }
    if (!reminder) {
      console.warn("[moirai] no reminder available to show (generation done?)");
      return;
    }

    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: renderOverlay,
      args: [reminder.dataUrl, reminder.cue || "", OVERLAY_DURATION_MS],
    });

    console.log(
      `[moirai] ✅ overlay shown (${reminder.condition}) on:`, url
    );
    await logReminderShown(reminder.condition);
  } catch (error) {
    console.error("[moirai] overlay failed:", error);
  }
}

// Overlay "return to study" button → focus the study tab + record the click.
chrome.runtime.onMessage.addListener((message) => {
  if (message && message.action === "RETURN_TO_STUDY") {
    (async () => {
      try {
        await researchPost("/api/research/event/return", {
          clicked_return: true,
        });
      } catch (e) {
        console.warn("[moirai] clicked_return log failed:", e.message);
      }
      const tabs = await chrome.tabs.query({});
      const studyTab = tabs.find((t) => isAllowedMoirAI(t.url || ""));
      if (studyTab) {
        await chrome.tabs.update(studyTab.id, { active: true });
        await chrome.windows.update(studyTab.windowId, { focused: true });
      }
    })();
  }
});

async function checkActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  await showOverlayIfNotAllowed(tabs[0]);
}

// Case 1: switching to any old or new tab
chrome.tabs.onActivated.addListener(async () => {
  await checkActiveTab();
});

// Case 2: opening/loading a website in a new tab
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status !== "complete") return;

  const activeTabs = await chrome.tabs.query({
    active: true,
    currentWindow: true,
  });
  if (!activeTabs[0] || activeTabs[0].id !== tabId) return;

  await showOverlayIfNotAllowed(tab);
});

// Case 3: clicking/focusing another Chrome window
chrome.windows.onFocusChanged.addListener(async (windowId) => {
  if (windowId === chrome.windows.WINDOW_ID_NONE) return;
  await checkActiveTab();
});

// ── Website → extension messages ──
chrome.runtime.onMessageExternal.addListener((message, sender, sendResponse) => {
  const action = message && message.action;

  if (action === "CONNECT_EFT_USER") {
    const token = message.accessToken;
    if (!token || typeof token !== "string") {
      sendResponse({ success: false, error: "Missing access token" });
      return;
    }
    // Storage survives browser restarts and account changes. Clear all cached
    // intervention data before attaching a new participant token.
    chrome.storage.local.remove(
      ["reminderAssets", "reminderGeneric", "reminderRotation",
       "genericRotation", "genericRatio", "studyArm", "lastOverlayAt"],
      () => {
        chrome.storage.local.set(
          { eftAccessToken: token, eftConnectedAt: Date.now() },
          async () => {
            console.log("[moirai] connected — previous cache cleared");
            await prefetchReminder();
            sendResponse({ success: true });
          }
        );
      }
    );
    return true; // async response
  }

  if (action === "SESSION_STARTED") {
    // Sent once at session start AND as a ~20s heartbeat while the session
    // runs (so an extension reloaded mid-session gets re-armed). Heartbeats
    // must be cheap: only reset the cooldown / refetch images when something
    // actually changed.
    (async () => {
      const { eftAccessToken, studyActive, reminderAssets } = await getState([
        "eftAccessToken", "studyActive", "reminderAssets",
      ]);
      // Always take the token from THIS message — the participant may have
      // logged in as a different user since the last CONNECT, so the stored
      // token (and its cached reminder) could belong to someone else.
      const newToken =
        typeof message.accessToken === "string" && message.accessToken
          ? message.accessToken
          : null;
      const tokenChanged = !!newToken && newToken !== eftAccessToken;
      const freshStart = !studyActive; // inactive → active transition

      const patch = { studyActive: true, lastKnownActive: true };
      if (tokenChanged) patch.eftAccessToken = newToken;
      if (freshStart) patch.lastOverlayAt = 0;
      await chrome.storage.local.set(patch);

      if (freshStart) {
        console.log("[moirai] study session STARTED — reminders active");
      }
      // Refresh the cache when the user changed, the session just started
      // (the reminder may have been (re)generated), or nothing is cached yet.
      if (tokenChanged || freshStart || !reminderAssets ||
          reminderAssets.length === 0) {
        await prefetchReminder();
      }
      sendResponse({ success: true });
    })();
    return true;
  }

  if (action === "SESSION_ENDED") {
    chrome.storage.local.set({ studyActive: false, lastKnownActive: false }, () => {
      console.log("[moirai] study session ENDED — reminders inactive");
      sendResponse({ success: true });
    });
    return true;
  }

  sendResponse({ success: false, error: "Unknown action" });
});
