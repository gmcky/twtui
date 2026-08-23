"""Twitch public web GraphQL client (anonymous web Client-Id, no OAuth).

The anonymous client-id serves single pages fine but cursor pagination (`after`)
fails an integrity check, so lists load one large page (~100) rather than
lazy-loading more on scroll. searchFor is capped at ~10 results by Twitch.
"""

from concurrent.futures import ThreadPoolExecutor

import requests

GQL_URL = "https://gql.twitch.tv/gql"
GQL_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"

OFFLINE = {"live": False, "viewers": 0, "game": "", "display": ""}

SEARCH_QUERY = """
query($q: String!) {
  searchFor(userQuery: $q, platform: "web", options: {}) {
    channels {
      edges {
        item {
          ... on User {
            login
            displayName
            stream { id viewersCount game { displayName } }
          }
        }
      }
    }
  }
}
"""

USERS_QUERY = """
query($logins: [String!]) {
  users(logins: $logins) {
    login
    displayName
    stream { id viewersCount game { displayName } }
  }
}
"""

TOP_GAMES_QUERY = """
query($n: Int!) {
  games(first: $n) { edges { node { name displayName viewersCount } } }
}
"""

GAMES_SEARCH_QUERY = """
query($q: String!) {
  searchFor(userQuery: $q, platform: "web", options: {}) {
    games { edges { item { ... on Game { name displayName viewersCount } } } }
  }
}
"""

GAME_STREAMS_QUERY = """
query($name: String!, $n: Int!) {
  game(name: $name) {
    displayName
    streams(first: $n) {
      edges { node {
        viewersCount
        broadcaster { login displayName }
        game { displayName }
      } }
    }
  }
}
"""

CHANNEL_VIDEOS_QUERY = """
query($login: String!, $n: Int!) {
  user(login: $login) {
    videos(first: $n, sort: TIME, type: ARCHIVE) {
      edges { node {
        id title lengthSeconds publishedAt viewCount
        game { displayName }
      } }
    }
  }
}
"""


def _gql(query, variables):
    return requests.post(
        GQL_URL,
        headers={"Client-Id": GQL_CLIENT_ID},
        json={"query": query, "variables": variables},
        timeout=10,
    ).json()


def _gql_live(logins):
    # Resolve live-status -> {login: meta}.
    try:
        users = _gql(USERS_QUERY, {"logins": logins})["data"]["users"]
    except Exception:
        return {}
    out = {}
    for u in users:
        if not u:
            continue
        s = u.get("stream")
        out[u["login"].lower()] = {
            "live": bool(s),
            "viewers": (s or {}).get("viewersCount") or 0,
            "game": ((s or {}).get("game") or {}).get("displayName") or "",
            "display": u.get("displayName") or u["login"],
        }
    return out


def get_status(channels):
    # Chunk and fetch in parallel.
    chunks = [channels[i : i + 90] for i in range(0, len(channels), 90)]
    meta = {}
    with ThreadPoolExecutor(max_workers=max(len(chunks), 1)) as pool:
        for part in pool.map(_gql_live, chunks):
            meta.update(part)
    return {ch: meta.get(ch.lower(), OFFLINE) for ch in channels}


def twitch_search(query, limit=15):
    # Fuzzy search, live first.
    try:
        edges = _gql(SEARCH_QUERY, {"q": query})["data"]["searchFor"]["channels"]["edges"]
    except Exception:
        return []
    out = []
    for e in edges[:limit]:
        it = e.get("item") or {}
        login = it.get("login")
        if not login:
            continue
        s = it.get("stream")
        out.append(
            {
                "login": login,
                "display": it.get("displayName") or login,
                "live": bool(s),
                "viewers": (s or {}).get("viewersCount") or 0,
                "game": ((s or {}).get("game") or {}).get("displayName") or "",
            }
        )
    out.sort(key=lambda x: not x["live"])  # stable: live first, relevance kept
    return out


def top_games(limit=100):
    # Most-watched categories.
    try:
        edges = _gql(TOP_GAMES_QUERY, {"n": limit})["data"]["games"]["edges"]
    except Exception:
        return []
    out = []
    for e in edges:
        n = e["node"]
        name = n.get("name") or n.get("displayName")
        if not name:
            continue
        out.append(
            {
                "name": name,
                "display": n.get("displayName") or name,
                "viewers": n.get("viewersCount") or 0,
            }
        )
    return out


def search_games(query, limit=15):
    # Fuzzy category search.
    try:
        edges = _gql(GAMES_SEARCH_QUERY, {"q": query})["data"]["searchFor"]["games"]["edges"]
    except Exception:
        return []
    out = []
    for e in edges[:limit]:
        it = e.get("item") or {}
        name = it.get("name")
        if not name:
            continue
        out.append(
            {
                "name": name,
                "display": it.get("displayName") or name,
                "viewers": it.get("viewersCount") or 0,
            }
        )
    return out


def game_streams(name, limit=100):
    # Top live channels by viewers.
    try:
        edges = _gql(GAME_STREAMS_QUERY, {"name": name, "n": limit})["data"]["game"]["streams"][
            "edges"
        ]
    except Exception:
        return []
    out = []
    for e in edges:
        n = e["node"]
        b = n.get("broadcaster") or {}
        login = b.get("login")
        if not login:
            continue
        out.append(
            {
                "login": login,
                "display": b.get("displayName") or login,
                "live": True,
                "viewers": n.get("viewersCount") or 0,
                "game": (n.get("game") or {}).get("displayName") or "",
            }
        )
    return out


def channel_videos(login, limit=20):
    # Recent VODs.
    try:
        edges = _gql(CHANNEL_VIDEOS_QUERY, {"login": login, "n": limit})["data"]["user"]["videos"][
            "edges"
        ]
    except Exception:
        return []
    out = []
    for e in edges:
        n = e["node"]
        vid = n.get("id")
        if not vid:
            continue
        out.append(
            {
                "id": vid,
                "title": n.get("title") or "untitled",
                "length": n.get("lengthSeconds") or 0,
                "date": (n.get("publishedAt") or "")[:10],
                "views": n.get("viewCount") or 0,
                "game": (n.get("game") or {}).get("displayName") or "",
            }
        )
    return out
