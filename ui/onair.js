// Putting a comment on the programme and taking it off, with the mixer's
// public methods only: source.add and source.set for the graphic, and
// scene.item.add and scene.item.set on whatever scene is on air. Nothing here
// is private to this plugin; an agent could make the same calls.

const ITEM = { card: "social-chat-card", strap: "social-chat-strap" };
const ENTER = {
  card: { type: "slide", edge: "left", duration_ms: 450, easing: "ease-out" },
  strap: { type: "slide", edge: "bottom", duration_ms: 400, easing: "ease-out" },
};
const EXIT = { type: "fade", duration_ms: 300, on_take: true };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function tool(client, name, args) {
  const answer = await client.call("tool.call", { name: "social-chat/" + name, arguments: args || {} });
  const body = answer && (answer.structuredContent || answer);
  if (answer && answer.isError) {
    const err = new Error((body && body.error) || "the tool refused");
    err.data = body && body.data;
    throw err;
  }
  return body;
}

async function programmeScene(client) {
  const programme = await client.call("program.get", {});
  if (!programme.scene) {
    throw new Error("the programme is showing a source, not a scene. Take a scene first, then put the comment on air.");
  }
  return client.call("scene.get", { id: programme.scene });
}

function itemIn(scene, name) {
  return (scene.records || []).find((r) => r.kind === "item" && r.name === name);
}

async function ensureSource(client, card) {
  const sources = (client.state && client.state.sources) || [];
  const have = sources.find((s) => s.id === card.source);
  if (have && /fail|error/.test(String(have.state || ""))) {
    await client.call("source.remove", { id: card.source }).catch(() => {});
  } else if (have) {
    try {
      await client.call("source.set", { id: card.source, params: { fields: card.fields } });
      return;
    } catch (e) {
      // The template moved (the plugin was updated) or lost a field: start again.
      await client.call("source.remove", { id: card.source }).catch(() => {});
    }
  }
  await client.call("source.add", {
    id: card.source, name: "Social Chat " + card.style, uri: card.uri, params: { fields: card.fields },
  });
}

async function ensureItem(client, scene, style) {
  const name = ITEM[style];
  const found = itemIn(scene, name);
  if (found) return found;
  const canvas = scene.canvas || { width: 1920, height: 1080 };
  await client.call("scene.item.add", {
    scene: scene.name, content: { source: name }, name, visible: false,
    transform: { position: { x: 0, y: 0 }, frame: { w: canvas.width, h: canvas.height }, fit: "contain" },
    enter: ENTER[style], exit: EXIT,
  });
  return { name, visible: false };
}

/** Put one comment on air. Answers the card the plugin made for it. */
export async function putOnAir(client, id, style) {
  const card = await tool(client, "card_fields", { id, style });
  card.source = ITEM[card.style];
  const scene = await programmeScene(client);
  for (const [other, name] of Object.entries(ITEM)) {
    const item = itemIn(scene, name);
    if (other !== card.style && item && item.visible) {
      await client.call("scene.item.set", { scene: scene.name, item: name, props: { visible: false } });
    }
  }
  const up = itemIn(scene, ITEM[card.style]);
  if (up && up.visible) {
    // Something is already up: let it go out, then bring the new words in.
    await client.call("scene.item.set", { scene: scene.name, item: up.name, props: { visible: false } });
    await sleep(EXIT.duration_ms + 50);
  }
  await ensureSource(client, card);
  await ensureItem(client, scene, card.style);
  await client.call("scene.item.set", { scene: scene.name, item: ITEM[card.style], props: { visible: true } });
  return card;
}

/** Take whatever comment is up off the programme. */
export async function takeOff(client) {
  const scene = await programmeScene(client);
  for (const name of Object.values(ITEM)) {
    const item = itemIn(scene, name);
    if (item && item.visible) {
      await client.call("scene.item.set", { scene: scene.name, item: name, props: { visible: false } });
    }
  }
  await tool(client, "card_off", {});
}
