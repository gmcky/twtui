<p align="center">
  <img src="https://em-content.zobj.net/source/apple/391/television_1f4fa.png" width="90" />
</p>

<h1 align="center">twtui</h1>

<p align="center">
  <strong>Watch Twitch from your terminal.</strong>
</p>

<p align="center">
  <a href="https://github.com/gmcky/twtui/stargazers"><img src="https://img.shields.io/github/stars/gmcky/twtui?style=flat&color=blue" alt="Stars"></a>
  <a href="https://github.com/gmcky/twtui/commits/main"><img src="https://img.shields.io/github/last-commit/gmcky/twtui?style=flat" alt="Last Commit"></a>
  <img src="https://img.shields.io/badge/python-3.9+-brightgreen?style=flat" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat" alt="MIT">
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#install">Install</a> •
  <a href="#usage">Usage</a> •
  <a href="#roadmap">Roadmap</a> •
  <a href="#notes">Notes</a>
</p>

---

twtui lists your followed Twitch channels, searches all of Twitch, and opens any
live stream in mpv or VLC, all from the terminal: no browser, no login, no API
key. streamlink does the resolving and launching; twtui is the fast,
keyboard-driven front end around it.

It began as a stream launcher and is growing into a full terminal Twitch client
(VODs, clips, and an integrated chat overlay). See [Roadmap](#roadmap).

![Followed channels](docs/screenshots/followed.png)

![Categories](docs/screenshots/categories.png)

## Features

- **Followed channels** at a glance: live status, viewer count, current category.
- **Search all of Twitch** by login or display name, in any language.
- **Categories**: browse top games and the top channels within one.
- **Follow / unfollow** from anywhere; the list is saved per user to a plain text file.
- **One-key launch** into mpv or VLC. A stream that dies on launch is marked
  `✗ failed` instead of pretending to be open.
- **Clips**: paste a clip link into search and it opens, fully seekable.
- **Quality presets** (Low latency, High quality, Data saver, Unstable connection)
  set a whole bundle of streamlink options in one pick; change any setting and the
  preset becomes Custom.
- **Full streamlink control as plain settings**: quality, low-latency, codecs,
  live edge, retries, timeout, buffer size, segment threads, proxy, IP version,
  player path and args. No flag strings to memorize.
- **Configurable** theme colors, list auto-refresh, result counts, and hotkeys.
  Hotkeys work on any keyboard layout and are rebindable.
- **Session hygiene**: optional kill-streams-on-exit, startup cleanup of dead
  players, confirm-before-quit, and run-on-startup (Windows, macOS, Linux).

## Install

Needs [streamlink](https://streamlink.github.io/) and a player (mpv or VLC) on your PATH.

```bash
git clone https://github.com/gmcky/twtui
cd twtui
pip install -e .
twtui
```

Or run it straight from a clone:

```bash
pip install rich requests psutil
python -m twtui.app
```

## Usage

The app opens on your followed list. Move with the arrow keys, `Enter` to watch the
selected channel, `s` for settings. The in-app footer shows the current keys, and
every hotkey is rebindable in settings.

- **Follow channels** from search, or edit `channels.txt` in your config dir:
  - Windows: `%APPDATA%\twitch-tui\channels.txt`
  - Linux: `~/.config/twitch-tui/channels.txt`
  - macOS: `~/Library/Application Support/twitch-tui/channels.txt`
- **Watch a clip**: open search, paste a clip link
  (`clips.twitch.tv/<slug>` or `twitch.tv/<chan>/clip/<slug>`), then `Enter`.

Settings persist to `config.json` in the same config dir.

## Roadmap

Working toward a full terminal Twitch client on top of the current launcher.

- **VODs and clips**: browse a channel's past broadcasts and open VODs on a seekable
  timeline. The groundwork exists in the codebase but is gated off in this build.
- **Real DVR**: seekable live playback backed by an on-disk buffer, driving mpv as
  the player instead of the current external-player launch.
- **Chat overlay**: Twitch login (OAuth), 7TV / BetterTTV emotes, channel-point
  auto-collect, drops, predictions, and moderator actions.
- **More streamlink options** surfaced as friendly settings.
- **Distribution**: `pipx install twtui` from PyPI, plus CI.

## Notes

- Unofficial. It uses Twitch's public web GraphQL, not the official API, so it can
  break when Twitch changes things. Search returns ~10 results and lists load a
  single page (row counts are configurable, but Twitch caps search server-side);
  deeper paging needs a signed token and is not implemented.
- Not affiliated with Twitch.

## License

MIT
