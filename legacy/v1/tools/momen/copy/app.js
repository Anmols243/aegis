/* AEGIS dashboard — standalone copy of the Momen-built frontend.
   Wired to the live API; seed data only as offline fallback. */
"use strict";

const API = new URLSearchParams(location.search).get("api") || "https://aegis-live.loca.lt";
const TOKEN = new URLSearchParams(location.search).get("token") ||
  "GOUXxJgSnkFgj59Qzfrgpr2pS90D9CW7";
const INBOX = "zesty-willow-3025@homingbox.net";
const SCAM_LINE = 0.70;

/* ---------------- offline seed (Momen literals, verbatim) ---------------- */
const SEED_VERDICTS = [
  {
    email_id: "live-demo-phish-001", label: "SCAM", score: 0.748, confidence: 0.41,
    sender: "security@paypa1-secure.com", received_at: "2026-10-05T08:10:00+00:00",
    body_preview: "Dear Customer,\n\nWe detected unusual activity on your PayPal account.\nVerify now: http://paypa1-secure.com/verify?session=8f3k2\n\nyour account will be suspended within 24 hours",
    red_flags: [
      {title: "Lookalike domain paypa1-secure.com \u2014 digit '1' for 'l'",
       evidence: "http://paypa1-secure.com/verify?session=8f3k2", severity: "high"},
      {title: "Urgency language threatening suspension",
       evidence: "\u201cyour account will be suspended within 24 hours\u201d", severity: "medium"}
    ],
    det_signals: [
      {name: "punycode / homoglyph domain", severity: "critical"},
      {name: "sender/link domain mismatch", severity: "high"}
    ],
    signals: {"forensic": 0.97, "sandbox": 0.30, "phishing-intel": 0.92},
    contributions: {"forensic": 0.42, "phishing-intel": 0.31, "vision": 0.15, "sandbox": 0.12},
    dissent: ["agents disagree: forensic=0.97 vs sandbox=0.30"],
    timings: {"triage": 0.4, "forensic": 6.2, "vision": 3.1, "sandbox": 9.8},
    campaign_note: "Part of a 16-email campaign sharing infrastructure."
  },
  {
    email_id: "live-test-newsletter-001", label: "LIKELY_SAFE", score: 0.137,
    confidence: 0.76, sender: "[email]",
    received_at: "2026-10-05T07:55:00+00:00",
    body_preview: "From: [email]\nSubject: PyWeekly #812\n\nThis week's highlights from the Python world.",
    red_flags: [], det_signals: [],
    signals: {"forensic": 0.01, "sandbox": 0.13},
    contributions: {"forensic": 0.5, "sandbox": 0.5},
    dissent: [], timings: {"triage": 0.2, "forensic": 1.1},
    campaign_note: ""
  }
];
const SEED_CAMPAIGNS = [{
  n_emails: 17,
  emails: ["live-demo-phish-001"],
  infra: ["domain:paypa1-secure.com", "domain:paypa1-secure.xyz",
          "url:http://paypa1-secure.com/verify", "url:http://paypa1-secure.xyz/login",
          "tpl:a91f", "tpl:3c0e", "tpl:77b2", "tpl:f00d"]
}];
const SEED_REDTEAM = {
  fixtures: 5, caught: 0, missed: 5, fixed: 0, open: 5,
  by_axis: {"fresh-lookalike-domain": {total: 1, missed: 1},
            "restructured": {total: 2, missed: 2},
            "homoglyph-brand": {total: 2, missed: 2},
            "rephrased-urgency": {total: 2, missed: 2},
            "tld-swap": {total: 2, missed: 2},
            "rephrased-lure": {total: 2, missed: 2}},
  cases: [
    {id: "rt-20261004-001", actual_label: "SUSPICIOUS", score: 0.691,
     mutation_axes: ["fresh-lookalike-domain", "restructured"]},
    {id: "rt-20261004-002", actual_label: "SUSPICIOUS", score: 0.691,
     mutation_axes: ["homoglyph-brand", "rephrased-urgency"]},
    {id: "rt-20261004-003", actual_label: "SUSPICIOUS", score: 0.688,
     mutation_axes: ["tld-swap", "rephrased-lure"]},
    {id: "rt-20261004-004", actual_label: "SUSPICIOUS", score: 0.691,
     mutation_axes: ["homoglyph-brand", "tld-swap", "rephrased-urgency"]},
    {id: "rt-20261004-005", actual_label: "SUSPICIOUS", score: 0.691,
     mutation_axes: ["rephrased-lure", "restructured"]}
  ]
};

/* ---------------- state ---------------- */
const state = {
  verdicts: [], stats: null, campaigns: [], redteam: null,
  filter: "ALL", query: "", selectedId: null, online: true,
  techOpen: false
};

/* ---------------- helpers ---------------- */
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;");

function parseMaybe(v) {
  if (typeof v === "string") {
    try { const p = JSON.parse(v); return p; } catch (e) { return v; }
  }
  return v == null ? [] : v;
}
const asArr = v => Array.isArray(parseMaybe(v)) ? parseMaybe(v) : [];
const asObj = v => { const p = parseMaybe(v); return (p && typeof p === "object" && !Array.isArray(p)) ? p : {}; };

function subjectOf(v) {
  const bp = String(v.body_preview || "");
  const skip = /^(dear\b|hi\b|hello\b|hey\b|from:|to:|date:)/i;
  for (const line of bp.split("\n")) {
    const t = line.trim().replace(/^(subject:\s*)/i, "");
    if (t.length < 8 || skip.test(t)) continue;
    return t.slice(0, 120);
  }
  // fall back to first non-trivial line
  for (const line of bp.split("\n")) {
    const t = line.trim();
    if (t.length > 4) return t.slice(0, 120);
  }
  return v.email_id;
}
function relTime(iso) {
  const d = new Date(iso), now = Date.now();
  const s = Math.max(1, Math.round((now - d) / 1000));
  if (s < 60) return s + "s ago";
  if (s < 3600) return Math.round(s / 60) + "m ago";
  if (s < 86400) return Math.round(s / 3600) + "h ago";
  return Math.round(s / 86400) + "d ago";
}
function confWord(c) { return c >= 0.7 ? "High" : c >= 0.4 ? "Medium" : "Low"; }
function verdictSentence(l) {
  return l === "SCAM" ? "This email is a scam."
    : l === "SUSPICIOUS" ? "This one is suspicious \u2014 treat it carefully."
    : "This email looks legitimate.";
}
function explainOf(v) {
  const flags = asArr(v.red_flags);
  if (flags.length && flags[0].title) return flags[0].title + ".";
  if (v.label === "LIKELY_SAFE") return "No warning signs found; agent votes stayed near zero.";
  return "Evidence is summarized in the red flags below.";
}

/* ---------------- API ---------------- */
async function get(path) {
  const r = await fetch(API + path + (path.includes("?") ? "&" : "?") + "token=" + TOKEN);
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}

async function refresh() {
  try {
    const [stats, vdata] = await Promise.all([
      get("/api/stats"), get("/api/verdicts?limit=50")
    ]);
    let campaigns = [], redteam = null;
    try { campaigns = await get("/api/campaigns"); } catch (e) {}
    try { redteam = await get("/api/redteam"); } catch (e) {}
    state.online = true;
    state.stats = stats;
    state.verdicts = Array.isArray(vdata) ? vdata : (vdata.verdicts || []);
    state.campaigns = Array.isArray(campaigns) ? campaigns : (campaigns.campaigns || []);
    state.redteam = redteam;
  } catch (e) {
    state.online = false;
    state.stats = null;
    state.verdicts = SEED_VERDICTS;
    state.campaigns = SEED_CAMPAIGNS;
    state.redteam = SEED_REDTEAM;
  }
  // keep selection valid
  const ids = new Set(state.verdicts.map(v => v.email_id));
  if (!state.selectedId || !ids.has(state.selectedId)) {
    const vis = visibleVerdicts();
    state.selectedId = vis.length ? vis[0].email_id : (state.verdicts[0] || {}).email_id || null;
  }
  render();
}

/* ---------------- rendering ---------------- */
function visibleVerdicts() {
  const q = state.query.trim().toLowerCase();
  return state.verdicts.filter(v => {
    if (state.filter !== "ALL" && v.label !== state.filter) return false;
    if (!q) return true;
    return (v.sender + " " + subjectOf(v) + " " + v.email_id).toLowerCase().includes(q);
  });
}

function stamp(label, flagged) {
  const t = flagged && label === "SUSPICIOUS" ? "FLAGGED \u00b7 SUSPICIOUS" : label.replace("_", " ");
  return `<span class="stamp ${esc(label)}">${esc(t)}</span>`;
}

function renderStats() {
  const s = state.stats, vs = state.verdicts;
  const total = s ? s.total : vs.length;
  const by = s ? s.by_label || {} : {};
  const n = l => by[l] != null ? by[l] : vs.filter(v => v.label === l).length;
  countUp($("stTotal"), total); countUp($("stScam"), n("SCAM"));
  countUp($("stSusp"), n("SUSPICIOUS")); countUp($("stSafe"), n("LIKELY_SAFE"));
  $("stTotalNote").textContent = state.online ? "live feed" : "cached verdicts";
}
function countUp(el, to) {
  const from = parseInt(el.dataset.v || "0", 10);
  el.dataset.v = to;
  if (from === to) { el.textContent = String(to).padStart(2, "0"); return; }
  const t0 = performance.now(), dur = 600;
  (function tick(t) {
    const p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 3);
    el.textContent = String(Math.round(from + (to - from) * e)).padStart(2, "0");
    if (p < 1) requestAnimationFrame(tick);
  })(t0);
}

function renderList() {
  const vis = visibleVerdicts();
  const box = $("rows");
  if (!vis.length) { box.innerHTML = `<div class="empty">No emails match this filter.</div>`; }
  else box.innerHTML = vis.map(v => `
    <button class="mrow ${v.email_id === state.selectedId ? "sel" : ""}" data-id="${esc(v.email_id)}">
      <span class="r1">${stamp(v.label)}<span class="subj">${esc(subjectOf(v))}</span></span>
      <span class="r2"><span class="meta">${esc(v.sender || "unknown sender")} &middot; ${esc(relTime(v.received_at))}</span>
      <span class="score ${esc(v.label)}">${Number(v.score).toFixed(3)}</span></span>
    </button>`).join("");
  $("mailcount").textContent = String(vis.length).padStart(2, "0") + " SHOWN";
  box.querySelectorAll(".mrow").forEach(b =>
    b.addEventListener("click", () => { state.selectedId = b.dataset.id; state.techOpen = false; renderList(); renderReader(); }));
}

function renderReader() {
  const v = state.verdicts.find(x => x.email_id === state.selectedId) || state.verdicts[0];
  const el = $("reader");
  if (!v) { el.innerHTML = `<div class="empty">No verdict selected.</div>`; return; }
  const flags = asArr(v.red_flags), sigs = asArr(v.det_signals),
        votes = asObj(v.signals), contrib = asObj(v.contributions),
        dissent = asArr(v.dissent), timings = asObj(v.timings);
  const totalT = Object.values(timings).reduce((a, b) => a + (+b || 0), 0);
  const agree = dissent.length ? "Disagreed" : "Agreed";

  const voteBars = Object.entries(votes)
    .filter(([, val]) => typeof val === "number" && isFinite(val))
    .map(([k, val]) => {
    const p = Math.round(val * 100);
    const col = val >= 0.7 ? "var(--scam)" : val >= 0.4 ? "var(--susp)" : "var(--safe)";
    return `<div class="votebar"><span class="vn">${esc(k)}</span><span class="vt"><span class="vf" style="width:${p}%;background:${col}"></span></span><span class="vv">${val.toFixed(2)}</span></div>`;
  }).join("");
  const contribBars = Object.entries(contrib)
    .filter(([, val]) => typeof val === "number" && isFinite(val))
    .map(([k, val]) => {
    const p = Math.round(val * 100);
    return `<div class="votebar"><span class="vn">${esc(k)}</span><span class="vt"><span class="vf" style="width:${p}%;background:var(--lime)"></span></span><span class="vv">${val.toFixed(2)}</span></div>`;
  }).join("");
  const sigLine = sigs.length
    ? `<div class="t-line"><b>DETERMINISTIC SIGNALS</b> &middot; ${sigs.map(s => `${esc(s.name || s)}${s.severity ? " \u2014 " + esc(String(s.severity).toUpperCase()) : ""}`).join(" &nbsp;&middot;&nbsp; ")}</div>` : "";
  const timeLine = Object.keys(timings).length
    ? `<div class="t-line"><b>TIMINGS</b> &middot; ${Object.entries(timings).map(([k, x]) => `${esc(k)} ${x}s`).join(" &nbsp;&middot;&nbsp; ")}</div>` : "";

  el.innerHTML = `
    ${stamp(v.label)}
    <div class="r-subject">${esc(subjectOf(v))}</div>
    <div class="r-meta">${esc(v.sender || "unknown sender")} &nbsp;&middot;&nbsp; ${esc(v.email_id)}</div>
    <div class="riskcard">
      <div><div class="riskval">${Number(v.score).toFixed(3)}</div>
      <div class="risklab">RISK SCORE</div></div>
      <div class="riskth">SCAM line &middot; ${SCAM_LINE.toFixed(2)}</div>
    </div>
    <div class="facts">
      <div class="fact"><div class="f-label">CONFIDENCE</div><div class="f-value">${confWord(v.confidence)} &middot; ${Math.round(v.confidence * 100)}%</div></div>
      <div class="fact"><div class="f-label">AGENT AGREEMENT</div><div class="f-value">${agree}</div></div>
      <div class="fact"><div class="f-label">ANALYSIS TIME</div><div class="f-value">${totalT ? totalT.toFixed(1) + "s" : "\u2014"}</div></div>
      <div class="fact"><div class="f-label">WARNING SIGNS</div><div class="f-value">${String(flags.length).padStart(2, "0")}</div></div>
    </div>
    <div class="r-verdict">${verdictSentence(v.label)}</div>
    <div class="r-explain">${esc(explainOf(v))}</div>
    ${flags.length ? `<div class="r-h">RED FLAGS</div>` + flags.map(f => `
      <div class="flag"><div class="f-t">${esc(f.title || "")}</div>
      ${f.evidence ? `<div class="f-e">${esc(f.evidence)}</div>` : ""}</div>`).join("") : ""}
    ${dissent.length ? `<div class="dissent"><div class="d-l">AGENT DISSENT</div>
      ${dissent.map(d => `<div class="d-d">${esc(typeof d === "string" ? d : JSON.stringify(d))}</div>`).join("")}</div>` : ""}
    ${v.campaign_note ? `<button class="campbtn" id="campbtn">View linked campaign &middot; ${esc(String(v.campaign_note).replace(/^Part of a /i, ""))}</button>` : ""}
    <div class="tech ${state.techOpen ? "open" : ""}" id="tech">
      <button class="tech-toggle" id="techToggle"><span class="car">\u25b8</span> TECHNICAL DETAILS</button>
      <div class="tech-body">
        ${sigLine}
        ${voteBars ? `<div class="t-line"><b>AGENT VOTES</b></div>${voteBars}` : ""}
        ${contribBars ? `<div class="t-line"><b>WHAT WEIGHED MOST</b></div>${contribBars}` : ""}
        ${timeLine}
      </div>
    </div>`;
  $("techToggle").addEventListener("click", () => { state.techOpen = !state.techOpen; $("tech").classList.toggle("open", state.techOpen); });
  const cb = $("campbtn");
  if (cb) cb.addEventListener("click", () => $("campaigns").scrollIntoView({behavior: "smooth"}));
}

/* ---------------- campaigns ---------------- */
const INFRA_LABELS = {domain: "DOMAIN", url: "URL", sender: "SENDER", phone: "PHONE", ip: "IP"};

function renderCampaigns() {
  const box = $("campaignCards");
  if (!state.campaigns.length) {
    box.innerHTML = `<p class="explainer" style="margin-top:6px">No campaigns detected yet.</p>`;
    return;
  }
  box.innerHTML = state.campaigns.map((c, ci) => {
    const infra = asArr(c.infra);
    const groups = {};
    const tpl = [];
    infra.forEach(x => {
      const s = String(x), i = s.indexOf(":");
      const k = i > 0 ? s.slice(0, i) : "?", val = i > 0 ? s.slice(i + 1) : s;
      if (k === "tpl") tpl.push(val); else (groups[k] = groups[k] || []).push(val);
    });
    const chips = Object.entries(groups).map(([k, vals]) =>
      vals.map(val => `<span class="ichip"><b>${INFRA_LABELS[k] || k.toUpperCase()}</b>${esc(val.length > 42 ? val.slice(0, 42) + "\u2026" : val)}</span>`).join("")
    ).join("");
    const emails = asArr(c.emails).slice(0, 4).map(e => {
      const v = typeof e === "string"
        ? state.verdicts.find(x => x.email_id === e) : e;
      if (!v) return "";
      return `<button class="c-row" data-id="${esc(v.email_id)}">
        ${stamp(v.label)}<span class="cs">${esc(subjectOf(v))}</span>
        <span class="cv">${Number(v.score).toFixed(3)}</span></button>`;
    }).join("");
    const nE = c.n_emails || asArr(c.emails).length;
    const nScam = asArr(c.emails).filter(e => {
      const v = typeof e === "string" ? state.verdicts.find(x => x.email_id === e) : e;
      return v && v.label === "SCAM";
    }).length;
    const doms = (groups.domain || []);
    const why = doms.length
      ? `These emails share the domain${doms.length > 1 ? "s" : ""} ${doms.slice(0, 2).map(esc).join(", ")}${doms.length > 2 ? ` (+${doms.length - 2} more)` : ""}${(groups.url || []).length ? `, ${(groups.url || []).length} URL${(groups.url || []).length > 1 ? "s" : ""}` : ""} \u2014 that is the fingerprint tying ${nE} email${nE === 1 ? "" : "s"} into one operation.`
      : `Shared infrastructure across ${nE} email${nE === 1 ? "" : "s"} links this campaign.`;
    return `<div class="ccard">
      <h3>Campaign ${ci + 1}</h3>
      <div class="c-counts">${nE} emails${nScam ? ` &middot; ${nScam} scam` : ""}</div>
      <div class="why"><div class="w-l">WHY THESE ARE LINKED</div><div class="w-n">${why}</div></div>
      <div class="infra-label">SHARED INFRASTRUCTURE</div>
      <div class="chipsrow">${chips}
        ${tpl.length ? `<button class="ichip ghost" data-tpl="${ci}">+${tpl.length} technical fingerprints</button>
        <span class="ichip ghost" id="tpl${ci}" style="display:none">${tpl.map(esc).join(" &middot; ")}</span>` : ""}
      </div>
      ${emails ? `<div class="c-emails-label">EMAILS IN THIS CAMPAIGN &middot; ${Math.min(4, asArr(c.emails).length)} SHOWN</div>${emails}` : ""}
    </div>`;
  }).join("");
  box.querySelectorAll(".c-row").forEach(b => b.addEventListener("click", () => {
    state.selectedId = b.dataset.id; state.techOpen = false;
    renderList(); renderReader();
    $("feed").scrollIntoView({behavior: "smooth"});
  }));
  box.querySelectorAll("[data-tpl]").forEach(b => b.addEventListener("click", () => {
    const t = $("tpl" + b.dataset.tpl);
    t.style.display = t.style.display === "none" ? "inline-block" : "none";
  }));
}

/* ---------------- red team ---------------- */
function renderRedteam() {
  const rt = state.redteam;
  if (!rt) { $("redstats").innerHTML = ""; $("honesty").textContent = ""; $("axes").textContent = ""; $("redcases").innerHTML = ""; return; }
  const cell = (l, v) => `<div class="rstat"><div class="rl">${l}</div><div class="rv">${String(v).padStart(2, "0")}</div></div>`;
  $("redstats").innerHTML =
    cell("VARIANTS", rt.fixtures) + cell("CAUGHT", rt.caught) + cell("MISSED", rt.missed) +
    cell("FIXED", rt.fixed) + cell("OPEN", rt.open);
  const cases = asArr(rt.cases);
  const susp = cases.filter(c => c.actual_label === "SUSPICIOUS");
  $("honesty").textContent = rt.missed > 0
    ? `${rt.missed} of ${rt.fixtures} fixtures missed the ${SCAM_LINE.toFixed(2)} SCAM bar and count as regression misses${susp.length ? ` \u2014 but all ${susp.length} were still flagged SUSPICIOUS, just under the line` : ""}.`
    : `${rt.caught} of ${rt.fixtures} variants caught at the SCAM bar.`;
  const byAxis = asObj(rt.by_axis);
  $("axes").textContent = Object.keys(byAxis).length
    ? "MISSES BY AXIS \u00b7 " + Object.entries(byAxis)
        .map(([k, v]) => `${k} ${String((v.missed != null ? v.missed : v.total) || 0).padStart(2, "0")}`).join(" \u00b7 ")
    : "";
  $("redcases").innerHTML = cases.map(c => `
    <div class="case">
      <span class="cid">${esc(c.id)}</span>
      <span class="cax">${asArr(c.mutation_axes).map(esc).join(" \u00b7 ")}</span>
      <span class="csc">${Number(c.score).toFixed(3)}</span>
      ${stamp(c.actual_label, true)}
    </div>`).join("");
}

/* ---------------- chrome ---------------- */
function renderChrome() {
  const b = $("livebadge");
  b.classList.toggle("off", !state.online);
  $("liveText").textContent = state.online ? "LIVE" : "OFFLINE \u2014 CACHED";
  $("refreshed").innerHTML = "LAST REFRESH &nbsp;&middot;&nbsp; " +
    (state.online ? new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit"}) : "CACHED SEED");
}

function render() { renderChrome(); renderStats(); renderList(); renderReader(); renderCampaigns(); renderRedteam(); }

/* ---------------- background paths (borrowed from live.html) ---------------- */
const bgPaths = (() => {
  const nodes = Array.from(document.querySelectorAll(".bgpaths path"));
  const P = nodes.map(p => ({
    el: p, dur: parseFloat(p.dataset.dur) || 16,
    o0: parseFloat(p.dataset.o0) || 0.06, o1: parseFloat(p.dataset.o1) || 0.14,
    ph: Math.random()
  }));
  let raf = null;
  const t0 = performance.now();
  function frame(now) {
    const t = (now - t0) / 1000;
    for (const x of P) {
      x.el.setAttribute("stroke-dashoffset", (-((t / x.dur) % 1)).toFixed(4));
      const b = 0.5 - 0.5 * Math.cos(2 * Math.PI * (t / (x.dur * 0.6) + x.ph));
      x.el.setAttribute("opacity", (x.o0 + (x.o1 - x.o0) * b).toFixed(3));
    }
    raf = requestAnimationFrame(frame);
  }
  function renderStatic() {
    P.forEach((x, i) => {
      x.el.setAttribute("stroke-dashoffset", (-(i / P.length)).toFixed(3));
      x.el.setAttribute("opacity", x.o0.toFixed(3));
    });
  }
  function motionWanted() {
    const ov = localStorage.getItem("aegis-motion");
    if (ov === "on") return true;
    if (ov === "off") return false;
    return !matchMedia("(prefers-reduced-motion: reduce)").matches;
  }
  function apply() {
    const btn = $("motionbtn"), on = motionWanted();
    if (btn) btn.classList.toggle("on", on);
    if (on && raf === null && P.length) raf = requestAnimationFrame(frame);
    if (!on) { if (raf !== null) { cancelAnimationFrame(raf); raf = null; } renderStatic(); }
  }
  const btn = $("motionbtn");
  if (btn) btn.addEventListener("click", () => {
    localStorage.setItem("aegis-motion",
      localStorage.getItem("aegis-motion") === "on" ? "off" : "on");
    apply();
  });
  apply();
  return {apply};
})();

/* ---------------- wiring ---------------- */
document.querySelectorAll(".railbtn").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll(".railbtn").forEach(x => x.classList.remove("active"));
  b.classList.add("active");
  $(b.dataset.target).scrollIntoView({behavior: "smooth"});
}));
document.querySelectorAll("#chips .chip").forEach(ch => ch.addEventListener("click", () => {
  document.querySelectorAll("#chips .chip").forEach(x => x.classList.remove("active"));
  ch.classList.add("active");
  state.filter = ch.dataset.f; state.techOpen = false;
  const vis = visibleVerdicts();
  state.selectedId = vis.length ? vis[0].email_id : state.selectedId;
  renderList(); renderReader();
}));
let searchT = null;
$("search").addEventListener("input", e => {
  clearTimeout(searchT);
  searchT = setTimeout(() => {
    state.query = e.target.value;
    const vis = visibleVerdicts();
    if (!vis.some(v => v.email_id === state.selectedId))
      state.selectedId = vis.length ? vis[0].email_id : state.selectedId;
    renderList(); renderReader();
  }, 180);
});
document.addEventListener("keydown", e => {
  if (e.key === "/" && document.activeElement !== $("search")) { e.preventDefault(); $("search").focus(); }
  if (e.key === "Escape" && document.activeElement === $("search")) { $("search").value = ""; state.query = ""; renderList(); renderReader(); }
});
$("copyInbox").addEventListener("click", async () => {
  try { await navigator.clipboard.writeText(INBOX); $("copyInbox").textContent = "COPIED \u2713"; }
  catch (e) { $("copyInbox").textContent = INBOX; }
  setTimeout(() => $("copyInbox").textContent = "COPY INBOX ADDRESS", 1800);
});

/* ---------------- boot ---------------- */
refresh();
setInterval(refresh, 10000);
