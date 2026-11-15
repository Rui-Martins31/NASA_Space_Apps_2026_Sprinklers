"""Read the pipeline's per-chunk data: from the real database, or from mock CSV files.

    mock_database.py      CSV files in test/mock_data/ standing in for the database
    pipeline_database.py  the pipeline's database (not connected yet)

Both answer the same three questions, always about a lat/lon box
(see circle_geometry.bounding_box; lon_min > lon_max means the box wraps around 180°):

    chunk_counts(box, first_month, last_month)
        rows {"lat", "lon", "year", "month", "count"}; lat/lon = chunk centre,
        months are (year, month) tuples, inclusive. A chunk with no activity
        in a month may have no row (count 0).
    chunk_means(box)
        rows {"lat", "lon", "month", "mean"}: the chunk's mean monthly count
        for that calendar month over the pipeline's reference years.
    hotspots(box, date_time_from, date_time_to)
        rows {"lat", "lon", "date_time" (datetime, UTC), "confidence_class"}.

Trimming the box to the circle is done afterwards, in features.py, so the
database only ever needs range queries on lat and lon.
"""

from .. import config


def open_database(kind, mock_dir=config.MOCK_DATA_DIR):
    """kind is "mock" (CSV files in mock_dir) or "database" (the pipeline's database)."""
    if kind == "mock":
        from .mock_database import MockDatabase
        return MockDatabase.from_dir(mock_dir)

    if kind == "database":
        from .pipeline_database import PipelineDatabase
        return PipelineDatabase()

    raise ValueError(f"unknown data option {kind!r}; choose one of: {', '.join(config.DATA_OPTIONS)}")
