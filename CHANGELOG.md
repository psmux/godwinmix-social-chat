# Changelog

## 1.0.0

The first release.

* Reads YouTube live chat (Data API v3, with an API key or OAuth), Twitch chat
  (anonymous, no account), Facebook Live comments (a Page token, streamed or
  polled) and any platform that can POST a webhook, into one list in time
  order with each comment once.
* A panel in the mixer with a filter per platform, search, pins, local bans,
  hidden comments, questions marked in their own colour, and each platform's
  connection state in words with the next step when it fails.
* One click puts a comment on the programme as a card or a lower third, drawn
  by the mixer from an SVG template, and one click takes it off.
* Practice mode, with made up comments for a rehearsal.
* Keys are sealed in the page before they reach the mixer, encrypted at rest
  on Windows, and never logged or shown whole.
* YouTube is read no faster than YouTube asks, nor than a floor you set, to
  keep inside the daily quota.
* X is a documented stub: its API needs a paid plan.
