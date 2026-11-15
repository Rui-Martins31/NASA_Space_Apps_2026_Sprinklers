"""Teste do notebook 06_metrics_lote5.ipynb executado em local com uma "Drive" simulada.

Mundo sintetico (2018-2019, um registo por dia e sensor, por isso todos os anos sao validos):
  PT: celula A (10.05, 20.05) todos os dias, MODIS e VIIRS; celula B (11.05, 20.05) so em 2018-06-01 e
      2019-06-01 (MODIS); celula D (12.05, 20.05) so em 2019-07-07 (VIIRS); celula E (13.05, 20.05) em
      2018-02-02 com type=1 (MODIS, nao elegivel por defeito).
  ES: celula C (40.05, -3.05) so em 2018-03-03 (MODIS).
"""
import ast
import contextlib
import datetime as dt
import io
import json
import re
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("pyarrow")

from helpers_lote1 import build_processed  # noqa: E402
from metrics.calendar_metrics import (  # noqa: E402
    cal_annual, cal_coverage, cal_daily, cal_monthly, eligible_cell_days, global_day_counts,
)

REPO = Path(__file__).resolve().parents[3]
NOTEBOOK = REPO / "data/pipeline/notebooks/06_metrics_lote5.ipynb"
A, B, C, D, E = (10.05, 20.05), (11.05, 20.05), (40.05, -3.05), (12.05, 20.05), (13.05, 20.05)


def world():
    """{(sensor, ano): DataFrame processed} do mundo descrito acima."""
    out = {}
    for year in (2018, 2019):
        modis, viirs = [], []
        day = dt.date(year, 1, 1)
        while day.year == year:
            iso = day.isoformat()
            modis.append(dict(country="PT", latitude=A[0], longitude=A[1], acq_date=iso))
            viirs.append(dict(country="PT", instrument="VIIRS", satellite="N20",
                              latitude=A[0], longitude=A[1], acq_date=iso))
            day += dt.timedelta(days=1)
        modis.append(dict(country="PT", latitude=B[0], longitude=B[1], acq_date=f"{year}-06-01"))
        if year == 2018:
            modis.append(dict(country="ES", satellite="Aqua", latitude=C[0], longitude=C[1], acq_date="2018-03-03"))
            modis.append(dict(country="PT", latitude=E[0], longitude=E[1], acq_date="2018-02-02", type=1))
        else:
            viirs.append(dict(country="PT", instrument="VIIRS", satellite="N20",
                              latitude=D[0], longitude=D[1], acq_date="2019-07-07"))
        if year == 2018:       # pais com anos validos mas sem nenhuma celula elegivel
            modis.append(dict(country="ZZ", latitude=50.05, longitude=5.05, acq_date="2018-04-04",
                              confidence_class="l", confidence_raw="10"))
        out[("modis", year)] = build_processed(modis)
        out[("viirs-jpss1", year)] = build_processed(viirs)
    return out


def write_drive(root, with_l1=True, files=None):
    processed = root / "processed"
    processed.mkdir()
    files = files if files is not None else world()
    for (sensor, year), df in files.items():
        df.to_parquet(processed / f"{sensor}_{year}.parquet", index=False)
    metrics = root / "metrics"
    metrics.mkdir()
    if with_l1:
        allrows = pd.concat(files.values(), ignore_index=True)
        cov = cal_coverage(global_day_counts(allrows))
        cd = pd.concat([eligible_cell_days(df) for df in files.values()], ignore_index=True)
        monthly = cal_monthly(cal_daily(cd), cov, sorted(allrows["country"].unique()))
        for name, tbl in {"l1_cal_coverage": cov, "l1_cal_monthly": monthly,
                          "l1_cal_annual": cal_annual(monthly)}.items():
            tbl.to_parquet(metrics / f"{name}.parquet", index=False)
    return metrics


def load_sources():
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    sources = []
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == [] and cell["execution_count"] is None
            source = "".join(cell["source"])
            ast.parse(source)
            sources.append(source)
    return sources


def test_notebook_is_clean():
    text = NOTEBOOK.read_text(encoding="utf-8")
    assert not re.search(r"[A-Za-z]:\\\\|/Users/|C:/", text), "caminho do PC no notebook"
    sources = load_sources()
    assert len(sources) == 6
    assert "git clone" in sources[0] or "git', 'clone'" in sources[0]


def rows(df, **where):
    sel = df
    for k, v in where.items():
        sel = sel[sel[k] == v]
    return sel


def test_notebook_pipeline_resume_grid_change_and_missing_input(tmp_path):
    sources = load_sources()
    metrics = write_drive(tmp_path)
    ns = dict(ROOT=tmp_path, REPO=REPO)
    with contextlib.redirect_stdout(io.StringIO()):
        for src in sources[1:]:
            exec(compile(src, "06_metrics_lote5.ipynb", "exec"), ns)
        t = ns["tables"]
        assert sorted(t) == ["l5_add05_type_sensitivity", "l5_add06_union_step", "l5_esp02_active_cells",
                             "l5_esp03_recurrence", "l5_esp06_interannual", "l5_qa05_confirmed_days"]
        for name, tbl in t.items():                      # o que esta em disco e o que esta em memoria
            on_disk = pd.read_parquet(metrics / f"{name}.parquet")
            assert len(on_disk) == len(tbl) and list(on_disk.columns) == list(tbl.columns)
        assert not list(metrics.glob("*.tmp"))

        # ESP-02: celulas distintas por pais, serie e ano (calculado a mao no cabecalho do ficheiro)
        e2 = {(r.country, r.series, r.year): r.n_active_cells for r in t["l5_esp02_active_cells"].itertuples()}
        assert e2 == {("ES", "combined", 2018): 1, ("ES", "modis", 2018): 1,
                      ("PT", "combined", 2018): 2, ("PT", "combined", 2019): 3,
                      ("PT", "modis", 2018): 2, ("PT", "modis", 2019): 2,
                      ("PT", "viirs", 2018): 1, ("PT", "viirs", 2019): 2}
        # ESP-03 PT modis 2018: dias por celula [365, 1] -> media 183, mediana 183, p90 = 1 + 0.9*364 = 328.6
        r = rows(t["l5_esp03_recurrence"], country="PT", series="modis", year=2018).iloc[0]
        assert (r.n_active_cells, r.mean_days, r.median_days, r.max_days) == (2, 183.0, 183.0, 365)
        assert r.p90_days == pytest.approx(328.6)
        assert (r.n_cells_1d, r.n_cells_2_5d, r.n_cells_6_15d, r.n_cells_16plus) == (1, 0, 0, 1)
        # ESP-06: PT modis A e B em 2 anos; PT viirs A em 2 anos e D em 1; ES modis C em 1 ano
        e6 = t["l5_esp06_interannual"]
        pt_m = rows(e6, country="PT", series="modis").iloc[0]
        assert (pt_m.n_years_analysed, pt_m.n_cells, pt_m.n_cells_2plus_years, pt_m.pct_cells_2plus,
                pt_m.mean_years_per_cell, pt_m.max_years) == (2, 2, 2, 100.0, 2.0, 2)
        pt_v = rows(e6, country="PT", series="viirs").iloc[0]
        assert (pt_v.n_cells, pt_v.n_cells_2plus_years, pt_v.pct_cells_2plus, pt_v.mean_years_per_cell) == (2, 1, 50.0, 1.5)
        es_m = rows(e6, country="ES", series="modis").iloc[0]
        assert (es_m.n_years_analysed, es_m.n_cells, es_m.n_cells_2plus_years, es_m.pct_cells_2plus) == (2, 1, 0, 0.0)
        zz_rows = rows(e6, country="ZZ", series="modis")
        assert len(zz_rows) == 1, "pais sem celulas elegiveis tem de aparecer no ESP-06"
        zz = zz_rows.iloc[0]
        assert (zz.n_years_analysed, zz.n_cells, zz.n_cells_2plus_years) == (2, 0, 0)
        assert pd.isna(zz.pct_cells_2plus) and pd.isna(zz.mean_years_per_cell) and pd.isna(zz.max_years)
        # ADD-05 PT MODIS 2018: default 366 linhas/celula-dias; sem filtro de type +1 (celula E, type 1)
        a5 = rows(t["l5_add05_type_sensitivity"], country="PT", year=2018, instrument="MODIS").set_index("variant")
        assert a5.loc["default", ["n_eligible", "n_cell_days"]].tolist() == [366, 366]
        assert a5.loc["no_type_filter", ["n_eligible", "n_cell_days"]].tolist() == [367, 367]
        assert a5.loc["no_type_filter", "delta_cell_days_pct"] == pytest.approx(100 / 366)
        assert a5.loc["type0_or_unknown", "delta_cell_days_pct"] == 0.0
        # QA-05: fevereiro de 2018 do MODIS tem 28 dias, todos com registos
        q = rows(t["l5_qa05_confirmed_days"], instrument="MODIS", year=2018, month=2).iloc[0]
        assert (q.n_days_expected, q.n_days_confirmed, q.pct_confirmed, q.scope) == (28, 28, 100.0, "global_proxy")
        # QA-05: janeiro de 2018 (primeiro mes do sensor) tambem completo; 2 sensores x 24 meses = 48 linhas
        jan = rows(t["l5_qa05_confirmed_days"], instrument="MODIS", year=2018, month=1).iloc[0]
        assert (jan.n_days_expected, jan.n_days_confirmed) == (31, 31)
        assert len(t["l5_qa05_confirmed_days"]) == 48
        # ADD-05: 5 grupos (pais, ano, instrumento) x 3 variantes; ES so tem a celula C
        full5 = t["l5_add05_type_sensitivity"]
        assert len(full5) == 15
        es = rows(full5, country="ES", year=2018, instrument="MODIS").set_index("variant")
        assert es["n_cell_days"].tolist() == [1, 1, 1] or es.loc["default", "n_cell_days"] == 1
        # ADD-06 PT: 2018 combined == modis (366); 2019 combined 367 (celula D so no VIIRS) vs modis 366
        a6 = t["l5_add06_union_step"].set_index(["country", "year"])
        assert a6.loc[("PT", 2018), "ratio_combined_modis"] == 1.0
        assert a6.loc[("PT", 2019), "sum_combined"] == 367 and a6.loc[("PT", 2019), "sum_modis"] == 366
        assert a6.loc[("PT", 2019), "excess_pct"] == pytest.approx(100 / 366)
        assert a6.loc[("PT", 2019), "n_months"] == 12

        # log e parametros
        log = pd.read_csv(metrics / "_log_lote5.csv")
        assert len(log) == 6 and json.loads((metrics / "_params_lote5.json").read_text())["grid_deg"] == 0.1

        # retoma: um segundo passe nao refaz parciais completos
        marker = metrics / "_partial_lote5/modis_2018/_done.json"
        mtime = marker.stat().st_mtime_ns
        exec(sources[3], ns)
        assert marker.stat().st_mtime_ns == mtime
        # parcial apagado e refeito
        part = metrics / "_partial_lote5/modis_2018/add05.parquet"
        part.unlink()
        (metrics / "_partial_lote5/modis_2018/_done.json").unlink()
        exec(sources[3], ns)
        assert part.exists()
        # mudar a grelha refaz tudo e regista a nova grelha
        ns["GRID_DEG"] = 0.25
        exec(sources[3], ns)
        assert json.loads(marker.read_text())["grid_deg"] == 0.25
        exec(sources[4], ns)                              # consolida de novo com a grelha nova, sem misturar
        assert json.loads((metrics / "_params_lote5.json").read_text())["grid_deg"] == 0.25
        ns["GRID_DEG"] = 0.1
        exec(sources[3], ns)                              # volta a 0.1: refaz os parciais (nao mistura grelhas)
        exec(sources[4], ns)

    # max_unknown_days chega ao ADD-06: com um mes de dias desconhecidos, 0 exclui-o e 1 tolera-o
    monthly = pd.read_parquet(metrics / "l1_cal_monthly.parquet")
    hit = (monthly.country == "PT") & (monthly.year == 2019) & (monthly.month == 3) & monthly.series.isin(["modis", "combined"])
    monthly.loc[hit, "n_unknown_days"] = 1
    monthly.to_parquet(metrics / "l1_cal_monthly.parquet", index=False)
    with contextlib.redirect_stdout(io.StringIO()):
        exec(sources[4], ns)
        assert ns["tables"]["l5_add06_union_step"].set_index(["country", "year"]).loc[("PT", 2019), "n_months"] == 11
        ns["MAX_UNKNOWN_DAYS"] = 1
        exec(sources[4], ns)
        assert ns["tables"]["l5_add06_union_step"].set_index(["country", "year"]).loc[("PT", 2019), "n_months"] == 12
        ns["MAX_UNKNOWN_DAYS"] = 0

    # tabela l1 em falta: erro claro
    (metrics / "l1_cal_monthly.parquet").unlink()
    with pytest.raises(FileNotFoundError, match="02_metrics_lote1.*l1_cal_monthly|l1_cal_monthly.*02_metrics_lote1"):
        exec(sources[1], ns)


def test_notebook_fails_clearly_without_processed(tmp_path):
    sources = load_sources()
    (tmp_path / "metrics").mkdir()
    with pytest.raises(AssertionError, match="notebook 01"):
        exec(sources[1], dict(ROOT=tmp_path, REPO=REPO))


def run_cells(root, **config):
    """Executa as celulas 1..5 com a configuracao dada (SENSORS/YEARS...) e devolve o namespace."""
    sources = load_sources()
    ns = dict(ROOT=root, REPO=REPO)
    with contextlib.redirect_stdout(io.StringIO()):
        exec(sources[1], ns)
        ns.update(config)
        for src in sources[2:]:
            exec(compile(src, "06_metrics_lote5.ipynb", "exec"), ns)
    return ns


def test_partial_run_one_year_only_counts_processed_years_in_esp06(tmp_path):
    write_drive(tmp_path)
    ns = run_cells(tmp_path, YEARS={2018})
    e6 = ns["tables"]["l5_esp06_interannual"]
    pt = rows(e6, country="PT", series="modis").iloc[0]
    # so 2018 foi processado: 1 ano analisado, nenhuma celula em 2 anos (e nao 2 anos com 0% de recorrencia)
    assert (pt.n_years_analysed, pt.n_cells, pt.n_cells_2plus_years, pt.pct_cells_2plus) == (1, 2, 0, 0.0)
    assert set(ns["tables"]["l5_esp02_active_cells"].year) == {2018}


def test_partial_run_without_viirs_has_no_combined_and_verification_passes(tmp_path):
    write_drive(tmp_path)
    ns = run_cells(tmp_path, SENSORS={"modis"}, YEARS={2019})
    t = ns["tables"]
    # 2019 tem tambem VIIRS em processed/: sem ele a serie `combined` seria so MODIS e fica de fora
    assert set(t["l5_esp02_active_cells"].series) == {"modis"}
    assert set(t["l5_esp06_interannual"].series) == {"modis"}
    assert rows(t["l5_esp06_interannual"], country="PT").iloc[0].n_years_analysed == 1


def test_partial_run_viirs_only_passes_verification(tmp_path):
    write_drive(tmp_path)
    ns = run_cells(tmp_path, SENSORS={"viirs-jpss1"}, YEARS={2019})
    assert set(ns["tables"]["l5_esp02_active_cells"].series) == {"viirs"}


def test_selection_that_matches_nothing_fails_clearly(tmp_path):
    write_drive(tmp_path)
    with pytest.raises(ValueError, match="nenhum ficheiro.*viirs-jpss1"):
        run_cells(tmp_path, SENSORS={"viirs"})


def test_year_without_eligible_cells_does_not_break_consolidation(tmp_path):
    only_low = {("modis", 2018): build_processed([dict(confidence_class="l", confidence_raw="10")])}
    write_drive(tmp_path, files=only_low)
    ns = run_cells(tmp_path)
    assert len(ns["tables"]["l5_esp02_active_cells"]) == 0
    e6 = ns["tables"]["l5_esp06_interannual"]
    assert set(e6.n_cells) <= {0}


def test_snpp_files_and_stale_cached_years_never_enter_core_outputs(tmp_path):
    metrics = write_drive(tmp_path)
    ns = run_cells(tmp_path)
    before = {name: frame.copy(deep=True) for name, frame in ns["tables"].items()}
    snpp = build_processed([dict(country="SNPP_ONLY", instrument="VIIRS", satellite="N",
                                 latitude=60.0, longitude=10.0, acq_date="2018-03-01")])
    snpp.to_parquet(tmp_path / "processed/viirs-snpp_2018.parquet", index=False)
    stale = metrics / "_partial_lote5/viirs-snpp_2018"
    stale.mkdir()
    (stale / "_done.json").write_text(json.dumps(dict(sensor="viirs-snpp", year=2018, grid_deg=0.1)))
    # Old complete-looking source and annual caches must not become current input.
    pd.DataFrame(dict(country=["SNPP_ONLY"], series=["viirs"], cell=[999], year=[1999], n_days=[1])).to_parquet(
        metrics / "_partial_lote5/cell_year_1999.parquet", index=False)
    # A pre-separation annual cache for a selected year also needs rebuilding.
    annual_path = metrics / "_partial_lote5/cell_year_2018.parquet"
    annual = pd.read_parquet(annual_path)
    contaminated = annual.iloc[[0]].copy()
    contaminated["country"] = "SNPP_ONLY"
    pd.concat([annual, contaminated], ignore_index=True).to_parquet(annual_path, index=False)
    (metrics / "_partial_lote5/cell_year_2018.json").write_text(json.dumps({"schema": 1}))
    updated = run_cells(tmp_path)
    for name, expected in before.items():
        pd.testing.assert_frame_equal(updated["tables"][name], expected)
    params = json.loads((metrics / "_params_lote5.json").read_text())
    assert params["sensors"] == ["modis", "viirs-jpss1"]
    assert params["years"] == [2018, 2019]
    assert (stale / "_done.json").exists()
    assert (metrics / "_partial_lote5/cell_year_1999.parquet").exists()
    all_core = run_cells(tmp_path, SENSORS=None)
    for name, expected in before.items():
        pd.testing.assert_frame_equal(all_core["tables"][name], expected)
    with pytest.raises(ValueError, match="09_har12_snpp"):
        run_cells(tmp_path, SENSORS={"viirs-snpp"})


def test_changed_selection_ignores_completed_unselected_core_caches(tmp_path):
    write_drive(tmp_path)
    run_cells(tmp_path)
    ns = run_cells(tmp_path, SENSORS={"modis"}, YEARS={2019})
    for name in ["l5_esp02_active_cells", "l5_esp03_recurrence", "l5_add05_type_sensitivity"]:
        assert set(ns["tables"][name].year) == {2019}
    assert set(ns["tables"]["l5_esp02_active_cells"].series) == {"modis"}
    assert set(ns["tables"]["l5_add05_type_sensitivity"].instrument) == {"MODIS"}
    assert set(ns["tables"]["l5_qa05_confirmed_days"].instrument) == {"MODIS"}
    assert set(ns["tables"]["l5_qa05_confirmed_days"].year) == {2019}
    assert ns["tables"]["l5_add06_union_step"].empty
