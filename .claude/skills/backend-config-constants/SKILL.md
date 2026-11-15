---
name: backend-config-constants
description: "Backend rule: every setting, constant, fixed message and registry list lives in backend/src/config.py, never in the module that uses it. Use whenever you write or change Python in backend/ (features, database, validation, main.py), before adding any module-level UPPER_CASE name, magic number, repeated string or list of ids."
---

# Backend constants live in `backend/src/config.py`

`config.py` is "every setting and constant of the backend, in one place". Keep it that way.

## What goes in `config.py`

- Settings: host, port, data source, file names, limits (`MAX_RADIUS_KM`, ...).
- Numeric constants: grid size, Earth radius, rounding (`METRIC_DECIMALS`), minimum sample sizes.
- Fixed user-facing strings reused by the code: notes and messages (`NOTE_NO_DATA`, ...).
- Registry lists: which features / metrics the API serves (`FEATURES`, `METRICS`).

If you are about to write a module-level `UPPER_CASE = ...` anywhere other than `config.py`,
put it in `config.py` instead and import it (`from . import config`, then `config.NAME`).
The same goes for a number or string literal that means something beyond the line it is on.

## What stays out

- Values local to one expression, whose meaning is obvious there (`range(1, 13)` for months, `100` in a percentage).
- Functions. `config.py` holds data only: it must not import `features`, `database` or `main`
  (they import `config`, so that would be circular). A registry in `config.py` therefore lists
  *names* (e.g. metric ids); `main.py` maps them to functions when it builds the app.
- The mock-data scripts in `backend/test/` (`generate_mock_data.py`, `build_mock_*.py`): they
  stand in for the pipeline, so their own parameters (regions, fire events, sensor dates) stay
  in them. Anything the backend itself reads (file names, grid size) still comes from `config.py`.

## Group and comment

Put each new constant under the matching `# --- Section ---` header of `config.py` (add a
section if none fits), with a short comment when the name alone does not say the unit or why.
