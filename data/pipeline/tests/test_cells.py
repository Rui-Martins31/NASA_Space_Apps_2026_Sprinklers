"""Funcoes de celula acrescentadas a common.py: cell_to_ids, cell_center, lat_band, coarsen_cell."""
import numpy as np
import pytest

from metrics.common import (GLOBAL_CELL, cell_center, cell_ids, cell_key, cell_to_ids,
                            coarsen_cell, lat_band)


@pytest.mark.parametrize("grid", [0.1, 0.05, 0.01])
def test_cell_to_ids_inverts_cell_key(grid):
    lat = np.array([-89.9999, -33.3333, 0.0, 38.7223, 90.0])
    lon = np.array([-179.9999, -9.1393, 0.0, 120.5, 180.0])
    ilat, ilon = cell_ids(lat, lon, grid)
    back = cell_to_ids(cell_key(lat, lon, grid), grid)
    assert (back[0] == ilat).all() and (back[1] == ilon).all()


def test_cell_to_ids_rejects_global_and_out_of_grid():
    with pytest.raises(ValueError, match="fora da grelha"):
        cell_to_ids([GLOBAL_CELL])
    with pytest.raises(ValueError, match="fora da grelha"):
        cell_to_ids([1800 * 3600])


def test_cell_center_is_inside_its_own_cell():
    lat = np.array([38.7223, -33.3333, 0.0001, 89.9999])
    lon = np.array([-9.1393, 151.2, -0.0001, 179.9999])
    for grid in (0.1, 0.01):
        clat, clon = cell_center(cell_key(lat, lon, grid), grid)
        assert (np.abs(clat - lat) <= grid / 2 + 1e-9).all()
        assert (np.abs(clon - lon) <= grid / 2 + 1e-9).all()
        # o centro de uma celula cai na mesma celula
        assert (cell_key(clat, clon, grid) == cell_key(lat, lon, grid)).all()


def test_cell_center_exact_values():
    # celula (ilat=1, ilon=0) a 0.1: lat 90 - 89.9 ... centro lat = -89.95, lon = -179.95
    key = cell_key([-89.9], [-180.0], 0.1)
    assert cell_center(key, 0.1) == (pytest.approx([-89.85]), pytest.approx([-179.95]))


def test_lat_band_ranges_and_boundaries():
    ilat = np.array([0, 999, 1000, 17999])
    assert lat_band(ilat, 0.01).tolist() == [0, 0, 1, 17]
    assert lat_band(np.array([0, 99, 100, 1799]), 0.1).tolist() == [0, 0, 1, 17]


def test_coarsen_cell_maps_fine_cells_to_the_containing_coarse_cell():
    lat = np.array([38.7223, 38.7299, 38.7301, -9.99, 89.9999])
    lon = np.array([-9.1393, -9.1301, -9.1299, 10.01, 179.9999])
    fine = cell_key(lat, lon, 0.01)
    assert (coarsen_cell(fine, 0.01, 0.1) == cell_key(lat, lon, 0.1)).all()
    assert (coarsen_cell(fine, 0.01, 0.01) == fine).all()


def test_coarsen_cell_rejects_non_multiple():
    with pytest.raises(ValueError, match="multiplo"):
        coarsen_cell([0], 0.1, 0.05)
