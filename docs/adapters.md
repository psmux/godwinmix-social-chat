# Adding a platform

Each platform is an adapter: one class in `social_chat/adapters/`, usually
with its parsing in a second module beside it so the tests can feed it
recorded payloads with no network. The Twitch adapter is the shortest
complete example; the webhook is the simplest one that listens rather than
connects.

## The contract

```python
from .base import Adapter, Problem, CONNECTED, WAITING

class Kick(Adapter):
    platform = "kick"        # the slug in every comment id: "kick:<their id>"
    title = "Kick"           # what the panel shows

    @classmethod
    def configured(cls, settings):
        # True when the settings say this platform should run.
        return bool(settings.get("kick_channel"))

    def session(self):
        # Connect, read until something goes wrong, then return or raise.
        # The base class runs this on its own thread, again and again.
        ...
        self.say(CONNECTED, "reading #ourchannel")
        for raw in incoming:
            self.emit(parse.comment_of(raw))   # a dict made by model.comment()
        raise Problem("Kick closed the connection", "Reconnecting by itself.", retry_s=5)

    def close(self):
        # Drop the connection so a blocking read returns. Called on stop and
        # after every session.
        ...
```

What the base class gives you:

| Call | What it does |
|---|---|
| `self.emit(item)` | adds a comment to the merged list. A comment seen before (same id) is dropped, and so is one from a locally banned author |
| `self.sink.remove(id)` | takes one comment away, for a platform that says a message was deleted |
| `self.sink.remove_where(test)` | takes away every comment `test(item)` is true for, for a platform that says a user was banned |
| `self.say(state, detail, next)` | the words the panel shows. `state` is one of the constants in `base.py` |
| `self.wait(seconds)` | sleeps, and answers True as soon as the adapter is asked to stop. Use it between polls |
| `raise Problem(detail, next, retry_s, state)` | ends the session with words for the operator. `retry_s=None` stops retrying until the settings change, which is right for a wrong key |

Any other exception is caught, shown as "stopped: ..." and retried with a
growing wait, from 2 seconds up to 2 minutes. A session that ran for over a
minute resets the wait.

## Building a comment

```python
from ..model import comment

comment("kick", raw["id"], raw["sender"]["username"], raw["content"], raw["created_at"],
        author_id=raw["sender"]["id"], avatar=raw["sender"].get("profile_pic"),
        badges=["moderator"], kind="chat")
```

The time may be ISO 8601, epoch seconds or epoch milliseconds. `kind` is
`chat`, `superchat` (paid, with `amount` as words like `"$5.00"`), `member` or
`event`. Whether it is a question is worked out from the words.

## Settings and secrets

1. Add each setting to `DEFAULTS` in `social_chat/settings.py`, named
   `<platform>_<what>`, so a change to it reconnects only your adapter.
2. A key or token also goes in `SECRETS`. It then arrives sealed from the
   panel, is encrypted at rest, is masked in every answer and is taken out of
   every log line.
3. Add the same key to `schemas/settings.json` with a description, a default
   and an example (`"format": "secret"` for a secret), and to `GROUPS` in
   `ui/settings.js` so the panel's form shows it. `tests/test_manifest.py`
   fails until the schema and `DEFAULTS` agree.

## Registering it

Import the class in `social_chat/adapters/__init__.py` and add it to
`ADAPTERS`. Give it an icon in `ui/icons.js` (a 24 by 24 SVG shape and a
colour) and a colour and label in `social_chat/card.py` for the on air card.
Add a line for it to `_setup_hint` in `social_chat/service.py`, which is what
the panel says while it is not set up.

## Testing it

Save a few real payloads, in the shape the platform documents, under
`tests/fixtures/`, with names and ids made up. Then test the parsing on its
own and the session with its network calls replaced, the way
`tests/test_youtube.py` does with `adapter.call` and `adapter.wait`. A test
that needs the network is skipped unless an environment variable asks for
it, as `tests/test_live_twitch.py` does.

## What an X adapter would do

`social_chat/adapters/x_stub.py` only says that X needs a paid plan. With a
paid key, a working adapter would:

1. Take a bearer token (a secret) and the id of the live post.
2. Add a filtered stream rule `conversation_id:<post id>` through
   `POST /2/tweets/search/stream/rules`.
3. Hold `GET /2/tweets/search/stream?tweet.fields=created_at,author_id,conversation_id&expansions=author_id&user.fields=profile_image_url,username`
   open and read one JSON object a line, as the Facebook adapter reads its
   event stream.
4. Build each comment from `data.text`, `data.created_at` and the matching
   user in `includes.users`, and remove the rule when the session ends.

Recent search (`GET /2/tweets/search/recent?query=conversation_id:<id>`)
polled every few seconds is the alternative on plans without the stream, with
the plan's request limits to respect.
