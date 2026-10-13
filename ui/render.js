// Drawing the list, the pins, the platform chips and the problems. Pure
// functions from the panel's state to HTML strings; chat.js owns the state.

import { icon, COLOURS } from "./icons.js";

export const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const STATE_WORDS = {
  connected: "connected", connecting: "connecting", waiting: "waiting",
  failing: "not connected", unavailable: "not available", off: "off",
};

function clock(ms) {
  const d = new Date(ms);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function initials(name) {
  const parts = String(name || "?").split(/[\s_.\-]+/).filter(Boolean);
  return (parts.slice(0, 2).map((p) => p[0]).join("") || "?").toUpperCase();
}

export function avatarHtml(c, pictures) {
  const pic = c.avatar && pictures.get(c.avatar);
  const colour = c.colour || COLOURS[c.platform] || "#64748b";
  const face = pic ? `<img alt="" src="${esc(pic)}">` : esc(initials(c.author));
  return `<div class="avatar" style="background:${esc(colour)}">${face}${icon(c.platform, "badge")}</div>`;
}

function tags(c) {
  let out = "";
  if (c.amount) out += `<span class="tag money">${esc(c.amount)}</span>`;
  if (c.kind === "member") out += `<span class="tag">member</span>`;
  for (const b of c.badges || []) if (b === "owner" || b === "moderator") out += `<span class="tag">${esc(b)}</span>`;
  if (c.question) out += `<span class="tag q">?</span>`;
  return out;
}

export function rowHtml(c, view) {
  const classes = ["row"];
  if (c.question && view.highlight) classes.push("question");
  if (view.onairId === c.id) classes.push("onair");
  if (view.hidden.has(c.id)) classes.push("hidden-c");
  const pinned = view.pinned.has(c.id);
  const authorColour = c.platform === "twitch" && c.colour ? ` style="color:${esc(c.colour)}"` : "";
  return `<div class="${classes.join(" ")}" data-id="${esc(c.id)}" tabindex="0">
    ${avatarHtml(c, view.pictures)}
    <div class="meta"><span class="author"${authorColour}>${esc(c.author)}</span>${tags(c)}<span class="when">${clock(c.time)}</span></div>
    <div class="text">${esc(c.text)}</div>
    <div class="actions">
      <button class="air" data-act="air" title="Put this comment on air">On air</button>
      <button data-act="pin" title="${pinned ? "Unpin" : "Pin to the top"}">${pinned ? "Unpin" : "Pin"}</button>
      <button data-act="hide" title="Hide this comment here">${view.hidden.has(c.id) ? "Show" : "Hide"}</button>
      <button data-act="ban" title="Hide everything this person writes, in this mixer only">Ban</button>
    </div>
  </div>`;
}

export function chipsHtml(statuses, filters) {
  return statuses
    .filter((s) => s.state !== "off" || s.count > 0)
    .map((s) => `<span class="chip ${filters.has(s.platform) ? "" : "muted"}" data-platform="${esc(s.platform)}"
        title="${esc(s.title)}: ${esc(STATE_WORDS[s.state] || s.state)}. ${esc(s.detail)}${s.next ? " " + esc(s.next) : ""} Click to show or hide its comments.">
        ${icon(s.platform)}<span class="dot ${esc(s.state)}"></span>${esc(s.count || 0)}</span>`)
    .join("") || `<span class="chip muted">No platform set up yet. Open Settings.</span>`;
}

export function problemsHtml(statuses) {
  return statuses
    .filter((s) => ["failing", "unavailable", "waiting"].includes(s.state))
    .map((s) => `<div class="problem ${esc(s.state)}"><b>${esc(s.title)}: ${esc(STATE_WORDS[s.state])}</b>
       ${esc(s.detail)}. <span class="next">${esc(s.next)}</span></div>`)
    .join("");
}

export function matches(c, view) {
  if (!view.filters.has(c.platform) && !(c.practice && view.filters.has("practice"))) return false;
  if (view.questionsOnly && !c.question) return false;
  if (view.hidden.has(c.id) && !view.showHidden) return false;
  if (view.search) {
    const hay = (c.author + " " + c.text).toLowerCase();
    if (!hay.includes(view.search)) return false;
  }
  return true;
}
