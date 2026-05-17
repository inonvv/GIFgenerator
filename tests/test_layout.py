"""Headless smoke test for the App layout.

Catches the class of bug where a widget exists in code but is clipped off
the bottom of the fixed-size window (what happened in v0.1.7).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app  # noqa: E402

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
