"""ADD-05 (Lote 5): sensibilidade das celulas-dia ao filtro de `type`.

Funcao pura: DataFrame no esquema de processed/ -> tabela "tidy" ordenada pelas chaves.
A confianca e sempre `n`/`h` (NA e `l` ficam fora em todas as variantes); o que varia e o
filtro de `type`. A chave e a celula (`cell`, de `cell_key`; `country` ja nao e chave) e a tabela
inclui linhas globais `cell == GLOBAL_CELL` que somam as celulas. Convencoes em
spec/metodologia_metricas.md (7F, linha ADD-05).
"""
from __future__ import annotations

import pandas as pd

from .common import (ELIGIBLE_CONFIDENCE, GLOBAL_CELL, GRID_DEG, cell_key, parse_dates,
                     require_columns, valid_coords)

KEY = ["cell", "year", "instrument"]
OUT_COLUMNS = KEY + ["variant", "n_eligible", "n_cell_days", "delta_cell_days_pct"]
REQUIRED = ["instrument", "latitude", "longitude", "acq_date", "type", "confidence_class"]

DEFAULT_VARIANTS = {
    "default": {"types": (0,), "include_na_type": False},
    "no_type_filter": {"types": None, "include_na_type": True},
    "type0_or_unknown": {"types": (0,), "include_na_type": True},
}


def _empty() -> pd.DataFrame:
    out = pd.DataFrame({
        "cell": pd.Series([], dtype="int64"),
        "year": pd.Series([], dtype="int64"),
        "instrument": pd.Series([], dtype="string"),
        "variant": pd.Series([], dtype="string"),
        "n_eligible": pd.Series([], dtype="int64"),
        "n_cell_days": pd.Series([], dtype="int64"),
        "delta_cell_days_pct": pd.Series([], dtype="float64"),
    })
    return out[OUT_COLUMNS]


def _variant_mask(work: pd.DataFrame, spec: dict) -> pd.Series:
    """Linhas que passam uma variante: confianca n/h E (type permitido, ou type NA e
    include_na_type)."""
    type_na = work["type"].isna().to_numpy()
    if spec["types"] is None:
        type_ok = ~type_na
    else:
        type_ok = work["type"].isin(list(spec["types"])).fillna(False).to_numpy(dtype=bool)
    ok = type_ok | (type_na & bool(spec["include_na_type"]))
    return pd.Series(work["conf_ok"].to_numpy() & ok, index=work.index)


def add05_type_sensitivity(df: pd.DataFrame, variants: dict | None = None,
                           grid_deg: float = GRID_DEG) -> pd.DataFrame:
    """ADD-05: por (celula, ano, instrumento) e variante do filtro de `type`, linhas que a
    passam (`n_eligible`), pares distintos (celula, dia) (`n_cell_days`; por celula e o nº de dias
    distintos dessa celula) e a variacao percentual de celulas-dia face a `default` (NA se o
    default tiver 0).

    Colunas: cell, year, instrument, variant, n_eligible, n_cell_days, delta_cell_days_pct.
    Para alem das linhas por celula (esparsas: so celulas com pelo menos uma linha em alguma
    variante; as variantes sem linhas tem contagens 0) ha, por (ano, instrumento, variante), uma
    linha global `cell == GLOBAL_CELL` com as contagens somadas sobre as celulas e o delta
    recalculado a partir dessas somas (os deltas das celulas nao se somam). Ordenada por
    (cell, year, instrument, variant), logo as linhas globais vem primeiro.

    Linhas com data invalida ou coordenadas invalidas ficam fora. `variants` tem de conter a
    chave `default`. A variante de grelha nao existe aqui (e do L7).
    """
    variants = DEFAULT_VARIANTS if variants is None else variants
    if "default" not in variants:
        raise ValueError("variants tem de conter a chave 'default'")
    require_columns(df, REQUIRED)

    date = parse_dates(df["acq_date"]).reset_index(drop=True)
    keep = date.notna().to_numpy() & valid_coords(df["latitude"], df["longitude"])
    work = pd.DataFrame({
        "instrument": df["instrument"].astype("string").fillna("unknown").to_numpy(),
        "latitude": df["latitude"].to_numpy(dtype="float64"),
        "longitude": df["longitude"].to_numpy(dtype="float64"),
        "type": df["type"].reset_index(drop=True),
        "date": date,
        "conf_ok": df["confidence_class"].isin(list(ELIGIBLE_CONFIDENCE))
                     .fillna(False).to_numpy(dtype=bool),
    })
    work = work[keep].reset_index(drop=True)
    if work.empty:
        return _empty()
    work["year"] = work["date"].dt.year.astype("int64")
    work["cell"] = cell_key(work["latitude"], work["longitude"], grid_deg).astype("int64")

    parts = []
    for name in sorted(variants):
        sub = work[_variant_mask(work, variants[name]).to_numpy()]
        if sub.empty:
            continue
        n_rows = sub.groupby(KEY, sort=True, observed=True).size().rename("n_eligible")
        n_days = (sub.drop_duplicates(KEY + ["date"])
                  .groupby(KEY, sort=True, observed=True).size().rename("n_cell_days"))
        part = pd.concat([n_rows, n_days], axis=1).reset_index()
        part["variant"] = name
        parts.append(part)
    if not parts:
        return _empty()
    counts = pd.concat(parts, ignore_index=True)

    groups = counts[KEY].drop_duplicates()
    grid = groups.merge(pd.DataFrame({"variant": sorted(variants)}), how="cross")
    per_cell = grid.merge(counts, on=KEY + ["variant"], how="left")
    for c in ("n_eligible", "n_cell_days"):
        per_cell[c] = per_cell[c].fillna(0).astype("int64")

    # linhas globais: so as contagens somam (celulas distintas => pares (celula, dia) distintos)
    total = (per_cell.groupby(["year", "instrument", "variant"], sort=True, observed=True)
             [["n_eligible", "n_cell_days"]].sum().reset_index())
    total["cell"] = GLOBAL_CELL
    out = pd.concat([total[per_cell.columns], per_cell], ignore_index=True)

    base = (out[out["variant"] == "default"][KEY + ["n_cell_days"]]
            .rename(columns={"n_cell_days": "n_default"}))
    out = out.merge(base, on=KEY, how="left")
    out["delta_cell_days_pct"] = (100.0 * (out["n_cell_days"] - out["n_default"])
                                  / out["n_default"].where(out["n_default"] != 0)).astype("float64")
    out["cell"] = out["cell"].astype("int64")
    out["year"] = out["year"].astype("int64")
    out = out[OUT_COLUMNS].sort_values(KEY + ["variant"]).reset_index(drop=True)
    return out
