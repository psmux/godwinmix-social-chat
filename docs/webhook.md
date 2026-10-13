# The webhook

`POST http://<address>:<port>/comments` (or `/`) with a JSON body. The
address is `127.0.0.1` and the port `8790` unless Settings say otherwise.

## The body

One comment, a list of comments, or `{"comments": [...]}`. At most 256 KB and
200 comments a request.

| Field | Also read as | Required | Meaning |
|---|---|---|---|
| `text` | `message`, `comment`, `content`, `body`, `msg` | yes | the words. A comment with none is skipped |
| `author` | `user`, `username`, `user_name`, `display_name`, `name`, `nick` | no | who wrote it. An object with a `name` works too: `{"user": {"name": "Sam"}}` |
| `platform` | `source`, `service`, `network` | no | which platform, as a short name: `tiktok`, `kick`. Default `webhook` |
| `id` | `message_id`, `comment_id`, `msg_id`, `uuid` | no | the platform's own id. Without one, the same words from the same person at the same time count as the same comment |
| `time` | `timestamp`, `created_at`, `created_time`, `published_at`, `ts` | no | ISO 8601, epoch seconds or epoch milliseconds. Default: when it arrived |
| `avatar` | `avatar_url`, `picture`, `profile_image_url`, `image` | no | an `https://` address of a profile picture |
| `author_id` | `user_id`, `userid`, `uid` | no | the author's id on the platform, which a local ban matches on |
| `amount` | | no | for a paid message, the amount as words, such as `"$5.00"` |
| `kind` | | no | `chat`, `superchat`, `member` or `event` |
| `url` | | no | a link to the author or the message |

A comment is kept once: the same `platform` and `id` sent twice is counted as
a duplicate.

## The answer

`202` with `{"accepted": 2, "duplicates": 0, "skipped": 1}`. A request with a
missing or wrong secret is `401`, a body that is not JSON `400`, an empty or
oversized body `413`, and any other path `404`, each with `{"error": "..."}`
saying what to change. `GET /` answers `{"ok": true, ...}`, for a health check.

## The secret

With a secret set in Settings, send it as `X-Social-Chat-Secret: <secret>` or
`Authorization: Bearer <secret>`. Set one before changing the address to
`0.0.0.0`, because anyone who can reach the port can otherwise put words in
the list, and from there on air.

## Example

```sh
curl -X POST http://127.0.0.1:8790/comments \
  -H 'Content-Type: application/json' \
  -H 'X-Social-Chat-Secret: change-me' \
  -d '{"comments": [
        {"platform": "tiktok", "id": "7301", "author": "Sam", "text": "hello from TikTok"},
        {"source": "kick", "user": {"name": "streamfan"}, "message": "first!"}
      ]}'
```
