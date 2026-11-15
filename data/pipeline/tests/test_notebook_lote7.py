"""Executa as celulas reais do notebook 08 (L7, HAR-08..14) com tabelas L1/L6 e `processed/` sinteticos.

As tabelas L1 e o fator HAR-06 vem das celulas A..E de `test_notebook_lote6` (2018..2023, todos os meses validos):
A modis 3 / viirs 6 (fator 2), B 2 / 2 (1), C 0 / 1 (sem fator proprio: fallback global 1056/600 = 1.76), D m / 2m (2),
E 1 / 0 (0.0); a serie global e modis 6 + m e viirs 9 + 2m (m = mes). Os ficheiros `processed/` (2018, 2019, 2022) so servem
a HAR-13/14, que recontam as deteccoes por variante.
"""

import ast
import contextlib
import io
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from metrics import harmonization_errors as he
from metrics import harmonization_factor as hf
from metrics.common import GLOBAL_CELL
from metrics.store import ParquetSink, write_run, write_table
from test_notebook_lote6 import CELL_COLUMNS, cell_of, dense_frame, monthly_frames

CELL_NAMES = "ABCDE"
GLOBAL_FACTOR = 1056 / 600
ERROR_TABLES = {"l7_har08_mae", "l7_har09_wape", "l7_har10_bias", "l7_har11_error_reduction"}
SMALL_TABLES = {"l7_har12_residual_step", "l7_har13_grid_sensitivity", "l7_har14_confidence_sensitivity"}
TABLES = ERROR_TABLES | SMALL_TABLES


def synthetic_inputs(root, empty=False):
    """Cria `processed/` e `metrics/` (l1_cal_monthly, l1_meta_month_validity, l6_har06_factor) em `root`."""
    processed, metrics = root / "processed", root / "metrics"
    processed.mkdir()
    metrics.mkdir()
    for year in [2018, 2019, 2022]:
        for sensor, instrument, confidences in [("modis", "MODIS", ["h", "n"]), ("viirs-jpss1", "VIIRS", ["h", "n", "l"])]:
            rows = [[instrument, index * 0.11, 0.0, f"{year}-{month:02d}-01", 0, confidence]
                    for month in range(1, 13) for index, confidence in enumerate(confidences)]
            frame = pd.DataFrame(rows, columns=["instrument", "latitude", "longitude", "acq_date", "type",
                                                "confidence_class"])
            frame["type"] = frame["type"].astype("Int8")
            frame["confidence_class"] = frame.confidence_class.astype("string")
            (frame.iloc[:0] if empty else frame).to_parquet(processed / f"{sensor}_{year}.parquet", index=False)
    monthly, validity = monthly_frames(empty)
    dense = dense_frame().iloc[:0] if empty else dense_frame()
    sink = ParquetSink(metrics)
    write_table(sink, "l1_cal_monthly", monthly, grid_deg=0.01, sort_by=["year", "month", "series"])
    write_table(sink, "l1_meta_month_validity", validity, grid_deg=0.01, partition_by=[])
    write_table(sink, "l6_har06_factor", hf.har06_factor(dense), grid_deg=0.01, partition_by=[])
    return processed, metrics, sink


def notebook_sources():
    """(repo, {tag: codigo}) com as celulas de codigo etiquetadas por `# cell: <tag>` do notebook 08."""
    repo = Path(__file__).resolve().parents[3]
    notebook = json.loads((repo / "data/pipeline/notebooks/08_metrics_lote7.ipynb").read_text(encoding="utf-8"))
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


def prepare(root, empty=False, chunk=2, namespace_extra=None):
    repo, source = notebook_sources()
    processed, metrics, sink = synthetic_inputs(root, empty)
    namespace = dict(PROCESSED=processed, METRICS=metrics, REPO=repo, display=lambda value: None)
    exec(source["params"], namespace)
    namespace["CHUNK_CELLS"] = chunk
    return source, processed, metrics, sink, namespace


def run(namespace, source, tags=("defs", "inputs", "variants", "slices", "publish", "verify")):
    with contextlib.redirect_stdout(io.StringIO()):
        for tag in tags:
            exec(source[tag], namespace)


def table(sink, name):
    out = sink.read(name)
    keys = [c for c in ["variant", "cell", "period"] if c in out.columns]
    return out.sort_values(keys).reset_index(drop=True)


def cell_row(frame, name):
    rows = frame[frame["cell"].eq(cell_of(name))]
    assert len(rows) == 1
    return rows.iloc[0]


def global_row(frame):
    return frame[frame["cell"].eq(GLOBAL_CELL)].iloc[0]


def test_notebook_parameters_tags_and_no_obsolete_io(tmp_path):
    source, _, _, _, namespace = prepare(tmp_path)
    assert set(source) == {"params", "defs", "inputs", "variants", "slices", "publish", "verify"}
    assert namespace["GRID_DEG"] == 0.01 and namespace["STATS_GRID_DEG"] == namespace["GRID_DEG"]
    assert (namespace["CAL_START"], namespace["CAL_END"], namespace["TEST_START"]) == (2018, 2021, 2022)
    text = "".join(source.values())
    for obsolete in ["country", "atomic_parquet", "_log_lote7", "_params_har12_snpp", "l1_cal_monthly.parquet",
                     "l6_har06_factor.parquet"]:
        assert obsolete not in text


@pytest.mark.parametrize("chunk", [1, 2, 20000])
def test_roundtrip_hand_values_and_equals_the_unsliced_computation(tmp_path, chunk):
    source, processed, metrics, sink, namespace = prepare(tmp_path, chunk=chunk)
    inputs = {p: p.read_bytes() for name in ["l1_cal_monthly", "l1_meta_month_validity", "l6_har06_factor"]
              for p in (metrics / name).rglob("*.parquet")}
    run(namespace, source, ("defs",))
    seen = []
    original = namespace["write_run"]
    namespace["write_run"] = lambda s, *a, **k: (seen.append(set(s.names())), original(s, *a, **k))[1]
    run(namespace, source, ("inputs", "variants", "slices", "publish", "verify"))
    assert len(seen) == 1 and TABLES <= seen[0] and "_runs" not in seen[0]       # `_runs` por ultimo
    runs = sink.read("_runs")
    assert runs.lote.tolist() == ["lote7"] and runs.grid_deg.tolist() == [0.01]
    assert set(json.loads(runs.tables.iloc[0])) == TABLES
    params = json.loads(runs.params.iloc[0])
    assert params["cal_end"] == 2021 and params["test_start"] == 2022 and params["chunk_cells"] == chunk
    assert params["sensitivity_years"] == [2018, 2019, 2022] and params["har12_source"] == "none"
    assert {n for n in sink.names() if n.startswith("l7_")} == TABLES

    # HAR-08..11: valores escritos a mao por celula e a linha global (fator global 1.76)
    mae = table(sink, "l7_har08_mae")
    assert len(mae) == 6 and mae.cell.tolist().count(GLOBAL_CELL) == 1
    assert [(cell_row(mae, n).n_pairs, cell_row(mae, n).mae_raw, cell_row(mae, n).mae_adjusted) for n in "ABE"] == [
        (24, 3.0, 0.0), (24, 0.0, 0.0), (24, 1.0, 0.0)]
    assert (cell_row(mae, "D").mae_raw, cell_row(mae, "D").mae_adjusted) == (6.5, 0.0)
    assert (cell_row(mae, "C").mae_raw, cell_row(mae, "C").mae_adjusted) == (1.0, 1.0)     # 0 x 1.76 continua a errar 1
    g = global_row(mae)
    assert (g.n_pairs, g.n_adjusted_pairs, g.mae_raw) == (24, 24, 9.5)
    assert g.mae_adjusted == pytest.approx(0.72)
    wape = table(sink, "l7_har09_wape")
    assert global_row(wape).wape_raw == pytest.approx(100 * 114 / 264) and cell_row(wape, "A").wape_adjusted == 0.0
    bias = table(sink, "l7_har10_bias")
    assert global_row(bias).bias_raw == pytest.approx(-9.5) and global_row(bias).bias_adjusted == pytest.approx(0.0, abs=1e-9)
    assert cell_row(bias, "A").bias_raw == -3.0
    reduction = table(sink, "l7_har11_error_reduction")
    assert cell_row(reduction, "A").error_reduction_pct == 100.0 and np.isnan(cell_row(reduction, "B").error_reduction_pct)
    assert global_row(reduction).error_reduction_pct == pytest.approx(100 * (9.5 - 0.72) / 9.5)

    # a computacao por fatias == as funcoes sem fatias sobre a tabela densa e o fator HAR-06 completo
    dense, options = dense_frame(), dict(cal_start=2018, cal_end=2021, test_start=2022, max_unknown_days=0)
    factors = hf.har06_factor(dense, min_cal_months=24, **options)
    for name, function in [("l7_har08_mae", he.har08_mae), ("l7_har09_wape", he.har09_wape),
                           ("l7_har10_bias", he.har10_bias), ("l7_har11_error_reduction", he.har11_error_reduction)]:
        expected = function(dense, factors, **options).sort_values(["cell", "period"]).reset_index(drop=True)
        actual = table(sink, name).drop(columns=CELL_COLUMNS)
        assert_frame_equal(actual[expected.columns], expected, check_dtype=False)

    # HAR-12 sem entradas S-NPP; HAR-13/14 globais por variante (a mao: ver o docstring do modulo e o notebook)
    step = table(sink, "l7_har12_residual_step")
    assert step.cell.tolist() == [GLOBAL_CELL] and step.status.tolist() == ["requires_snpp_inputs"]
    grids = table(sink, "l7_har13_grid_sensitivity")
    assert set(grids.cell) == {GLOBAL_CELL} and grids.variant.nunique() == 2
    grid = grids[grids.period.eq("test")].set_index("variant")
    assert grid.loc["grid_0.1", "sum_modis"] == 24 and grid.loc["grid_0.25", "sum_modis"] == 12
    assert grid.loc["grid_0.25", "delta_modis_pct"] == -50.0 and grid.loc["grid_0.1", "delta_modis_pct"] == 0.0
    confidence = table(sink, "l7_har14_confidence_sensitivity")
    confidence = confidence[confidence.period.eq("test")].set_index("variant")
    assert confidence.loc["all_confidence", "sum_viirs"] == 36 and confidence.loc["high_only", "sum_viirs"] == 12
    assert confidence.loc["all_confidence", "factor_used"] == 1.5

    # colunas de celula: so as linhas por celula as levam; a linha global fica sem ilat/lat
    for name in ERROR_TABLES:
        frame = sink.read(name)
        assert {"cell", *CELL_COLUMNS} <= set(frame.columns) and "country" not in frame.columns
        assert frame[frame.cell == GLOBAL_CELL][CELL_COLUMNS].isna().all().all()
    assert not list(metrics.rglob("*.tmp")) and not list(metrics.rglob("*.old"))
    assert {p: p.read_bytes() for p in inputs} == inputs                         # as entradas ficam intactas


def test_chunking_does_not_change_the_results(tmp_path):
    outputs = {}
    for chunk in (1, 20000):
        root = tmp_path / f"chunk{chunk}"
        root.mkdir()
        source, _, metrics, sink, namespace = prepare(root, chunk=chunk)
        run(namespace, source)
        outputs[chunk] = ({p.name for p in (metrics / "_partial_lote7").glob("err_*")},
                          {name: table(sink, name).drop(columns=CELL_COLUMNS) for name in ERROR_TABLES})
    assert len(outputs[1][0]) == 4 and len(outputs[20000][0]) == 1
    for name in ERROR_TABLES:
        assert_frame_equal(outputs[1][1][name], outputs[20000][1][name], check_dtype=False)


def test_resume_markers_signatures_and_force(tmp_path):
    source, processed, metrics, sink, namespace = prepare(tmp_path)
    run(namespace, source)
    partial = metrics / "_partial_lote7"
    year_part, marker = partial / "variant_monthly_2018.parquet", partial / "variants_2018.json"
    slice_part = sorted(partial.glob("err_*"))[0] / "har08.parquet"
    times = (year_part.stat().st_mtime_ns, slice_part.stat().st_mtime_ns)
    run(namespace, source, ("inputs", "variants", "slices"))
    assert (year_part.stat().st_mtime_ns, slice_part.stat().st_mtime_ns) == times
    marker.write_text("{", encoding="utf-8")
    run(namespace, source, ("inputs", "variants", "slices"))
    assert "variants" in json.loads(marker.read_text(encoding="utf-8"))
    year_part.unlink()
    slice_part.unlink()
    run(namespace, source, ("inputs", "variants", "slices"))
    assert year_part.is_file() and slice_part.is_file()
    reused = (year_part.stat().st_mtime_ns, slice_part.stat().st_mtime_ns)
    namespace["FORCE"] = True
    run(namespace, source, ("inputs", "variants", "slices"))
    assert year_part.stat().st_mtime_ns != reused[0] and slice_part.stat().st_mtime_ns != reused[1]
    namespace["FORCE"] = False

    # um fator diferente (notebook 07 refeito) invalida as fatias de erros mas nao as contagens por variante
    reused = (year_part.stat().st_mtime_ns, slice_part.stat().st_mtime_ns)
    factors = sink.read("l6_har06_factor")
    factors.loc[factors.cell == cell_of("A"), "factor_used"] = 1.0
    write_table(sink, "l6_har06_factor", factors.drop(columns=CELL_COLUMNS), grid_deg=0.01, partition_by=[])
    run(namespace, source)
    assert year_part.stat().st_mtime_ns == reused[0] and slice_part.stat().st_mtime_ns != reused[1]
    assert table(sink, "l7_har08_mae").pipe(cell_row, "A").mae_adjusted == 3.0          # 3 x 1.0 contra viirs 6
    # a serie global (nova validade) invalida a contagem por variante desse ano
    validity = sink.read("l1_meta_month_validity")
    validity.loc[(validity.year == 2018) & (validity.month == 1), "n_unknown_days"] = 5
    write_table(sink, "l1_meta_month_validity", validity, grid_deg=0.01, partition_by=[])
    reused = year_part.stat().st_mtime_ns
    run(namespace, source)
    assert year_part.stat().st_mtime_ns != reused
    assert not list(metrics.rglob("*.tmp"))


def test_har12_uses_the_snpp_inputs_only_when_the_sentinel_is_complete(tmp_path):
    source, processed, metrics, sink, namespace = prepare(tmp_path)
    run(namespace, source, ("defs", "inputs", "variants", "slices"))
    model = dict(reference_sensor="viirs-snpp", transition_year=2020, window_years=3, min_months_each_side=24,
                 min_years_each_side=2, max_unknown_days=0)
    months = [(year, month) for year in range(2017, 2023) for month in range(1, 13)]
    snpp = pd.DataFrame([[GLOBAL_CELL, year, month, "modis" if year < 2020 else "viirs", 10 + (year >= 2020) * 6 + month,
                          False, 0, "x"] for year, month in months],
                        columns=["cell", "year", "month", "series", "cell_days", "partial", "n_unknown_days", "sensor"])
    factor = pd.DataFrame([[GLOBAL_CELL, 1.0, False]], columns=["cell", "factor_used", "uses_global_fallback"])
    write_table(sink, "l7_har12_snpp_monthly", snpp, grid_deg=0.01, partition_by=[])
    write_table(sink, "l7_har12_snpp_factor", factor, grid_deg=0.01, partition_by=[])
    run(namespace, source, ("publish",))                                       # sem a linha em `_runs`: nao ha sentinela
    assert table(sink, "l7_har12_residual_step").status.tolist() == ["requires_snpp_inputs"]
    write_run(sink, "har12_snpp", params={"model_options": model}, tables={"l7_har12_snpp_monthly": len(snpp)})
    run(namespace, source, ("publish",))
    step = table(sink, "l7_har12_residual_step")
    assert step.status.tolist() == ["ok"] and step.reference_sensor.tolist() == ["viirs-snpp"]
    assert step.step_raw.iloc[0] == pytest.approx(6.0, abs=1e-9) and step.cell.tolist() == [GLOBAL_CELL]
    assert set(sink.read("_runs").lote) == {"har12_snpp", "lote7"}
    shutil.rmtree(metrics / "l7_har12_snpp_factor")                              # sidecar em falta: volta a requires_snpp_inputs
    run(namespace, source, ("publish",))
    assert table(sink, "l7_har12_residual_step").status.tolist() == ["requires_snpp_inputs"]


def test_input_errors_are_explicit(tmp_path):
    source, processed, metrics, sink, namespace = prepare(tmp_path)
    (tmp_path / "other").mkdir()
    other = synthetic_inputs(tmp_path / "other")[1]
    run(namespace, source, ("defs",))
    shutil.rmtree(metrics / "l6_har06_factor")
    with pytest.raises(FileNotFoundError, match="notebooks 02 and 07.*l6_har06_factor"):
        exec(source["inputs"], namespace)
    shutil.copytree(other / "l6_har06_factor", metrics / "l6_har06_factor")
    shutil.rmtree(metrics / "l1_cal_monthly")
    with pytest.raises(FileNotFoundError, match="notebooks 02 and 07.*l1_cal_monthly"):
        exec(source["inputs"], namespace)
    shutil.copytree(other / "l1_cal_monthly", metrics / "l1_cal_monthly")
    (processed / "viirs-jpss1_2018.parquet").unlink()
    with pytest.raises(FileNotFoundError, match="Missing processed counterparts.*viirs-jpss1_2018"):
        exec(source["inputs"], namespace)
    namespace["YEARS"] = {2010}
    with pytest.raises(FileNotFoundError, match="No selected processed sensor-year files"):
        exec(source["inputs"], namespace)


def test_invalid_factor_table_is_rejected_before_processing_detections(tmp_path):
    source, processed, metrics, sink, namespace = prepare(tmp_path)
    factors = sink.read("l6_har06_factor").drop(columns=CELL_COLUMNS)
    factors.loc[factors.cell == GLOBAL_CELL, "factor_used"] = -1.0
    write_table(sink, "l6_har06_factor", factors, grid_deg=0.01, partition_by=[])
    with pytest.raises(ValueError, match="factor_used"):
        run(namespace, source, ("defs", "inputs"))
    assert not list((metrics / "_partial_lote7").glob("variant*"))


def test_runs_is_not_written_when_a_stage_fails(tmp_path):
    source, processed, metrics, sink, namespace = prepare(tmp_path)
    run(namespace, source, ("defs", "inputs", "variants", "slices"))
    original = namespace["write_table"]

    def broken(sink_, name, df, **kwargs):
        if name == "l7_har14_confidence_sensitivity":
            raise OSError("simulated failure while writing")
        return original(sink_, name, df, **kwargs)

    namespace["write_table"] = broken
    with pytest.raises(OSError, match="simulated"):
        run(namespace, source, ("publish",))
    assert not sink.exists("_runs")
    namespace["write_table"] = original
    run(namespace, source, ("publish", "verify"))
    assert sink.read("_runs").lote.tolist() == ["lote7"]


def test_wrong_instrument_and_dates_outside_the_file_year_are_rejected(tmp_path):
    source, processed, metrics, sink, namespace = prepare(tmp_path)
    frame = pd.read_parquet(processed / "viirs-jpss1_2019.parquet")
    frame.assign(instrument="MODIS").to_parquet(processed / "viirs-jpss1_2019.parquet", index=False)
    with pytest.raises(ValueError, match="Unexpected instrument"):
        run(namespace, source, ("defs", "inputs", "variants"))
    frame.assign(acq_date="2017-01-01").to_parquet(processed / "viirs-jpss1_2019.parquet", index=False)
    with pytest.raises(ValueError, match="outside filename year"):
        run(namespace, source, ("inputs", "variants"))
    assert not sink.exists("_runs")


def test_empty_inputs_publish_empty_tables(tmp_path):
    source, processed, metrics, sink, namespace = prepare(tmp_path, empty=True)
    run(namespace, source)
    assert {n for n in sink.names() if n.startswith("l7_")} == TABLES
    assert all(len(sink.read(name)) == 0 for name in TABLES)
    assert json.loads(sink.read("_runs").tables.iloc[0]) == {name: 0 for name in TABLES}
    assert not list(metrics.rglob("*.tmp"))
