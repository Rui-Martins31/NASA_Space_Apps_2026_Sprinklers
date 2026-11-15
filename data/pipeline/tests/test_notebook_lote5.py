"""Teste do notebook 06_metrics_lote5.ipynb (por celula), executado com uma "Drive" simulada.

Mundo sintetico (2018-2019, um registo por dia e sensor, por isso todos os anos sao validos), grelha 0.01:
  A (10.05, 20.05): todos os dias, MODIS e VIIRS.
  B (11.05, 20.05): so em 2018-06-01 e 2019-06-01 (MODIS).
  C (40.05, -3.05): so em 2018-03-03 (MODIS, Aqua).
  D (12.05, 20.05): so em 2019-07-07 (VIIRS).
  E (13.05, 20.05): em 2018-02-02 com type=1 (MODIS; nao elegivel por defeito, entra sem filtro de type).
  F (50.05, 5.05):  em 2018-04-04 com confianca baixa (MODIS; nunca elegivel).
As tabelas do L1 escrevem-se com as proprias funcoes do pacote (como o notebook 02 as publica).
"""
import ast
import contextlib
import datetime as dt
import io
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pyarrow")
pytest.importorskip("duckdb")

from helpers_lote1 import build_processed  # noqa: E402
from metrics.calendar_metrics import (  # noqa: E402
    cal_annual, cal_coverage, cal_monthly, coarsen_cell_days, eligible_cell_days, global_day_counts,
    month_validity, year_validity,
)
from metrics.common import GLOBAL_CELL, cell_key  # noqa: E402
from metrics.store import ParquetSink, write_table  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
NOTEBOOK = REPO / "data/pipeline/notebooks/06_metrics_lote5.ipynb"
A, B, C, D, E, F = (10.05, 20.05), (11.05, 20.05), (40.05, -3.05), (12.05, 20.05), (13.05, 20.05), (50.05, 5.05)
TABLES = {
    "l5_cell_year", "l5_esp02_active_cells", "l5_esp03_recurrence", "l5_esp06_interannual",
    "l5_esp06_cell_years_active", "l5_add05_type_sensitivity", "l5_qa05_confirmed_days", "l5_add06_union_step",
}
CELL_COLUMNS = {"cell", "ilat", "ilon", "lat", "lon", "lat_band"}


def cid(point, grid=0.01):
    return int(cell_key([point[0]], [point[1]], grid)[0])


def world():
    """{(sensor, ano): DataFrame processed} do mundo descrito acima (o `country` nao influencia nada)."""
    out = {}
    for year in (2018, 2019):
        modis, viirs = [], []
        day = dt.date(year, 1, 1)
        while day.year == year:
            iso = day.isoformat()
            modis.append(dict(country="PT", latitude=A[0], longitude=A[1], acq_date=iso))
            viirs.append(dict(country="XX", instrument="VIIRS", satellite="N20",
                              latitude=A[0], longitude=A[1], acq_date=iso))
            day += dt.timedelta(days=1)
        modis.append(dict(country="PT", latitude=B[0], longitude=B[1], acq_date=f"{year}-06-01"))
        if year == 2018:
            modis.append(dict(country="ES", satellite="Aqua", latitude=C[0], longitude=C[1], acq_date="2018-03-03"))
            modis.append(dict(country="PT", latitude=E[0], longitude=E[1], acq_date="2018-02-02", type=1))
            modis.append(dict(country="ZZ", latitude=F[0], longitude=F[1], acq_date="2018-04-04",
                              confidence_class="l", confidence_raw="10"))
        else:
            viirs.append(dict(country="PT", instrument="VIIRS", satellite="N20",
                              latitude=D[0], longitude=D[1], acq_date="2019-07-07"))
        out[("modis", year)] = build_processed(modis)
        out[("viirs-jpss1", year)] = build_processed(viirs)
    return out


def write_l1(metrics, files, grid=0.01, stats_grid=None):
    """Tabelas do L1 que o notebook 06 le (as mesmas que o notebook 02 publica)."""
    sink = ParquetSink(metrics)
    cov = cal_coverage(global_day_counts(pd.concat(files.values(), ignore_index=True)))
    cell_days = pd.concat([eligible_cell_days(df, grid) for df in files.values()], ignore_index=True)
    validity = month_validity(cov)
    monthly = cal_monthly(cell_days, cov)
    tables = {"l1_cal_coverage": (cov, grid), "l1_meta_month_validity": (validity, grid),
              "l1_meta_year_validity": (year_validity(validity), grid),
              "l1_cal_monthly": (monthly, grid), "l1_cal_annual": (cal_annual(monthly), grid)}
    if stats_grid and stats_grid != grid:
        s_monthly = cal_monthly(coarsen_cell_days(cell_days, grid, stats_grid), cov)
        tables.update(l1_stats_cal_monthly=(s_monthly, stats_grid), l1_stats_cal_annual=(cal_annual(s_monthly), stats_grid))
    for name, (tbl, g) in tables.items():
        write_table(sink, name, tbl, grid_deg=g, partition_by=[] if name in {
            "l1_cal_coverage", "l1_meta_month_validity", "l1_meta_year_validity"} else None)


def write_drive(root, with_l1=True, files=None, grid=0.01, stats_grid=None):
    processed, metrics = root / "processed", root / "metrics"
    processed.mkdir(exist_ok=True)
    metrics.mkdir(exist_ok=True)
    files = files if files is not None else world()
    for (sensor, year), df in files.items():
        df.to_parquet(processed / f"{sensor}_{year}.parquet", index=False)
    if with_l1:
        write_l1(metrics, files, grid, stats_grid)
    return processed, metrics


def cells():
    """{tag: codigo} das celulas de codigo etiquetadas por `# cell: <tag>`, e a de bootstrap (sem etiqueta)."""
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    sources = {}
    code_cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]
    for cell in code_cells:
        assert cell["outputs"] == [] and cell["execution_count"] is None      # notebook limpo
        source = "".join(cell["source"])
        ast.parse(source)
        sources[source.splitlines()[0][len("# cell: "):] if source.startswith("# cell: ") else "bootstrap"] = source
    assert len(sources) == len(code_cells)
    return sources


def namespace(root):
    return dict(PROCESSED=root / "processed", METRICS=root / "metrics", REPO=REPO)


def prepare(tmp_path, **kw):
    source = cells()
    processed, metrics = write_drive(tmp_path, **kw)
    ns = namespace(tmp_path)
    exec(source["params"], ns)
    return source, metrics, ns


def start(ns, source):
    with contextlib.redirect_stdout(io.StringIO()):
        exec(source["defs"], ns)


def run(ns, source, tags=("run", "publish", "verify")):
    with contextlib.redirect_stdout(io.StringIO()):
        for tag in tags:
            exec(compile(source[tag], f"06_metrics_lote5.ipynb[{tag}]", "exec"), ns)


def full_run(tmp_path, **config):
    source, metrics, ns = prepare(tmp_path)
    ns.update(config)
    start(ns, source)
    run(ns, source)
    return source, metrics, ns


def rows(df, **where):
    sel = df
    for k, v in where.items():
        sel = sel[sel[k] == v]
    return sel


def is_global(df):
    return df["cell"] == GLOBAL_CELL


def test_notebook_is_clean_and_has_the_expected_parameters(tmp_path):
    source = cells()
    assert set(source) == {"bootstrap", "params", "defs", "run", "publish", "verify"}
    assert "git clone" in source["bootstrap"] or "git', 'clone'" in source["bootstrap"]
    text = NOTEBOOK.read_text(encoding="utf-8")
    assert not re.search(r"[A-Za-z]:\\\\|/Users/|C:/", text), "caminho do PC no notebook"
    ns = {}
    exec(source["params"], ns)
    assert ns["GRID_DEG"] == 0.01 and ns["STATS_GRID_DEG"] == ns["GRID_DEG"]
    assert ns["CHUNK_CELLS"] == 20000 and ns["MAX_UNKNOWN_DAYS"] == 0
    assert ns["SENSORS"] == {"modis", "viirs-jpss1"} and ns["YEARS"] is None and ns["FORCE"] is False
    code = "".join(source[t] for t in ("defs", "run", "publish", "verify"))
    for old in ("country", "ESP06_BLOCK", "atomic_write", "_log_lote5", "_params_lote5"):
        assert old not in code, old


def test_pipeline_tables_values_and_run_registration(tmp_path):
    source, metrics, ns = prepare(tmp_path)
    start(ns, source)
    seen = []
    original = ns["write_run"]
    ns["write_run"] = lambda sink, *a, **k: (seen.append(set(sink.names())), original(sink, *a, **k))[1]
    run(ns, source)
    sink = ParquetSink(metrics)
    # _runs e a ULTIMA coisa a ser escrita: quando e chamada ja existem as 8 tabelas L5, e ele ainda nao
    assert len(seen) == 1 and TABLES <= seen[0] and "_runs" not in seen[0]
    assert {n for n in sink.names() if n.startswith("l5_")} == TABLES
    assert not list(metrics.rglob("*.tmp")) and not list(metrics.rglob("*.old"))
    runs = sink.read("_runs")
    assert runs.lote.tolist() == ["lote5"] and runs.grid_deg.tolist() == [0.01]
    assert set(json.loads(runs.tables.iloc[0])) == TABLES
    params = json.loads(runs.params.iloc[0])
    assert (params["grid_deg"], params["stats_grid_deg"], params["chunk_cells"], params["max_unknown_days"]) == (0.01, 0.01, 20000, 0)
    assert params["sensors"] == ["modis", "viirs-jpss1"] and params["years"] == [2018, 2019]
    assert json.loads(runs.tables.iloc[0])["l5_cell_year"] == len(sink.read("l5_cell_year"))

    # l5_cell_year: por celula, esparsa; a celula F (confianca baixa) nunca aparece
    cy = sink.read("l5_cell_year")
    assert CELL_COLUMNS | {"series", "year", "n_days"} == set(cy.columns) and "country" not in cy.columns
    got = {(r.cell, r.series, r.year): r.n_days for r in cy.itertuples()}
    cells_a, cells_b, cells_c, cells_d, cells_e = (cid(p) for p in (A, B, C, D, E))
    assert got == {
        (cells_a, "modis", 2018): 365, (cells_a, "viirs", 2018): 365, (cells_a, "combined", 2018): 365,
        (cells_a, "modis", 2019): 365, (cells_a, "viirs", 2019): 365, (cells_a, "combined", 2019): 365,
        (cells_b, "modis", 2018): 1, (cells_b, "combined", 2018): 1, (cells_b, "modis", 2019): 1, (cells_b, "combined", 2019): 1,
        (cells_c, "modis", 2018): 1, (cells_c, "combined", 2018): 1,
        (cells_d, "viirs", 2019): 1, (cells_d, "combined", 2019): 1,
    }
    assert cells_e not in set(cy.cell) and cid(F) not in set(cy.cell)
    assert (cy.loc[cy.cell == cells_a, ["lat", "lon"]].round(3).drop_duplicates().to_numpy() == [[10.055, 20.055]]).all()
    assert set(cy.series) == {"modis", "viirs", "combined"} and (sink.path("l5_cell_year") / "series=modis").is_dir()

    # ESP-02 (populacao, cell = -1): celulas ativas por serie e ano, calculado a mao no cabecalho do ficheiro
    e2 = sink.read("l5_esp02_active_cells")
    assert is_global(e2).all()
    assert {(r.series, r.year): r.n_active_cells for r in e2.itertuples()} == {
        ("modis", 2018): 3, ("viirs", 2018): 1, ("combined", 2018): 3,
        ("modis", 2019): 2, ("viirs", 2019): 2, ("combined", 2019): 3}
    # ESP-03 modis 2018: dias por celula [365, 1, 1] -> media 367/3, mediana 1, p90 = 1 + 0.8 * 364 = 292.2
    r = rows(sink.read("l5_esp03_recurrence"), series="modis", year=2018).iloc[0]
    assert (r.cell, r.n_active_cells, r.median_days, r.max_days) == (GLOBAL_CELL, 3, 1.0, 365)
    assert r.mean_days == pytest.approx(367 / 3) and r.p90_days == pytest.approx(292.2)
    assert (r.n_cells_1d, r.n_cells_2_5d, r.n_cells_6_15d, r.n_cells_16plus) == (2, 0, 0, 1)
    # ESP-06 (populacao sobre todas as celulas): modis A e B em 2 anos, C em 1; viirs A em 2 e D em 1
    e6 = sink.read("l5_esp06_interannual")
    assert is_global(e6).all()
    m = rows(e6, series="modis").iloc[0]
    assert (m.n_years_analysed, m.n_cells, m.n_cells_2plus_years, m.max_years) == (2, 3, 2, 2)
    assert m.pct_cells_2plus == pytest.approx(200 / 3) and m.mean_years_per_cell == pytest.approx(5 / 3)
    v = rows(e6, series="viirs").iloc[0]
    assert (v.n_cells, v.n_cells_2plus_years, v.pct_cells_2plus, v.mean_years_per_cell) == (2, 1, 50.0, 1.5)
    c = rows(e6, series="combined").iloc[0]
    assert (c.n_cells, c.n_cells_2plus_years, c.pct_cells_2plus, c.mean_years_per_cell) == (4, 2, 50.0, 1.5)
    # ESP-06 por celula: anos validos com atividade
    active = sink.read("l5_esp06_cell_years_active")
    assert CELL_COLUMNS | {"series", "n_years_active", "n_years_valid"} == set(active.columns)
    got = {(r.cell, r.series): (r.n_years_active, r.n_years_valid) for r in active.itertuples()}
    assert got[(cells_a, "modis")] == (2, 2) and got[(cells_b, "combined")] == (2, 2)
    assert got[(cells_c, "modis")] == (1, 2) and got[(cells_d, "viirs")] == (1, 2) and len(got) == 9
    # as populacoes ESP-06 = agregado da tabela por celula
    for series, n_cells, n_2plus in [("modis", 3, 2), ("viirs", 2, 1), ("combined", 4, 2)]:
        sub = active[active.series == series]
        assert (len(sub), int((sub.n_years_active >= 2).sum())) == (n_cells, n_2plus)

    # ADD-05: por celula e linha global recalculada a partir das somas
    a5 = sink.read("l5_add05_type_sensitivity")
    assert list(a5.columns[:1]) == ["cell"] and "country" not in a5.columns
    glob = rows(a5, cell=GLOBAL_CELL, year=2018, instrument="MODIS").set_index("variant")
    assert glob.loc["default", ["n_eligible", "n_cell_days"]].tolist() == [367, 367]          # A 365 + B + C
    assert glob.loc["no_type_filter", ["n_eligible", "n_cell_days"]].tolist() == [368, 368]   # + E (type 1)
    assert glob.loc["no_type_filter", "delta_cell_days_pct"] == pytest.approx(100 / 367)
    assert glob.loc["type0_or_unknown", "delta_cell_days_pct"] == 0.0
    cell_e = rows(a5, cell=cells_e, year=2018, instrument="MODIS").set_index("variant")
    assert cell_e.loc["default", ["n_eligible", "n_cell_days"]].tolist() == [0, 0]
    assert cell_e.loc["no_type_filter", ["n_eligible", "n_cell_days"]].tolist() == [1, 1]
    assert pd.isna(cell_e.loc["no_type_filter", "delta_cell_days_pct"])                          # default 0 => NA
    assert rows(a5, cell=cells_a, year=2018, instrument="MODIS", variant="default").n_cell_days.iloc[0] == 365
    assert cid(F) not in set(a5.cell)                                                              # confianca baixa
    # global = soma das celulas, e o delta global nao e a soma dos deltas
    per_cell = a5[~is_global(a5)].groupby(["year", "instrument", "variant"])[["n_eligible", "n_cell_days"]].sum()
    only_global = a5[is_global(a5)].set_index(["year", "instrument", "variant"])
    assert (only_global[["n_eligible", "n_cell_days"]] == per_cell).all().all()
    assert len(a5[~is_global(a5)]) % 3 == 0 and len(only_global) % 3 == 0                       # 3 variantes por grupo
    # QA-05 (global): fevereiro de 2018 do MODIS tem 28 dias, todos com registos; 2 sensores x 24 meses
    q5 = sink.read("l5_qa05_confirmed_days")
    q = rows(q5, instrument="MODIS", year=2018, month=2).iloc[0]
    assert (q.n_days_expected, q.n_days_confirmed, q.pct_confirmed, q.scope) == (28, 28, 100.0, "global_proxy")
    assert len(q5) == 48

    # ADD-06: por celula e global (soma entre celulas)
    a6 = sink.read("l5_add06_union_step")
    assert list(a6.columns[:1]) == ["cell"] and "country" not in a6.columns
    ix = a6.set_index(["cell", "year"])
    assert ix.loc[(cells_a, 2018), ["n_months", "sum_modis", "sum_combined"]].tolist() == [12, 365, 365]
    assert ix.loc[(cells_a, 2018), "ratio_combined_modis"] == 1.0
    assert ix.loc[(cells_d, 2019), ["sum_modis", "sum_combined"]].tolist() == [0, 1]             # so no VIIRS
    assert pd.isna(ix.loc[(cells_d, 2019), "ratio_combined_modis"])
    assert ix.loc[(GLOBAL_CELL, 2018), ["n_months", "sum_modis", "sum_combined"]].tolist() == [12, 367, 367]
    assert ix.loc[(GLOBAL_CELL, 2019), ["n_months", "sum_modis", "sum_combined"]].tolist() == [12, 366, 367]
    assert ix.loc[(GLOBAL_CELL, 2019), "excess_pct"] == pytest.approx(100 / 366)
    assert ix.loc[(GLOBAL_CELL, 2019), "ratio_combined_modis"] == pytest.approx(367 / 366)
    for year in (2018, 2019):                                                                      # global = soma das celulas
        cells_y = a6[(a6.year == year) & ~is_global(a6)]
        assert cells_y.sum_modis.sum() == ix.loc[(GLOBAL_CELL, year), "sum_modis"]
        assert cells_y.sum_combined.sum() == ix.loc[(GLOBAL_CELL, year), "sum_combined"]


def test_each_per_cell_table_is_sorted_and_partitioned_for_the_backend(tmp_path):
    source, metrics, ns = full_run(tmp_path)
    sink = ParquetSink(metrics)
    cy = sink.read("l5_cell_year")
    for _, group in cy.groupby(["series", "lat_band"]):                  # ordenada por (ilat, ilon) em cada particao
        pairs = list(zip(group.ilat, group.ilon))
        assert pairs == sorted(pairs)
    assert (sink.path("l5_cell_year") / "series=modis").is_dir()
    assert sorted(p.name for p in (sink.path("l5_esp06_cell_years_active")).iterdir()) == ["series=combined", "series=modis", "series=viirs"]
    # as tabelas com linha global nao se particionam por lat_band (a faixa da linha global seria NA)
    assert not any(p.is_dir() for p in sink.path("l5_add06_union_step").iterdir())
    assert not any(p.is_dir() for p in sink.path("l5_add05_type_sensitivity").iterdir())
    a6 = sink.read("l5_add06_union_step")
    assert a6[~is_global(a6)].ilat.is_monotonic_increasing and a6.cell.iloc[0] == GLOBAL_CELL


def test_slicing_into_many_chunks_gives_the_same_tables(tmp_path):
    source, metrics, ns = full_run(tmp_path)
    sink = ParquetSink(metrics)
    reference = {n: sink.read(n).sort_values(list(sink.read(n).columns)).reset_index(drop=True)
                 for n in ("l5_add06_union_step", "l5_add05_type_sensitivity", "l5_esp06_cell_years_active")}
    slices_before = sorted((metrics / "_partial_lote5/add06").glob("b*.parquet"))
    assert [p.stem for p in slices_before] == ["b10_0", "b13_0"]          # A, B, D na faixa 10; C (lat 40) na 13
    ns["CHUNK_CELLS"] = 2
    run(ns, source)                                                       # outras fatias, mesmas tabelas
    stems = {p.stem for p in (metrics / "_partial_lote5/add06").glob("b*.parquet")}
    assert {"b10_0", "b10_1", "b13_0"} <= stems                           # faixa 10: 3 celulas em fatias de 2
    assert json.loads(sink.read("_runs").params.iloc[0])["chunk_cells"] == 2
    for name, expected in reference.items():
        got = sink.read(name)
        pd.testing.assert_frame_equal(got.sort_values(list(got.columns)).reset_index(drop=True), expected, check_dtype=False)
    ix = sink.read("l5_add06_union_step").set_index(["cell", "year"])
    assert ix.loc[(GLOBAL_CELL, 2019), ["n_months", "sum_modis", "sum_combined"]].tolist() == [12, 366, 367]   # n_months nao se soma


def test_resume_by_marker_and_cache_invalidation(tmp_path):
    source, metrics, ns = full_run(tmp_path)
    part = metrics / "_partial_lote5"
    marker = part / "modis_2018/_done.json"
    watched = [marker, part / "cell_year_2018.parquet", part / "cell_year_2018.json",
               part / "add06" / next((part / "add06").glob("b*.json")).name]
    stamps = {p: p.stat().st_mtime_ns for p in watched}
    run(ns, source)                                                       # segundo passe: nada se refaz
    assert {p: p.stat().st_mtime_ns for p in watched} == stamps
    assert json.loads(marker.read_text())["signature"]["grid_deg"] == 0.01

    (part / "modis_2018/add05.parquet").unlink()                          # parcial apagado => refeito
    run(ns, source)
    assert (part / "modis_2018/add05.parquet").exists() and marker.stat().st_mtime_ns != stamps[marker]
    marker.write_text("{")                                                # marcador invalido => refeito
    run(ns, source)
    assert json.loads(marker.read_text())["sensor"] == "modis"

    stamp = watched[1].stat().st_mtime_ns                                 # FORCE refaz tudo
    ns["FORCE"] = True
    run(ns, source)
    ns["FORCE"] = False
    assert watched[1].stat().st_mtime_ns != stamp

    frame = pd.read_parquet(tmp_path / "processed/modis_2019.parquet")    # fonte alterada => assinatura nova
    frame = frame[frame.latitude != B[0]]
    frame.to_parquet(tmp_path / "processed/modis_2019.parquet", index=False)
    write_l1(metrics, {k: pd.read_parquet(tmp_path / f"processed/{k[0]}_{k[1]}.parquet") for k in
                       [("modis", 2018), ("modis", 2019), ("viirs-jpss1", 2018), ("viirs-jpss1", 2019)]})
    run(ns, source)
    sink = ParquetSink(metrics)
    assert (cid(B), "modis", 2019) not in {(r.cell, r.series, r.year) for r in sink.read("l5_cell_year").itertuples()}
    assert rows(sink.read("l5_esp06_interannual"), series="modis").iloc[0].n_cells == 3       # A, B (2018), C
    assert (part / "cell_year_2019.json").exists() and not list(metrics.rglob("*.tmp"))


def test_changing_the_grid_invalidates_the_caches_and_rebuilds_the_tables(tmp_path):
    source, metrics, ns = full_run(tmp_path)
    sink = ParquetSink(metrics)
    assert cid(A) in set(sink.read("l5_cell_year").cell)
    stale = json.loads((metrics / "_partial_lote5/modis_2018/_done.json").read_text())
    assert stale["grid_deg"] == 0.01
    write_l1(metrics, world(), grid=0.1)                                  # o L1 tambem tem de estar na nova grelha
    ns.update(GRID_DEG=0.1, STATS_GRID_DEG=0.1)
    start(ns, source)
    run(ns, source)
    new = json.loads((metrics / "_partial_lote5/modis_2018/_done.json").read_text())
    assert new["grid_deg"] == 0.1 and new["signature"]["grid_deg"] == 0.1
    cy = sink.read("l5_cell_year")
    assert set(cy.cell) == {cid(p, 0.1) for p in (A, B, C, D)} and cid(A) not in set(cy.cell)
    assert sink.read("_runs").grid_deg.tolist() == [0.1]
    assert set(cy.lat.round(3)) == {10.05, 11.05, 40.05, 12.05}
    a6 = sink.read("l5_add06_union_step").set_index(["cell", "year"])
    assert a6.loc[(GLOBAL_CELL, 2019), ["sum_modis", "sum_combined"]].tolist() == [366, 367]
    ns.update(GRID_DEG=0.01, STATS_GRID_DEG=0.01)                         # voltar a 0.01 nao mistura grelhas
    write_l1(metrics, world(), grid=0.01)
    start(ns, source)
    run(ns, source)
    assert set(sink.read("l5_cell_year").cell) == {cid(p) for p in (A, B, C, D)}


def test_stats_grid_is_used_by_add06_only(tmp_path):
    source, metrics, ns = prepare(tmp_path, stats_grid=0.1)
    ns["STATS_GRID_DEG"] = 0.1
    start(ns, source)
    run(ns, source)
    sink = ParquetSink(metrics)
    assert set(sink.read("l5_cell_year").cell) == {cid(p) for p in (A, B, C, D)}               # base a 0.01
    a6 = sink.read("l5_add06_union_step")
    assert set(a6[~is_global(a6)].cell) == {cid(p, 0.1) for p in (A, B, C, D)}                 # estatistica a 0.1
    assert set(a6[~is_global(a6)].lat.round(3)) == {10.05, 11.05, 12.05, 40.05}
    assert a6.set_index(["cell", "year"]).loc[(GLOBAL_CELL, 2018), "sum_modis"] == 367
    assert json.loads(sink.read("_runs").params.iloc[0])["stats_grid_deg"] == 0.1
    ns["STATS_GRID_DEG"] = 0.007                                                               # nao e uma grelha valida / multiplo
    with pytest.raises(ValueError):
        start(ns, source)


def test_max_unknown_days_reaches_add06_and_esp06(tmp_path):
    source, metrics, ns = full_run(tmp_path)
    sink = ParquetSink(metrics)
    validity = sink.read("l1_meta_month_validity")
    hit = (validity.year == 2019) & (validity.month == 3) & validity.series.isin(["modis", "combined"])
    validity.loc[hit, "n_unknown_days"] = 1
    write_table(sink, "l1_meta_month_validity", validity, grid_deg=0.01, partition_by=[])
    write_table(sink, "l1_meta_year_validity", year_validity(validity), grid_deg=0.01, partition_by=[])
    run(ns, source, ("run", "publish"))
    ix = sink.read("l5_add06_union_step").set_index(["cell", "year"])
    assert ix.loc[(cid(A), 2019), "n_months"] == 11 and ix.loc[(GLOBAL_CELL, 2019), "n_months"] == 11
    assert rows(sink.read("l5_esp06_interannual"), series="modis").iloc[0].n_years_analysed == 1   # 2019 deixa de ser valido
    ns["MAX_UNKNOWN_DAYS"] = 1
    run(ns, source, ("run", "publish"))
    ix = sink.read("l5_add06_union_step").set_index(["cell", "year"])
    assert ix.loc[(cid(A), 2019), "n_months"] == 12 and ix.loc[(GLOBAL_CELL, 2019), "sum_modis"] == 366
    assert rows(sink.read("l5_esp06_interannual"), series="modis").iloc[0].n_years_analysed == 2
    assert json.loads(sink.read("_runs").params.iloc[0])["max_unknown_days"] == 1


def test_missing_inputs_fail_clearly(tmp_path):
    source = cells()
    (tmp_path / "metrics").mkdir()
    with pytest.raises(AssertionError, match="notebook 01"):                 # sem processed/
        exec(source["defs"], dict(namespace(tmp_path), **_params(source)))
    write_drive(tmp_path)
    ns = namespace(tmp_path)
    exec(source["params"], ns)
    import shutil                                                           # tabela do L1 em falta: erro claro
    shutil.rmtree(tmp_path / "metrics/l1_cal_monthly")
    with pytest.raises(FileNotFoundError, match="02_metrics_lote1.*l1_cal_monthly|l1_cal_monthly.*02_metrics_lote1"):
        exec(source["defs"], ns)
    write_l1(tmp_path / "metrics", world())
    shutil.rmtree(tmp_path / "metrics/l1_meta_year_validity")
    with pytest.raises(FileNotFoundError, match="l1_meta_year_validity"):
        exec(source["defs"], ns)


def _params(source):
    ns = {}
    exec(source["params"], ns)
    return {k: v for k, v in ns.items() if k.isupper()}


def test_selection_that_matches_nothing_fails_clearly(tmp_path):
    source, metrics, ns = prepare(tmp_path)
    start(ns, source)
    ns["SENSORS"] = {"viirs"}
    with pytest.raises(ValueError, match="nenhum ficheiro.*viirs-jpss1"):
        run(ns, source)
    ns.update(SENSORS={"modis"}, YEARS={1999})
    with pytest.raises(ValueError, match="nenhum ficheiro selecionado"):
        run(ns, source)
    ns.update(SENSORS={"modis"}, YEARS={2018, 1999})
    with pytest.raises(FileNotFoundError, match="1999"):
        run(ns, source)
    assert not (metrics / "_runs").exists()


def test_partial_run_one_year_only_counts_processed_years_in_esp06(tmp_path):
    source, metrics, ns = full_run(tmp_path, YEARS={2018})
    sink = ParquetSink(metrics)
    m = rows(sink.read("l5_esp06_interannual"), series="modis").iloc[0]
    # so 2018 foi processado: 1 ano analisado, nenhuma celula em 2 anos (e nao 2 anos com 0% de recorrencia)
    assert (m.n_years_analysed, m.n_cells, m.n_cells_2plus_years, m.pct_cells_2plus) == (1, 3, 0, 0.0)
    assert set(sink.read("l5_esp02_active_cells").year) == {2018}
    assert set(sink.read("l5_add06_union_step").year) == {2018}


def test_partial_run_without_viirs_has_no_combined_and_verification_passes(tmp_path):
    source, metrics, ns = full_run(tmp_path, SENSORS={"modis"}, YEARS={2019})
    sink = ParquetSink(metrics)
    # 2019 tem tambem VIIRS em processed/: sem ele a serie `combined` seria so MODIS e fica de fora
    assert set(sink.read("l5_esp02_active_cells").series) == {"modis"}
    assert set(sink.read("l5_esp06_interannual").series) == {"modis"}
    assert set(sink.read("l5_cell_year").series) == {"modis"}
    assert sink.read("l5_esp06_interannual").n_years_analysed.tolist() == [1]
    assert sink.read("l5_add06_union_step").empty                      # ADD-06 precisa de modis e combined
    assert set(sink.read("l5_qa05_confirmed_days").instrument) == {"MODIS"}
    assert set(sink.read("l5_qa05_confirmed_days").year) == {2019}
    assert set(sink.read("l5_add05_type_sensitivity").instrument) == {"MODIS"}


def test_partial_run_viirs_only_passes_verification(tmp_path):
    source, metrics, ns = full_run(tmp_path, SENSORS={"viirs-jpss1"}, YEARS={2019})
    sink = ParquetSink(metrics)
    assert set(sink.read("l5_esp02_active_cells").series) == {"viirs"}
    assert set(sink.read("l5_cell_year").cell) == {cid(A), cid(D)}


def test_year_without_eligible_cells_does_not_break_consolidation(tmp_path):
    only_low = {("modis", 2018): build_processed([dict(confidence_class="l", confidence_raw="10")])}
    write_drive(tmp_path, files=only_low)
    source = cells()
    ns = namespace(tmp_path)
    exec(source["params"], ns)
    ns.update(SENSORS={"modis"})
    start(ns, source)
    run(ns, source)
    sink = ParquetSink(tmp_path / "metrics")
    assert sink.read("l5_cell_year").empty and sink.read("l5_esp02_active_cells").empty
    assert sink.read("l5_esp06_cell_years_active").empty and sink.read("l5_add05_type_sensitivity").empty
    e6 = sink.read("l5_esp06_interannual")
    assert (e6.n_cells == 0).all() and set(e6.cell) <= {GLOBAL_CELL}       # sem celulas: nunca ha recorrencia
    assert sink.read("l5_add06_union_step").empty and TABLES <= set(sink.names())
    assert sink.read("_runs").lote.tolist() == ["lote5"]


def test_snpp_files_and_stale_cached_years_never_enter_core_outputs(tmp_path):
    source, metrics, ns = full_run(tmp_path)
    sink = ParquetSink(metrics)
    before = {n: sink.read(n) for n in TABLES}
    snpp = build_processed([dict(country="SNPP_ONLY", instrument="VIIRS", satellite="N",
                                 latitude=60.0, longitude=10.0, acq_date="2018-03-01")])
    snpp.to_parquet(tmp_path / "processed/viirs-snpp_2018.parquet", index=False)
    stale = metrics / "_partial_lote5/viirs-snpp_2018"
    stale.mkdir()
    (stale / "_done.json").write_text(json.dumps(dict(sensor="viirs-snpp", year=2018, grid_deg=0.01)))
    # Old complete-looking annual caches must not become current input.
    pd.DataFrame(dict(series=["viirs"], cell=[999], year=[1999], n_days=[1])).to_parquet(
        metrics / "_partial_lote5/cell_year_1999.parquet", index=False)
    annual_path = metrics / "_partial_lote5/cell_year_2018.parquet"      # a contaminated cache of a selected year
    annual = pd.read_parquet(annual_path)
    contaminated = annual.iloc[[0]].copy()
    contaminated["cell"] = cid((60.0, 10.0))
    pd.concat([annual, contaminated], ignore_index=True).to_parquet(annual_path, index=False)
    (metrics / "_partial_lote5/cell_year_2018.json").write_text(json.dumps({"schema": 1}))
    run(ns, source)
    for name, expected in before.items():
        got = sink.read(name)
        pd.testing.assert_frame_equal(got.sort_values(list(got.columns)).reset_index(drop=True),
                                      expected.sort_values(list(expected.columns)).reset_index(drop=True))
    params = json.loads(sink.read("_runs").params.iloc[0])
    assert params["sensors"] == ["modis", "viirs-jpss1"] and params["years"] == [2018, 2019]
    assert (stale / "_done.json").exists() and (metrics / "_partial_lote5/cell_year_1999.parquet").exists()
    ns["SENSORS"] = None                                                  # None == o mesmo nucleo
    run(ns, source)
    assert sink.read("l5_cell_year").shape == before["l5_cell_year"].shape
    ns["SENSORS"] = {"viirs-snpp"}
    with pytest.raises(ValueError, match="09_har12_snpp"):
        run(ns, source)


def test_changed_selection_ignores_completed_unselected_core_caches(tmp_path):
    source, metrics, ns = full_run(tmp_path)
    ns.update(SENSORS={"modis"}, YEARS={2019})
    run(ns, source)
    sink = ParquetSink(metrics)
    for name in ["l5_esp02_active_cells", "l5_esp03_recurrence", "l5_add05_type_sensitivity", "l5_cell_year"]:
        assert set(sink.read(name).year) == {2019}
    assert set(sink.read("l5_esp02_active_cells").series) == {"modis"}
    assert set(sink.read("l5_add05_type_sensitivity").instrument) == {"MODIS"}
    assert set(sink.read("l5_qa05_confirmed_days").instrument) == {"MODIS"}
    assert set(sink.read("l5_qa05_confirmed_days").year) == {2019}
    assert sink.read("l5_add06_union_step").empty


def test_failed_stage_leaves_no_run_record(tmp_path):
    files = world()
    files[("viirs-jpss1", 2019)] = files[("modis", 2019)]                  # MODIS rows in a VIIRS file
    write_drive(tmp_path, files=files, with_l1=False)
    write_l1(tmp_path / "metrics", world())
    source = cells()
    ns = namespace(tmp_path)
    exec(source["params"], ns)
    start(ns, source)
    with pytest.raises(ValueError, match="instrument does not match"):
        run(ns, source)
    assert not (tmp_path / "metrics/_runs").exists()
    assert not any(n.startswith("l5_") for n in ParquetSink(tmp_path / "metrics").names())


def test_dates_outside_the_file_year_fail_before_run_is_recorded(tmp_path):
    files = world()
    stray = build_processed([dict(latitude=A[0], longitude=A[1], acq_date="2019-01-01")])
    files[("modis", 2018)] = pd.concat([files[("modis", 2018)], stray], ignore_index=True)
    write_drive(tmp_path, files=files, with_l1=False)
    write_l1(tmp_path / "metrics", files)
    source = cells()
    ns = namespace(tmp_path)
    exec(source["params"], ns)
    start(ns, source)
    with pytest.raises(AssertionError, match="chaves repetidas"):
        run(ns, source)
    assert not (tmp_path / "metrics/_runs").exists()


def test_verification_detects_a_cell_year_that_disagrees_with_the_l1_annual(tmp_path):
    source, metrics, ns = full_run(tmp_path)
    sink = ParquetSink(metrics)
    annual = sink.read("l1_cal_annual")
    annual.loc[(annual.cell == cid(B)) & (annual.series == "modis") & (annual.year == 2018), "cell_days"] = 5
    write_table(sink, "l1_cal_annual", annual, grid_deg=0.01)
    with pytest.raises(AssertionError, match="CAL-04"):
        run(ns, source, ("verify",))
    write_table(sink, "l1_cal_annual", sink.read("l1_cal_annual").iloc[:-1], grid_deg=0.01)
    with pytest.raises(AssertionError, match="CAL-04"):                     # celula em falta no L1 tambem falha
        run(ns, source, ("verify",))
