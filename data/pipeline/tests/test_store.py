"""store.py: colunas de celula, ordenacao, particoes, destinos Memory/Parquet, publicacao, _runs."""
import json

import numpy as np
import pandas as pd
import pytest

from metrics.common import GLOBAL_CELL, cell_key
from metrics.store import (MemorySink, ParquetSink, add_cell_columns, default_partitions,
                           prepare_table, read_table, write_run, write_table)

LAT = [38.7223, -33.3333, 38.7201]
LON = [-9.1393, 151.2, -9.1301]


def monthly(grid=0.01):
    cell = cell_key(LAT, LON, grid)
    return pd.DataFrame({"cell": cell, "series": ["combined", "modis", "combined"],
                         "year": [2020, 2020, 2019], "month": [8, 8, 7], "cell_days": [5, 2, 1]})


def test_add_cell_columns_values_and_dtypes():
    out = add_cell_columns(monthly(), 0.01)
    assert list(out.columns[:6]) == ["cell", "ilat", "ilon", "lat", "lon", "lat_band"]
    assert out["ilat"].dtype == np.int32 and out["lat_band"].dtype == np.int8
    # centro = celula de 0.01 que contem o ponto
    assert out.loc[0, "lat"] == pytest.approx(38.725) and out.loc[0, "lon"] == pytest.approx(-9.135)
    assert out.loc[0, "ilat"] == int((38.7223 + 90) / 0.01) and out.loc[0, "lat_band"] == 12


def test_add_cell_columns_global_rows_get_na():
    df = pd.DataFrame({"cell": [GLOBAL_CELL, int(cell_key([38.7], [-9.1], 0.1)[0])], "v": [1, 2]})
    out = add_cell_columns(df, 0.1)
    assert out["ilat"].isna().tolist() == [True, False]
    assert str(out["ilat"].dtype) == "Int32" and str(out["lat_band"].dtype) == "Int8"
    assert default_partitions(out.assign(series="x")) == ["series"]  # lat_band sai com linhas globais


def test_add_cell_columns_requires_cell_and_rejects_bad_cell():
    with pytest.raises(ValueError, match="'cell'"):
        add_cell_columns(pd.DataFrame({"x": [1]}))
    with pytest.raises(ValueError, match="fora da grelha"):
        add_cell_columns(pd.DataFrame({"cell": [-5]}))


def test_prepare_table_sorts_by_ilat_ilon_then_keys_and_does_not_mutate():
    df = monthly()
    before = df.copy()
    out = prepare_table(df, 0.01, sort_by=["series", "year", "month"])
    assert out["ilat"].is_monotonic_increasing
    assert out["ilat"].tolist() == sorted(out["ilat"].tolist())
    same_cell = out[out["ilat"] == out["ilat"].iloc[1]]
    assert same_cell["ilon"].is_monotonic_increasing
    pd.testing.assert_frame_equal(df, before)


def test_write_table_memory_sink_roundtrip_and_partitions():
    sink = MemorySink()
    out = write_table(sink, "l1_cal_monthly", monthly(), grid_deg=0.01, sort_by=["series", "year", "month"])
    assert sink.partitions["l1_cal_monthly"] == ("series", "lat_band")
    back = read_table(sink, "l1_cal_monthly")
    pd.testing.assert_frame_equal(back, out)
    only = read_table(sink, "l1_cal_monthly", columns=["cell", "cell_days"],
                      filters=[("series", "==", "modis")])
    assert only["cell_days"].tolist() == [2]


def test_table_without_cell_is_not_given_cell_columns():
    sink = MemorySink()
    glob = pd.DataFrame({"series": ["modis"], "year": [2020], "month": [1], "partial": [False]})
    write_table(sink, "l1_meta_month_validity", glob)
    assert "ilat" not in read_table(sink, "l1_meta_month_validity").columns


def test_parquet_sink_roundtrip_partitioned_preserves_values_and_dtypes(tmp_path):
    sink = ParquetSink(tmp_path)
    out = write_table(sink, "l1_cal_monthly", monthly(), grid_deg=0.01, sort_by=["series", "year", "month"])
    assert sink.exists("l1_cal_monthly") and sink.names() == ["l1_cal_monthly"]
    assert (tmp_path / "l1_cal_monthly" / "series=combined").is_dir()
    back = read_table(sink, "l1_cal_monthly")
    assert sorted(back.columns) == sorted(out.columns)
    key = ["cell", "series", "year", "month"]
    a = back.sort_values(key).reset_index(drop=True)
    b = out.sort_values(key).reset_index(drop=True)
    pd.testing.assert_frame_equal(a[b.columns], b, check_dtype=False)
    assert back["series"].dtype == object or str(back["series"].dtype).startswith("str")
    assert sorted(read_table(sink, "l1_cal_monthly", filters=[("lat_band", "==", 12)])["cell"]) == sorted(
        out.loc[out["lat_band"] == 12, "cell"])


def test_parquet_sink_replaces_table_atomically_and_leaves_no_tmp(tmp_path):
    sink = ParquetSink(tmp_path)
    write_table(sink, "t", monthly(), grid_deg=0.01)
    write_table(sink, "t", monthly().iloc[:1], grid_deg=0.01)
    assert len(read_table(sink, "t")) == 1
    assert [p.name for p in tmp_path.iterdir()] == ["t"]


def test_parquet_sink_failed_write_keeps_previous_table(tmp_path):
    sink = ParquetSink(tmp_path)
    write_table(sink, "t", monthly(), grid_deg=0.01)
    bad = monthly().assign(cell_days=[object(), object(), object()])
    with pytest.raises(Exception):
        write_table(sink, "t", bad, grid_deg=0.01)
    assert len(read_table(sink, "t")) == 3
    assert sink.names() == ["t"]


def test_parquet_sink_read_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="nao existe"):
        ParquetSink(tmp_path).read("nada")


def test_write_from_parquet_consolidates_sorts_and_partitions(tmp_path):
    parts = tmp_path / "partial"
    parts.mkdir()
    full = prepare_table(monthly(), 0.01)
    full.iloc[:2].to_parquet(parts / "a.parquet")
    full.iloc[2:].to_parquet(parts / "b.parquet")
    sink = ParquetSink(tmp_path / "out")
    sink.write_from_parquet("l1_cal_monthly", str(parts / "*.parquet"), partition_cols=("series", "lat_band"))
    back = sink.read("l1_cal_monthly")
    assert len(back) == 3 and back["cell_days"].sum() == 8
    assert (tmp_path / "out" / "l1_cal_monthly" / "series=combined").is_dir()
    with pytest.raises(Exception):
        sink.write_from_parquet("x", str(parts / "nada*.parquet"))
    assert not (tmp_path / "out" / "x").exists()


def test_write_from_parquet_without_partitions_makes_a_folder_and_accepts_a_file_list(tmp_path):
    parts = tmp_path / "partial"
    parts.mkdir()
    full = prepare_table(monthly(), 0.01)
    full.iloc[:2].to_parquet(parts / "a.parquet")
    full.iloc[2:].to_parquet(parts / "b.parquet")
    (parts / "old.parquet").write_bytes(b"not used, not in the list")
    sink = ParquetSink(tmp_path / "out")
    sink.write_from_parquet("t", [parts / "a.parquet", parts / "b.parquet"])
    assert (tmp_path / "out" / "t").is_dir() and sink.exists("t")
    back = sink.read("t")
    assert len(back) == 3 and back["ilat"].is_monotonic_increasing
    with pytest.raises(ValueError, match="vazia"):
        sink.write_from_parquet("u", [])


def test_write_from_parquet_accepts_temp_directory_and_memory_limit(tmp_path):
    parts = tmp_path / "partial"
    parts.mkdir()
    prepare_table(monthly(), 0.01).to_parquet(parts / "a.parquet")
    sink = ParquetSink(tmp_path / "out")
    sink.write_from_parquet("t", str(parts / "*.parquet"), temp_directory=tmp_path / "spill", memory_limit="1GB")
    assert (tmp_path / "spill").is_dir() and len(sink.read("t")) == 3


def test_write_run_registers_and_replaces_same_lote(tmp_path):
    sink = ParquetSink(tmp_path)
    write_run(sink, "lote1", params={"grid_deg": 0.01}, tables={"a": 3}, commit="abc", grid_deg=0.01,
              run_utc="2026-01-01T00:00:00+00:00")
    runs = write_run(sink, "lote2", params={"x": 1}, tables={"b": 1}, commit="abc", grid_deg=0.01)
    runs = write_run(sink, "lote1", params={"grid_deg": 0.1}, tables={"a": 9}, commit="def", grid_deg=0.1)
    assert runs["lote"].tolist() == ["lote1", "lote2"]
    row = runs[runs["lote"] == "lote1"].iloc[0]
    assert row["commit"] == "def" and row["grid_deg"] == 0.1
    assert json.loads(row["tables"]) == {"a": 9} and json.loads(row["params"]) == {"grid_deg": 0.1}
    assert sink.names() == ["_runs"]
