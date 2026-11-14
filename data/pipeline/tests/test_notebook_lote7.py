"""Execute the L7 notebook's real cells using synthetic L1/L6/processed inputs."""

import ast
import contextlib
import io
import json
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from metrics.harmonization_factor import har06_factor


def synthetic_inputs(root, empty):
    processed = root / "processed"
    metrics = root / "metrics"
    processed.mkdir()
    metrics.mkdir()
    records = []
    for year in [2018, 2019, 2022]:
        for month in range(1, 13):
            for series in ["modis", "viirs"]:
                records.append(["Portugal", year, month, series, 2, False, 0])
        for sensor, instrument, confidences in [
            ("modis", "MODIS", ["h", "n"]),
            ("viirs-jpss1", "VIIRS", ["h", "n", "l"]),
        ]:
            rows = [
                ["Portugal", instrument, "Terra" if instrument == "MODIS" else "N20",
                 index * 0.11, 0.0, f"{year}-{month:02d}-01", 0, confidence]
                for month in range(1, 13) for index, confidence in enumerate(confidences)
            ]
            frame = pd.DataFrame(rows, columns=[
                "country", "instrument", "satellite", "latitude", "longitude",
                "acq_date", "type", "confidence_class",
            ])
            frame["type"] = frame["type"].astype("Int8")
            frame["confidence_class"] = frame.confidence_class.astype("string")
            if empty:
                frame = frame.iloc[:0]
            frame.to_parquet(processed / f"{sensor}_{year}.parquet", index=False)
    monthly = pd.DataFrame(records, columns=[
        "country", "year", "month", "series", "cell_days", "partial", "n_unknown_days",
    ])
    if empty:
        monthly = monthly.iloc[:0]
    monthly.to_parquet(metrics / "l1_cal_monthly.parquet", index=False)
    har06_factor(monthly).to_parquet(metrics / "l6_har06_factor.parquet", index=False)


def notebook_sources():
    repo = Path(__file__).resolve().parents[3]
    notebook = json.loads((repo / "data/pipeline/notebooks/08_metrics_lote7.ipynb").read_text(encoding="utf-8"))
    sources = []
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == []
            assert cell["execution_count"] is None
            source = "".join(cell["source"])
            ast.parse(source)
            sources.append(source)
    assert "metricas-pipeline" in sources[0]
    return repo, sources


@pytest.mark.parametrize("empty", [False, True])
def test_actual_notebook_roundtrip_resume_and_input_errors(tmp_path, empty):
    repo, sources = notebook_sources()
    synthetic_inputs(tmp_path, empty)
    metrics = tmp_path / "metrics"
    monthly_path = metrics / "l1_cal_monthly.parquet"
    factor_path = metrics / "l6_har06_factor.parquet"
    monthly_bytes, factor_bytes = monthly_path.read_bytes(), factor_path.read_bytes()
    namespace = dict(ROOT=tmp_path, REPO=repo)
    with contextlib.redirect_stdout(io.StringIO()):
        for source in sources[1:]:
            exec(compile(source, "08_metrics_lote7.ipynb", "exec"), namespace)
        assert len(namespace["tables"]) == 7
        for name, expected in namespace["tables"].items():
            actual = pd.read_parquet(metrics / f"{name}.parquet")
            text = {column: "object" for column in expected.columns
                    if pd.api.types.is_object_dtype(expected[column].dtype)}
            assert_frame_equal(actual.astype(text), expected)
        if not empty:
            assert namespace["tables"]["l7_har08_mae"].mae_adjusted.tolist() == [0.0, 0.0]
            assert namespace["tables"]["l7_har12_residual_step"].status.eq("not_applicable").all()
            grids = namespace["tables"]["l7_har13_grid_sensitivity"]
            grid = grids.loc[grids.country.eq("Portugal")].set_index("variant")
            assert grid.loc["grid_0.1", "sum_modis"] == 24
            assert grid.loc["grid_0.25", "sum_modis"] == 12
            assert grid.loc["grid_0.25", "delta_modis_pct"] == -50.0
            confidence = namespace["tables"]["l7_har14_confidence_sensitivity"]
            confidence = confidence.loc[confidence.country.eq("Portugal")].set_index("variant")
            assert confidence.loc["all_confidence", "sum_viirs"] == 36
            assert confidence.loc["high_only", "sum_viirs"] == 12
            assert confidence.loc["all_confidence", "factor_used"] == 1.5
        part = metrics / "_partial_lote7/monthly_2018.parquet"
        marker = metrics / "_partial_lote7/2018.json"
        unchanged = part.stat().st_mtime_ns
        exec(sources[3], namespace)
        assert part.stat().st_mtime_ns == unchanged
        marker.write_text("{", encoding="utf-8")
        exec(sources[3], namespace)
        assert "variants" in json.loads(marker.read_text(encoding="utf-8"))
        part.unlink()
        exec(sources[3], namespace)
        assert part.is_file()
        namespace["FORCE"] = True
        exec(sources[3], namespace)
        namespace["FORCE"] = False
        for source in sources[4:]:
            exec(source, namespace)
    assert len(list(metrics.glob("l7_*.parquet"))) == 7
    assert not list(metrics.rglob("*.tmp"))
    assert monthly_path.read_bytes() == monthly_bytes
    assert factor_path.read_bytes() == factor_bytes
    log = pd.read_csv(metrics / "_log_lote7.csv")
    assert len(log) == 7
    parameters = json.loads(log.parameters.iloc[0])
    assert parameters["cal_end"] == 2021
    assert parameters["test_start"] == 2022
    factor_path.unlink()
    with pytest.raises(FileNotFoundError, match="notebooks 02 and 07.*l6_har06_factor"):
        exec(sources[2], namespace)
    factor_path.write_bytes(factor_bytes)
    (tmp_path / "processed/viirs-jpss1_2018.parquet").unlink()
    with pytest.raises(FileNotFoundError, match="Missing processed counterparts.*viirs-jpss1_2018"):
        exec(sources[2], namespace)
