// The Settings view: where each platform's channel, address and key go.
// Saved through the plugin's save_settings tool, which applies at once and
// reconnects only the platforms whose settings changed. A key or token is
// never sent back here: the field stays empty and says what is stored.

import { tool } from "./onair.js";
import { icon } from "./icons.js";
import { esc } from "./render.js";
import { seal } from "./seal.js";

const GROUPS = [
  ["youtube", "YouTube", [
    ["youtube_video", "text", "Stream address, video id or @handle", "A stream address costs 1 quota unit to look up; a channel costs 100."],
    ["youtube_api_key", "secret", "API key", "From a Google Cloud project with the YouTube Data API v3 on. The README says how."],
    ["youtube_oauth_token", "secret", "OAuth access token (optional)", "Only for a private stream, or to find your own stream without its address."],
    ["youtube_min_poll_seconds", "number", "Read the chat no faster than every (seconds)", "Each read costs 5 of the 10,000 units a day: 5 s lasts about 2.8 hours."],
    ["youtube_client_id", "text", "OAuth client id (optional)", ""],
    ["youtube_client_secret", "secret", "OAuth client secret (optional)", ""],
    ["youtube_refresh_token", "secret", "OAuth refresh token (optional)", "With the two above, the plugin renews the access token itself."],
  ]],
  ["twitch", "Twitch", [
    ["twitch_channels", "text", "Channel names, separated by commas", "Read anonymously. No account or key is needed."],
  ]],
  ["facebook", "Facebook", [
    ["facebook_page_token", "secret", "Page access token", "From the Page that is live, with pages_read_engagement and pages_read_user_content."],
    ["facebook_live_video", "text", "Live video address (optional)", "Leave empty to use whatever the Page is streaming now."],
    ["facebook_mode", ["stream", "poll"], "Connection", "stream is one connection Facebook pushes to; it falls back to poll by itself."],
    ["facebook_poll_seconds", "number", "Poll every (seconds)", ""],
  ]],
  ["webhook", "Webhook", [
    ["webhook_enabled", "bool", "Accept comments POSTed as JSON", ""],
    ["webhook_bind", "text", "Listen on address", "127.0.0.1 is this machine only. Set a secret before opening it to the network."],
    ["webhook_port", "number", "Port", ""],
    ["webhook_secret", "secret", "Secret (optional)", "Sent by the poster in the X-Social-Chat-Secret header."],
  ]],
  ["x", "X", [
    ["x_enabled", "bool", "Show X in the list of platforms", "X's API is paid, so this is a stub that says so. Send X replies in through the webhook."],
  ]],
  ["practice", "Practice", [
    ["practice_mode", "bool", "Send made up comments for a rehearsal", "Every name is invented. Turn it off before the show."],
  ]],
  ["display", "On air and display", [
    ["card_style", ["card", "strap"], "On air style", "card: picture, name and three lines. strap: a one line lower third."],
    ["question_colour", "color", "Question colour", ""],
    ["keep", "number", "Comments kept in the list", ""],
  ]],
];

function field([key, type, label, hint], values) {
  const v = values[key];
  let input;
  if (type === "bool") {
    input = `<label class="check"><input type="checkbox" name="${key}" ${v ? "checked" : ""}> ${esc(label)}</label>`;
    return input + (hint ? `<div class="hint">${esc(hint)}</div>` : "");
  }
  if (Array.isArray(type)) {
    input = `<select name="${key}">${type.map((o) => `<option ${o === v ? "selected" : ""}>${o}</option>`).join("")}</select>`;
  } else if (type === "secret") {
    const stored = v ? esc(v) : "nothing stored";
    input = `<input type="password" name="${key}" placeholder="${stored}" autocomplete="off">`;
  } else {
    const kind = type === "number" ? "number" : type === "color" ? "color" : "text";
    input = `<input type="${kind}" name="${key}" value="${esc(v)}" autocomplete="off">`;
  }
  return `<label>${esc(label)}</label>${input}${hint ? `<div class="hint">${esc(hint)}</div>` : ""}`;
}

function formHtml(values, statuses, view) {
  const state = Object.fromEntries(statuses.map((s) => [s.platform, s]));
  const groups = GROUPS.map(([id, title, fields]) => {
    const s = state[id];
    const words = s ? `<span class="state">${esc(s.state)}${s.detail ? ": " + esc(s.detail) : ""}</span>` : "";
    const mark = id === "display" ? "" : icon(id);
    return `<h3>${mark}${esc(title)}${words}</h3>${fields.map((f) => field(f, values)).join("")}`;
  }).join("");
  const banned = view.banned.length
    ? view.banned.map((b) => `<div class="banned-row">${icon(b.platform)}<span>${esc(b.author)}</span><button class="btn" data-unban="${esc(b.key)}">Unban</button></div>`).join("")
    : `<div class="hint">Nobody is banned.</div>`;
  return `<h2><span class="grow">Social Chat settings</span><button class="btn" id="close">Close</button></h2>
    <div class="hint">Keys and tokens stay on this machine and are only sent to the platform they belong to.</div>
    <form id="form">${groups}</form>
    <h3>Banned here</h3>${banned}
    <label class="check"><input type="checkbox" id="show-hidden" ${view.showHidden ? "checked" : ""}> Show hidden comments, faded</label>
    <div class="buttons"><button class="btn primary" id="save">Save</button>
      <button class="btn" id="reconnect">Reconnect all</button>
      <button class="btn" id="test">Send a test comment</button><span class="saved" id="saved"></span></div>`;
}

function read(form, values, sealKey) {
  const changes = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    let v = el.type === "checkbox" ? el.checked : el.value;
    // A key is sealed for the plugin before it leaves the page: the mixer
    // records every tool.call, and this way its log holds only ciphertext.
    if (el.type === "password") { if (v) changes[el.name] = { sealed: seal(sealKey, v.trim()) }; continue; }
    if (el.type === "number") v = Number(v);
    if (v !== values[el.name]) changes[el.name] = v;
  }
  return changes;
}

export async function openSettings(client, box, view) {
  const say = (t) => { const el = box.querySelector("#saved"); if (el) el.textContent = t; };
  const draw = async () => {
    const got = await tool(client, "settings", {});
    box.innerHTML = formHtml(got.settings, got.statuses, view);
    box.hidden = false;
    box.querySelector("#close").onclick = () => { box.hidden = true; };
    box.querySelector("#show-hidden").onchange = (e) => { view.showHidden = e.target.checked; view.dirty = true; };
    box.querySelector("#save").onclick = async () => {
      try {
        const done = await tool(client, "save_settings", { values: read(box.querySelector("#form"), got.settings, got.seal_key) });
        await draw();
        say(done.changed.length ? "Saved: " + done.changed.join(", ") : "Nothing changed");
      } catch (e) { say("Not saved: " + (e.message || e)); }
    };
    box.querySelector("#reconnect").onclick = async () => { await tool(client, "reconnect", {}); say("Reconnecting"); };
    box.querySelector("#test").onclick = async () => {
      await tool(client, "test_comment", { author: "Test", text: "Is this reaching the mixer? Testing from the Social Chat panel." });
      say("A test comment is in the list");
    };
    for (const b of box.querySelectorAll("[data-unban]")) {
      b.onclick = async () => {
        const m = await tool(client, "ban", { key: b.dataset.unban, banned: false });
        view.banned = m.banned || [];
        await draw();
      };
    }
  };
  try { await draw(); } catch (e) { box.hidden = false; box.innerHTML = `<div class="error-line">Could not read the settings: ${esc(e.message || e)}</div>`; }
}
