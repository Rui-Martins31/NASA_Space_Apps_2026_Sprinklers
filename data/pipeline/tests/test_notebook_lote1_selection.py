"""Execute L1 notebook cells with sensor/year selections and stale caches."""

import ast
import contextlib
import io
import json
from pathlib import Path

import pandas as pd
import pytest


def cells():
    repo = Path(__file__).resolve().parents[3]
    notebook = json.loads((repo / "data/pipeline/notebooks/02_metrics_lote1.ipynb").read_text(encoding="utf-8"))
    sources = {}
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] == "code":
            source = "".join(cell["source"])
            ast.parse(source)
            sources[index] = source
    return repo, sources


def fixture(root):
    processed = root / "processed"
    metrics = root / "metrics"
    processed.mkdir()
    metrics.mkdir()
    for sensor, instrument, satellite, latitude in [
        ("modis", "MODIS", "Terra", 0.0),
        ("viirs-jpss1", "VIIRS", "N20", 1.0),
        ("viirs-snpp", "VIIRS", "N", 2.0),
    ]:
        for year in [2018, 2020]:
            source = pd.DataFrame(dict(country=["Portugal"], instrument=[instrument],
                                       satellite=[satellite], latitude=[latitude], longitude=[0.0],
                                       acq_date=[f"{year}-01-01"], type=pd.Series([0], dtype="Int8"),
                                       confidence_class=pd.Series(["h"], dtype="string")))
            source.to_parquet(processed / f"{sensor}_{year}.parquet", index=False)
    return processed, metrics


def run_selected(namespace, source):
    with contextlib.redirect_stdout(io.StringIO()):
        for index in [4, 5, 7]:
            exec(source[index], namespace)


def test_default_selection_excludes_snpp_and_old_partials(tmp_path):
    repo, source = cells()
    processed, metrics = fixture(tmp_path)
    namespace = dict(PROCESSED=processed, METRICS=metrics, REPO=repo, display=lambda value: None)
    exec(source[2], namespace)
    assert namespace["SENSORS"] == {"modis", "viirs-jpss1"}
    exec(source[3], namespace)
    stale = metrics / "_partial_lote1/viirs-snpp_2018"
    stale.mkdir()
    (stale / "_done.json").write_text(json.dumps(dict(sensor="viirs-snpp", year=2018, grid_deg=0.1)))
    # Deliberately incomplete old S-NPP cache must never be read.
    pd.DataFrame(dict(country=["Wrong"], date=pd.to_datetime(["2018-01-01"]), series=["viirs"], n_cells=[999])).to_parquet(
        metrics / "_partial_lote1/cal_daily_2018.parquet", index=False)
    run_selected(namespace, source)
    assert set(namespace["log"].sensor) == {"modis", "viirs-jpss1"}
    assert set(namespace["final"]["l1_obs01_raw_counts"].satellite) == {"Terra", "N20"}
    assert namespace["daily"].country.unique().tolist() == ["Portugal"]
    assert namespace["daily"].groupby("series", observed=True).n_cells.sum().to_dict() == {
        "combined": 4, "modis": 2, "viirs": 2,
    }
    assert set(namespace["monthly"].year) == {2018, 2020}

    # Change the selection without deleting any previous source/year caches.
    namespace.update(SENSORS={"modis"}, YEARS={2018})
    run_selected(namespace, source)
    assert namespace["log"].sensor.tolist() == ["modis"]
    assert namespace["log"].year.tolist() == [2018]
    assert namespace["daily"].series.tolist() == ["combined", "modis"]
    assert namespace["daily"].n_cells.tolist() == [1, 1]
    assert namespace["monthly"].year.unique().tolist() == [2018]
    assert namespace["cov"].instrument.unique().tolist() == ["MODIS"]
    params = json.loads((metrics / "_params_lote1.json").read_text())
    assert params["sensors"] == ["modis"]
    assert params["years"] == [2018]


def test_reuse_checks_source_metadata_and_missing_outputs(tmp_path):
    repo, source = cells()
    processed, metrics = fixture(tmp_path)
    namespace = dict(PROCESSED=processed, METRICS=metrics, REPO=repo, display=lambda value: None)
    exec(source[2], namespace)
    exec(source[3], namespace)
    namespace.update(SENSORS={"modis"}, YEARS={2018})
    run_selected(namespace, source)
    part = metrics / "_partial_lote1/modis_2018/obs01.parquet"
    original_time = part.stat().st_mtime_ns
    run_selected(namespace, source)
    assert part.stat().st_mtime_ns == original_time
    frame = pd.read_parquet(processed / "modis_2018.parquet")
    frame.loc[1] = frame.iloc[0]
    frame.to_parquet(processed / "modis_2018.parquet", index=False)
    run_selected(namespace, source)
    assert namespace["final"]["l1_obs01_raw_counts"].n_raw.sum() == 2
    part.unlink()
    run_selected(namespace, source)
    assert part.exists()
    marker = metrics / "_partial_lote1/modis_2018/_done.json"
    marker.write_text("{")
    run_selected(namespace, source)
    assert json.loads(marker.read_text())["sensor"] == "modis"


def test_unsupported_or_missing_selection_is_clear(tmp_path):
    repo, source = cells()
    processed, metrics = fixture(tmp_path)
    namespace = dict(PROCESSED=processed, METRICS=metrics, REPO=repo, display=lambda value: None)
    exec(source[2], namespace)
    exec(source[3], namespace)
    namespace["SENSORS"] = {"viirs-snpp"}
    with pytest.raises(ValueError, match="09_har12_snpp"):
        run_selected(namespace, source)
    namespace.update(SENSORS={"modis"}, YEARS={1999})
    with pytest.raises(FileNotFoundError, match="selected"):
        run_selected(namespace, source)


def test_selected_files_without_valid_dates_fail_clearly(tmp_path):
    repo, source = cells()
    processed, metrics = fixture(tmp_path)
    frame = pd.read_parquet(processed / "modis_2018.parquet").iloc[:0]
    frame.to_parquet(processed / "modis_2018.parquet", index=False)
    namespace = dict(PROCESSED=processed, METRICS=metrics, REPO=repo, display=lambda value: None)
    exec(source[2], namespace)
    exec(source[3], namespace)
    namespace.update(SENSORS={"modis"}, YEARS={2018})
    with pytest.raises(ValueError, match="no valid acquisition dates"):
        run_selected(namespace, source)
