# SPDX-License-Identifier: GPL-3.0-or-later
"""Application entry point."""

from __future__ import annotations

import logging
import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

from .. import APP_ID, APP_NAME, __version__  # noqa: E402
from ..settings import Settings  # noqa: E402
from .window import MainWindow  # noqa: E402


class BMeasureLogApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.settings = Settings()

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        for name, callback in (("about", self._show_about), ("quit", lambda *_: self.quit())):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("win.copy-latest", ["<Control>c"])
        self.set_accels_for_action("win.reconnect", ["<Control>r"])
        self.set_accels_for_action("win.clear", ["<Control>BackSpace"])
        self.set_accels_for_action("win.preferences", ["<Control>comma"])

    def do_activate(self) -> None:
        window = self.props.active_window or MainWindow(self, self.settings)
        window.present()

    def _show_about(self, *_) -> None:
        Adw.AboutDialog(
            application_name=APP_NAME,
            application_icon="bluetooth-active-symbolic",
            version=__version__,
            comments="Logs readings from Bluetooth laser distance meters.\n\n"
            "Unofficial; not affiliated with or endorsed by Robert Bosch GmbH.",
            copyright="\u00a9 2026 BMeasureLog contributors",
            license_type=Gtk.License.GPL_3_0,
        ).present(self.props.active_window)


def main(argv: list[str] | None = None) -> int:
    level = logging.DEBUG if os.environ.get("BMEASURELOG_DEBUG") else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    return BMeasureLogApp().run(argv if argv is not None else sys.argv)
