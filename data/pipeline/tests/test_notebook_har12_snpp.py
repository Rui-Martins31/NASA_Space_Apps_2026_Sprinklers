"""Executa o notebook 09 (HAR-12 com S-NPP isolado, serie global) e verifica que o notebook 08 reaproveita as entradas."""

import ast
import contextlib
import io
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from metrics.common import GLOBAL_CELL
from metrics.store import ParquetSink, write_table
from test_notebook_lote7 import notebook_sources as lote7_sources
from test_notebook_lote7 import synthetic_inputs

SIDECARS = ["l7_har12_snpp_monthly", "l7_har12_snpp_factor"]


def processed_year(root, sensor, year):
    dates = pd.date_range(f"{year}-01-01", f"{year}-12-31")
    latitudes = [0.0] if sensor == "modis" else [0.0, 0.11]
    frame = pd.DataFrame([
        ["MODIS" if sensor == "modis" else "VIIRS", "Terra" if sensor == "modis" else "N", latitude, 0.0,
         date.strftime("%Y-%m-%d"), 0, "h" if date.day <= 8 else "l"]
        for date in dates for latitude in latitudes
    ], columns=["instrument", "satellite", "latitude", "longitude", "acq_date", "type", "confidence_class"])
    frame["type"] = frame["type"].astype("Int8")
    frame["confidence_class"] = frame.confidence_class.astype("string")
    frame.to_parquet(root / "processed" / f"{sensor}_{year}.parquet", index=False)


def notebook_cells():
    repo = Path(__file__).resolve().parents[3]
    notebook = json.loads((repo / "data/pipeline/notebooks/09_har12_snpp.ipynb").read_text(encoding="utf-8"))
    sources, codes = {}, []
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        assert cell["outputs"] == [] and cell["execution_count"] is None
        source = "".join(cell["source"])
        ast.parse(source)
        codes.append(source)
        if source.startswith("# cell: "):
            sources[source.splitlines()[0][len("# cell: "):]] = source
    assert "metricas-pipeline" in codes[0]
    return repo, sources


def prepare(root, with_years=True):
    repo, source = notebook_cells()
    (root / "processed").mkdir()
    (root / "metrics").mkdir()
    if with_years:
        for year in list(range(2007, 2012)) + [2018, 2019, 2020, 2021]:
            processed_year(root, "modis", year)
        for year in [2012, 2013, 2014, 2015, 2018, 2020, 2021]:
            processed_year(root, "viirs-snpp", year)
    namespace = dict(PROCESSED=root / "processed", METRICS=root / "metrics", REPO=repo, display=lambda value: None)
    exec(source["params"], namespace)
    return source, namespace


def run(namespace, source, tags=("defs", "build", "publish", "verify")):
    with contextlib.redirect_stdout(io.StringIO()):
        for tag in tags:
            exec(source[tag], namespace)


def test_notebook_parameters_and_tags(tmp_path):
    source, namespace = prepare(tmp_path, with_years=False)
    assert set(source) == {"params", "defs", "build", "publish", "verify"}
    assert namespace["GRID_DEG"] == 0.01 and namespace["FORCE"] is False
    assert namespace["MODEL_OPTIONS"]["reference_sensor"] == "viirs-snpp"
    text = "".join(source.values())
    for obsolete in ["country", "atomic_parquet", "_log_har12_snpp", "_params_har12_snpp"]:
        assert obsolete not in text


def test_isolated_snpp_notebook_estimates_step_and_l7_reuses_it(tmp_path):
    source, namespace = prepare(tmp_path)
    metrics = tmp_path / "metrics"
    sink = ParquetSink(metrics)
    # os produtos NOAA-20 existentes e os ficheiros viirs-jpss1 nao se tocam nem se leem
    baseline = pd.DataFrame({"cell": [GLOBAL_CELL], "factor_used": [9.0]})
    write_table(sink, "l6_har06_factor", baseline, partition_by=[])
    baseline_bytes = {p: p.read_bytes() for p in (metrics / "l6_har06_factor").rglob("*.parquet")}
    (tmp_path / "processed" / "viirs-jpss1_2019.parquet").write_bytes(b"not a parquet file")
    run(namespace, source)
    result = namespace["result"]
    assert result.cell.tolist() == [GLOBAL_CELL]
    row = result.iloc[0]
    assert (row.status, row.scope, row.reference_sensor) == ("ok", "global", "viirs-snpp")
    assert row.factor_used == 2.0 and not row.uses_global_fallback
    assert row.step_raw == pytest.approx(8.0, abs=1e-9)
    assert row.step_adjusted == pytest.approx(0.0, abs=1e-9)
    assert (row.n_pre_months, row.n_post_months) == (60, 48)
    assert set(namespace["monthly"].cell) == {GLOBAL_CELL}
    assert set(namespace["monthly"].series) == {"modis", "viirs"}
    assert namespace["factors"].cell.tolist() == [GLOBAL_CELL] and namespace["factors"].scope.tolist() == ["global"]
    # 8 dias elegiveis (confianca h) por mes; S-NPP nao tem 2019, logo so 2018, 2020 e 2021 sao meses comparaveis (36)
    assert namespace["factors"].iloc[0].n_cal_months == 36
    assert namespace["factors"].iloc[0].sum_modis == 8 * 36 and namespace["factors"].iloc[0].sum_viirs == 16 * 36

    # tabelas gravadas: globais pequenas (um ficheiro, sem particoes), `_runs` com o sentinela e os parametros
    for name in SIDECARS + ["l7_har12_residual_step"]:
        stored = sink.read(name)
        assert (stored.cell == GLOBAL_CELL).all() and not list((metrics / name).glob("*=*"))
    assert set(sink.read("l7_har12_snpp_monthly").series) == {"modis", "viirs"}
    runs = sink.read("_runs")
    assert runs.lote.tolist() == ["har12_snpp"] and runs.grid_deg.tolist() == [0.01]
    params = json.loads(runs.params.iloc[0])
    assert params["missing_years"]["viirs-snpp"] == [2016, 2019] and params["missing_years"]["modis"] == []
    assert params["model_options"]["reference_sensor"] == "viirs-snpp" and params["grid_deg"] == 0.01
    assert {entry["sensor"] for entry in params["sources"]} == {"modis", "viirs-snpp"}
    assert json.loads(runs.tables.iloc[0]) == {"l7_har12_residual_step": 1, "l7_har12_snpp_factor": 1,
                                               "l7_har12_snpp_monthly": len(namespace["monthly"])}
    assert {p: p.read_bytes() for p in baseline_bytes} == baseline_bytes
    assert not list(metrics.rglob("*.tmp")) and not list(metrics.rglob("*.old"))

    # exportacao interrompida: o sentinela e apagado ANTES de escrever e so volta a existir no fim
    original = namespace["write_table"]

    def interrupted(sink_, name, df, **kwargs):
        if name == "l7_har12_snpp_factor":
            raise OSError("simulated interrupted bundle export")
        return original(sink_, name, df, **kwargs)

    namespace["write_table"] = interrupted
    with pytest.raises(OSError, match="interrupted bundle"):
        exec(source["publish"], namespace)
    assert "har12_snpp" not in set(sink.read("_runs").lote)
    namespace["write_table"] = original
    run(namespace, source, ("publish", "verify"))
    assert sink.read("_runs").lote.tolist() == ["har12_snpp"]

    # o notebook 08 reaproveita as entradas isoladas (as suas entradas NOAA-20 sao outras)
    noaa_root = tmp_path / "noaa"
    noaa_root.mkdir()
    synthetic_inputs(noaa_root)
    for name in SIDECARS + ["_runs"]:
        shutil.copytree(metrics / name, noaa_root / "metrics" / name)
    repo, l7_source = lote7_sources()
    l7 = dict(PROCESSED=noaa_root / "processed", METRICS=noaa_root / "metrics", REPO=repo, display=lambda value: None)
    with contextlib.redirect_stdout(io.StringIO()):
        for tag in ["params", "defs", "inputs", "variants", "slices", "publish", "verify"]:
            exec(l7_source[tag], l7)
    updated = ParquetSink(noaa_root / "metrics").read("l7_har12_residual_step")
    assert updated.status.tolist() == ["ok"] and updated.cell.tolist() == [GLOBAL_CELL]
    assert updated.step_adjusted.tolist() == pytest.approx([0.0], abs=1e-9)
    assert updated.reference_sensor.eq("viirs-snpp").all()
    runs = ParquetSink(noaa_root / "metrics").read("_runs")
    assert set(runs.lote) == {"har12_snpp", "lote7"}
    assert json.loads(runs.params[runs.lote == "lote7"].iloc[0])["har12_source"] == "snpp"


def test_resume_per_source_file_and_grid_signature(tmp_path):
    source, namespace = prepare(tmp_path)
    metrics = tmp_path / "metrics"
    run(namespace, source)
    partial = metrics / "_partial_har12_snpp"
    part, marker = partial / "modis_2018.parquet", partial / "modis_2018.json"
    times = part.stat().st_mtime_ns
    run(namespace, source, ("build",))
    assert part.stat().st_mtime_ns == times                                    # reutiliza
    assert json.loads(marker.read_text(encoding="utf-8"))["grid_deg"] == 0.01
    marker.write_text("{", encoding="utf-8")                                    # marcador corrompido: recalcula
    run(namespace, source, ("build",))
    assert json.loads(marker.read_text(encoding="utf-8"))["year"] == 2018
    part.unlink()
    run(namespace, source, ("build",))
    assert part.is_file()
    reused = part.stat().st_mtime_ns
    namespace["FORCE"] = True
    run(namespace, source, ("build",))
    assert part.stat().st_mtime_ns != reused
    namespace["FORCE"] = False
    reused = part.stat().st_mtime_ns
    namespace["GRID_DEG"] = 0.1                                                  # outra grelha invalida os parciais
    run(namespace, source, ("defs", "build", "publish"))
    assert part.stat().st_mtime_ns != reused
    assert json.loads(marker.read_text(encoding="utf-8"))["grid_deg"] == 0.1
    assert json.loads(ParquetSink(metrics).read("_runs").params.iloc[0])["grid_deg"] == 0.1
    assert namespace["result"].iloc[0].step_raw == pytest.approx(8.0, abs=1e-9)   # 0.0 e 0.11 continuam em celulas distintas


def test_snpp_sensor_validation_and_dates_outside_the_file_year(tmp_path):
    source, namespace = prepare(tmp_path)
    path = tmp_path / "processed" / "viirs-snpp_2012.parquet"
    frame = pd.read_parquet(path)
    frame.assign(satellite="N20").to_parquet(path, index=False)               # NOAA-20 mascarado de S-NPP
    with pytest.raises(ValueError, match="S-NPP satellite label"):
        run(namespace, source, ("defs", "build"))
    frame.assign(acq_date="2011-12-31").to_parquet(path, index=False)
    with pytest.raises(ValueError, match="outside filename year"):
        run(namespace, source, ("build",))
    assert not ParquetSink(tmp_path / "metrics").exists("_runs")


def test_snpp_notebook_requires_processed_inputs(tmp_path):
    source, namespace = prepare(tmp_path, with_years=False)
    run(namespace, source, ("defs",))
    with pytest.raises(FileNotFoundError, match="processed modis.*notebook 01"):
        exec(source["build"], namespace)
    for year in [2018, 2019]:
        processed_year(tmp_path, "modis", year)
    with pytest.raises(FileNotFoundError, match="processed viirs-snpp.*notebook 01"):
        exec(source["build"], namespace)
