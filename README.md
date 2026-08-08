<p align="center">
  <img src="https://em-content.zobj.net/source/apple/391/television_1f4fa.png" width="90" />
</p>

<h1 align="center">twtui</h1>

<p align="center">
  <strong>A terminal UI for watching Twitch.</strong>
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
  <a href="#keys">Keys</a> •
  <a href="#notes">Notes</a>
</p>

---

See which of your followed Twitch channels are live, search all of Twitch, browse
categories, and open any stream in your player without leaving the terminal.
Streams launch through [streamlink](https://streamlink.github.io/). No login, no
API key.

![Followed channels](docs/screenshots/followed.png)

| Search | Categories |
|---|---|
| ![Search](docs/screenshots/search.png) | ![Categories](docs/screenshots/categories.png) |

## Features

- Followed-channel list with live status, viewer count and current game.
- Fuzzy search across all of Twitch (matches logins and display names, any language).
- Browse top categories and the top channels within one.
- Follow / unfollow from anywhere; the list is saved per user.
- Open a stream in your player with one key.
- Hotkeys work on any keyboard layout.
- Small settings screen (background streamlink, kill-on-exit), saved to config.

## Install

Needs [streamlink](https://streamlink.github.io/) and a player (mpv or VLC) on your PATH.

```bash
git clone https://github.com/gmcky/twtui
cd twtui
pip install -e .
twtui
```

Or run it without installing:

```bash
pip install rich requests
python watch.py        # or: python -m twtui
```

## Usage

- The app opens on your followed list. Add channels by following them from search
  (see keys below), or edit `channels.txt` in your config dir:
  - Windows: `%APPDATA%\twitch-tui\channels.txt`
  - Linux: `~/.config/twitch-tui/channels.txt`
  - macOS: `~/Library/Application Support/twitch-tui/channels.txt`
- `Enter` on a channel opens it in your player.

## Keys

| Key | Action |
|-----|--------|
| `↑` `↓` | Move |
| `Enter` | Watch selected |
| `Tab` | Switch followed list ⇄ search |
| `←` `→` | Switch Streamers / Categories (in search) |
| `Ctrl+F` | Follow / unfollow (in search or a category) |
| `Ctrl+G` | Open categories |
| `f` | Unfollow (in the followed list) |
| `r` | Refresh live status |
| `s` | Settings |
| `Ctrl+Q` | Quit (from anywhere) |
| `Esc` | Back / quit |

## Notes

- Unofficial. It uses Twitch's public web GraphQL, not the official API, so it can
  break if Twitch changes things. Search returns ~10 results and lists load one
  page (~100); deeper paging needs a signed token and is not implemented.
- Not affiliated with Twitch.

## License

MIT
