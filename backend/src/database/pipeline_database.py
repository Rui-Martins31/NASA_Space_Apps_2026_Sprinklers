"""The pipeline's database. Not connected yet: its schema is still being decided.

When it is, implement the methods described in database/__init__.py
here. Each is one range query on lat and lon (plus month or date_time), for
example in MongoDB:

    {"lat": {"$gte": box["lat_min"], "$lte": box["lat_max"]},
     "lon": {"$gte": box["lon_min"], "$lte": box["lon_max"]}}

with an "$or" on lon when box["lon_min"] > box["lon_max"]. Connection
settings go in config.py.
"""


class PipelineDatabase:
    def __init__(self):
        raise NotImplementedError(
            "the pipeline's database is not connected yet; run with --data mock")
