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

// How long the overlay stays visible.
const OVERLAY_DURATION_MS = 5000;

// ─────────────────────────────────────────────────────────────
// State kept in chrome.storage.local (survives service-worker restarts):
//   eftAccessToken   – participant JWT (set via CONNECT_EFT_USER)
//   studyActive      – true only between SESSION_STARTED / SESSION_ENDED
//   reminderDataUrl  – prefetched image as data URL (instant overlay)
//   reminderCue      – prefetched text cue
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

    // `assets` is ALREADY this participant's arm: the eft arm's own images,
    // or the shared generic set for control. The server withholds the other
    // arm entirely, so there is nothing here to choose between.
    //
    // This used to read `data.personalized || data.assets`. An empty array is
    // TRUTHY in JavaScript, so a control participant — whose `personalized`
    // is [] by design — cached nothing, the throw below fired, and the
    // PREVIOUS participant's images stayed in storage and kept being shown.
    const cached = await cacheAssets(data.assets || []);
    const arm = data.study_group === "control" ? "neutral" : "personalized";

    if (cached.length === 0) throw new Error("no assets cached");

    await chrome.storage.local.set({
      reminderAssets: cached,
      // The arm decides the label, and it comes from the server. Nothing on
      // this side gets to guess: a wrong label silently moves a participant
      // between conditions in the analysis.
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
// Between-subjects: the participant's ARM is fixed for the whole study and
// the server only ever sends that arm's images, so there is no choice to make
// here and no randomisation. This function rotates through what it was given
// and reports the arm the server stated.
//
// It used to roll per trigger against a ratio. That belonged to the earlier
// within-participant design; kept alongside per-participant arms it produced
// labels that disagreed with what the server had actually sent.
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
    // Never defaulted to "personalized": a control participant mislabelled
    // that way is silently analysed in the wrong arm.
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

// ── SCHEDULED CUE DELIVERY ────────────────────────────────────────────
// A tab switch NO LONGER SHOWS ANYTHING on its own. It opens a disengagement
// episode (an outcome measure) and asks the server whether a cue slot happens
// to be open right now.
//
// The server owns the clock. This worker cannot: MV3 evicts and restarts it
// at Chrome's discretion, so anything it scheduled locally can simply vanish.

async function studyGet(path) {
  const { eftAccessToken } = await getState("eftAccessToken");
  if (!eftAccessToken) return null;
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { Authorization: `Bearer ${eftAccessToken}` },
    });
    return res.ok ? await res.json() : null;
  } catch (e) {
    console.warn("[moirai] GET", path, "failed:", e.message);
    return null;
  }
}

// Which disengagement episode this worker believes is open. Stored rather
// than held in memory because the service worker is evicted between events,
// and an unpaired start would leave an episode open forever — its duration
// NULL, silently dropping it out of time-on-task.
async function openEpisode(type) {
  const { episodeOpen } = await getState("episodeOpen");
  if (episodeOpen) return;
  await chrome.storage.local.set({ episodeOpen: true });
  await researchPost("/api/study/disengagement/start", { type });
  console.log("[moirai] disengagement opened:", type);
}

async function closeEpisode(endedBy = "return") {
  const { episodeOpen } = await getState("episodeOpen");
  if (!episodeOpen) return;
  await chrome.storage.local.set({ episodeOpen: false });
  await researchPost("/api/study/disengagement/end", { ended_by: endedBy });
  console.log("[moirai] disengagement closed:", endedBy);
}

// Delivers a scheduled cue IF one is due and this client should own it.
// `state` is off_tab or off_browser — the only two states this side can
// legitimately report. The app reports active/idle; the arm decides the
// condition, and neither client is asked for it.
async function maybeDeliverScheduledCue(tab, state = "off_tab") {
  if (!tab || !tab.id) return;

  const url = tab.url || "";
  if (isAllowedMoirAI(url)) return; // on the study site — the app's job

  const active = await isStudyActive();
  if (!active) return;

  // Ask FIRST. Outside the two windows the answer is null, which is the
  // common case and the whole point: disengagement no longer triggers a cue.
  const due = await studyGet("/api/study/cue/due");
  if (!due || due.due_slot == null) return;

  if (!canInject(url)) {
    // chrome://, the PDF viewer, the Web Store. Do NOT claim: claiming here
    // would burn the slot on a tab that cannot render it, and the
    // participant would be recorded as having received a cue they never saw.
    // The slot stays open for the rest of its grace window and the next tab
    // event retries.
    console.log("[moirai] slot", due.due_slot,
      "due but cannot inject into:", url || "(chrome page)");
    return;
  }

  const grant = await researchPost("/api/study/cue/claim", {
    state,
    claimed_by: "extension",
  });
  if (!grant || !grant.granted) {
    // Almost always means the app won the race, which is correct behaviour.
    console.log("[moirai] slot not granted:",
      grant ? grant.reason : "no response");
    return;
  }

  const asset = grant.asset || {};
  const imageUrl = asset.image_url || "";
  if (!imageUrl) {
    console.warn("[moirai] cue granted with no image");
    return;
  }

  // Prefer the prefetched cache so nothing has to load at trigger time; fall
  // back to the URL the grant carried.
  let dataUrl = null;
  try {
    const cached = await nextReminder();
    dataUrl = cached && cached.dataUrl ? cached.dataUrl : null;
  } catch (e) {
    console.warn("[moirai] cache read failed:", e.message);
  }
  if (!dataUrl) {
    dataUrl = imageUrl.startsWith("http") ? imageUrl : `${API_BASE}${imageUrl}`;
  }

  try {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: renderOverlay,
      args: [dataUrl, asset.cue || "", OVERLAY_DURATION_MS],
    });
    await chrome.storage.local.set({ activeDeliveryId: grant.delivery_id });
    await researchPost(`/api/study/cue/${grant.delivery_id}/shown`, {});
    console.log(`[moirai] ✅ scheduled cue slot ${grant.slot} shown ` +
      `(${grant.condition}, state=${state}) on:`, url);
  } catch (error) {
    console.error("[moirai] overlay failed:", error);
  }
}

// Overlay "return to study" button → focus the study tab + record the click.
chrome.runtime.onMessage.addListener((message) => {
  if (message && message.action === "RETURN_TO_STUDY") {
    (async () => {
      try {
        const { activeDeliveryId } = await getState("activeDeliveryId");
        if (activeDeliveryId) {
          await researchPost(
            `/api/study/cue/${activeDeliveryId}/interaction`,
            { clicked_return: true });
        }
        // Closing the episode is what resolves RETURN LATENCY server-side —
        // the primary measure for a cue delivered to someone already away.
        await closeEpisode("return");
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

// Every tab/window event does two things now: keep the disengagement log
// honest, and give a due cue another chance to land.
async function onAttentionChanged(tab, state = "off_tab") {
  if (!tab) return;
  if (!(await isStudyActive())) return;

  if (isAllowedMoirAI(tab.url || "")) {
    // Back on the study site — the absence is over.
    await closeEpisode("return");
    return;
  }
  await openEpisode("tab_switch");
  await maybeDeliverScheduledCue(tab, state);
}

async function checkActiveTab(state = "off_tab") {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  await onAttentionChanged(tabs[0], state);
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

  await onAttentionChanged(tab);
});

// Case 3: Chrome window focus. WINDOW_ID_NONE means Chrome itself lost focus
// — the participant is in another application entirely. That used to return
// early and record nothing, which made "watching a video in another app"
// indistinguishable from "reading attentively".
chrome.windows.onFocusChanged.addListener(async (windowId) => {
  if (windowId === chrome.windows.WINDOW_ID_NONE) {
    await checkActiveTab("off_browser");
    return;
  }
  await checkActiveTab();
});

// Case 4: the safety net. Tab events are plentiful, but a participant who
// opens one distractor tab and sits on it generates NONE — and that is
// exactly the person a scheduled cue exists for. The alarm guarantees the
// slot is checked even when nothing on screen changes.
//
// 30s is the MV3 floor, so a cue can be up to 30s late in the worst case.
// That is why every delivery records delivery_offset_ms: the timing is
// audited rather than assumed.
chrome.alarms.create("moirai-cue-check", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== "moirai-cue-check") return;
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
    // WIPE the previous participant's cached reminders first.
    //
    // chrome.storage.local survives logout, account switches and browser
    // restarts. Without this, a second participant on the same browser
    // inherits the first one's images — and if their own prefetch fails for
    // any reason, they are shown a stranger's future and it is recorded as
    // their own reminder. That is cross-participant contamination, not a
    // display glitch, and it has already happened during testing.
    chrome.storage.local.remove(
      ["reminderAssets", "reminderGeneric", "reminderRotation",
       "genericRotation", "genericRatio", "studyArm",
       "episodeOpen", "activeDeliveryId"],
      () => {
        chrome.storage.local.set(
          { eftAccessToken: token, eftConnectedAt: Date.now() },
          async () => {
            console.log("[moirai] connected — previous cache cleared");
            // Prefetch right away so the first overlay is instant.
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
      // A fresh session must not inherit the previous one's open
      // episode or delivery id, or the first return would close an
      // episode that belongs to another session.
      if (freshStart) {
        patch.episodeOpen = false;
        patch.activeDeliveryId = null;
      }
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
