"""Member classification / transverse-line grouping used by the transverse member plots."""
import numpy as np
import xarray as xr

from osdagbridge.core.bridge_types.plate_girder.results_data import (
    classify_members,
    transverse_line_forces,
    transverse_member_lines,
)


def _grid():
    """2 girders (z=0, z=2) x 3 stations (x=0, 5, 10); grillage axes X span, Y up, Z width."""
    nodes = {
        1: [0, 0, 0], 2: [5, 0, 0], 3: [10, 0, 0],      # girder 1
        4: [0, 0, 2], 5: [5, 0, 2], 6: [10, 0, 2],      # girder 2
        7: [0, 0, 1], 8: [5, 0, 1], 9: [10, 0, 1],      # mid nodes of each cross line
    }
    members = {
        10: [1, 2], 11: [2, 3], 12: [4, 5], 13: [5, 6],  # longitudinal
        # cross lines, deliberately listed out of order and with mixed orientation
        20: [8, 5], 21: [2, 8],
        22: [7, 1], 23: [4, 7],
        24: [3, 9], 25: [9, 6],
    }
    return nodes, members


def test_classify_members_splits_girders_from_cross_members():
    nodes, members = _grid()
    longitudinal, transverse = classify_members(nodes, members)
    assert sorted(longitudinal) == [10, 11, 12, 13]
    assert sorted(transverse) == [20, 21, 22, 23, 24, 25]


def test_transverse_lines_ordered_along_span_and_across_width():
    nodes, members = _grid()
    lines = transverse_member_lines(nodes, members)
    # one line per station, sorted by x; first/last are the end diaphragms
    assert lines == [[22, 23], [21, 20], [24, 25]]


def test_line_forces_convert_end_forces_to_internal_forces():
    nodes, members = _grid()
    # constant internal shear of 5 kN on both elements of the x=0 line: OpenSees end forces are +5 / -5 kN
    forces = xr.DataArray(
        np.array([[5000.0, -5000.0], [5000.0, -5000.0]]),
        coords={"Element": [22, 23], "Component": ["Vy_i", "Vy_j"]},
        dims=("Element", "Component"),
    )
    pts = transverse_line_forces(xr.Dataset({"forces": forces}), nodes, members, [22, 23], "Vy_i", "Vy_j")
    assert [z for _, z, _ in pts] == sorted(z for _, z, _ in pts)  # ordered across the width
    assert all(abs(v - 5.0) < 1e-9 for _, _, v in pts)              # no zig-zag


def test_skewed_line_still_grouped():
    nodes, members = _grid()
    nodes[8] = [5.4, 0, 1]  # skew shifts the mid node along the span
    nodes[5] = [5.8, 0, 2]
    lines = transverse_member_lines(nodes, members)
    assert [21, 20] in lines and len(lines) == 3
