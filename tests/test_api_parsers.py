def test_twitch_search_live_first(monkeypatch):
    from twtui import api

    canned = {
        "data": {
            "searchFor": {
                "channels": {
                    "edges": [
                        {"item": {"login": "off1", "displayName": "Off1", "stream": None}},
                        {
                            "item": {
                                "login": "live1",
                                "displayName": "Live1",
                                "stream": {
                                    "id": "1",
                                    "viewersCount": 50,
                                    "game": {"displayName": "Chess"},
                                },
                            }
                        },
                    ]
                }
            }
        }
    }
    monkeypatch.setattr(api, "_gql", lambda q, v: canned)
    out = api.twitch_search("x")
    assert [c["login"] for c in out] == ["live1", "off1"]
    assert out[0]["viewers"] == 50 and out[0]["game"] == "Chess"


def test_gql_live(monkeypatch):
    from twtui import api

    canned = {
        "data": {
            "users": [
                {
                    "login": "FOO",
                    "displayName": "Foo",
                    "stream": {"viewersCount": 10, "game": {"displayName": "G"}},
                },
                {"login": "bar", "displayName": "Bar", "stream": None},
            ]
        }
    }
    monkeypatch.setattr(api, "_gql", lambda q, v: canned)
    out = api._gql_live(["foo", "bar"])
    assert "foo" in out
    assert out["foo"]["live"] is True
    assert out["foo"]["viewers"] == 10
    assert out["foo"]["game"] == "G"
    assert out["foo"]["display"] == "Foo"
    assert "bar" in out
    assert out["bar"]["live"] is False


def test_get_status(monkeypatch):
    from twtui import api

    monkeypatch.setattr(api, "_gql_live", lambda logins: {"foo": {"live": True}})
    out = api.get_status(["foo", "bar"])
    assert out["foo"]["live"] is True
    assert out["bar"]["live"] is False
    assert out["bar"]["display"] == ""


def test_top_games(monkeypatch):
    from twtui import api

    canned = {
        "data": {"games": {"edges": [{"node": {"id": "1", "name": "G", "viewersCount": 10}}]}}
    }
    monkeypatch.setattr(api, "_gql", lambda q, v: canned)
    out = api.top_games()
    assert len(out) == 1
    assert out[0]["name"] == "G"

    monkeypatch.setattr(api, "_gql", lambda q, v: {})
    assert api.top_games() == []


def test_search_games(monkeypatch):
    from twtui import api

    canned = {"data": {"searchFor": {"games": {"edges": [{"item": {"id": "1", "name": "G"}}]}}}}
    monkeypatch.setattr(api, "_gql", lambda q, v: canned)
    out = api.search_games("g")
    assert len(out) == 1
    assert out[0]["name"] == "G"

    monkeypatch.setattr(api, "_gql", lambda q, v: {})
    assert api.search_games("g") == []


def test_game_streams(monkeypatch):
    from twtui import api

    canned = {
        "data": {
            "game": {
                "streams": {
                    "edges": [
                        {
                            "node": {
                                "broadcaster": {"login": "foo", "displayName": "Foo"},
                                "viewersCount": 10,
                            }
                        }
                    ]
                }
            }
        }
    }
    monkeypatch.setattr(api, "_gql", lambda q, v: canned)
    out = api.game_streams("G")
    assert len(out) == 1
    assert out[0]["login"] == "foo"

    monkeypatch.setattr(api, "_gql", lambda q, v: {})
    assert api.game_streams("G") == []


def test_channel_videos(monkeypatch):
    from twtui import api

    def mock_gql(q, v):
        return {
            "data": {
                "user": {
                    "videos": {
                        "edges": [
                            {
                                "node": {
                                    "id": "123456",
                                    "title": "Test VOD",
                                    "lengthSeconds": 3661,
                                    "publishedAt": "2023-10-10T12:00:00Z",
                                    "viewCount": 500,
                                    "game": {"displayName": "Just Chatting"},
                                }
                            }
                        ]
                    }
                }
            }
        }

    monkeypatch.setattr(api, "_gql", mock_gql)
    res = api.channel_videos("test", limit=1)
    assert len(res) == 1
    assert res[0]["id"] == "123456"
    assert res[0]["title"] == "Test VOD"
    assert res[0]["length"] == 3661
    assert res[0]["date"] == "2023-10-10"
    assert res[0]["views"] == 500
    assert res[0]["game"] == "Just Chatting"


def test_parser_exception(monkeypatch):
    from twtui import api

    def raise_err(q, v):
        raise RuntimeError()

    monkeypatch.setattr(api, "_gql", raise_err)
    assert api.twitch_search("x") == []
    assert api.top_games() == []
    assert api.search_games("x") == []
    assert api.game_streams("x") == []
