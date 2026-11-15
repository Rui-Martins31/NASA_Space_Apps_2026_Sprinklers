"""Read the pipeline's per-chunk data: from the real database, or from mock CSV files.

    mock_database.py      CSV files in test/mock_data/ standing in for the database
    pipeline_database.py  the pipeline's database (not connected yet)

Both answer the same questions, about a lat/lon box
(see circle_geometry.bounding_box; lon_min > lon_max means the box wraps around 180°):

    chunk_counts(box, first_month, last_month)
        rows {"lat", "lon", "year", "month", "count"}; count = cell-days
        (days with at least one eligible detection); lat/lon = chunk centre,
        months are (year, month) tuples, inclusive. A chunk with no activity
        in a month may have no row (count 0).
    chunk_means(box)
        rows {"lat", "lon", "month", "mean"}: the chunk's mean monthly count
        for that calendar month over the pipeline's reference years.
    hotspots(box, date_time_from, date_time_to)
        rows {"lat", "lon", "date_time" (datetime, UTC), "confidence_class"}.
    chunk_metrics(metric, box, date_time_from, date_time_to)
        rows {"metric", "lat", "lon", "year", "month", "date", "key", "value", "low", "high"}:
        the pipeline's value of one metric (e.g. "his-05") for one chunk. Fields
        that do not apply are None:
          - lat/lon None = a global value (not tied to a place), always returned;
          - the time fields say what the value covers: a day ("date", plus its
            year and month), a month (year + month), a calendar month of the
            reference years (month only), or the whole record (none). A row is
            returned when that day / month falls in the period; month-only and
            whole-record rows always are;
          - "key" splits a metric into categories (e.g. "VIIRS · high");
          - "low"/"high" are the bounds of a range (e.g. p10-p90).
    data_range()
        (first, last) datetime of the data the pipeline has loaded.

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
