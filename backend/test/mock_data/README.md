# Mock data

CSV files that stand in for the pipeline's database while it is being built.
Each file plays one collection/table. `python main.py` (or `--data mock`)
serves these; the backend asks for a lat/lon box and trims it to the circle
itself, so the real database only needs range queries on `lat` and `lon`.

| File | One row per | Columns |
|---|---|---|
| `hotspots.csv` | detection | `lat`, `lon`, `date_time` (ISO-8601, UTC), `confidence_class` (`low`/`nominal`/`high`) |
| `chunk_counts.csv` | chunk × month with activity | `lat`, `lon` (chunk centre), `year`, `month`, `count` |
| `chunk_means.csv` | chunk × calendar month | `lat`, `lon` (chunk centre), `month`, `mean` (mean monthly `count` over the reference years) |

- Chunks are 0.1° cells; a chunk belongs to a circle when its centre is inside it.
- Missing rows mean zero: a chunk with no activity in a month has no `chunk_counts` row.
- `count` and `mean` must be **additive** over chunks: the backend adds them up for the circle. A median or a percentile cannot be stored this way.

The data is invented (mainland Portugal, 2000-11 to 2026-11). To regenerate:

```bash
python test/generate_mock_data.py   # hotspots.csv (fixed seed)
python test/build_mock_chunks.py    # chunk_counts.csv, chunk_means.csv from hotspots.csv
```

`build_mock_chunks.py` is only a stand-in for the pipeline: the real unit and
reference period are the pipeline's to decide.
