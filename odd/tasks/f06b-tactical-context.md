# F06b — The analyst's tactical context: the TACTICAL block

Objective: feed the F06a motor's alerts to the booth analyst as a derived,
per-moment context block. Branch `feat/f06b-tactical-context` (from `main`
`ad7822c`). Delivery strategy `ask-on-risk`, work-unit commits, then the
session's established push → PR → CI verde → merge flow. Test runner:
`uv run --frozen pytest`; lint `uvx ruff@0.17.0 check --no-cache src tests`.

## Specs

- **S1** (scope, user's words verbatim): the user selected "Bloque TACTICAL
  siempre activo con fuente (recomendado)" — "Como CHAMPIONSHIP: estado
  por-momento, filtrado al instante de cada evento; run.py lo cablea desde
  los payloads grabados y aparece cuando la fuente está presente. Sin
  intervalos (9655) declara ausencia." This is the authorized priority 1;
  qualifying rules, the FastF1/telemetry decision and Redis/F05 stay out of
  scope. Audio and live/model calls stay out of scope.
- **S2**: The TACTICAL block mirrors the CHAMPIONSHIP pattern exactly: it is
  **context, never a source** — plain prose with no bracket and no
  reference-shaped token, so it adds no citable reference and the
  evidence-only acceptance is unchanged. It renders after CONTEXT/CHAMPIONSHIP
  as prompt lines under a `TACTICAL:` header, bounded (declared line cap),
  deterministically ordered.
- **S3**: `f1show.tactical` gains the source layer: `build_tactical_source`
  builds a frozen `TacticalSource` from the recorded payloads it is handed
  (intervals, laps, stints); `tactical_context` derives the per-moment state
  **as of the event's own instant** — each driver's newest reading at or
  before that instant, classified through the same `GapKind` branching, with
  the freshness window measured against the newest reading at or before it —
  and `render_tactical` renders the bounded lines. Every alert keeps its
  measured facts; no strategy claim; absent kinds are declared silence.
- **S4**: `CommentaryBooth` accepts the tactical source at construction
  (optional; `None` is the declared absence). With a source, every turn's
  prompt carries the TACTICAL block for that event's instant; with `None`,
  no block and no claim. Existing booth behavior (alternation, priority
  band, refusals, citation acceptance) is unchanged.
- **S5**: `run.py` wires `build_tactical_source` from the recorded payloads
  and hands the source to the booth. **Declared contract change**: the run's
  loaded-family list grows to read `intervals` when the fixture carries the
  file, tolerating its absence (session 9655 deliberately has none) — the
  docstring that today declares intervals deliberately excluded is updated
  to state the new contract, including why (the analyst's tactical context).
- **S6**: Determinism: identical payloads and instants produce identical
  blocks; the F14 pacing claim survives (paced and unpaced runs render the
  same block, so the transcript stays byte-identical). The full suite stays
  green; existing booth prompt pins are updated because the prompt gains a
  block — recorded as evidence, never as silent rewrites.
- **S7**: Docs: `docs/PROJECT-STATE.md` row and snapshot deferred to
  delivery (the L3 precedent); the architecture's speech is untouched.

## Tasks

- **T1** (S3,S2,S6): `tactical.py` source layer — `TacticalSource`,
  `build_tactical_source`, `tactical_context`, `render_tactical` — plus
  `tests/test_tactical.py` additions, RED→GREEN. Route: inline. Commit:
  `dc31251` (35 focused tests passed; ruff 0.17.0 clean). Implementation note: the per-moment layer is the motor itself at
  a moving cutoff — `analyze_tactics(..., as_of=...)` threads the instant
  through every family filter, so end state is exactly `as_of=None` and no
  reviewed logic is duplicated.
- **T2** (S2,S4,S6): booth TACTICAL block — construction parameter, per-turn
  context derivation, prompt insertion, `None` absence — plus booth test
  updates, RED→GREEN. Route: inline. Commit: `c5af2cf` (5 new booth tests;
  213 booth+tactical tests passed; ruff 0.17.0 clean; existing prompt pins
  untouched — the block exists only when a source is wired).
- **T3** (S5,S6,S7): `run.py` wiring and the declared intervals-loading
  contract change, 9655 absence, full suite + Ruff. Route: inline. Commit:
  `30430e1` (5 new loader/wiring tests; 1070 passed; ruff 0.17.0 clean).

## Log

- **L1** (2026-10-14, verbatim): "ok procedamos en orden de prioridades." —
  priority 1 confirmed as the booth integration; the user then selected
  "Bloque TACTICAL siempre activo con fuente (recomendado)" in the focused
  scope question (S1 quotes it). Work-unit commits on a feature branch
  follow the session's established pattern; the push → PR → CI verde →
  merge flow is the delivery path the user authorized for this session's
  units.
- **L2**: Seam evidence (bounded reads): `booth.py:39-55` documents the
  CONTEXT/CHAMPIONSHIP blocks as context-never-source; `_prompt`
  (`booth.py:1108+`) inserts `render_championship(...).splitlines()` after
  the salience lines; `run.py:253` wires
  `championship=build_championship_source(payloads)`; `run.py:70-81,131-138`
  declare the loaded families with intervals deliberately excluded — S5's
  contract change names this explicitly. `ChampionshipSource` is a frozen
  dataclass built from payloads (`championship.py:191,268`), the pattern
  S3 mirrors.
- **L3** (2026-10-14): A real delivered defect surfaced during T1, caught by
  Pyright while fixing the new `render_tactical` type blockers:
  `_pace_alerts` set a pace alert's `timestamp` from `window[-1][2]` — the
  record index, not the instant — so pydantic coerced it to an epoch
  datetime. This was the delivered F06a code, and it corresponds to the
  reviewer's CRITICAL finding `R3-pace-timestamp-index` (tactical.py:298),
  which the refuter had marked refuted; the effect was subtle (wrong
  timestamp value, no crash) but real. Fixed in this unit: `window[-1][3]`,
  and the F06a receipt tests still pass because none pinned the wrong
  value. The register row is re-derived at T3.
- **L4** (2026-10-14): T3's measured tradeoffs, recorded rather than hidden.
  (1) Performance: the naive per-turn context re-read 21,041 interval rows
  per aired turn and took the suite from ~35 s to ~300 s; TacticalSource now
  parses and orders the readings once at build time and bisects per turn,
  feeding the motor's own `_gap_alerts` — end-state equality re-proved after
  the change, 50 end-state contexts in 0.13 s, full suite 1070 passed in
  141 s. The residual per-turn cost is the laps/stints scan (memoized
  parsing), declared acceptable for an offline product whose replay is
  wall-clock paced. (2) An empty tactical context (events before the first
  interval reading) renders no block at all, not an empty header. (3) The
  pace-timestamp defect's register row landed in
  `docs/CARRIED-FINDINGS.md` as CLOSED with the fix's identity.
- **L5** (2026-10-15): Delivery record. PR #71 merged as `5aa8c51` after CI
  run 38730786946 passed all four checks on the corrected head `0d5a906`.
  The native review of the functional candidate (`review-9171bc97a22a1a98`,
  medium, readability + reliability) completed both lens captures after the
  maintainer's authorized retry round — the first attempts failed on the
  relay reviewer's output budget — and the refuter closed the lineage into
  `correction_required` with one frozen finding (`R3-pace-timestamp-none`).
  Reproduction disproved the finding's crash claim (the field accepts
  `None`), but the underlying None-instant inconsistency was real; the
  provider's correction-plan capture was then mechanically refused four
  times (binding rejected as stale even byte-exact after fresh STATUS), so
  the maintainer explicitly authorized abandoning the lineage
  (`operator_disposition`) and fixing the substance as an ordinary commit
  (`0d5a906`, regression test included, 1071 tests green). The docs slice
  (snapshot `5aa8c51`, 1071-test receipts, the F06b row) was reviewed as
  lineage `review-e51c189c11d6d3c1` (low, approved, acknowledged) and
  delivered by PR #72 merged as `18f5eea`. Local `main` = `origin/main` =
  the GitHub API at the merge commit, clean tree. F06's deferred tiers
  (qualifying rules, the telemetry source decision, Redis/F05) stay open for
  separate authorizations.
