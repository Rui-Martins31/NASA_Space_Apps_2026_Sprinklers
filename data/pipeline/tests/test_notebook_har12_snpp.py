"""Run the isolated S-NPP notebook and verify L7 can reuse its model inputs."""

import ast
import contextlib
import io
import json
from pathlib import Path

import pandas as pd
import pytest


def processed_year(root, sensor, year):
    dates = pd.date_range(f"{year}-01-01", f"{year}-12-31")
    latitudes = [0.0] if sensor == "modis" else [0.0, 0.11]
    frame = pd.DataFrame([
        ["Portugal", "MODIS" if sensor == "modis" else "VIIRS",
         "Terra" if sensor == "modis" else "N", latitude, 0.0,
         date.strftime("%Y-%m-%d"), 0, "h" if date.day <= 8 else "l"]
        for date in dates for latitude in latitudes
    ], columns=["country", "instrument", "satellite", "latitude", "longitude",
                "acq_date", "type", "confidence_class"])
    frame["type"] = frame["type"].astype("Int8")
    frame["confidence_class"] = frame.confidence_class.astype("string")
    frame.to_parquet(root / "processed" / f"{sensor}_{year}.parquet", index=False)


def sources(path):
    notebook = json.loads(path.read_text(encoding="utf-8"))
    result = []
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == []
            assert cell["execution_count"] is None
            code = "".join(cell["source"])
            ast.parse(code)
            result.append(code)
    return result


def test_isolated_snpp_notebook_estimates_step_and_l7_reuses_it(tmp_path):
    repo = Path(__file__).resolve().parents[3]
    (tmp_path / "processed").mkdir()
    (tmp_path / "metrics").mkdir()
    for year in list(range(2007, 2012)) + [2018, 2019, 2020, 2021]:
        processed_year(tmp_path, "modis", year)
    for year in [2012, 2013, 2014, 2015, 2018, 2020, 2021]:
        processed_year(tmp_path, "viirs-snpp", year)
    metrics = tmp_path / "metrics"
    # Existing NOAA-20 products must retain their bytes.
    baseline_path = metrics / "l6_har06_factor.parquet"
    pd.DataFrame({"country": ["Portugal"], "factor_used": [9.0]}).to_parquet(baseline_path, index=False)
    baseline_bytes = baseline_path.read_bytes()
    code = sources(repo / "data/pipeline/notebooks/09_har12_snpp.ipynb")
    namespace = dict(ROOT=tmp_path, REPO=repo)
    with contextlib.redirect_stdout(io.StringIO()):
        for cell in code[1:]:
            exec(compile(cell, "09_har12_snpp.ipynb", "exec"), namespace)
    result = namespace["result"]
    country = result.loc[result.country.eq("Portugal")].iloc[0]
    assert country.status == "ok"
    assert country.factor_used == 2.0
    assert country.step_raw == pytest.approx(8.0, abs=1e-9)
    assert country.step_adjusted == pytest.approx(0.0, abs=1e-9)
    assert country.n_pre_months == 60
    assert country.n_post_months == 48
    params = json.loads((metrics / "_params_har12_snpp.json").read_text(encoding="utf-8"))
    assert params["missing_years"]["viirs-snpp"] == [2016, 2019]
    assert baseline_path.read_bytes() == baseline_bytes
    assert not list(metrics.glob("*.tmp"))
    original_writer = namespace["atomic_parquet"]

    def interrupted_writer(frame, path):
        if path.name == "l7_har12_snpp_factor.parquet":
            raise OSError("simulated interrupted bundle export")
        original_writer(frame, path)

    namespace["atomic_parquet"] = interrupted_writer
    with pytest.raises(OSError, match="interrupted bundle"):
        exec(code[3], namespace)
    assert not (metrics / "_params_har12_snpp.json").exists()
    namespace["atomic_parquet"] = original_writer
    with contextlib.redirect_stdout(io.StringIO()):
        exec(code[3], namespace)
    assert (metrics / "_params_har12_snpp.json").is_file()

    # Execute L7's actual summary/export cells with the isolated S-NPP sidecars.
    # Its ordinary error and sensitivity inputs remain the separate NOAA-20 fixture.
    from test_notebook_lote7 import synthetic_inputs, notebook_sources

    noaa_root = tmp_path / "noaa"
    noaa_root.mkdir()
    synthetic_inputs(noaa_root, empty=False)
    for name in ["l7_har12_snpp_monthly.parquet", "l7_har12_snpp_factor.parquet", "_params_har12_snpp.json"]:
        (noaa_root / "metrics" / name).write_bytes((metrics / name).read_bytes())
    _, l7_code = notebook_sources()
    l7 = dict(ROOT=noaa_root, REPO=repo)
    with contextlib.redirect_stdout(io.StringIO()):
        for cell in l7_code[1:]:
            exec(compile(cell, "08_metrics_lote7.ipynb", "exec"), l7)
    updated = l7["tables"]["l7_har12_residual_step"]
    assert updated.status.eq("ok").all()
    assert updated.step_adjusted.tolist() == pytest.approx([0.0, 0.0], abs=1e-9)
    assert updated.reference_sensor.eq("viirs-snpp").all()


def test_snpp_notebook_requires_processed_inputs(tmp_path):
    repo = Path(__file__).resolve().parents[3]
    code = sources(repo / "data/pipeline/notebooks/09_har12_snpp.ipynb")
    namespace = dict(ROOT=tmp_path, REPO=repo)
    exec(code[1], namespace)
    with pytest.raises(FileNotFoundError, match="processed modis.*notebook 01"):
        exec(code[2], namespace)
