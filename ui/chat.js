// The Social Chat panel. A sandboxed page: it talks to the mixer over the
// shell's postMessage bridge, and to the plugin only through tool.call, the
// same public method any client or agent uses.
//
// It asks the plugin for what changed once a second while it is on screen,
// and once every five seconds when the page is hidden. Each answer carries
// only the comments added or removed since the last one.

import { connectPanel } from "/client/sandbox-client.js";
import { tool, putOnAir, takeOff } from "./onair.js";
import { rowHtml, chipsHtml, problemsHtml, matches, esc } from "./render.js";
import { openSettings } from "./settings.js";

const $ = (id) => document.getElementById(id);
const MAX_SHOWN = 300;
const view = {
  comments: new Map(), order: [], seq: 0, epoch: "", statuses: [],
  filters: new Set(["youtube", "twitch", "facebook", "webhook", "x", "practice"]),
  known: new Set(), search: "", questionsOnly: false, showHidden: false, highlight: true,
  pinned: new Set(), pins: [], hidden: new Set(), banned: [], onairId: null, onair: null,
  pictures: new Map(), style: "card", dirty: true,
};
let client;
let stuck = true;

function absorb(answer) {
  if (answer.reset || answer.epoch !== view.epoch) {
    view.comments.clear();
    view.epoch = answer.epoch;
  }
  for (const c of answer.added || []) view.comments.set(c.id, c);
  for (const id of answer.removed || []) view.comments.delete(id);
  if ((answer.added || []).length || (answer.removed || []).length || answer.reset) view.dirty = true;
  view.seq = answer.seq;
  view.order = [...view.comments.values()].sort((a, b) => a.time - b.time || a.seq - b.seq);
  view.statuses = answer.statuses || [];
  for (const s of view.statuses) {
    if (!view.known.has(s.platform)) view.known.add(s.platform);
  }
  const m = answer.moderation || {};
  view.pins = m.pins || [];
  view.pinned = new Set(view.pins.map((p) => p.id));
  view.hidden = new Set(m.hidden || []);
  view.banned = m.banned || [];
  view.onair = answer.onair;
  view.onairId = answer.onair ? answer.onair.id : null;
  const sig = JSON.stringify([view.statuses, m.version, view.onairId]);
  if (sig !== view.sig) { view.sig = sig; view.dirty = true; }
  document.documentElement.style.setProperty("--question", answer.question_colour || "#f5b301");
  if (!view.styleTouched && answer.card_style) $("style").value = view.style = answer.card_style;
}

function paint() {
  $("chips").innerHTML = chipsHtml(view.statuses, view.filters);
  $("problems").innerHTML = problemsHtml(view.statuses);
  $("pins").innerHTML = view.pins.map((c) => rowHtml(c, view)).join("");
  const list = $("list");
  const shown = view.order.filter((c) => matches(c, view)).slice(-MAX_SHOWN);
  const atBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 40;
  list.innerHTML = shown.length ? shown.map((c) => rowHtml(c, view)).join("")
    : `<div class="empty">${view.order.length ? "No comment matches." : "No comments yet. They appear here as they arrive."}</div>`;
  if (stuck || atBottom) list.scrollTop = list.scrollHeight;
  $("more").hidden = stuck || atBottom;
  const bar = $("onair");
  bar.classList.toggle("live", !!view.onair);
  $("onair-text").textContent = view.onair ? `${view.onair.comment.author}: ${view.onair.comment.text}` : "Nothing on air";
  $("off").disabled = !view.onair;
  view.dirty = false;
}

async function fetchPictures() {
  const wanted = [];
  for (const c of view.order.slice(-MAX_SHOWN).concat(view.pins)) {
    if (c.avatar && !view.pictures.has(c.avatar) && wanted.length < 40) wanted.push(c.avatar);
  }
  if (!wanted.length) return;
  for (const url of wanted) view.pictures.set(url, "");
  const got = await tool(client, "avatars", { urls: wanted }).catch(() => ({ avatars: {} }));
  for (const [url, data] of Object.entries(got.avatars || {})) view.pictures.set(url, data);
  view.dirty = true;
}

// A long poll: the plugin holds the call for up to three seconds when nothing
// has changed, so a quiet chat costs one call every three seconds. After an
// answer that did carry comments the next call waits a second and a half, so
// a busy chat arrives in batches rather than as a call a second. Each call is
// a line in the mixer's session log, which is why this is not faster.
async function poll() {
  let pause = 1500;
  try {
    const before = view.seq;
    absorb(await tool(client, "comments", { after: view.seq, epoch: view.epoch, wait_ms: 3000 }));
    if (view.down) { view.down = false; notice(""); }
    if (view.seq === before) pause = 0;
    fetchPictures();
  } catch (e) {
    view.down = true;
    pause = 3000;
    notice(`<div class="problem"><b>The plugin is not answering</b>${esc(e.message || e)} <span class="next">Check that social-chat is running in Plugins; this retries by itself.</span></div>`, true);
  }
  if (view.dirty) paint();
  setTimeout(poll, document.hidden ? 5000 : pause);
}

let noticeTimer;
function notice(html, keep) {
  $("notice").innerHTML = html;
  clearTimeout(noticeTimer);
  if (!keep) noticeTimer = setTimeout(() => { $("notice").innerHTML = ""; }, 6000);
}

function find(id) {
  return view.comments.get(id) || view.pins.find((p) => p.id === id);
}

async function act(what, id) {
  const c = find(id);
  try {
    if (what === "air") await putOnAir(client, id, view.style);
    if (what === "pin") await tool(client, "pin", { id, pinned: !view.pinned.has(id) });
    if (what === "hide") await tool(client, "hide", { id, hidden: !view.hidden.has(id) });
    if (what === "ban" && c) {
      // A sandboxed page may not open confirm(), so a ban takes two clicks.
      if (view.banArmed !== id) {
        view.banArmed = id;
        notice(`<div class="problem waiting"><b>Ban ${esc(c.author)}?</b>Press Ban again within five seconds. Their comments leave this list; the platform is not told.</div>`);
        setTimeout(() => { if (view.banArmed === id) { view.banArmed = null; view.dirty = true; } }, 5000);
        return;
      }
      view.banArmed = null;
      await tool(client, "ban", { id, banned: true });
    }
  } catch (e) {
    notice(`<div class="problem"><b>That did not work</b>${esc(e.message || e)}</div>`);
    return;
  }
  view.dirty = true;
}

function wire() {
  for (const box of [$("list"), $("pins")]) {
    box.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-act]");
      const row = e.target.closest(".row");
      if (b && row) act(b.dataset.act, row.dataset.id);
    });
  }
  $("list").addEventListener("scroll", () => {
    const l = $("list");
    stuck = l.scrollHeight - l.scrollTop - l.clientHeight < 40;
    $("more").hidden = stuck;
  });
  $("more").onclick = () => { stuck = true; paint(); };
  $("chips").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip[data-platform]");
    if (!chip) return;
    const p = chip.dataset.platform;
    view.filters.has(p) ? view.filters.delete(p) : view.filters.add(p);
    paint();
  });
  $("search").addEventListener("input", (e) => { view.search = e.target.value.trim().toLowerCase(); paint(); });
  $("questions").onclick = () => { view.questionsOnly = !view.questionsOnly; $("questions").classList.toggle("on", view.questionsOnly); paint(); };
  $("style").onchange = (e) => { view.style = e.target.value; view.styleTouched = true; };
  $("off").onclick = async () => {
    try { await takeOff(client); } catch (e) { notice(`<div class="problem"><b>Could not take it off</b>${esc(e.message || e)}</div>`); }
  };
  $("gear").onclick = () => openSettings(client, $("settings"), view);
}

async function boot() {
  client = await connectPanel();
  if (client.resize) client.resize(560);
  wire();
  poll();
}

boot();
