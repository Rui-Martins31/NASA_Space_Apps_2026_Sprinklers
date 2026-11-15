"""query_area.py (consulta por circulo ao esquema por celula) e publish_metrics.py."""
import importlib.util
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from metrics.common import cell_center, cell_key
from metrics.store import ParquetSink, write_table

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


query_area, publish_metrics = load("query_area"), load("publish_metrics")

LISBON = (38.72, -9.14)


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * query_area.EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def build_monthly(root, grid=0.01):
    """Grelha 12x12 km a volta de Lisboa mais celulas longe (Porto, Sydney); 2 series, 2 anos."""
    rng = np.random.default_rng(7)
    lats = np.round(np.arange(38.60, 38.84, 0.02), 4)
    lons = np.round(np.arange(-9.30, -8.98, 0.02), 4)
    pts = [(la, lo) for la in lats for lo in lons] + [(41.15, -8.61), (-33.87, 151.21)]
    rows = []
    for la, lo in pts:
        cell = int(cell_key([la], [lo], grid)[0])
        for series in ("modis", "combined"):
            for year in (2019, 2020):
                for month in (1, 7):
                    rows.append((cell, series, year, month, int(rng.integers(1, 9))))
    df = pd.DataFrame(rows, columns=["cell", "series", "year", "month", "cell_days"])
    write_table(ParquetSink(root), "l1_cal_monthly", df, grid_deg=grid, sort_by=["series", "year", "month"])
    return df


def brute_force(df, grid, lat, lon, radius, series):
    clat, clon = cell_center(df["cell"].to_numpy(), grid)
    d = np.array([haversine(lat, lon, a, b) for a, b in zip(clat, clon)])
    sub = df[(d <= radius) & (df["series"] == series)]
    return sub.groupby(["year", "month"]).agg(cell_days=("cell_days", "sum"), n_cells=("cell", "nunique")).reset_index()


@pytest.mark.parametrize("radius", [5, 12, 30])
def test_area_series_matches_brute_force(tmp_path, radius):
    df = build_monthly(tmp_path)
    got = query_area.area_monthly_series(tmp_path, "l1_cal_monthly", *LISBON, radius, "combined")
    want = brute_force(df, 0.01, *LISBON, radius, "combined")
    assert len(want) > 0
    pd.testing.assert_frame_equal(got, want.astype(got.dtypes.to_dict()), check_like=True)


def test_area_excludes_far_cells_and_other_series(tmp_path):
    build_monthly(tmp_path)
    got = query_area.area_monthly_series(tmp_path, "l1_cal_monthly", *LISBON, 100, "modis")
    all_modis = ParquetSink(tmp_path).read("l1_cal_monthly", filters=[("series", "==", "modis")])
    lisbon_cells = all_modis[all_modis["lat"].between(38.5, 39.0)]
    assert got["cell_days"].sum() == lisbon_cells["cell_days"].sum()  # Porto e Sydney ficam fora


def test_area_with_no_cells_is_empty(tmp_path):
    build_monthly(tmp_path)
    assert len(query_area.area_monthly_series(tmp_path, "l1_cal_monthly", 0.0, -30.0, 10, "combined")) == 0


def test_bounding_box_contains_circle_and_handles_edges():
    la0, la1, lo0, lo1 = query_area.bounding_box(*LISBON, 20)
    assert la0 < 38.72 - 20 / 111.2 + 1e-3 and lo1 > -9.14
    assert query_area.bounding_box(89.9, 0.0, 50)[2:] == (-180.0, 180.0)      # polo
    assert query_area.bounding_box(0.0, 179.9, 50)[2:] == (-180.0, 180.0)     # antimeridiano


def test_publish_copies_only_final_tables_and_replaces(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    sink = ParquetSink(src)
    write_table(sink, "l1_cal_monthly", build_monthly(tmp_path / "x"), grid_deg=0.01, sort_by=["series"])
    sink.write("_runs", pd.DataFrame({"lote": ["lote1"]}), ())
    (src / "_partial_lote1").mkdir()
    (src / "_partial_lote1" / "cache.parquet").write_bytes(b"x")
    (src / "_l2_parts").mkdir()
    (src / "t.tmp").mkdir()
    assert publish_metrics.publish(src, dst) == ["_runs", "l1_cal_monthly"]
    assert sorted(p.name for p in dst.iterdir()) == ["_runs", "l1_cal_monthly"]
    # republicar substitui sem deixar sobras
    write_table(sink, "l1_cal_monthly", build_monthly(tmp_path / "y").iloc[:4], grid_deg=0.01)
    publish_metrics.publish(src, dst)
    assert len(ParquetSink(dst).read("l1_cal_monthly")) == 4
    assert sorted(p.name for p in dst.iterdir()) == ["_runs", "l1_cal_monthly"]


def test_publish_errors(tmp_path):
    with pytest.raises(FileNotFoundError, match="inexistente"):
        publish_metrics.publish(tmp_path / "nada", tmp_path / "d")
    (tmp_path / "vazia").mkdir()
    with pytest.raises(ValueError, match="nenhuma tabela"):
        publish_metrics.publish(tmp_path / "vazia", tmp_path / "d")
