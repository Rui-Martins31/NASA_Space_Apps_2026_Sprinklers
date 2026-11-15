"""Escrita e leitura das tabelas de metricas, uma tabela (pasta Parquet) por metrica.

Substitui os `atomic_write(tabela, METRICS/<nome>.parquet)` dos notebooks. Cada tabela por
celula leva as colunas `ilat, ilon, lat, lon, lat_band` (derivadas de `cell`), e fica ordenada por
(ilat, ilon) e particionada por `series` e `lat_band`, para o backend (DuckDB) ler so as faixas
que um circulo (lat, lon, raio) toca. As linhas globais usam `cell == GLOBAL_CELL` (-1).

Destinos (`Sink`): `ParquetSink` (pastas Parquet; Drive ou disco do backend) e `MemorySink` (testes).
Sem acesso a rede nem a Drive: o notebook escolhe o `root` do `ParquetSink`.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .common import GLOBAL_CELL, GRID_DEG, cell_center, cell_to_ids, lat_band

CELL_COLUMNS = ["ilat", "ilon", "lat", "lon", "lat_band"]
RUNS_NAME = "_runs"
RUNS_COLUMNS = ["lote", "run_utc", "grid_deg", "commit", "params", "tables"]


# ------------------------------------------------------------------ colunas de celula
def add_cell_columns(df: pd.DataFrame, grid_deg: float = GRID_DEG, cell_col: str = "cell") -> pd.DataFrame:
    """Devolve uma copia de `df` com `ilat, ilon, lat, lon, lat_band` calculadas a partir de `cell`.
    Linhas com `cell == GLOBAL_CELL` ficam com NA nestas colunas (e o dtype passa a anulavel).
    Levanta ValueError se `cell` nao existir ou tiver valores fora da grelha (alem de -1)."""
    if cell_col not in df.columns:
        raise ValueError(f"coluna '{cell_col}' em falta no DataFrame")
    out = df.copy()
    cell = out[cell_col].to_numpy(dtype="int64")
    is_global = cell == GLOBAL_CELL
    real = cell[~is_global]
    ilat_r, ilon_r = cell_to_ids(real, grid_deg)
    lat_r, lon_r = cell_center(real, grid_deg)
    band_r = lat_band(ilat_r, grid_deg)
    if is_global.any():
        def _fill(values, dtype):
            col = pd.array([pd.NA] * len(out), dtype=dtype)
            col[~is_global] = values
            return col
        out["ilat"] = _fill(ilat_r, "Int32")
        out["ilon"] = _fill(ilon_r, "Int32")
        out["lat"] = _fill(lat_r, "Float64")
        out["lon"] = _fill(lon_r, "Float64")
        out["lat_band"] = _fill(band_r, "Int8")
    else:
        out["ilat"] = ilat_r.astype("int32")
        out["ilon"] = ilon_r.astype("int32")
        out["lat"] = lat_r
        out["lon"] = lon_r
        out["lat_band"] = band_r.astype("int8")
    cols = [cell_col] + CELL_COLUMNS
    return out[cols + [c for c in out.columns if c not in cols]]


def prepare_table(df: pd.DataFrame, grid_deg: float = GRID_DEG, sort_by=None) -> pd.DataFrame:
    """Tabela pronta a gravar: colunas de celula (se houver `cell`) e ordenada por (ilat, ilon)
    seguida de `sort_by` (as restantes colunas-chave). Sem `cell` so ordena por `sort_by`."""
    out = add_cell_columns(df, grid_deg) if "cell" in df.columns else df.copy()
    keys = (["ilat", "ilon"] if "cell" in out.columns else []) + [c for c in (sort_by or []) if c in out.columns]
    if keys:
        out = out.sort_values(keys, kind="mergesort", na_position="first")
    return out.reset_index(drop=True)


def default_partitions(df: pd.DataFrame) -> list[str]:
    """`series` e `lat_band` quando existem. `lat_band` sai se houver linhas globais (NA)."""
    cols = []
    if "series" in df.columns:
        cols.append("series")
    if "lat_band" in df.columns and not df["lat_band"].isna().any():
        cols.append("lat_band")
    return cols


# ------------------------------------------------------------------ destinos
class Sink:
    """Interface minima: gravar uma tabela inteira, le-la, e saber se existe."""

    def write(self, name: str, df: pd.DataFrame, partition_cols=()) -> None:
        raise NotImplementedError

    def read(self, name: str, columns=None, filters=None) -> pd.DataFrame:
        raise NotImplementedError

    def exists(self, name: str) -> bool:
        raise NotImplementedError

    def names(self) -> list[str]:
        raise NotImplementedError


def _apply_filters(df: pd.DataFrame, filters) -> pd.DataFrame:
    """filters = [(coluna, op, valor), ...] em AND; ops: ==, !=, <, <=, >, >=, in."""
    ops = {"==": lambda s, v: s == v, "!=": lambda s, v: s != v, "<": lambda s, v: s < v,
           "<=": lambda s, v: s <= v, ">": lambda s, v: s > v, ">=": lambda s, v: s >= v,
           "in": lambda s, v: s.isin([v] if isinstance(v, str) else list(v))}
    for col, op, value in filters or []:
        if op not in ops:
            raise ValueError(f"operador de filtro desconhecido: {op}")
        df = df[ops[op](df[col], value).to_numpy(dtype=bool, na_value=False)]
    return df


class MemorySink(Sink):
    """Guarda as tabelas em memoria (testes). `partitions[name]` regista as colunas de particao."""

    def __init__(self):
        self.tables: dict[str, pd.DataFrame] = {}
        self.partitions: dict[str, tuple] = {}

    def write(self, name, df, partition_cols=()):
        self.tables[name] = df.copy().reset_index(drop=True)
        self.partitions[name] = tuple(partition_cols)

    def read(self, name, columns=None, filters=None):
        if name not in self.tables:
            raise FileNotFoundError(f"tabela '{name}' nao existe")
        df = _apply_filters(self.tables[name], filters)
        return (df[list(columns)] if columns else df).copy().reset_index(drop=True)

    def exists(self, name):
        return name in self.tables

    def names(self):
        return sorted(self.tables)


class ParquetSink(Sink):
    """Uma pasta Parquet por tabela em `root/<nome>/`. A publicacao escreve em `<nome>.tmp/` e
    troca de pasta no fim (como o antigo `atomic_write`): nunca fica uma tabela a meio."""

    def __init__(self, root):
        self.root = Path(root)

    def path(self, name: str) -> Path:
        return self.root / name

    def _publish(self, tmp: Path, name: str) -> None:
        final, old = self.path(name), self.root / f"{name}.old"
        if old.exists():
            shutil.rmtree(old)
        if final.exists():
            final.replace(old)
        tmp.replace(final)
        if old.exists():
            shutil.rmtree(old)

    def write(self, name, df, partition_cols=()):
        import pyarrow as pa
        import pyarrow.parquet as pq
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.root / f"{name}.tmp"
        if tmp.exists():
            shutil.rmtree(tmp)
        table = pa.Table.from_pandas(df.reset_index(drop=True), preserve_index=False)
        if partition_cols and len(df):
            pq.write_to_dataset(table, tmp, partition_cols=list(partition_cols), compression="zstd")
        else:
            tmp.mkdir(parents=True)
            pq.write_table(table, tmp / "part-0.parquet", compression="zstd")
        self._publish(tmp, name)

    def write_from_parquet(self, name, source, order_by=("ilat", "ilon"), partition_cols=(),
                           temp_directory=None, memory_limit=None):
        """Consolida muitos Parquet pequenos (p. ex. caches por ano) numa tabela ordenada e
        particionada, com DuckDB, que ordena e escreve fora da memoria (Colab gratuito).
        `source` e um padrao de ficheiros (ex.: '/content/.../_partial/*.parquet') ou uma
        lista explicita de ficheiros. Sem `partition_cols` a tabela e um unico ficheiro
        `part-0.parquet` dentro da pasta, como em `write`. `temp_directory` (pasta local rapida,
        p. ex. `/content/duckdb_tmp` no Colab) e `memory_limit` (p. ex. '8GB') controlam onde e
        quando o DuckDB despeja para disco ao ordenar tabelas maiores que a memoria."""
        import duckdb
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.root / f"{name}.tmp"
        if tmp.exists():
            shutil.rmtree(tmp)

        def q(path) -> str:
            return str(path).replace("\\", "/").replace("'", "''")

        if isinstance(source, (list, tuple)):
            if not source:
                raise ValueError("lista de ficheiros vazia")
            src = "[" + ", ".join(f"'{q(p)}'" for p in source) + "]"
        else:
            src = f"'{q(source)}'"
        order = f" ORDER BY {', '.join(order_by)}" if order_by else ""
        con = duckdb.connect()
        try:
            if temp_directory:
                Path(temp_directory).mkdir(parents=True, exist_ok=True)
                con.execute(f"SET temp_directory = '{q(Path(temp_directory).as_posix())}'")
            if memory_limit:
                con.execute(f"SET memory_limit = '{str(memory_limit).replace(chr(39), '')}'")
            if partition_cols:
                target, opts = tmp, f", PARTITION_BY ({', '.join(partition_cols)}), OVERWRITE_OR_IGNORE"
            else:
                tmp.mkdir(parents=True)
                target, opts = tmp / "part-0.parquet", ""
            try:
                con.execute(f"COPY (SELECT * FROM read_parquet({src}, union_by_name=true){order}) "
                            f"TO '{q(target.as_posix())}' (FORMAT PARQUET, COMPRESSION zstd{opts})")
            except Exception:
                if tmp.exists():
                    shutil.rmtree(tmp)
                raise
        finally:
            con.close()
        if not tmp.exists():
            raise ValueError(f"nenhum ficheiro encontrado para '{source}'")
        self._publish(tmp, name)

    def read(self, name, columns=None, filters=None):
        p = self.path(name)
        if not p.exists():
            raise FileNotFoundError(f"tabela '{name}' nao existe em {self.root}")
        df = pd.read_parquet(p, columns=list(columns) if columns else None)
        for c in df.columns:  # colunas de particao voltam como categoricas
            if isinstance(df[c].dtype, pd.CategoricalDtype):
                df[c] = df[c].astype(df[c].cat.categories.dtype)
        return _apply_filters(df, filters).reset_index(drop=True)

    def exists(self, name):
        return self.path(name).is_dir() and not name.endswith((".tmp", ".old"))

    def names(self):
        if not self.root.exists():
            return []
        return sorted(p.name for p in self.root.iterdir()
                      if p.is_dir() and not p.name.endswith((".tmp", ".old")) and not p.name.startswith("_partial"))


# ------------------------------------------------------------------ API para os notebooks
def stats_source(name: str, grid_deg: float, stats_grid_deg: float) -> str:
    """Nome da tabela L1 de onde as estatisticas leem. Com `stats_grid_deg == grid_deg` e a propria
    tabela (`l1_cal_monthly`); com uma grelha mais grossa e `l1_stats_cal_monthly`."""
    if stats_grid_deg == grid_deg:
        return name
    if not name.startswith("l1_"):
        raise ValueError(f"so tabelas l1_* tem versao por grelha de estatisticas: {name}")
    return "l1_stats_" + name[len("l1_"):]



def write_table(sink: Sink, name: str, df: pd.DataFrame, *, grid_deg: float = GRID_DEG,
                sort_by=None, partition_by=None) -> pd.DataFrame:
    """Prepara (colunas de celula, ordenacao) e grava a tabela `name`. Devolve a tabela gravada.
    `partition_by=None` usa `series` e `lat_band` quando existem."""
    out = prepare_table(df, grid_deg, sort_by)
    sink.write(name, out, default_partitions(out) if partition_by is None else list(partition_by))
    return out


def read_table(sink: Sink, name: str, columns=None, filters=None) -> pd.DataFrame:
    """Le uma tabela gravada por `write_table` (as colunas de particao voltam como colunas normais)."""
    return sink.read(name, columns=columns, filters=filters)


def write_run(sink: Sink, lote: str, *, params: dict, tables: dict, commit: str = "unknown",
              grid_deg: float = GRID_DEG, run_utc: str | None = None) -> pd.DataFrame:
    """Regista a execucao em `_runs` (substitui `_log_loteN.csv` e `_params_loteN.json`).
    Escreve-se DEPOIS de todas as tabelas: uma execucao a meio nao fica registada.
    `tables` = {nome: n_linhas}. Substitui a linha anterior do mesmo `lote`."""
    row = pd.DataFrame([{
        "lote": lote,
        "run_utc": run_utc or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "grid_deg": float(grid_deg),
        "commit": commit,
        "params": json.dumps(params, sort_keys=True, default=str),
        "tables": json.dumps({k: int(v) for k, v in sorted(tables.items())}),
    }], columns=RUNS_COLUMNS)
    if sink.exists(RUNS_NAME):
        prev = sink.read(RUNS_NAME)
        row = pd.concat([prev[prev["lote"] != lote], row], ignore_index=True)
    row = row.sort_values("lote").reset_index(drop=True)
    sink.write(RUNS_NAME, row, ())
    return row
