---
name: social-chat
description: Read the live comments from YouTube, Twitch, Facebook and webhook posts that the social-chat GodwinMix plugin merges into one list, find a question or a good comment, and put it on air as a comment card or a lower third. Use when an operator asks what the audience is saying, asks to show a viewer's comment on screen, asks to take a comment off air, or asks why a platform's chat is not arriving.
---

# Social Chat

The `social-chat` plugin reads live comments from several platforms into one
list, in time order, once each. Its tools are reached with `tool.call` (MCP:
`gmx_social-chat_<tool>`).

## Read the chat

```
tool.call {name: "social-chat/comments", arguments: {after: 0, limit: 50}}
```

Each comment is `{id, platform, author, text, time, question, kind, amount?}`.
`question` is true when it asks something. Keep `seq` from the answer and pass
it as `after` next time to get only what changed.

## Why a platform is quiet

```
tool.call {name: "social-chat/status", arguments: {}}
```

Every platform has a `state` (`connected`, `connecting`, `waiting`, `failing`,
`unavailable`, `off`), a `detail` and a `next` step. Tell the operator the
`next` step as it is written. Never ask for a key in chat; the operator types
it in the panel's Settings.

## Put a comment on air

1. `tool.call {name: "social-chat/card_fields", arguments: {id: "<comment id>", style: "card"}}`
   answers `{source, uri, fields}`. `style` is `card` or `strap`.
2. If the source does not exist: `source.add {id: <source>, uri: <uri>, params: {fields: <fields>}}`.
   Otherwise: `source.set {id: <source>, params: {fields: <fields>}}`.
3. `program.get {}` gives the programme `scene`. If that scene has no item named
   `<source>`, add one over the whole canvas, hidden, with a way in and out:
   `scene.item.add {scene, content: {source: <source>}, name: <source>, visible: false,
   transform: {position: {x: 0, y: 0}, frame: {w: <canvas width>, h: <canvas height>}},
   enter: {type: "slide", edge: "left", duration_ms: 450}, exit: {type: "fade", duration_ms: 300, on_take: true}}`.
4. `scene.item.set {scene, item: <source>, props: {visible: true}}`.

Check it with `snapshot {"id": "program"}` before saying it is on air.

## Take it off

`scene.item.set {scene, item: <source>, props: {visible: false}}`, then
`tool.call {name: "social-chat/card_off", arguments: {}}`.

## Moderation, local only

`pin`, `hide` and `ban` change this mixer's list and nothing on the platform.
Ask before banning anyone.
