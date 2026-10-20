# F06d — Pit-window candidates: declared stint norms over recorded races

Objective: give F06 its last deterministic tier — a per-driver projection of when each
driver's next pit stop plausibly falls, derived from the recorded races and a declared,
count-corroborated stint-norm table, as a third pure entry point beside the existing two.
Branch `feat/f06d-pit-windows` (from `main` `7b49cf7`). Test runner `uv run --frozen pytest`;
lint `uvx ruff@0.17.0 check --no-cache src tests`. Delivery is a separate user decision.

## Specs

- **S1** (scope, the user's own choices verbatim): asked which F06 floor to open, the user
  selected **"Pit-window candidates (recomendado)"**; asked how much the unit covers, the user
  selected **"Motor standalone (recomendado)"**, whose stated description is *"Como F06c: módulo
  probado y entregado sin tocar booth ni run. El cableo queda como unidad aparte si después lo
  querés en el prompt del analista."* Therefore out of scope and not implied: any booth or
  `run.py` wiring, the FastF1/telemetry decision, Redis/F05, and every live call (no capture is
  needed — see L2).
- **S2** (the acceptance bar F06 still owes for this tier, verbatim from
  `odd/tasks/f1show.md:1723`): *"Treat tyre-life and pit-loss estimates as assumptions, not
  facts"* and *"No hardcoded Monza or unqualified strategy claims"*; `docs/ARCHITECTURE.md`
  carries the same bar as *"circuit/session parameters are configuration, not hardcoded"*. The
  explorer found the sentence the module itself adds to this: `tactical.py:24-25` states *"tyre
  life and pit loss are estimates by construction, and no record, best-ever or circuit
  comparison exists"* — a pit-window unit must keep that sentence true or edit it deliberately
  without breaking it.
- **S3** (data contract, from L2's measured census): the reading is **race-only** — a session
  whose `session_type` is not `Race` is refused by a typed error naming what is supported, not
  degraded: 9608's qualifying `pit` family supports **event** readings only (`stop_duration`
  null 99/99; its populated 25.8–892.3 s values are garage dwell, not stationary losses).
  Durations: `lane_duration`/`pit_duration` are the **primary** time cost (present 23/23 on
  9617 and 60/60 on 9655) with `stop_duration` the stationary component **when populated**
  (23/23 on 9617; null 33/60 on 9655, clustered on the laps 36–37 safety-car pit batch plus lap
  47 — a cluster the reading must declare, never average away). Every absence is a counted
  declaration, never a silent drop or a zero.
- **S4** (declared stint norms, and where they live): the norms are **estimates**, so they do
  **not** go into `standings.py` — that module's discipline is for regulation datasets, and
  mislodging estimates there would dress them as rules. They live in a **declared, read-only
  table beside the motor in `tactical.py`** (no new module, so no new staleness key is owed),
  reusing `standings.py`'s *discipline*: keyed by **(season, compound)**, each row carrying the
  **count of corroborating stints** it was derived from, a refusing accessor that names what is
  declared, and `RECORDED_SEASON = 2024` injected at the caller (never imported back — the F06c
  L10 decision). Norms are corroborated **only by transition-terminated stints** (right-censored
  stints at race end are excluded from the norm and their count is carried), and the table
  states the measured corroboration — 9617: MEDIUM n=14 (13–32 laps), HARD n=4 (27–40), under the
  declared criterion that opening stints of **fewer than four laps are excluded as early-stop/DNF
  outliers** (driver 44's lap-1 DNF and driver 23's laps-1–3 early stop) — so a reader sees both
  the thinness of the base and the criterion that produced it. No venue constant appears anywhere in the motor.
- **S5** (the motor): a **third pure entry point** in `src/f1show/tactical.py` beside
  `analyze_tactics` and `analyze_qualifying_cutoffs`, returning a source-traceable
  **`PitWindowReading`** (the F06c output shape, not a new `TacticalKind`): per driver, the
  **projected stop lap** = current stint's `lap_start` + the declared norm for that stint's
  compound, and a **window** around it of declared tolerance; each projection labelled an
  estimate in the result; drivers with no current stint, no compound, or no declared norm are
  **declared** rows, never coerced; the 9655 safety-car batch (1-lap stints clustered at laps
  36–37) is declared as a batch, never averaged into the norm. No strategy claim, no best-ever
  comparison, no circuit name. Identical payloads produce an identical reading.
- **S6** (contracts that change deliberately, in the same commit as the behaviour):
  `tactical.py`'s `:3` (*"the single entry point"*), `:9-12` (the F06c scope block — the unit
  becomes the **third** pure entry point), `:14` (*"wiring either motor"*), and `:24-25` (the
  estimate sentence, restated so a declared-norm projection is consistent with it: the norms
  are declared estimates, not records). The two `intervals` corpus claims stay untouched (both
  still hold). No new citable reference and no new airing shape may appear; the booth and the
  run path are untouched.
- **S7** (docs and record): `docs/PROJECT-STATE.md` row and snapshot deferred to delivery (the
  L3 precedent); `docs/ARCHITECTURE.md`'s *Tactical analyst* row updated (pit-window candidates
  no longer "remain"); `docs/CARRIED-FINDINGS.md` gains this unit's rows, including that a
  third entry point inherits the `F06c-as-of-naive` exposure (its trigger names "either entry
  point" — now three); `odd/tasks/f1show.md` gains the `### F06d` section and F06's own
  `Commit/checks` bullet updates — after this unit F06's remaining tiers are **the
  FastF1/telemetry decision** and **Redis/F05** only.

## Tasks

- **T1** (S4, S3): the declared stint-norm table and refusing accessor, plus tests first
  (RED → GREEN): declared season/compound resolving, undeclared season refusing, undeclared
  compound refusing, read-only table, corroborating counts pinned to L2's measured values.
  Route: one writer in this worktree, surface-confined to `src/f1show/tactical.py` and
  `tests/test_tactical.py`; the parent commits. Commit: `86037ac` — **175 + 158 authored**
  additions (0 removed), focused **62 passed** (+7 tests), full suite **1104**, Ruff clean.
- **T2** (S5, S3, S6): the third entry point and `PitWindowReading`, RED → GREEN against the
  spec's boundary, refusal, absence and safety-car-batch cases, with the provenance of each
  value pinned — plus the S6 docstring sentences updated **in the same commit**. Route: one
  writer in this worktree, same surfaces; the parent commits. Commit: pending.
- **T3** (S7): the cross-document rows on this branch — ARCHITECTURE's Tactical-analyst row,
  the CARRIED-FINDINGS rows, the `### F06d` section in `odd/tasks/f1show.md`, F06's bullet.
  Route: parent, then verified. Commit: pending.
- **T4** (all): independent verification per the assess plan, the native review under RDD,
  local integration, and the delivery decision put to the user. Route: parent. Commit: pending.

## Delivery slices

Strategy inherited: `auto-chain` with the cached `feature-branch-chain`
(`odd/tasks/f1show.md:113-115`). Boundary measured as work lands, never carried forward; one
deliverable work unit per child PR. **Boundary so far: 479 authored lines across 2 commits**
(`b3dbe26` 146 + `86037ac` 333) — the same inherited-strategy gate F06c hit, applied here
without a new menu because the chain strategy is cached. The F06c precedent stands: if a
cohesive unit cannot fit ~400 authored lines, one honest slicing pass is recorded and nothing
is trimmed to fit.

## Log

- **L1** (2026-10-20, verbatim): *"ok procede con F06"* — followed by the user's two selections
  quoted in S1. F06c had just closed in `main` (`7b49cf7`).
- **L2** (2026-10-20): **explorer handoff (`gentle-ai-explore`, read-only), the facts this spec
  cites.** Verdict: **capture NOT required** — the deciding fact is that a pit *window* is a
  race concept and 9608's `pit` family can only ever support an event reading. Pit census:
  **9617** 23 records / 19 drivers / `stop_duration` 23/23 (2.2–12.5 s) / lane+pit 23/23
  (23.6–35.0); **9655** 60 records / 18 drivers / `stop_duration` null 33/60 (clustered laps
  36–37 + lap 47) / lane+pit 60/60 (22.6–45.0); **9608** 99/20/event-only. Stints census:
  9617 43 records, zero nulls, MEDIUM/HARD/SOFT, **all 20 opening stints transition-terminated
  (none right-censored)** — the corrected census is MEDIUM n=14 (13–32 laps), HARD n=4 (27–40)
  under the sub-4-lap exclusion of L4, with raw census MEDIUM n=15 (3–32) / HARD n=5 (1–40);
  1–3-lap opening stints belong to driver 44 (**the genuine DNF**, lap 1) and driver 23 (**an
  early stop**, laps 1–3 — 23 ran three stints to lap 55, so L2's original "DNFs 44, 23" was
  wrong about 23); most later stints
  right-censored at race end (laps 55/56); 9655 ~82 records with 4 null-bound records (drivers
  43, 31), 2 `compound:"UNKNOWN"`, and 1-lap stints at laps 36–37 mirroring the null-stop SC
  batch; 9608 all SOFT, lengths 1–4, corroborating no norm. EXTERNAL-CONTRACTS has nothing on
  pit loss or stint norms, but records `pit.stop_duration` exists **only from the 2024 United
  States Grand Prix onwards** (`:147-148`) — which is why 9655's partial nulls are a source
  property, not a defect. Explorer uncertainty, carried: 9655's stint total (~82) was counted
  from a full read but not machine-verified; T1/T2 must re-measure before pinning any count.
  **T1's re-measurement settled it: 82 records machine-verified**, matching L2's claim, with the
  4 null-bound records (drivers 31, 43), 2 `compound:"UNKNOWN"`, 20 drivers and the 23 one-lap
  stints at laps 36–37 all confirmed.
- **L3** (2026-10-20): **decisions taken here, each resting on S2's bar or the user's own
  scope choice.** (1) **Race-only, refusing qualifying** — a window is a race concept and the
  refusal names what is supported (S3). (2) **Norms per (season, compound), counts carried** —
  with n=2 circuits a per-circuit norm would overfit exactly the way the bar forbids; the
  counts make the thinness visible instead of hidden (S4). (3) **lane/pit_duration primary,
  stop_duration stationary-when-present** — it is the only duration field complete in both
  races, and 9655's nulls are a documented source property (S3). (4) **Output is a
  `PitWindowReading`**, the F06c shape, not a new alert kind (S5). (5) **Right-censoring is
  exclusion with a carried count**, not imputation (S4). (6) **Booth surfacing is out of
  scope** — that is the user's own "standalone" selection, so no confirmation is owed (S1).
- **L4** (2026-10-20): **T1's first dispatch stopped on both of its mandatory gates, exactly as
  briefed, and the stop corrected this spec.** (1) The branch did not exist — branch creation is
  the parent's terminal git action. (2) The mandated re-measurement **refuted L2's MEDIUM
  corroboration**: no definition over `fixtures/openf1/stints.json` yields n=16 (raw opening
  stints are n=15, MEDIUM 3–32 / HARD 1–40) — L2's rows mixed two definitions internally (its
  HARD row already excluded the 1-lap DNF while its MEDIUM count kept both outliers and its
  MEDIUM range dropped one), and L2 also mislabelled driver 23 a DNF (23 ran three stints to
  lap 55). **Decision, taken by the parent on the worker's measured options: definition 2b** —
  opening stints of fewer than four laps are excluded as early-stop/DNF outliers, giving
  **MEDIUM n=14 (13–32, median 25.5) / HARD n=4 (27–40, median 37.5)**; the criterion is
  declared in the table, the medians may be half-lap values and their integer handling is T2's
  declared rule. S4 and L2 above are already corrected to these numbers. The process rule this
  stop re-proves, now twice in one feature: **a handoff number that cannot be reproduced under
  any definition is an overcount, not a definitional difference — and the re-measurement gate
  earned its keep by refusing to pin it.**
- **L5** (2026-10-20): **the re-dispatched T1 writer died after writing and before reporting**
  ("assistant reported an error", no output), leaving `+175/0` and `+158/0` in the working tree
  with **no writer-observed evidence**. The parent did not commit blind and did not discard: it
  verified the landed bytes itself — the diff is faithful to S4/2b (the exact 2b numbers, the
  sub-four-lap criterion declared in the table docstring, refusals naming seasons **and**
  compounds, `__all__` extended, **the S6 docstring untouched**, since those sentences are T2's);
  the RED is logically guaranteed (the new names occur **0 times** at HEAD); focused **62
  passed** (+7 tests, including one *named* so the declared criterion is load-bearing rather
  than decorative — `test_the_sub_four_lap_criterion_is_load_bearing_not_decorative`); full
  suite **1104 passed**; Ruff clean. The commit message states the incident. **Process rule:
  a writer's death post-write is an evidence gap the parent fills by measuring the bytes —
  never by trusting them, and never by throwing away verified-faithful work.**
