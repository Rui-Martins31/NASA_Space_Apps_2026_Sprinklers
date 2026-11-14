"""Auxiliares de teste do Lote 1 (sem conftest.py, para nao colidir com o Lote 2)."""
import pandas as pd

DEFAULTS = {
    "country": "Testland",
    "source_file": "modis_2020_Testland.csv",
    "instrument": "MODIS",
    "satellite": "Terra",
    "version": "6.03",
    "latitude": 10.05,
    "longitude": 20.05,
    "acq_date": "2020-01-01",
    "acq_time": "1200",
    "daynight": "D",
    "type": 0,
    "confidence_raw": "80",
    "confidence_class": "h",
    "brightness_primary": 320.0,
    "brightness_primary_band": "brightness",
    "brightness_aux": 295.0,
    "brightness_aux_band": "bright_t31",
    "scan": 1.0,
    "track": 1.0,
    "pixel_area_km2": 1.0,
    "frp": 10.0,
}

ORDERED = ["country", "source_file", "instrument", "satellite", "version",
           "latitude", "longitude", "acq_date", "acq_time", "acq_datetime_utc",
           "daynight", "type", "confidence_raw", "confidence_class",
           "brightness_primary", "brightness_primary_band",
           "brightness_aux", "brightness_aux_band",
           "scan", "track", "pixel_area_km2", "frp"]


def build_processed(rows):
    """DataFrame com o esquema de processed/ a partir de uma lista de dicts
    (so e preciso indicar o que difere de DEFAULTS). Dtypes como no notebook 01:
    type=Int8; version/acq_time/confidence_* = string; acq_datetime_utc derivado
    de acq_date + acq_time (hora invalida => NaT)."""
    recs = [{**DEFAULTS, **r} for r in rows]
    df = pd.DataFrame.from_records(recs, columns=list(DEFAULTS))
    t = df["acq_time"].astype("string")
    df["acq_datetime_utc"] = pd.to_datetime(
        df["acq_date"].astype("string") + " " + t.str[:2] + ":" + t.str[2:],
        format="%Y-%m-%d %H:%M", errors="coerce", utc=True)
    df["type"] = pd.array(df["type"], dtype="Int8")
    for c in ("version", "acq_time", "confidence_raw", "confidence_class"):
        df[c] = df[c].astype("string")
    return df[ORDERED]
