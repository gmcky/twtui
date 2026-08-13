import sys

from twtui.config import _linux_startup, _macos_startup, _startup_argv


def test_linux_startup(tmp_path):
    d = tmp_path / ".config" / "autostart"
    f = d / "twtui.desktop"

    _linux_startup(True, str(tmp_path))
    assert f.exists()
    content = f.read_text(encoding="utf-8")
    assert "Type=Application" in content
    assert "Name=twtui" in content
    assert "Exec=" in content
    assert "twtui.app" in content

    _linux_startup(False, str(tmp_path))
    assert not f.exists()

    # disable on missing file does not raise
    _linux_startup(False, str(tmp_path))


def test_macos_startup(tmp_path):
    d = tmp_path / "Library" / "LaunchAgents"
    f = d / "com.twtui.plist"

    _macos_startup(True, str(tmp_path))
    assert f.exists()
    content = f.read_text(encoding="utf-8")
    assert "<key>RunAtLoad</key><true/>" in content
    assert "<string>" in content
    assert "twtui.app" in content

    _macos_startup(False, str(tmp_path))
    assert not f.exists()

    # double disable is safe
    _macos_startup(False, str(tmp_path))


def test_startup_argv(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    argv = _startup_argv()
    assert argv[-1] == "twtui.app"
