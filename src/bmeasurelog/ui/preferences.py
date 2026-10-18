# SPDX-License-Identifier: GPL-3.0-or-later
"""Preferences dialog: units, rounding and clipboard behaviour."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from ..readings import Reading, ReadingKind  # noqa: E402
from ..settings import Settings  # noqa: E402
from ..units import UNITS  # noqa: E402

# Raw sample (base units) used for the live preview rows.
_SAMPLES = {ReadingKind.DISTANCE: (3.97852, "3.97852 m"), ReadingKind.SLOPE: (17.3456, "17.3456\u00b0")}


class _QuantityGroup(Adw.PreferencesGroup):
    """Unit + rounding rows for one kind of reading, with a live preview."""

    def __init__(self, settings: Settings, kind: ReadingKind, title: str) -> None:
        super().__init__(title=title)
        self._settings, self._kind = settings, kind
        self._units = UNITS[kind]
        self._updating = False

        self.unit_row = Adw.ComboRow(
            title="Unit", model=Gtk.StringList.new([u.name for u in self._units])
        )
        self.step_row = Adw.ComboRow(title="Round to", subtitle="Nearest multiple of")
        self.preview_row = Adw.ActionRow(css_classes=["property"])
        for row in (self.unit_row, self.step_row, self.preview_row):
            self.add(row)

        self.sync()
        self.unit_row.connect("notify::selected", self._on_unit)
        self.step_row.connect("notify::selected", self._on_step)

    def sync(self) -> None:
        """Pull current values from settings into the widgets."""
        self._updating = True
        unit = self._settings.unit_for(self._kind)
        self.unit_row.set_selected(self._units.index(unit))
        self.step_row.set_model(Gtk.StringList.new([s.label for s in unit.steps]))
        step = unit.find_step(self._settings.step_for(self._kind))
        self.step_row.set_selected(unit.steps.index(step) if step else 0)
        value, raw = _SAMPLES[self._kind]
        self.preview_row.set_title(self._settings.format(Reading(self._kind, value)))
        self.preview_row.set_subtitle(f"Preview of {raw}")
        self._updating = False

    def _on_unit(self, *_) -> None:
        if not self._updating:
            unit = self._units[self.unit_row.get_selected()]
            self._settings.update(**{f"{self._kind.value}_unit": unit.id})

    def _on_step(self, *_) -> None:
        if not self._updating:
            unit = self._settings.unit_for(self._kind)
            index = self.step_row.get_selected()
            if index < len(unit.steps):
                self._settings.update(**{f"{self._kind.value}_step": unit.steps[index].value})


class PreferencesDialog(Adw.PreferencesDialog):
    def __init__(self, settings: Settings) -> None:
        super().__init__(title="Preferences")
        self._settings = settings

        page = Adw.PreferencesPage()
        self.add(page)

        self._groups = [
            _QuantityGroup(settings, ReadingKind.DISTANCE, "Distance"),
            _QuantityGroup(settings, ReadingKind.SLOPE, "Slope"),
        ]
        for group in self._groups:
            page.add(group)

        clipboard = Adw.PreferencesGroup(title="Clipboard")
        self.auto_row = Adw.SwitchRow(
            title="Copy Automatically", subtitle="Copy every new reading to the clipboard"
        )
        self.unit_row = Adw.SwitchRow(
            title="Include Unit", subtitle="Copy \u201c3.980 m\u201d instead of \u201c3.980\u201d"
        )
        clipboard.add(self.auto_row)
        clipboard.add(self.unit_row)
        page.add(clipboard)

        self._sync()
        self.auto_row.connect(
            "notify::active", lambda r, _p: settings.update(auto_copy=r.get_active())
        )
        self.unit_row.connect(
            "notify::active", lambda r, _p: settings.update(copy_with_unit=r.get_active())
        )

        settings.connect(self._sync)
        self.connect("closed", lambda *_: settings.disconnect(self._sync))

    def _sync(self) -> None:
        for group in self._groups:
            group.sync()
        self.auto_row.set_active(self._settings.options.auto_copy)
        self.unit_row.set_active(self._settings.options.copy_with_unit)
