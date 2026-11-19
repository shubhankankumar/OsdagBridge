"""
In-place editing of dimension labels on the QPainter-drawn 2D CAD views.

Double-click an editable label (e.g. "Span Length = 20.0 m"): a line edit
replaces it, Enter / clicking outside applies the value, Esc cancels. The
widget only emits ``dimension_edited(key, value)``; validation and the input
dictionary update are done by the owner (template page), so the CAD and the
input dock follow one set of rules.
"""
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import QLineEdit, QToolTip

from osdagbridge.core.utils.common import (
    KEY_CARRIAGEWAY_WIDTH,
    KEY_SPAN,
    KEY_TS_DECK_THICKNESS,
    KEY_TS_GIRDER_SPACING,
)
from osdagbridge.desktop.ui.utils.custom_cursors import pointing_hand_cursor

# CAD label -> (input dict key, CAD param name, factor from CAD param (mm) to input dict units)
EDITABLE_DIMENSIONS = {
    "Carriageway Width": (KEY_CARRIAGEWAY_WIDTH, "carriageway_width", 1e-3),  # m
    "Girder Spacing":    (KEY_TS_GIRDER_SPACING, "girder_spacing",    1e-3),  # m
    "Deck Thickness":    (KEY_TS_DECK_THICKNESS, "deck_thickness",    1.0),   # mm
    "Span Length":       (KEY_SPAN,              "span_length",       1e-3),  # m
}

# Derived from the editable values above; editing them too would over-constrain the layout.
LOCKED_DIMENSIONS = ("Overhang", "Overall Bridge Width", "Bracing Spacing")


def label_name(text: str) -> str:
    """'Girder\\nSpacing\\n= 1.97 m' -> 'Girder Spacing'."""
    return " ".join(str(text).split()).split("=")[0].strip()


class _DimensionLineEdit(QLineEdit):
    cancelled = Signal()
    focus_lost = Signal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.cancelled.emit()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        # editingFinished is skipped on focus-out when the text is not yet valid ("", ".")
        super().focusOutEvent(event)
        self.focus_lost.emit()


class CadDimensionEditMixin:
    """
    Mixin for the QPainter CAD widgets. The host class must:
      * declare ``dimension_edited = Signal(str, float)``
      * keep its geometry in ``self.params`` (mm)
      * call ``_reset_label_regions()`` at the start of ``paintEvent``
      * call ``_register_label_region(painter, rect, text)`` for every drawn label
    Editing is off until ``dimension_editing_enabled`` is set True, so preview
    copies of the CAD (e.g. inside Additional Inputs) stay read-only.
    """

    dimension_editing_enabled = False

    def _reset_label_regions(self):
        self._label_regions = []

    def _register_label_region(self, painter, rect, text):
        # Off-screen renders (report images) use a different coordinate system.
        if painter.device() is not self:
            return
        if not hasattr(self, "_label_regions"):
            self._label_regions = []
        self._label_regions.append((QRectF(rect), label_name(text)))

    def _label_at(self, pos):
        for rect, name in reversed(getattr(self, "_label_regions", [])):
            if rect.contains(pos):
                return rect, name
        return None, ""

    def _update_label_cursor(self, pos):  # hand cursor over editable labels; call from mouseMoveEvent
        editable = self.dimension_editing_enabled and self._label_at(pos)[1] in EDITABLE_DIMENSIONS
        if editable:
            self.setCursor(pointing_hand_cursor())
        else:
            self.unsetCursor()

    def mousePressEvent(self, event):
        # Clicking the canvas applies an open edit even if the canvas does not take focus
        self._close_dimension_editor(commit=True)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if not self.dimension_editing_enabled:
            return super().mouseDoubleClickEvent(event)
        rect, name = self._label_at(event.position())
        if name in EDITABLE_DIMENSIONS:
            self._open_dimension_editor(rect, name)
        elif name in LOCKED_DIMENSIONS:
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"{name} is derived from other inputs and cannot be edited here.",
                self,
            )
        else:
            super().mouseDoubleClickEvent(event)

    def _open_dimension_editor(self, rect: QRectF, name: str):
        self._close_dimension_editor(commit=False)
        key, param, factor = EDITABLE_DIMENSIONS[name]

        editor = _DimensionLineEdit(self)
        editor.setValidator(QDoubleValidator(0.0, 1e6, 3, editor))
        editor.setAlignment(Qt.AlignCenter)
        editor.setToolTip(f"{name}: Enter to apply, Esc to cancel")
        editor.setStyleSheet("QLineEdit { border: 1px solid #90AF13; background: white; }")
        current = float(self.params.get(param, 0.0)) * factor
        editor.setText(f"{current:.3f}".rstrip("0").rstrip("."))
        width = max(int(rect.width()), 90)
        editor.setGeometry(int(rect.center().x() - width / 2), int(rect.top()), width, max(int(rect.height()), 22))

        self._dim_editor = (editor, key)
        editor.editingFinished.connect(lambda: self._close_dimension_editor(commit=True))  # Enter or focus out
        editor.cancelled.connect(lambda: self._close_dimension_editor(commit=False))
        editor.focus_lost.connect(lambda: self._close_dimension_editor(commit=True))
        editor.show()
        editor.setFocus()
        editor.selectAll()

    def _close_dimension_editor(self, commit: bool):
        state = getattr(self, "_dim_editor", None)
        if state is None:
            return
        self._dim_editor = None  # set first: hiding the editor fires editingFinished again
        editor, key = state
        text = editor.text().strip()
        editor.hide()
        editor.deleteLater()
        self.update()
        if commit and text:
            try:
                value = float(text)
            except ValueError:
                return
            self.dimension_edited.emit(key, value)
