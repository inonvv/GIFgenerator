"""Headless smoke tests for the GIFGenerator GUI.

Tests the class of bugs where:
  - a widget exists in code but is clipped off the bottom of the fixed window
    (v0.1.7 regression)
  - the user clicks an action button and nothing happens / something happens
    multiple times (v0.1.8 multi-share-window regression)
  - the form stays clickable while a job is in flight
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app  # noqa: E402
import share_server  # noqa: E402

EXPECTED_WIDGETS = [
    "make_btn",
    "progress",
    "status",
    "outputs_label",
    "open_btn",
    "open_gif_btn",
    "share_btn",
]


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


@pytest.fixture(scope="session")
def built_app():
    a = app.App()
    a.update()  # map the window so winfo_root* returns real coordinates
    yield a
    a.destroy()


def test_named_widgets_exist(built_app):
    missing = [name for name in EXPECTED_WIDGETS if not hasattr(built_app, name)]
    assert not missing, f"App is missing expected widgets: {missing}"


def test_widgets_fit_in_window_height(built_app):
    """The widget tree's required height must be <= the window's actual height.

    Uses winfo_reqheight (DPI-independent: what tkinter wants the window to be
    given its children) vs winfo_height (what the window actually is after the
    geometry constraint is applied). If req > actual, widgets are clipped off
    the bottom — exactly the v0.1.7 'buttons not visible' bug.
    """
    a = built_app
    required = a.winfo_reqheight()
    actual = a.winfo_height()
    assert required <= actual, (
        f"Widgets need {required}px but window is only {actual}px tall — "
        f"increase self.geometry(...) in app.py by at least {required - actual}px."
    )


def test_on_make_clicked_disables_inputs_and_success_re_enables(built_app, monkeypatch, tmp_path):
    """End-to-end lifecycle: clicking Make must lock the form, success unlocks it.

    Regression: v0.1.8 only disabled the Make button; URL/Start/Duration/Name
    fields and the Quality menu stayed editable mid-job. This test asserts the
    real call site (on_make_clicked → _on_success) and would fail if anyone
    removes the disable/enable calls from the lifecycle.
    """
    import threading as real_threading

    a = built_app
    assert hasattr(a, "_inputs") and a._inputs, "App should track its input widgets in self._inputs"

    a.url_var.set("https://example.com/v")
    a.start_var.set("0:00")
    a.duration_var.set("3")
    a.name_var.set("regression_test")

    # Stop on_make_clicked from spawning a real worker thread — we drive the
    # lifecycle manually below.
    class _FakeThread:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            pass

    monkeypatch.setattr(real_threading, "Thread", _FakeThread)

    a.on_make_clicked()
    a.update_idletasks()

    assert str(a.make_btn.cget("state")) == "disabled", "make_btn must be disabled while working"
    for w in a._inputs:
        assert str(w.cget("state")) == "disabled", (
            f"{w.winfo_class()} stayed clickable during a job — _on_make_clicked "
            f"must disable every widget in self._inputs"
        )

    # Simulate successful completion.
    a.last_outputs = tmp_path / "done.gif"
    a.last_outputs.write_bytes(b"GIF89a")
    a._on_success()
    a.update_idletasks()

    assert str(a.make_btn.cget("state")) == "normal", "make_btn must be re-enabled on success"
    for w in a._inputs:
        assert str(w.cget("state")) == "normal", (
            f"{w.winfo_class()} stayed disabled after success — _on_success "
            f"must re-enable every widget in self._inputs"
        )


def test_share_window_is_singleton(built_app, monkeypatch, tmp_path):
    """Clicking Send to phone twice must NOT spawn a second window/server.

    Regression: in v0.1.8 each click of share_btn called serve_file() and
    constructed a fresh ShareWindow, leaving multiple popups (some hidden
    behind the main window) and multiple HTTP servers bound to random ports.
    """
    a = built_app

    # Pretend a GIF was just made so the "Make a GIF first" guard passes.
    fake_gif = tmp_path / "fake.gif"
    fake_gif.write_bytes(b"GIF89a")
    a.last_outputs = fake_gif

    # Replace serve_file with a stub so we don't bind real ports under test.
    calls = {"n": 0}

    def fake_serve_file(path, *args, **kwargs):
        calls["n"] += 1
        return share_server.ShareSession(
            url="http://test/x.gif",
            _server=type("S", (), {"shutdown": lambda self: None, "server_close": lambda self: None})(),
            _thread=type("T", (), {})(),
            _stopped=type("E", (), {"is_set": lambda self: True, "set": lambda self: None})(),
        )

    monkeypatch.setattr(app, "serve_file", fake_serve_file)

    a.open_share_window()
    a.open_share_window()
    a.open_share_window()
    a.update_idletasks()

    assert calls["n"] == 1, f"serve_file should be called once, got {calls['n']}"
    assert a.share_window is not None
    # Clean up so other tests don't see stale window state
    a.share_window._on_close()
    a.update_idletasks()
