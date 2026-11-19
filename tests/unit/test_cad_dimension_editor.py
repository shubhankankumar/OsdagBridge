"""Label parsing for double-click editing of 2D CAD dimensions."""
from osdagbridge.core.utils.common import KEY_SPAN, KEY_TS_DECK_THICKNESS
from osdagbridge.desktop.ui.docks.cad_dimension_editor import (
    EDITABLE_DIMENSIONS,
    LOCKED_DIMENSIONS,
    label_name,
)


def test_label_name_handles_single_and_multiline_labels():
    assert label_name("Span Length = 20.0 m") == "Span Length"
    assert label_name("Girder\nSpacing\n= 1.97 m") == "Girder Spacing"
    assert label_name("Deck Thickness") == "Deck Thickness"  # before values are shown


def test_editable_and_locked_sets():
    assert set(EDITABLE_DIMENSIONS) == {"Carriageway Width", "Girder Spacing", "Deck Thickness", "Span Length"}
    assert not set(EDITABLE_DIMENSIONS) & set(LOCKED_DIMENSIONS)
    assert EDITABLE_DIMENSIONS["Span Length"][0] == KEY_SPAN
    # deck thickness is stored in mm in the input dict, the CAD keeps mm too
    assert EDITABLE_DIMENSIONS["Deck Thickness"][::2] == (KEY_TS_DECK_THICKNESS, 1.0)
