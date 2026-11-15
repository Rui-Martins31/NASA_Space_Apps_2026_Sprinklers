# Team synchronization and source-isolation validation

## Scope

On 15 November 2026, `origin/main` was merged into `metricas-pipeline` without
conflicts. This brings the current frontend integration changes together with
the two newer L7/S-NPP commits while preserving the published commit history.

The core reference remains MODIS plus NOAA-20 (`viirs-jpss1`). S-NPP
(`viirs-snpp`) has its independent HAR-12 processing in notebook 09. Notebook
01 can ingest all source types, but their downstream selections must remain
explicit.

## Source selection

Notebook 02 now defaults to the two core source names. Its source selection
governs file processing, cached table collection, coverage, logs and annual
daily consolidation. S-NPP selections identify notebook 09 as the supported
path. Completion metadata includes the source fingerprint and computation
parameters. Annual daily cache provenance includes its selected source cohort.

The same source-isolation issue was reproduced in notebook 06. Including
S-NPP produced repeated ADD-05 keys and inflated the VIIRS/combined recurrence
tables. Notebook 06 now applies the core source and selected-year filters to
discovery, cached collectors, annual consolidation, coverage and output
tables. Cache provenance forces legacy or differently selected annual
aggregates to be rebuilt. Unselected source files and caches are preserved.

Independent review found no remaining confirmed issues in notebooks 02 and
06. Six new regression tests exercise the actual notebook code, including
legacy caches containing S-NPP and caches from unselected years. The new
regressions were checked against the original notebooks and failed there.

## Real-data local pilot

The raw archives in the user's Downloads folder were opened read-only.
The pilot extracted only each archive's Portugal CSV for 2018 and executed
the actual notebook 01 harmonization function and L1 eligibility/grid logic.

| Source | Satellite | Raw rows | Eligible cell-satellite-days | Invalid times |
|---|---|---|---|---|
| viirs-jpss1_2018 | N20 | 3,672 | 790 | 0 |
| viirs-snpp_2018 | N | 3,827 | 1,119 | 0 |

The NOAA-20 sample spans 2 April through 31 December 2018. The S-NPP sample
spans 2 January through 31 December 2018. The isolated S-NPP builder produced
12 monthly rows, and the same builder correctly rejected the NOAA-20 input
when the caller identified it as S-NPP.

Portugal CSV SHA-256 values are recorded for reproducibility.

- NOAA-20 `6f38e5bda394d16196bc828bc106248cbc9b60cb9c8acdf7d75830dc613a48dc`
- S-NPP `8cb80293d22bf0c697e856d8756ca443bdeed0706776d49f39c5928f9a567a3d`

This is a source-ingestion smoke test, not a complete calibration or global
coverage validation. Coverage derived from a country subset cannot substitute
for the global coverage calendar. No pilot table was published as production
metrics. The detailed local record is ignored by Git under
`data/validation/real_pilot_2018/validation.json`.

## Colab access

The Google Drive connector failed during MCP initialization. Both browser
control entry points failed with `Computer Use native pipe is unavailable`.
The user was asked to reconnect the browser/Computer Use session and leave
Colab open with access to Sprinklers. Full real-data execution on Colab remains
pending that access. No cloud execution or validation is claimed here.

## Verification

- Pipeline: `python -m pytest tests -q` from `data/pipeline` passed with
  **702 passed, 3 skipped**, independently under pandas 2.2.3 and 3.1.1.
- Backend: `python -m unittest discover backend/test` from the repository
  root passed all **6 tests** in an isolated Flask environment.
- Frontend: `npm run build` from `frontend` passed TypeScript and Vite.
  Vite reported its large-chunk warning.
- Frontend: `npm run lint` from `frontend` exited successfully with one
  warning at `src/components/AreaPanel.tsx:49:19` (`set-state-in-effect`).
  That component is unchanged by this source-isolation fix.
- `git diff --check` passed. Raw archives, generated metrics, local validation
  records and dependency/build directories are excluded from this change.
- Full real-data execution on Colab remains pending the access described
  above. Local tests and the Portugal pilot do not close that requirement.
