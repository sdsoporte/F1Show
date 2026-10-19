# F06c — Qualifying cutoffs: declared season rules over a captured session

Objective: give F06 the tier it still owes — deterministic **qualifying cutoffs** driven by
declared per-season rules, computed over one newly captured qualifying session, as a
standalone motor. Branch `feat/f06c-qualifying-cutoffs` (from `main` `5cadb4b`). Test runner
`uv run --frozen pytest`; lint `uvx ruff@0.17.0 check --no-cache src tests`. Delivery is a
separate user decision taken at the end of the unit.

## Specs

- **S1** (scope, the user's own choices verbatim): the user selected the F06 piso
  **"Qualifying (recomendado)"**; asked what to capture, the user selected
  **"Sólo 9608 (Austin)"**; asked how much the unit covers, the user selected
  **"Motor standalone primero (recomendado)"**, whose stated description is *"Como F06a:
  módulo de corte probado y entregado sin tocar booth ni run. Sigue el patrón que ya usaste y
  deja el cableo como unidad aparte si querés."* Therefore **out of scope and not implied by
  any of these choices**: Sprint Qualifying (sessions `9612` and `9650`), any booth or `run.py`
  wiring, FastF1/telemetry, Redis/F05, and every live or model call other than the fixture
  capture authorized in S3.
- **S2** (the acceptance bar F06 still owes, verbatim from `odd/tasks/f1show.md:1723`):
  *"qualifying cutoffs follow the selected season/session rules; tests cover boundary values,
  lapped/null intervals, missing telemetry, pit interference and stale data. No hardcoded Monza
  or unqualified strategy claims."* This spec is the reason the unit exists; S5 delivers it.
- **S3** (the capture): record session `9608` (`Qualifying`, Austin, `2024-10-19T22:00Z`,
  meeting `1247`) into `fixtures/openf1/9608/`, **verbatim** — exact received bytes, compact
  single-line JSON, no re-serialisation, no trimming, no sampling — under the method PROVENANCE
  already declares: a throwaway recorder kept **outside** the repository, plain HTTP with
  `trust_env=False`, `follow_redirects=False`, a bounded timeout, `GET` only, host
  `api.openf1.org` only, **no authentication of any kind** (no token, no `Authorization`
  header, no cookies), `sleep 0.5` between requests, paced inside the documented free tier
  (3 requests/second, 30 requests/minute). Families to fetch: `sessions`, `drivers`, `laps`,
  `position`, `race_control`, `stints`, `pit`, and `session_result` — each with its **exact URL,
  HTTP status, bytes, records, timestamp span, request time and SHA256** recorded in a new
  PROVENANCE section. `intervals` is **deliberately excluded** (cutoffs need lap times and
  position, not gaps; it is also the one family that already broke the size gate). The three
  championship families are **deliberately not fetched**, and PROVENANCE must record the
  measured reason: *"these three paths answer for a race session; a practice or qualifying
  session has no championship rows"* (`fixtures/openf1/PROVENANCE.md:152`, the *Race-session-only*
  paragraph). The declared size
  gate applies unchanged: **stop and report** if any single family exceeds roughly 2 MB or the
  total exceeds roughly 12 MB, and the request budget is declared and counted.
- **S4** (declared rules, reuse the existing shape): the cutoff rules live in a **declared,
  read-only per-season table** following `standings.py` — a frozen rules dataclass
  (`standings.py:152-166`), a `MappingProxyType` table (`:199-221`), a `season_rules(season)`
  accessor that **refuses an undeclared year by naming the declared ones** (`:224-232`), and the
  recorded season injected from `RECORDED_SEASON = 2024` (`championship.py:142`) — **at the caller
  that owns the constant**, never by importing it back into `standings.py` (see L10). No rule value
  may be derived from, or pinned to, the captured
  session: the fixture supplies lap times and positions only, and **every** cutoff, phase length
  and elimination count comes from the declared table. An undeclared season is a typed refusal,
  never a fallback.
- **S5** (the motor): a pure, offline, deterministic cutoff analysis over recorded payloads —
  no network, no clock, no randomness; identical payloads and instants produce an identical
  result; every reading traceable to the source record that produced it. Unknowns, absences and
  missing families are **declared**, never coerced. Phase boundaries come from the data where the
  source carries them and from the declared rules where it does not, and which of the two
  produced a value must be visible in the result. Estimates are labelled as estimates; no
  strategy claim and no circuit-specific constant.
- **S6** (contracts that change deliberately, not silently): `src/f1show/tactical.py`'s module
  docstring declares the unit race-only — `:1` *"(F06a)"*, `:8-11` *"Scope of this unit (F06a).
  Race-only, recorded-corpus-only analysis of gaps, freshness, pace and stint age. Qualifying
  cutoffs, telemetry (car/location/weather), FastF1, Redis delivery, booth integration and audio
  are out of scope…"*, plus the corpus claims at `:40-44` and `build_tactical_source:599-602`.
  Whatever this unit touches there is edited **deliberately** and stated as the new contract;
  sentences left untouched must still be true afterwards. The booth's evidence rules do not move:
  no new citable reference and no new airing shape may appear anywhere.
- **S7** (docs and record): `docs/PROJECT-STATE.md` gains the F06c row and a snapshot naming the
  revision it describes (L3 precedent); `docs/CARRIED-FINDINGS.md` gains this unit's rows,
  including the loader-conformance limitation recorded in the Log below; `docs/ARCHITECTURE.md`
  is re-read for the `Tactical analyst` row and updated only if this unit makes its wording
  false; `odd/tasks/f1show.md` records F06c under F06 and keeps F06's own `- [ ]` marker and
  acceptance criteria unchanged.

## Tasks

- **T1** (S3): capture session `9608` verbatim with its full provenance section and request
  budget. Route: writer with `bash`, surface `fixtures/openf1/9608/**` and
  `fixtures/openf1/PROVENANCE.md`. Commit: `9396187` — 164 authored lines, and the full suite was
  run on this branch **before** it: **1071 passed** in 105s, exit 0.
- **T2** (S4, evidence L9): declared per-season qualifying rules — frozen rules type, read-only
  table, refusing accessor, `RECORDED_SEASON` injected **at the caller** — plus tests first
  (RED → GREEN), covering an undeclared season **and** an undeclared session kind. Route: one
  writer in **this** worktree, surface-confined to `src/f1show/standings.py` and
  `tests/test_standings.py`; the parent commits. Commit: `019d43a` — **178 + 140 authored lines,
  0 removed**, full suite **1078 passed** measured on the live bytes.
- **T3** (S5,S2): the cutoff motor over the captured payloads, RED → GREEN against the spec's
  boundary, missing-data and pit-interference cases, with the provenance of each value pinned.
  Route: writer in its own worktree; independent verification after. Commit: pending.
- **T4** (S6,S7): the deliberate docstring/contract edits, the docs rows and the register row.
  Route: parent, then verified. Commit: pending.
- **T5** (all): independent verification, native review under RDD, local integration, and the
  delivery decision put to the user. Route: parent. Commit: pending.

## Delivery slices

**Strategy inherited, not chosen here:** `delivery_strategy: auto-chain` with the cached
`chain_strategy: feature-branch-chain`, declared at `odd/tasks/f1show.md:113-115` — *"Future units
use a feature/tracker branch with bounded review slices … never review the whole accumulated
branch."* Under `auto-chain` the cached choice is used without asking again, so no menu is owed.
Selecting a strategy authorizes **no** push, PR, merge or review-mode change; those stay separate
decisions of the user.

**Budget rule:** ~400 authored changed lines is a planning heuristic, not a cap — never delete
tests, comments or whitespace to meet it, split cohesive behaviour instead.

**Boundary measured before this commit: 628 authored lines across 3 commits**, so every slice
below is bounded from here rather than inherited on assumption.

| Slice | Deliverable work unit | Commits | Authored lines |
| --- | --- | --- | --- |
| 1 | the recorded qualifying window and this spec (T1 + registration) | `9396187`, `963ef64` | 164 + 146 = **310** |
| 2 | the declared per-season rules (T2 + this record) | `019d43a`, this commit | **318** committed, plus this record |
| 3 | the cutoff motor (T3) | pending | bounded before coding; one honest slicing pass if it cannot fit |
| 4 | contracts, docs and the register row (T4) | pending | bounded before coding |
| 5 | verification, native review and delivery (T5) | pending | bounded before coding |

One deliverable work unit per child PR, each carrying the tests and docs it verifies; the tracker
PR stays draft/no-merge until every child is reviewed. Counts are re-measured before each commit,
never carried forward.

## Log

- **L1** (2026-10-19, verbatim): *"revisa en que quedamos."* — the session found F06b delivered
  (`main` `3ad9c42`) and three documents still denying F06's delivery.
- **L2** (2026-10-19, verbatim): *"si, procede por la corrección de PROJECT-STATE y después
  decidimos el piso de F06"* — the PROJECT-STATE rows were corrected, and the scope question
  that followed produced two further corrections the user approved verbatim as
  **"ARCHITECTURE + f1show.md"**: `docs/ARCHITECTURE.md:46` claimed the tactical analyst does
  not exist and `:73` marked it `[target]`, and `odd/tasks/f1show.md` carried **zero** mentions
  of F06a/F06b (`grep -c` = 0) despite both being delivered.
- **L3**: those corrections reached `main` as **`5cadb4b`** ("docs: update architecture, project
  state and f1show task", `2026-10-19T18:01:37Z`) — **directly on `main`, with no branch and no
  PR**, committed by an actor that was not this session: this session ran no `git commit` or
  `git push`, the writer was forbidden from it and reported a dirty tree at exit, there are no
  git hooks and no live `git` process, and the reflog shows the `merge origin/main:
  Fast-forward`-then-commit pattern of **another session on this same worktree**. CI run
  `39299112536` passed 4/4. The user was shown all of it and chose verbatim
  **"Aceptar y seguir con F06"**, so the delivery stands and the branch/PR route was waived for
  that change only.
- **L4** (2026-10-19): the piso was chosen **"Qualifying (recomendado)"** and then narrowed by
  the two decisions quoted in S1. Exploration (`gentle-ai-explore`, read-only) established the
  decisive facts: **every recorded family belongs to a race** (`PROVENANCE.md:42` and `:203`),
  so a capture is required; the qualifying sessions adjacent to the recorded races are `9608`
  (Austin, `2024-10-19`) and `9646` (Lusail, `2024-11-30`), with Sprint Qualifying `9612`/
  `9650` beside them; the user took the single-session option.
- **L5** (2026-10-19): **measured constraint that shapes this unit.** The loader's declared
  contract requires ten files per recorded session (`_LOADED_FAMILIES`,
  `src/f1show/run.py:83-87`), and it refuses both a missing file (`:122`) and a file with no row
  for the session (`:126`). Because the three championship families carry **no rows** for a
  qualifying session, **`load_recorded_session(9608, …)` would refuse even a complete capture** —
  so `fixtures/openf1/9608/` is declared a **motor-only** fixture directory: T3 reads its payloads
  directly, nothing routes it through the loader, and the limitation is carried with an owner and
  a trigger (the first unit that tries to *run* a qualifying session). Verified not to break what
  exists: no source or test file walks fixture directories — `iterdir`/`glob`/`walk` matches in
  `tests/` and `src/` are only `ast.walk` over an AST and `iterdir` over `tmp_path`.
- **L6** (2026-10-19): size and budget facts carried into S3 from PROVENANCE: the declared gate is
  **~2 MB per family / ~12 MB total** (it fired once, on `intervals` at 2,965,644 bytes, accepted
  whole by the maintainer), and the recorded requests were `GET`-only, unauthenticated, HTTP 200
  on the first attempt, paced at `sleep 0.5`. There is no capture script in the repository — the
  recorder is deliberately thrown away in `/tmp`, which is why T1 re-states the method instead of
  importing one.
- **L7** (2026-10-19): T1 captured, and the parent verified it rather than accepting the report — eight
  families, **340,640 bytes** total, largest family **154,940** (`position`), so the ~2 MB / ~12 MB gate
  **did not fire**; all eight answered HTTP 200 as JSON arrays and none came back empty; bytes, SHA256 and
  record counts re-measured by the parent and equal to the table; PROVENANCE appended **150 ins / 0 del**;
  `tests/test_run.py tests/test_second_session.py` **42 passed**.
- **L8** (2026-10-19): the measurement that changes S3's premise, found in verification rather than in the
  capture. **`session_result` does answer for a qualifying session** — **20 rows**, `position` populated
  1..20 — so the race-only sentence at `PROVENANCE.md:152` **over-claimed** for it. A correction paragraph
  was added at that source, the `confirms it for the two championship paths` overstatement in the new
  section was reworded to *leaves it unmeasured*, and the wrong `PROVENANCE.md:164` citation this spec
  carried (inherited from exploration, where it pointed at the request-budget text) was re-anchored to
  `:152`. **Two facts T3 must depend on, both measured on this capture:** `race_control` carries
  **`qualifying_phase` non-null on 17 of 40** records with values `1`/`2`/`3` while **`lap_number` is null
  on all 40**, so a phase exists only for the rows that carry it and must be declared absent elsewhere; and
  `laps.date_start` is null on **1 of 282** with `lap_duration` null on **22 of 282**. The two championship
  paths were **not fetched**, so what they return for 9608 stays unmeasured and is claimed by nobody.
- **L9** (2026-10-19): **the values T2 must declare, measured from the capture rather than assumed.**
  `race_control`'s `qualifying_phase` rows carry a `SESSION STARTED`/`SESSION FINISHED` pair per phase, so
  the three windows are data, not inference: phase 1 **22:00:00–22:18:00 (18 min)**, phase 2
  **22:25:00–22:40:00 (15 min)**, phase 3 **22:48:00–23:00:00 (12 min)**, separated by **7** and **8**
  minutes of break — the breaks are **not** uniform, so no inter-phase gap is declared as a rule. Counting
  distinct drivers whose lap **started** inside each window gives **20 → 15 → 10**: three phases, five
  eliminated after phase 1 and five after phase 2, ten classified. **14 laps start outside every window and
  one lap has a null `date_start`**, so boundary handling has real cases instead of idealised ones. What is
  declared for 2024 main qualifying is therefore the phase structure, the per-phase durations and the
  advancement counts; what is **deliberately not declared** is Sprint Qualifying — the user captured only
  `9608`, so an unmeasured session kind is refused rather than invented.
- **L10** (2026-10-19): **T2 closed as `019d43a`** — 178 added to `standings.py`, 140 to
  `tests/test_standings.py`, **0 removed**, so no pre-existing line or assertion was touched and
  `season_rules` kept its exact signature; full suite on the live bytes **1078 passed** (1071 base
  + 7). Three things the parent measured instead of accepting: the RED is a collection failure and
  is **logically guaranteed**, because the new names occur **0 times** in
  `HEAD:src/f1show/standings.py`; a mutation of the phase-2 duration to 16 was planted by the
  parent and failed **exactly** `test_the_declared_phase_structure_is_the_measured_one`, then was
  restored with zero residue and the diff back to `178 0`; and all four refusal messages executed
  verbatim, including season **2025** being refused even though `SEASON_RULES` declares it — a
  season with points is not a season with qualifying rules.
- **L11** (2026-10-19): three process facts, each a trap worth keeping. (1) The writer reported
  **134** test lines while the live file was **140**: pi-lens reformatted it **after** the child
  measured, so acceptance, commit and slice counts bind to the **parent's** measurement — this is
  the second time in this feature. (2) The RED was of the collection kind, which is exactly what
  F06a recorded first: the honest RED for a brand-new module API, not a shortcut. (3) A pi-lens
  advisory at `standings.py:562` (`float(row.points)` without a guard) is **pre-existing, not
  T2's**: that line sat at `:401` in `HEAD` and only slid down with the insertions, and T2's diff
  adds no `int()` or `float()` call at all. Because `StartStanding` is an unvalidated frozen
  dataclass, a non-numeric `points` would raise a bare `ValueError` instead of the module's typed
  `StandingsInputError` — **T4 owns the register row; owner: whoever next touches `_start_points`;
  trigger: any change to start-checkpoint parsing.**
