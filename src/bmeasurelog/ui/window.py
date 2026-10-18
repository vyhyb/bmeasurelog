# SPDX-License-Identifier: GPL-3.0-or-later
"""Main window: latest reading, history of the last 10, connection status."""

from __future__ import annotations

from collections import deque

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from .. import APP_NAME  # noqa: E402
from ..meters import PROFILES, ConnectionState  # noqa: E402
from ..meters.ble import BleConnection  # noqa: E402
from ..readings import Reading  # noqa: E402
from ..settings import Settings  # noqa: E402
from .preferences import PreferencesDialog  # noqa: E402

HISTORY_SIZE = 10


def _post(fn, *args) -> None:
    """Run ``fn(*args)`` on the GTK main loop; safe to call from any thread."""

    def run():
        fn(*args)
        return GLib.SOURCE_REMOVE

    GLib.idle_add(run)


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, settings: Settings) -> None:
        super().__init__(application=app, title=APP_NAME, default_width=400, default_height=600)
        self.settings = settings
        self.history: deque[Reading] = deque(maxlen=HISTORY_SIZE)  # newest first
        self.connected = False
        self._latest_copied = False
        self._rows: list[Adw.ActionRow] = []

        self._build_actions()
        self._build_ui()
        self._refresh()

        settings.connect(self._refresh)
        self.connect("close-request", self._on_close)

        self.connection = BleConnection(
            PROFILES,
            on_state=lambda state, name: _post(self._on_state, state, name),
            on_reading=lambda reading: _post(self._on_reading, reading),
        )
        self.connection.start()

    # ------------------------------------------------------------ actions
    def _build_actions(self) -> None:
        def add(name, callback):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

        add("copy-latest", lambda *_: self._copy_latest())
        add("clear", self._on_clear)
        add("reconnect", lambda *_: self.connection.reconnect())
        add("preferences", lambda *_: PreferencesDialog(self.settings).present(self))

    # ----------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        self.toasts = Adw.ToastOverlay()
        view = Adw.ToolbarView()

        header = Adw.HeaderBar()
        self.window_title = Adw.WindowTitle(title=APP_NAME, subtitle="")
        header.set_title_widget(self.window_title)
        header.pack_start(
            Gtk.Button(icon_name="user-trash-symbolic", tooltip_text="Clear History", action_name="win.clear")
        )
        menu = Gio.Menu()
        options = Gio.Menu()
        options.append("Preferences", "win.preferences")
        options.append("Reconnect", "win.reconnect")
        about = Gio.Menu()
        about.append(f"About {APP_NAME}", "app.about")
        menu.append_section(None, options)
        menu.append_section(None, about)
        header.pack_end(
            Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu, primary=True, tooltip_text="Main Menu")
        )
        view.add_top_bar(header)

        self.banner = Adw.Banner(button_label="Reconnect", action_name="win.reconnect")
        view.add_top_bar(self.banner)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.empty = Adw.StatusPage(icon_name="bluetooth-active-symbolic", vexpand=True)
        self.stack.add_named(self.empty, "empty")
        self.stack.add_named(self._build_list_page(), "list")
        view.set_content(self.stack)

        self.toasts.set_child(view)
        self.set_content(self.toasts)

    def _build_list_page(self) -> Gtk.Widget:
        self.value_label = Gtk.Label(css_classes=["title-1", "numeric"])
        attrs = Pango.AttrList()
        attrs.insert(Pango.attr_scale_new(2.6))
        self.value_label.set_attributes(attrs)
        self.hint_label = Gtk.Label(css_classes=["dim-label"])
        copy_button = Gtk.Button(
            label="Copy", halign=Gtk.Align.CENTER, css_classes=["suggested-action", "pill"],
            action_name="win.copy-latest",
        )
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12)
        for widget in (self.value_label, self.hint_label, copy_button):
            hero.append(widget)

        self.earlier = Adw.PreferencesGroup(title="Earlier")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=32)
        box.append(hero)
        box.append(self.earlier)
        clamp = Adw.Clamp(maximum_size=480, margin_top=24, margin_bottom=24, margin_start=12, margin_end=12)
        clamp.set_child(box)
        scrolled = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scrolled.set_child(clamp)
        return scrolled

    def _refresh(self) -> None:
        """Re-render everything from ``self.history`` and the current settings."""
        has = bool(self.history)
        self.lookup_action("clear").set_enabled(has)
        self.lookup_action("copy-latest").set_enabled(has)
        self.stack.set_visible_child_name("list" if has else "empty")

        if self.connected:
            self.empty.set_title("Ready to Measure")
            self.empty.set_description(
                f"Take a measurement. The last {HISTORY_SIZE} readings will appear here."
            )
        else:
            self.empty.set_title("Connecting…")
            self.empty.set_description(
                "Switch on your laser distance meter and its Bluetooth. "
                "If it is connected to another device, disconnect it there first."
            )

        if has:
            latest = self.history[0]
            self.value_label.set_label(self.settings.format(latest))
            self.hint_label.set_label(
                "Copied to clipboard" if self._latest_copied else f"Latest {latest.kind.value}"
            )

        for row in self._rows:
            self.earlier.remove(row)
        self._rows.clear()
        older = list(self.history)[1:]
        self.earlier.set_visible(bool(older))
        for reading in older:
            button = Gtk.Button(
                icon_name="edit-copy-symbolic", valign=Gtk.Align.CENTER,
                css_classes=["flat"], tooltip_text="Copy",
            )
            button.connect("clicked", lambda _b, r=reading: self._copy(r, toast=True))
            row = Adw.ActionRow(
                title=self.settings.format(reading),
                subtitle=f"{reading.kind.label} \u00b7 {reading.timestamp.strftime('%X')}",
            )
            row.add_suffix(button)
            row.set_activatable_widget(button)
            self.earlier.add(row)
            self._rows.append(row)

    # ------------------------------------------------- connection callbacks
    def _on_state(self, state: ConnectionState, device_name: str | None) -> None:
        self.connected = state is ConnectionState.CONNECTED
        self.window_title.set_subtitle(device_name or "")
        if state is ConnectionState.SEARCHING:
            self.banner.set_title("Searching for the laser measure…")
        elif state is ConnectionState.LOST:
            self.banner.set_title("Connection lost")
        self.banner.set_revealed(not self.connected)
        self._refresh()

    def _on_reading(self, reading: Reading) -> None:
        self.history.appendleft(reading)
        self._latest_copied = False
        if self.settings.options.auto_copy:
            self._copy(reading, toast=False)
            self._latest_copied = True
        self._refresh()

    # ----------------------------------------------------------- actions
    def _copy(self, reading: Reading, toast: bool) -> None:
        text = self.settings.clipboard_text(reading)
        Gdk.Display.get_default().get_clipboard().set(text)
        if toast:
            self.toasts.add_toast(Adw.Toast(title=f"Copied {text}", timeout=2))

    def _copy_latest(self) -> None:
        if self.history:
            self._copy(self.history[0], toast=True)
            self._latest_copied = True
            self._refresh()

    def _on_clear(self, *_) -> None:
        saved = list(self.history)
        self.history.clear()
        self._refresh()

        def undo(*_):
            self.history = deque(list(self.history) + saved, maxlen=HISTORY_SIZE)
            self._refresh()

        toast = Adw.Toast(title="History cleared", button_label="Undo")
        toast.connect("button-clicked", undo)
        self.toasts.add_toast(toast)

    def _on_close(self, *_) -> bool:
        self.settings.disconnect(self._refresh)
        self.connection.stop()
        return False
