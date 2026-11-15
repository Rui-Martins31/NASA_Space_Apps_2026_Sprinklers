"""Exemplo de consulta por area (lat, lon, raio) as tabelas por celula, com DuckDB.

Mostra, e os testes verificam, que o esquema gravado pelo pipeline (colunas `ilat, ilon, lat, lon,
lat_band` e pastas particionadas por `series`/`lat_band`) basta para o backend ir buscar uma area.
Nao e o backend: so a consulta de referencia.

    python data/pipeline/scripts/query_area.py data/metrics l1_cal_monthly 38.72 -9.14 20 combined
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

EARTH_RADIUS_KM = 6371.0088
KM_PER_DEG_LAT = 111.195


def bounding_box(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    """(lat_min, lat_max, lon_min, lon_max) do retangulo que contem o circulo. Nao trata o
    antimeridiano (±180) nem os polos: nestes casos devolve o mundo todo em longitude."""
    dlat = radius_km / KM_PER_DEG_LAT
    lat_min, lat_max = max(-90.0, lat - dlat), min(90.0, lat + dlat)
    cos_lat = math.cos(math.radians(max(abs(lat_min), abs(lat_max))))
    if cos_lat < 1e-6:
        return lat_min, lat_max, -180.0, 180.0
    dlon = radius_km / (KM_PER_DEG_LAT * cos_lat)
    if dlon >= 180 or lon - dlon < -180 or lon + dlon > 180:
        return lat_min, lat_max, -180.0, 180.0
    return lat_min, lat_max, lon - dlon, lon + dlon


def area_monthly_series(root, table: str, lat: float, lon: float, radius_km: float, series: str,
                        value: str = "cell_days"):
    """Soma de `value` por (year, month) nas celulas cujo CENTRO esta a `radius_km` de (lat, lon).
    Devolve um DataFrame [year, month, value, n_cells]. Usa a poda por `lat_band` e por
    `lat`/`lon` antes da distancia (haversine)."""
    import duckdb
    lat_min, lat_max, lon_min, lon_max = bounding_box(lat, lon, radius_km)
    path = (Path(root) / table).as_posix().replace("'", "''")
    con = duckdb.connect()
    try:
        return con.execute(f"""
            SELECT year, month, SUM({value})::BIGINT AS {value}, COUNT(DISTINCT cell)::BIGINT AS n_cells
            FROM read_parquet('{path}/**/*.parquet', hive_partitioning=true)
            WHERE series = ?
              AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?
              AND 2 * {EARTH_RADIUS_KM} * asin(sqrt(
                    pow(sin(radians(lat - ?) / 2), 2)
                    + cos(radians(?)) * cos(radians(lat)) * pow(sin(radians(lon - ?) / 2), 2))) <= ?
            GROUP BY year, month ORDER BY year, month
        """, [series, lat_min, lat_max, lon_min, lon_max, lat, lat, lon, radius_km]).df()
    finally:
        con.close()


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 6:
        print(__doc__)
        return 2
    root, table, lat, lon, radius, series = args
    print(area_monthly_series(root, table, float(lat), float(lon), float(radius), series).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
