# F06a — Race tactical motor: deterministic gap/pace/stint alerts

Objective: a standalone, offline tactical analysis module over the recorded
corpus. Branch `feat/f06a-race-tactics` (from `main` `4cad489`). Delivery
strategy `ask-on-risk`, work-unit commits, no push/PR/merge. Test runner:
`uv run --frozen pytest`; lint `uvx ruff@0.17.0 check --no-cache src tests`.

## Specs

- **S1** (scope, user's words verbatim): "Motor offline para carreras
  (recomendado)" — "Alertas de gap, ritmo y stint como módulo probado. Sin
  cambiar el booth ni el run." Entrega: "motor determinista, referencias a
  datos y pruebas de límites, vueltas de desventaja, ausencias y datos
  viejos." Conserva: "el comportamiento actual del replay." Después:
  "conectar las alertas al analista." Qualifying, FastF1/telemetry, Redis,
  booth integration, audio, live/model/TTS calls, new fixture capture and
  publication are all out of scope for this unit.
- **S2**: The motor consumes `classify_gap` (the F04 handoff deadline);
  `+1 LAP` stays a lap count, never cast to seconds. Branching is by
  `GapKind`; no comparison of readings across kinds.
- **S3**: Gap alerts from recorded `intervals` rows only (session 9617; the
  9655 fixture deliberately has none): a `SECONDS` reading at or under the
  configured battle threshold is a battle alert naming the follower driver;
  a `LAPS` reading is a lapped alert with its lap count; `UNKNOWN` is
  declared as unknown; `ABSENT` produces no alert (documented, tested).
- **S4**: Stale data: a driver whose newest interval reading is older than
  the configured staleness window behind the newest reading overall gets one
  stale alert; its readings feed no battle or lapped alert.
- **S5**: Pace alerts from recorded `laps`: per driver, the median of the
  last K clean laps (lap 1 never counted; pit in/out laps excluded; null
  durations excluded); drivers with fewer than K clean laps are excluded; a
  driver whose median exceeds the session best median by more than the
  configured threshold gets a pace alert naming both medians and the delta.
  No record, best-ever or circuit claim is made.
- **S6**: Stint alerts from recorded `stints` + `laps`: computed tyre age =
  `tyre_age_at_start` + laps completed on the stint up to the driver's last
  completed clean lap; age at or over the configured threshold is an alert.
  Tyre life and pit loss remain estimates, never asserted facts.
- **S7**: Every alert carries source references (family, record index,
  driver, timestamp where the family has one). Determinism: identical
  payloads produce an identical ordered tuple; the order is total and
  declared. Missing families (intervals absent) are declared absence, not
  errors. Records whose `session_key` is not the analyzed one are not
  attributed. Thresholds are configurable; defaults are declared.
- **S8**: The replay path and both booths are untouched: no edits to
  `booth.py`, `run.py`, collector behavior, or existing fixtures. New public
  exports are additive. Existing suite stays green.

## Tasks

- **T1** (S2,S3,S4,S7): `src/f1show/tactical.py` — gap/stale analysis
  consuming `classify_gap`, plus `tests/test_tactical.py` RED→GREEN, exports.
  Route: inline. Commit: `9c9555c`. RED observed (ImportError on collection
  before implementation); GREEN 14 passed; ruff 0.17.0 clean. Measured pins:
  defaults 17 stale / 3 lapped / 0 battles; window 600 s → 1 battle (driver
  4) / 7 lapped / 1 stale.
- **T2** (S5,S7): pace alerts, RED→GREEN. Route: inline. Commit: `e436093`.
  RED observed (unknown setting rejected at collection); GREEN 21 passed;
  ruff 0.17.0 clean. Measured pin: 12 pace alerts, best median 97.889 s.
- **T3** (S6,S7): stint/tyre-age alerts, RED→GREEN. Route: inline. Commit:
  `d6d33a9`. RED observed (unknown setting rejected at collection); GREEN 27
  passed; ruff 0.17.0 clean. Measured pin: 11 tyre-age alerts, second
  stints, estimated ages 25-40 laps.
- **T4** (S1,S8): carried-findings rows re-derived, suite + Ruff, and the
  `docs/PROJECT-STATE.md` row **deferred to delivery** (L3). Route: inline.
  Commit: pending.

## Log

- **L1** (2026-10-14, verbatim): "ok, vamos con F06" — followed by the
  user's scope selection "Motor offline para carreras (recomendado)" with the
  description and preview quoted in S1. Local work-unit commits authorized;
  push/PR/merge explicitly not part of this unit.
- **L2**: Explorer handoff (task mv89o9sp-2-w7a6) established: no intervals
  in 9655; both recorded sessions are races; `classify_gap` has zero product
  callers; consuming it reopens carried findings at
  `docs/CARRIED-FINDINGS.md` (canonical rendering fidelity; GapReading
  cross-kind) — addressed in T4, honestly.
- **L3** (2026-10-14): The `docs/PROJECT-STATE.md` row is deferred to the
  delivery step. The map's table is "built and delivered, all in main" and
  names the revision it describes; F06a lives on `feat/f06a-race-tactics`
  and this unit's authorization is local work-unit commits only — no push,
  PR or merge. Adding the row now would describe an unmerged branch as
  delivered. The row lands when integration is authorized.
- **L4** (2026-10-14): Carried findings re-derived against current bytes.
  `R3-canonical-not-faithful` (`collector.py:198`, was `:198-199`): measured
  on this unit's consumption — the `default=repr` fallback is unreachable
  from recorded JSON payloads (json.loads yields only JSON-representable
  values; equal values render identically across key order; `1`/`"1"` and
  `True`/`1` render distinctly) — marked DEAD RECORD per the register's own
  precedent, with the programmatic-caller residual named. `R3-gapreading-
  cross-kind` (`collector.py:113-131`, was `:121-131`): CLOSED by
  consumption — the motor branches on `GapKind` and emits only the field
  its kind guarantees; pinned by tests. Coordinates re-derived against the
  current file.
- **L5** (2026-10-14): Verification receipts for the branch: focused
  `tests/test_tactical.py` 27 passed (RED observed before each unit's
  implementation: collection ImportErrors and unknown-setting
  ValidationErrors); full frozen suite 1053 passed, 1 warning (the known
  external google/genai deprecation) in 34.97s; Python 3.12 floor 1053
  passed in 35.48s; `uvx ruff@0.17.0 check --no-cache src tests` clean.
  Pyright through lens_diagnostics reports `reportMissingImports` for
  venv-resolved deps on both this module and the untouched `collector.py`
  — a tooling environment defect (Pyright does not resolve `.venv`),
  recorded as memory 6088; runtime resolution is authoritative.
