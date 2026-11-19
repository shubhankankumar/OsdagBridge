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


def _forces(rows, components):
    tags = list(rows)
    return xr.Dataset({"forces": xr.DataArray(
        np.array([rows[t] for t in tags]),
        coords={"Element": tags, "Component": components},
        dims=("Element", "Component"),
    )})


def test_line_forces_convert_end_forces_to_internal_forces():
    nodes, members = _grid()
    members[23] = [7, 4]  # 22 runs -Z (z 1 -> 0), 23 runs +Z (z 1 -> 2)
    # Same 5 kN internal shear in both: end forces are +5/-5 kN along +Z, -5/+5 kN along -Z
    ds = _forces({22: [-5000.0, 5000.0], 23: [5000.0, -5000.0]}, ["Vy_i", "Vy_j"])
    pts = transverse_line_forces(ds, nodes, members, [22, 23], "Vy_i", "Vy_j")
    assert [z for _, z, _ in pts] == sorted(z for _, z, _ in pts)  # ordered across the width
    assert all(abs(v - 5.0) < 1e-9 for _, _, v in pts)              # no zig-zag, no sign flip


def test_transverse_bending_read_from_global_mx():
    # Cross member 73 of the 22 m test bridge (SW load case), runs +Z, L = 2.433 m.
    # Global Mx is its vertical bending; global Mz (its torsion) is 0.
    from osdagbridge.core.bridge_types.plate_girder.plot_generator import transverse_line_values
    nodes = {1: [5.0, 0.0, 0.0], 2: [5.0, 0.0, 2.433]}
    members = {73: [1, 2]}
    ds = _forces({73: [-790.0, 2522.0, -712.0, 712.0, 0.0, 0.0]},
                 ["Mx_i", "Mx_j", "Vy_i", "Vy_j", "Mz_i", "Mz_j"])
    _, _, m = transverse_line_values(ds, "Mz", nodes, members, [73])
    _, _, v = transverse_line_values(ds, "Fy", nodes, members, [73])
    _, _, t = transverse_line_values(ds, "Mx", nodes, members, [73])
    assert np.allclose(m, [0.790, 2.522])
    assert np.isclose(m[1] - m[0], abs(v[0]) * 2.433, atol=1e-3)  # dM = V * L
    assert np.allclose(t, 0.0)


def test_skewed_line_still_grouped():
    nodes, members = _grid()
    nodes[8] = [5.4, 0, 1]  # skew shifts the mid node along the span
    nodes[5] = [5.8, 0, 2]
    lines = transverse_member_lines(nodes, members)
    assert [21, 20] in lines and len(lines) == 3
