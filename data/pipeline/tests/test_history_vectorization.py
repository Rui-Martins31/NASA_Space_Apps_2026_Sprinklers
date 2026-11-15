"""Equivalencia entre as estatisticas de historico vetorizadas e a implementacao antiga (lenta).

As funcoes `_slow_*` sao copias das implementacoes anteriores a vetorizacao (ciclos Python por grupo ou
por linha), apenas com a chave `country` trocada por `cell`. Os testes comparam o resultado novo com o
antigo em dados aleatorios com semente fixa: varias celulas e series, anos em falta, meses parciais e
com dias desconhecidos, grupos com menos de 5 anos, empates, zeros e janelas de referencia.
"""
import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from helpers_lote4 import recs
from metrics import calendar_summary as cs
from metrics import history_cumulative as hc
from metrics import history_distribution as hd
from metrics import history_pool as hp
from metrics.common import require_columns

KEYS = ["cell", "series", "month"]


# ====================================================================== referencias lentas
def _slow_pool_groups(monthly, ref_start, ref_end, max_unknown_days):
    ok = hp.valid_mask(monthly, max_unknown_days)
    if ref_start is not None:
        ok &= monthly["year"] >= ref_start
    if ref_end is not None:
        ok &= monthly["year"] <= ref_end
    pool = monthly[ok.to_numpy()]
    return {k: (g["year"].to_numpy(), g["cell_days"].to_numpy(dtype="float64"))
            for k, g in pool.groupby(KEYS, sort=False, observed=True)}


def _slow_reference_fixed(monthly, ref_start=None, ref_end=None, min_ref_years=hp.MIN_REF_YEARS,
                          max_unknown_days=hp.MAX_UNKNOWN_DAYS):
    require_columns(monthly, hp.REQUIRED)
    hp.require_unique(monthly, ["cell", "series", "year", "month"])
    groups = _slow_pool_groups(monthly, ref_start, ref_end, max_unknown_days)
    pairs = monthly[["cell", "series"]].drop_duplicates().sort_values(["cell", "series"])
    rows = []
    for cell, series in pairs.itertuples(index=False):
        for month in range(1, 13):
            _, vals = groups.get((cell, series, month), (None, np.empty(0)))
            n = len(vals)
            ok = n >= max(min_ref_years, 1)
            rows.append({
                "cell": cell, "series": series, "month": month, "n_ref_years": n,
                "ref_mean": float(vals.mean()) if ok else np.nan,
                "ref_std": (float(vals.std(ddof=1)) if n > 1 else np.nan) if ok else np.nan,
                "ref_median": float(np.median(vals)) if ok else np.nan,
                "ref_p10": float(np.percentile(vals, 10, method="linear")) if ok else np.nan,
                "ref_p90": float(np.percentile(vals, 90, method="linear")) if ok else np.nan})
    out = pd.DataFrame(rows, columns=hp.FIXED_COLUMNS)
    out["month"] = out["month"].astype("int64")
    out["n_ref_years"] = out["n_ref_years"].astype("int64")
    return out.reset_index(drop=True)


def _slow_reference_loo(monthly, ref_start=None, ref_end=None, min_ref_years=hp.MIN_REF_YEARS,
                        max_unknown_days=hp.MAX_UNKNOWN_DAYS):
    require_columns(monthly, hp.REQUIRED)
    hp.require_unique(monthly, ["cell", "series", "year", "month"])
    m = monthly[hp.REQUIRED].copy()
    m["valid_month"] = hp.valid_mask(m, max_unknown_days).to_numpy()
    groups = _slow_pool_groups(monthly, ref_start, ref_end, max_unknown_days)
    parts = []
    need = max(min_ref_years, 1)
    for key, g in m.groupby(KEYS, sort=False, observed=True):
        years, vals = groups.get(key, (np.empty(0, dtype="int64"), np.empty(0)))
        ev_year = g["year"].to_numpy()
        x = g["cell_days"].to_numpy(dtype="float64")
        use = years[None, :] != ev_year[:, None]
        n = use.sum(axis=1)
        ok = n >= need
        safe_n = np.where(n > 0, n, 1)
        mean = (use * vals[None, :]).sum(axis=1) / safe_n
        ss = (use * (vals[None, :] - mean[:, None]) ** 2).sum(axis=1)
        std = np.where(n > 1, np.sqrt(ss / np.where(n > 1, n - 1, 1)), np.nan)
        below = (use & (vals[None, :] < x[:, None])).sum(axis=1)
        equal = (use & (vals[None, :] == x[:, None])).sum(axis=1)
        valid = g["valid_month"].to_numpy()
        pos_ok = ok & valid
        part = g[["cell", "series", "year", "month", "cell_days", "valid_month"]].copy()
        part["n_ref_years"] = n.astype("int64")
        part["ref_mean"] = np.where(ok, mean, np.nan)
        part["ref_std"] = np.where(ok, std, np.nan)
        part["n_below"] = pd.array(np.where(pos_ok, below, 0), dtype="Int64")
        part["n_equal"] = pd.array(np.where(pos_ok, equal, 0), dtype="Int64")
        part.loc[~pos_ok, ["n_below", "n_equal"]] = pd.NA
        parts.append(part)
    if not parts:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in hp.LOO_COLUMNS})
    out = pd.concat(parts, ignore_index=True)[hp.LOO_COLUMNS]
    out["valid_month"] = out["valid_month"].astype(bool)
    return out.sort_values(["cell", "series", "year", "month"]).reset_index(drop=True)


def _slow_his09(monthly, ref_start=None, ref_end=None, min_ref_years=hp.MIN_REF_YEARS,
                max_unknown_days=hp.MAX_UNKNOWN_DAYS):
    ref = _slow_reference_fixed(monthly, ref_start, ref_end, min_ref_years, max_unknown_days)
    band = ref.rename(columns={"ref_p10": "p10", "ref_p90": "p90"})[hd.HIS02_COLUMNS]
    if monthly.empty:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in hd.HIS09_COLUMNS})
    m = monthly[["cell", "series", "year", "month", "cell_days"]].assign(
        valid_month=hp.valid_mask(monthly, max_unknown_days).to_numpy()).merge(
        band[["cell", "series", "month", "p90"]], on=["cell", "series", "month"], how="left")
    evaluated = m["valid_month"].astype(bool) & m["p90"].notna()
    above = evaluated & (m["cell_days"].astype("float64") > m["p90"])
    rows = []
    for (cell, series, year), idx in m.groupby(["cell", "series", "year"], sort=False, observed=True).groups.items():
        ev = evaluated.loc[idx]
        ab = above.loc[idx]
        months = sorted(int(x) for x in m.loc[idx][ab.to_numpy()]["month"])
        rows.append({"cell": cell, "series": series, "year": year,
                     "n_months_evaluated": int(ev.sum()), "n_months_above": int(ab.sum()),
                     "months_above": ",".join(str(x) for x in months)})
    out = pd.DataFrame(rows, columns=hd.HIS09_COLUMNS)
    out["year"] = out["year"].astype("int64")
    return out[hd.HIS09_COLUMNS].sort_values(["cell", "series", "year"]).reset_index(drop=True)


def _slow_month_lookup(monthly, max_unknown_days):
    ok = hp.valid_mask(monthly, max_unknown_days).to_numpy()
    keys = zip(monthly["cell"], monthly["series"], monthly["year"], monthly["month"])
    return {k: (int(c), bool(v)) for k, c, v in zip(keys, monthly["cell_days"], ok)}


def _slow_his07(monthly, ref_start=None, ref_end=None, min_ref_years=hp.MIN_REF_YEARS,
                max_unknown_days=hp.MAX_UNKNOWN_DAYS):
    hp.require_unique(monthly, ["cell", "series", "year", "month"])
    look = _slow_month_lookup(monthly, max_unknown_days)
    rows = []
    for (cell, series, year, month) in look:
        ytd, comparable = 0, True
        for m in range(1, month + 1):
            item = look.get((cell, series, year, m))
            if item is None:
                ytd, comparable = None, False
                break
            ytd += item[0]
            comparable &= item[1]
        rows.append([cell, series, int(year), int(month), ytd, comparable])
    pools: dict = {}
    for cell, series, year, month, ytd, comp in rows:
        if not comp:
            continue
        if (ref_start is not None and year < ref_start) or (ref_end is not None and year > ref_end):
            continue
        pools.setdefault((cell, series, month), {})[year] = ytd
    need = max(min_ref_years, 1)
    out_rows = []
    for cell, series, year, month, ytd, comp in rows:
        vals = [v for y, v in pools.get((cell, series, month), {}).items() if y != year]
        ok = comp and len(vals) >= need
        mean = sum(vals) / len(vals) if ok else np.nan
        out_rows.append([cell, series, year, month, ytd, comp, len(vals), mean,
                         ytd - mean if ok else np.nan])
    out = pd.DataFrame(out_rows, columns=hc.YTD_COLUMNS)
    out["ytd_cell_days"] = pd.array(out["ytd_cell_days"].tolist(), dtype="Int64")
    out["comparable"] = out["comparable"].astype(bool)
    out["n_ref_years"] = out["n_ref_years"].astype("int64")
    out["ref_ytd_mean"] = out["ref_ytd_mean"].astype("float64")
    out["ytd_diff"] = out["ytd_diff"].astype("float64")
    return out.sort_values(["cell", "series", "year", "month"]).reset_index(drop=True)


def _slow_his08(monthly, max_unknown_days=hp.MAX_UNKNOWN_DAYS):
    hp.require_unique(monthly, ["cell", "series", "year", "month"])
    look = _slow_month_lookup(monthly, max_unknown_days)
    rows = []
    for (cell, series, year, month), (cd, valid) in look.items():
        prev = look.get((cell, series, year - 1, month))
        pair = prev is not None and prev[1] and valid
        diff = cd - prev[0] if pair else None
        pct = 100.0 * diff / prev[0] if pair and prev[0] != 0 else np.nan
        rows.append([cell, series, int(year), int(month), cd,
                     prev[0] if prev is not None else None, pair, diff, pct])
    out = pd.DataFrame(rows, columns=hc.YOY_COLUMNS)
    out["cell_days"] = out["cell_days"].astype("int64")
    out["prev_cell_days"] = pd.array(out["prev_cell_days"].tolist(), dtype="Int64")
    out["diff_abs"] = pd.array(out["diff_abs"].tolist(), dtype="Int64")
    out["valid_pair"] = out["valid_pair"].astype(bool)
    out["yoy_pct"] = out["yoy_pct"].astype("float64")
    return out.sort_values(["cell", "series", "year", "month"]).reset_index(drop=True)


def _slow_theil_sen(x, y):
    i, j = np.triu_indices(len(x), k=1)
    dx = x[j] - x[i]
    keep = dx != 0
    slopes = (y[j][keep] - y[i][keep]) / dx[keep]
    slope = float(np.median(slopes))
    return (slope, float(np.median(y - slope * x)),
            float(np.percentile(slopes, 2.5, method="linear")),
            float(np.percentile(slopes, 97.5, method="linear")))


def _slow_his10(annual, max_unknown_days=hp.MAX_UNKNOWN_DAYS, min_years=hc.MIN_TREND_YEARS):
    hp.require_unique(annual, ["cell", "series", "year"])
    work = annual[hc.ANNUAL_REQUIRED].copy()
    work["_ok"] = hp.valid_mask(work, max_unknown_days).to_numpy()
    rows = []
    for (cell, series), g in work.groupby(["cell", "series"], sort=True):
        g = g[g["_ok"]].sort_values("year")
        n = len(g)
        est = [np.nan] * 4
        if n > 0 and n >= min_years:
            est = _slow_theil_sen(g["year"].to_numpy(dtype="float64"),
                                  g["cell_days"].to_numpy(dtype="float64"))
        rows.append([cell, series, n,
                     int(g["year"].min()) if n else None, int(g["year"].max()) if n else None,
                     *est])
    out = pd.DataFrame(rows, columns=hc.TREND_COLUMNS)
    out["n_years"] = out["n_years"].astype("int64")
    for c in ("first_year", "last_year"):
        out[c] = pd.array(out[c].tolist(), dtype="Int64")
    for c in hc.TREND_COLUMNS[5:]:
        out[c] = out[c].astype("float64")
    return out.sort_values(["cell", "series"]).reset_index(drop=True)


def _slow_cal12(cal09):
    columns = cs.REFERENCE + ["share_pct", "is_peak_month"]
    source = cs._input(cal09, cs.REFERENCE)
    if source.empty:
        return cs._output(pd.DataFrame(), columns)
    groups = source.groupby(cs.GROUP, observed=True, dropna=False)
    totals = groups.mean_cell_days.transform(lambda values: values.sum(min_count=12))
    complete = groups.month.transform("nunique").eq(12)
    source["share_pct"] = 100.0 * source.mean_cell_days / totals.where(complete & totals.ne(0))
    peaks = source.loc[source.mean_cell_days.notna()].sort_values(
        ["mean_cell_days", "month"], ascending=[False, True]
    ).drop_duplicates(cs.GROUP)
    source["is_peak_month"] = source.index.isin(peaks.index)
    return cs._output(source, columns)


def _slow_cal09(monthly, ref_start=None, ref_end=None, min_ref_years=5, max_unknown_days=0):
    source = cs._input(monthly, cs.MONTHLY)
    if source.empty:
        return cs._output(pd.DataFrame(), cs.REFERENCE)
    skeleton = source[cs.GROUP].drop_duplicates().merge(pd.DataFrame({"month": range(1, 13)}), how="cross")
    pool = cs._reference_pool(source, ref_start, ref_end, max_unknown_days)
    summary = pool.groupby(cs.GROUP + ["month"], observed=True, dropna=False).agg(
        n_years=("year", "nunique"), mean_cell_days=("cell_days", "mean"),
    ).reset_index()
    result = skeleton.merge(summary, how="left", on=cs.GROUP + ["month"])
    result["n_years"] = result.n_years.fillna(0)
    result["mean_cell_days"] = result.mean_cell_days.where(result.n_years.ge(min_ref_years))
    return cs._output(result, cs.REFERENCE)


# ====================================================================== dados aleatorios
def random_monthly(seed, n_cells=12, years=range(2000, 2023), months=range(1, 13)):
    """Tabela mensal densa com buracos: celulas com poucos anos, meses/anos em falta, parciais,
    dias desconhecidos, empates (valores pequenos), zeros e celulas com todos os valores iguais."""
    rng = np.random.default_rng(seed)
    cells = rng.choice(np.arange(10, 10_000), size=n_cells, replace=False).astype("int64")
    frames = []
    for cell in cells:
        for series in ("modis", "viirs", "combined"):
            lo = rng.integers(0, 14)                            # inicio do intervalo da serie
            span = rng.integers(2, len(years) - lo + 1) if rng.random() < 0.8 else len(years) - lo
            yrs = np.array(list(years)[lo:lo + span], dtype="int64")
            if len(yrs) == 0:
                continue
            grid = pd.MultiIndex.from_product([yrs, list(months)], names=["year", "month"]).to_frame(index=False)
            scale = rng.choice([0, 1, 3, 40, 900])
            grid["cell_days"] = (rng.integers(0, 6, len(grid)) * scale if rng.random() < 0.9
                                 else np.full(len(grid), 7)).astype("int64")   # alguns grupos constantes
            grid["partial"] = rng.random(len(grid)) < 0.08
            grid["n_unknown_days"] = np.where(rng.random(len(grid)) < 0.08, rng.integers(1, 4, len(grid)), 0)
            grid = grid[rng.random(len(grid)) > 0.06]           # buracos
            grid["cell"] = cell
            grid["series"] = series
            frames.append(grid)
    df = pd.concat(frames, ignore_index=True)[["cell", "series", "year", "month", "cell_days",
                                               "partial", "n_unknown_days"]]
    df["partial"] = df["partial"].astype(bool)
    return df.sample(frac=1.0, random_state=seed).reset_index(drop=True)


def random_annual(seed, n_cells=60):
    """Tabela anual com grupos de 0 a 23 anos, parciais, dias desconhecidos, empates e series constantes."""
    rng = np.random.default_rng(seed)
    cells = rng.choice(np.arange(10, 10_000), size=n_cells, replace=False).astype("int64")
    frames = []
    for cell in cells:
        for series in ("modis", "viirs", "combined"):
            n = int(rng.integers(1, 24))
            years = np.sort(rng.choice(np.arange(2000, 2023), size=n, replace=False))
            kind = rng.integers(0, 3)
            if kind == 0:
                cell_days = rng.integers(0, 366, n)                                  # ruido
            elif kind == 1:
                cell_days = (3 * (years - 2000) + rng.integers(0, 4, n))             # tendencia com empates
            else:
                cell_days = np.full(n, 40)                                           # constante
            frames.append(pd.DataFrame({
                "cell": cell, "series": series, "year": years.astype("int64"),
                "cell_days": cell_days.astype("int64"), "partial": rng.random(n) < 0.15,
                "n_unknown_days": np.where(rng.random(n) < 0.1, rng.integers(1, 5, n), 0)}))
    df = pd.concat(frames, ignore_index=True)
    return df.sample(frac=1.0, random_state=seed + 1).reset_index(drop=True)


def _same(new, old, **kwargs):
    """Compara com tolerancia de arredondamento (somas em ordem diferente); `series` pode ser str/object."""
    new, old = new.copy(), old.copy()
    for frame in (new, old):
        if "series" in frame.columns:
            frame["series"] = frame["series"].astype(object)
    assert_frame_equal(new, old, check_dtype=False, rtol=1e-12, atol=1e-12, **kwargs)


SEEDS = [11, 12, 13]
OPTIONS = [dict(), dict(ref_start=2005, ref_end=2018), dict(ref_start=2010), dict(ref_end=2012, min_ref_years=3),
           dict(max_unknown_days=2, min_ref_years=1)]


# ====================================================================== equivalencia
@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("options", OPTIONS, ids=lambda o: str(o) or "default")
def test_reference_fixed_equals_slow(seed, options):
    df = random_monthly(seed)
    new, old = hp.reference_fixed(df, **options), _slow_reference_fixed(df, **options)
    _same(new, old)
    assert new["n_ref_years"].dtype == "int64" and new["cell"].dtype == "int64"
    assert (new["n_ref_years"] < 5).any() and (new["n_ref_years"] >= 5).any()      # ambos os ramos exercitados


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("options", OPTIONS, ids=lambda o: str(o) or "default")
def test_reference_loo_equals_slow(seed, options):
    df = random_monthly(seed)
    new, old = hp.reference_loo(df, **options), _slow_reference_loo(df, **options)
    _same(new, old)
    assert ((new["ref_std"] == 0) == (old["ref_std"] == 0)).all()          # std exatamente 0 (zscore NA) coincide
    assert (new["ref_std"] == 0).any()
    assert new["n_below"].dtype == "Int64" and new["n_below"].isna().any() and new["n_below"].notna().any()
    assert not new["valid_month"].all()


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("options", OPTIONS[:3], ids=lambda o: str(o) or "default")
def test_his09_equals_slow(seed, options):
    df = random_monthly(seed)
    new, old = hd.his09_months_above(df, **options), _slow_his09(df, **options)
    _same(new, old)
    assert (new["n_months_above"] > 0).any() and (new["months_above"] == "").any()


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("options", OPTIONS, ids=lambda o: str(o) or "default")
def test_his07_equals_slow(seed, options):
    df = random_monthly(seed)
    new, old = hc.his07_ytd(df, **options), _slow_his07(df, **options)
    _same(new, old)
    assert not new["comparable"].all() and new["ytd_cell_days"].isna().any() and new["ytd_diff"].notna().any()


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("max_unknown_days", [0, 2])
def test_his08_equals_slow(seed, max_unknown_days):
    df = random_monthly(seed)
    new, old = hc.his08_yoy(df, max_unknown_days), _slow_his08(df, max_unknown_days)
    _same(new, old)
    assert new["valid_pair"].any() and not new["valid_pair"].all() and new["yoy_pct"].isna().any()


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("min_years", [8, 3, 12])
def test_his10_equals_slow(seed, min_years):
    df = random_annual(seed)
    new, old = hc.his10_trend(df, min_years=min_years), _slow_his10(df, min_years=min_years)
    _same(new, old)
    assert new["slope_per_year"].notna().any() and new["slope_per_year"].isna().any()
    assert (new["n_years"] >= 8).any() and (new["n_years"] < 8).any()


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("options", [dict(), dict(ref_start=2004, ref_end=2016, min_ref_years=3)],
                         ids=lambda o: str(o) or "default")
def test_cal09_and_cal12_equal_slow(seed, options):
    df = random_monthly(seed)
    new09, old09 = cs.cal09_monthly_mean(df, **options), _slow_cal09(df, **options)
    _same(new09, old09)
    new12, old12 = cs.cal12_seasonal_profile(new09), _slow_cal12(old09)
    _same(new12, old12)
    assert new12["share_pct"].notna().any() and new12["share_pct"].isna().any() and new12["is_peak_month"].any()


def test_his05_his06_use_the_same_loo_and_stay_consistent_with_slow():
    """HIS-05/06 sao derivadas do LOO: com o LOO antigo dao as mesmas tabelas que com o novo."""
    df = random_monthly(21)
    new_z, new_p = hd.his05_zscore(df), hd.his06_percentile(df)
    original = hd.reference_loo
    try:
        hd.reference_loo = _slow_reference_loo
        old_z, old_p = hd.his05_zscore(df), hd.his06_percentile(df)
    finally:
        hd.reference_loo = original
    _same(new_z, old_z)
    _same(new_p, old_p)
    assert new_z["zscore"].notna().any() and new_p["percentile"].notna().any()


def test_his01_his02_equal_slow_fixed_reference():
    df = random_monthly(22)
    original = hd.reference_fixed
    try:
        hd.reference_fixed = _slow_reference_fixed
        old_med, old_band = hd.his01_hist_median(df), hd.his02_hist_band(df)
    finally:
        hd.reference_fixed = original
    _same(hd.his01_hist_median(df), old_med)
    _same(hd.his02_hist_band(df), old_band)


# ====================================================================== exemplos a mao e bordas
def test_worked_example_survives_vectorization():
    """Exemplo trabalhado do spec 7B: [10..60] no mes 3 -> anomalia LOO de 2003 = -6, soma LOO = 0."""
    rows = [dict(cell=5, series="modis", year=2001 + i, month=3, cell_days=v, partial=False, n_unknown_days=0)
            for i, v in enumerate([10, 20, 30, 40, 50, 60])]
    df = pd.DataFrame(rows)
    loo = hp.reference_loo(df)
    anomaly = loo["cell_days"] - loo["ref_mean"]
    assert anomaly.tolist() == [-30, -18, -6, 6, 18, 30]
    assert anomaly.sum() == pytest.approx(0.0, abs=1e-9)
    fixed = hp.reference_fixed(df)
    mar = recs(fixed[fixed["month"] == 3])[0]
    assert (mar["ref_mean"], mar["ref_median"], mar["n_ref_years"]) == (35.0, 35.0, 6)


def test_group_results_do_not_depend_on_other_cells():
    big = random_monthly(31, n_cells=15)
    one = big[big["cell"] == big["cell"].iloc[0]]
    for fn in (hp.reference_fixed, hp.reference_loo, hc.his07_ytd, hc.his08_yoy, hd.his09_months_above):
        full = fn(big)
        alone = full[full["cell"] == one["cell"].iloc[0]].reset_index(drop=True)
        assert_frame_equal(alone, fn(one))


def test_empty_pool_and_single_group_edge_cases():
    df = random_monthly(32, n_cells=1)
    df = df.assign(partial=True)                                  # nenhum mes valido: pool vazio
    fixed, loo = hp.reference_fixed(df), hp.reference_loo(df)
    assert fixed["n_ref_years"].eq(0).all() and fixed["ref_mean"].isna().all() and len(fixed) == 12 * df[["series"]].drop_duplicates().shape[0]
    assert loo["n_ref_years"].eq(0).all() and loo["n_below"].isna().all() and len(loo) == len(df)
    _same(fixed, _slow_reference_fixed(df))
    _same(loo, _slow_reference_loo(df))
