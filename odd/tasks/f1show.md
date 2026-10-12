# F1Show: complete distributed commentary system

## Outcome and current authorization

Build a replay-testable, real-time Formula 1 commentary system with five logical
roles: deterministic collector, tactical analyst and historian, plus two Gemini
commentator personas. Run four role services plus a dedicated sync writer, and Redis,
with Docker Compose.

**Authorization is per task and does not accumulate.** F00, F01 and F02 were
separately authorized and completed. The user explicitly approved publishing F01+F02
to `main`, followed by MIT licensing and `SECURITY.md`; the published tip is
`fc30084`. F03 implementation was authorized on 2026-10-09, including local work-unit
commits, and the user separately authorized the four F03b advisory fixes: "si continua
con los arreglos para que quede de forma correcta." The user then explicitly requested
fresh native consent, approval flow, commit and push, and selected publication of the
current F03a + F03b + F03b-1 advance on **`feat/f03-source-adapters` only**. Approval
must come from native review; `main` must not change. F04–F13 implementation, publication
of later units, pull requests, merges, deployment, authenticated/live API or model calls
and purchases are not authorized by these grants.

On 2026-10-10 the user explicitly requested: "ok, procede con el push, revisa la tres
sugerencias y luego procede con F03c-3". That authorizes a normal feature-branch push of
the reviewed F03c-1/F03c-2 advance, read-only examination of the three latest suggestions,
then F03c-3 implementation. It does not authorize advisory fixes, force-push, main/PR/merge,
new real-service/model calls or automatic publication of the next source unit.

## Baseline and decisions

- Workspace: `F1Show`; local Git repository, `main` created at the bootstrap commit.
- Preparation branch: `feat/f1show-bootstrap`; public GitHub repository:
  `sdsoporte/F1Show`, created with the existing SSH/gh configuration.
- Repository-local Git identity (user-selected; no global identity exists on this
  machine): `sdsoporte <211432262+sdsoporte@users.noreply.github.com>`.
- **Publication.** `main` was fast-forwarded to F02's tip and pushed on 2026-10-09:
  `413a75d..8cbe94b`, 15 commits, no merge commit. Independent audit passed 8/8,
  including all 36 published blobs matching local Git and 131 offline tests from a
  clean archive installation. MIT `LICENSE` and `SECURITY.md` followed in `fc30084`;
  local `main` and `origin/main` both resolve to that tip. The separately authorized
  F03a + F03b + F03b-1 advance is published on `origin/feat/f03-source-adapters`
  through `3ec02ea`; `git ls-remote` matched the local commit exactly. Main was unchanged.
  On 2026-10-10 a normal feature push published the 14 later commits through `3f52c33`,
  including native-approved source units `32a55aa` and `badfa54`. Before/after remote
  checks matched `3f52c33889dd02ab63eecfce1880a0cc8f448fb5`; remote main stayed `fc30084`.
- **Branch chain.** `feat/f1show-bootstrap` (F00–F01) → `feat/f02-python-foundation`
  (F02) → `feat/f03-source-adapters` (F03), each cut from the branch that had already
  landed, so a slice is never reviewed as part of an accumulated chain.
- The unrelated `/home/s/.git` is not this project's repository. Never stage it.
- User chose the full documented architecture, current SDK/models, deterministic
  analyst/historian, and archiving the original Word documents now.
- Move all ten originals from `docs/` to repository-relative `origis/` with exact
  byte preservation. Nine contain extracted text; Project Notes is an empty
  document. Keep the numbered code variants: their tails contain unique material.
- Maintain new project documentation in `docs/`; originals are historical evidence,
  not executable source or authoritative current API specifications.
- Use Python async, httpx, Redis Streams and maintained `google-genai`.
  Final dependency versions and available model IDs must be verified before coding.
- Three deterministic roles make zero LLM calls. Only the commentary service uses
  Gemini. No agent framework is required for the specified initial topology.
- Historical OpenF1 data is free and unauthenticated from the 2023 season onwards;
  real-time access requires a paid subscription (€9.90/month, verified 2026-10-09).
  Replay comes first. Do not promise free live data or authorize purchases.
- `sync` writer plus a local store replaces direct per-agent API access. A single
  sync process is the only component that talks to OpenF1; it writes to **SQLite in
  WAL mode** (one writer, many concurrent cross-process readers) and produces
  immutable per-session **Parquet snapshots** analysed with **DuckDB**, which double
  as the replay fixtures. DuckDB was rejected as the live store because its own
  documentation supports only one read-write process or many read-only processes, and
  every Compose service is a separate process. **Redis Streams remains the event
  transport**: agents still consume events, and the store serves state, context and
  history only.
- Live sync cadence is approximately 3 seconds. The end-to-end latency budget is sync
  interval + derivation + enrichment join + model call, of the order of 5–8 seconds;
  the measurable F12 acceptance limit is **≤ 8 seconds**.
- F01 gate decisions: commentary language is **configurable with no default fixed
  yet** (chosen before F09); the audience is the **technical Formula 1 fan** — a
  data-dense register where every claim is tied to session evidence; **model spend
  per session is not capped**, so the system measures and reports only; and the pilot
  ceiling is approved at F13 against measured usage. Until F13 there is **no hard cost
  stop of any kind**.
- Text/CLI transcript is the initial output. Audio/TTS, dashboards, social posting,
  multi-session operation and cloud deployment are separate future scope.

## ODD execution rules

1. Reconcile this file, the Engram mirror and the visible todo projection before
   resuming. Keep stable IDs and one active task. This file has outgrown the ~49.8 KB
   Engram record cap, so the mirror is split: `odd/f1show/tasks` holds the prefix and
   `odd/f1show/tasks-part2` holds the remainder. The on-disk file is authoritative.
2. Explore each bounded unit and resolve product uncertainty before source edits.
   Use a read-only explorer when evidence exceeds a small targeted read.
3. Derive narrow edit surfaces; delegate multi-file changes to one writer. Writers
   read the task first, never change ODD bookkeeping or perform Git delivery.
4. For deterministic behavior, observe meaningful RED, minimum GREEN and refactor
   checks. Use offline fixtures and fake clocks/providers; no live calls in CI.
5. Passive documentation has no meaningful behavior RED. Check paths, links,
   original hashes, whitespace, ignored secrets and intended publication scope.
6. Preserve code, tests and relevant docs in each work-unit commit on a feature
   branch. Record the observed commit and checks; obey explicit Git authorization.
7. Native review runs only under the user's RDD switch and provider continuations,
   against a work-unit commit or bounded PR slice, never a checkbox or the entire
   project backlog. Review does not authorize push, PR creation or merge.
8. Update this file, its split mirror (both parts) and todo after each actual task
   transition.
   Never close a task with failing required checks or missing implementation.

## Review workload and routing

- Bootstrap forecast: approximately 400–550 authored changed lines plus about
  4.7 MB of preserved binary Word sources. Check the actual count before delivery.
- The whole application will be several thousand authored lines; it is not one
  review candidate. Refine estimates before each authorized work unit.
- Delivery strategy: `auto-chain`; user-selected chain strategy:
  `feature-branch-chain`. Future units use a feature/tracker branch with bounded
  review slices. The bootstrap is one cohesive documentation/archive unit; the
  large binary sources are explicitly included, not application code.
- No PR creation or application delivery is authorized here. Choose concrete
  future slice boundaries before coding; never review the whole accumulated branch.
- About 400 authored diff lines per task is a planning heuristic, not a hard cap.
  Do not remove tests, comments or whitespace to meet it; split cohesive behavior.
- F00 route: delegated explorer (large Word corpus), delegated worker (multiple
  documentation files), bounded verification of artifacts and public-file scope.
- F01–F13 routes: scoped explorer when needed, single delegated writer, applicable
  writer checks and risk-gated independent verification. Parent owns Git/memory.

## Stable task checklist

### F00 — Bootstrap the repository and current project vision

- [x] **Done.** Isolated Git initialized, `.gitignore` created, the ten originals
  preserved in `origis/`, README/current architecture/source review written, public
  GitHub repository created with SSH origin. The authorized initial `main`
  publication of this commit closes the task.
- Checks: original count/hash equality (10/10 SHA-256 and byte counts against the
  pre-move baseline), each `.docx` readable as an OPC/ZIP package, no embedded media
  and no credential-shaped strings in any document part, Markdown links resolve,
  whitespace and final-newline hygiene, ignore matrix verified with
  `git check-ignore`, publication scope reviewed.
- No application test suite exists. Documentation/metadata checks are appropriate;
  no RED/GREEN, production readiness or complete secret audit is claimed.
- Evidence: Git root is F1Show, branch `feat/f1show-bootstrap`, gh account sdsoporte
  over SSH. Preparation commit `6ebfeff02f9d439eda1596af0bf92421de0d9025`: 15 files,
  655 authored lines plus about 4.7 MB of byte-preserved binaries.
- Independent verification found two defects, both fixed before the commit: a
  truncated SHA-256 in `origis/README.md` and a machine-local scratch path leaked
  into publishable prose. A third gap this plan did not anticipate — no Git identity
  configured on the machine, which made the required commit impossible — was closed
  with the repository-local identity recorded above.
- Known risk, not blocking: the originals embed Inter/Roboto/RobotoMono font binaries
  under their own licenses (SIL OFL / Apache), redistributed here as part of the
  unmodified documents. No application code, tests, container files or dependency
  manifests were created. Nothing else outstanding.
- The earlier admission block is resolved: it came from a session that started in
  `/home/s` before this repository had a `.git`, so the writer was refused. A session
  started from the repository root admits delegated work normally. Do not replay the
  failed jobs or reset review authority.

### F01 — Validate current external contracts and operating limits

- [x] **Done.** External contracts validated on 2026-10-09 against first-party sources
  plus two direct unauthenticated observations, and recorded in
  `docs/EXTERNAL-CONTRACTS.md`: OpenF1 tiers, prices, rate limits, endpoint inventory,
  cadence and two observed schemas; Jolpica base URL, observed shapes, documented
  limits and Ergast differences; `google-genai` version, the deprecation of the legacy
  package, the enumeration method, both auth paths, the dependency floor and the cost
  envelope. No model ID is named anywhere.
- Acceptance: evidence-linked dependency choices and configurable endpoint/model
  settings are satisfied by citing every claim and by requiring endpoints and model
  IDs to come from typed configuration rather than literals. Explicit live access
  prerequisites are recorded. **The "user-approved pilot budget" criterion is moved
  to F13**, because a total cannot be set honestly before the model and its measured
  usage are known; F01 records the verified subscription price and the decisions
  instead of inventing a number.
- Gate: resolved. Commentary language is configurable with no default fixed yet and is
  chosen before F09; the audience is the technical Formula 1 fan; the measurable
  latency limit is ≤ 8 seconds end-to-end; per-session model spend is uncapped by
  decision, which is recorded as the reason no hard cost stop exists until F13.
- Notable findings: a single sync writer is a **structural necessity**, not a cost
  preference — `car_data` at 3.7 Hz across ~20 drivers is ~74 req/s, about 25× the free
  tier and 12× the live tier. OpenF1 exposes no driver identifier beyond per-session
  `driver_number` and `name_acronym`, and `driver_number` is not stable across seasons,
  so the identity mapping is ours to build and freeze as a dated fixture.
- Correction carried forward: an earlier revision claimed Jolpica's driver object lacks
  `dateOfBirth`. It **does** expose it; the claim came from a truncated observation and
  is corrected in the documents. F08's acceptance is corrected by the same pass.
- Depends on F00. Evidence: `docs/EXTERNAL-CONTRACTS.md`, plus `docs/ARCHITECTURE.md`
  and `README.md` updated with cited sources. Commits `f908a28` (contract record) and
  `aab638b` (local store, cited access terms and the `dateOfBirth` correction).

### F02 — Establish Python foundation and shared contracts

- [x] **Done.** Create packaging/locked dependencies, typed configuration, event/enrichment/
  dialogue schemas and injectable clock, HTTP, bus, store and model boundaries. The
  store boundary must not expose SQLite-specific behaviour to the roles, so a later
  move off the single-writer model is a swap and not a rewrite; commentary language
  and model IDs come from typed configuration with no hardcoded defaults.
- Acceptance/checks: offline tests reject malformed data, missing credentials in
  live mode, wrong session IDs, invalid timestamps and secret-bearing log output.
- Depends on F01.

**Work units:**

- **F02a — Done.** Commits `d831505` (packaging and lock) and `97976d6` (authored
  modules and tests). Files: `pyproject.toml`, `uv.lock`, `.python-version`,
  `src/f1show/__init__.py`,
  `src/f1show/config.py`, `src/f1show/redaction.py`, `tests/conftest.py`,
  `tests/test_config.py`, `tests/test_redaction.py`. 39 offline tests pass
  (`uv run --frozen pytest -q`), `uv lock --check` reports the lock current, and the
  resolved versions are `pydantic 2.14.0`, `pydantic-settings 2.15.0`,
  `google-genai 2.29.0`, `httpx 0.28.1`, `redis 8.1.0`, `pytest 9.1.1` on Python 3.14.4.
- **F02a RED caveat, and how it was closed.** The writer reported honestly that its RED
  was collection-level only (`ModuleNotFoundError: No module named 'f1show.config'`), so
  no test body ever ran against unwritten behaviour and every test passed on its first
  executed run. That is the weakest admissible form of test-first, so the parent mutated
  each of the five validation rules in turn and confirmed that a test fails for each:
  the `latest` rejection, the positive-selector rule, the live-credentials rule, the
  timezone requirement and the redaction filter. **All five mutants were caught**, the
  working tree was restored byte-for-byte (verified by digest), and the suite was green
  afterwards. The tests have teeth; the initial RED did not prove it, and this does.
- **F02a parent fix.** `.gitignore` no longer ignores `.python-version`, which
  contradicted the interpreter pin the same commit introduces; the pin is now committed
  alongside `uv.lock`.
- **F02a disclosures carried forward as review focus.** `mode` defaults to `replay`,
  chosen as the offline-safe default. The session selector accepts numeric strings
  through pydantic's lax coercion, so only the literal `latest` is intercepted; that is
  deliberate for environment-variable configuration and still explicit and
  deterministic. `RedactingFilter` attached to a logger does not see records propagated
  from child loggers, so F03 must decide where it is installed — logger, handler, or
  both.
- **F02b — split into three bounded units**, because the whole unit would exceed the
  native reviewer context budget that already refused the F02a bundle, and because a
  candidate that large loses the authored code to the noise. Each unit is produced,
  reviewed as the working tree, acknowledged, and only then committed.
  - **F02b-1 — shared contracts. Done.** Commit `f792eb3`: `src/f1show/events.py`,
    `src/f1show/enrichment.py`, `src/f1show/dialogue.py`, the three test modules and the
    re-exported package surface — 653 lines across seven files, 76 tests passing. The RED
    was **assertion-level** this time (28 tests failed to raise while 48 passed with the
    fields plain and no validators, against the import-level RED of F02a), and eight
    mutations of the new invariants were each caught with the tree restored
    byte-for-byte. Reviewed natively over exactly those seven files, **approved**;
    authority burned under `gentle-ai.review-acknowledged/v1`.
  - **F02b-2 — injection boundaries. Done.** Commit `c8cdc59`: `src/f1show/ports.py`,
    `src/f1show/fakes.py`, the re-exported surface, the `anyio_backend` fixture and two
    test modules — 661 changed lines, 108 tests passing. Assertion-level RED again
    (25 failed while 7 passed with the protocols declared and the doubles
    unimplemented, zero errors). The author caught and fixed a **spurious pass in one of
    its own tests**, where the assertion was satisfied by pydantic's error text rather
    than by the behaviour, and re-ran the RED honestly. Async tests use anyio's
    already-present pytest plugin, so **no dependency was added and the lock is
    untouched**. Reviewed natively over the six files, **approved**; authority burned.
  - **F02b-2 parent verification, and two coverage gaps it exposed.** Eight mutations
    were run against the new invariants: five bit (cross-group ack isolation, closed
    store, model-request bounds, the storage-engine guard, clock freezing), one was a
    **dead mutation of the parent's own** (mutating a line after the `raise` that fires
    first — corrected and then it bit), one was an **equivalent mutant**
    (`FakeHttpClient` still raises `KeyError`, a `LookupError` subclass, after its
    explicit guard is removed, so the observable contract survives), and one exposed a
    real gap: the bus's acked-set check in `read` only matters for **out-of-order
    acks**, and the existing test acks in order, where the cursor advance already masks
    it. The implementation was verified correct by hand for that case (`['1','3']` after
    acking only `2`), so it is missing coverage, not a defect.
  - **F02b-3 — redaction hardening. Done.** Commit `217aa08`: `src/f1show/redaction.py`
    plus the two test modules, 323 authored changed lines, suite 108 → 120 passing.
    `record.exc_info` is now rendered, redacted, stored on `exc_text` and cleared so the
    formatter cannot re-render the raw traceback; log arguments are walked through
    mappings, lists, tuples, sets and frozensets with path-scoped cycle detection and a
    fail-closed depth cap; bytes secrets match in both decoded and repr form; and
    installation covers the logger **and** its handlers, idempotently. The RED was
    genuine: the previous implementation was restored and the ten new tests failed
    against it. Reviewed natively, **approved**; authority burned.
- **F02b-3 findings, carried into F02b-4.** Both WARNINGs describe the technique's
  inherent trade-off rather than a defect: rendering the traceback inside the filter
  means `formatException` runs for records that may never be emitted, and clearing
  `exc_info` means a consumer that wanted the structured exception object no longer has
  it. Also: container reconstruction via `type(value)(items)` assumes every container
  type is constructible that way, and the depth cap has no test (it was verified by hand
  during triangulation).
- **A pre-existing functional hazard, surfaced by F02b-3 and not a leak.** The filter
  rewrites `record.msg` before `%`-interpolation, so if a registered secret happens to
  be a substring of the format template — a secret equal to a `%(name)s` key, or a
  literal `"s"` colliding with `%s` — interpolation breaks with `KeyError` or
  `ValueError` instead of leaking. It predates F02b-3 and is unchanged by it: the
  failure mode is a crash, which is fail-closed rather than a disclosure, but it is a
  hazard worth a later unit.
  - **F02b-4 — contract and double hardening. Done.** Commit `6381df5`: all fourteen items
    closed across ten files, 226 changed lines, suite 120 → 131 passing. Nine produced an
    assertion-level RED against the previous code and four were coverage-only additions
    that passed immediately, which is stated rather than hidden. Reviewed natively,
    **approved**; authority burned. Everything advisory that is not a leak
    path, grouped because each item is small and only the grouping makes it reviewable.
    Contracts: `Provenance.source_url` accepts an empty string where `None` is meant
    (WARNING); `Turn.model_id` accepts whitespace because it carries no strip validator;
    `SessionRecord.date_start`/`date_end` use a plain `datetime` and so accept a naive
    value from ingestion; the `EventType` docstring claims a consumer must tolerate an
    unknown member while the model rejects unknown members, so either that tolerance is
    implemented at the consumer boundary or the claim is restated as strict here and
    tolerant there; and a `since` later than `until` is not rejected.
    Doubles: `FrozenClock.advance` accepts a negative value and can move time backwards;
    its docstring promises UTC while the fake returns whatever aware offset it was
    given; `InMemoryStore` returns shallow `dict` copies, so a caller could mutate
    stored state through a nested value; and the `close()` test does not cover every
    method. Tests: the bus needs an out-of-order-ack case, and the unregistered-URL test
    should assert the deliberate error rather than a broad `LookupError`, since
    `KeyError` satisfies it. Plus the F02b-3 items above (the two technique trade-offs,
    the container-reconstruction assumption, and the untested depth cap).
    **Every one of these is `informational` in the provider's own classification and
    must not be used to re-run review on any candidate.**

**F02b-1 design decisions (2026-10-09):**

- **Two strictness policies, on purpose.** Internal contracts forbid unknown fields,
  because an unexpected field there is a bug in our own pipeline. Ingested source
  records tolerate unknown fields, because a provider may add fields at any time and a
  pipeline that refuses them would break on a change it cannot control; the fields we
  depend on are still required and validated.
- **Provenance is mandatory and observation time is distinct from event time.** Every
  event carries the endpoint it came from and the moment it was observed, so a record
  can be re-derived and audited later without trusting the event's own timestamp.
- **Schemas cover only observed families.** Only OpenF1's `sessions` and `drivers`
  shapes were observed at F01, so those are the only record models written now. The
  normalized event payload stays explicitly provisional with a documented extension
  point, because the collector that produces it is F04. Inventing the other sixteen
  payloads here would be fabricating contracts.
- **Absence stays absent.** An enrichment record must carry at least one fact, so an
  empty enrichment cannot be emitted as if it were a finding. This is the structural
  form of "unknown records stay absent".
- **Dialogue turns carry non-empty evidence references**, which is the structural
  form of "personas may only use what they are given", and a transcript enforces
  non-decreasing turn order.
- **No new dependencies**, so no lock churn and no generated artifact in the review
  candidate.

**Decisions taken before the first source write (2026-10-09):**

- **Two bounded work units**, because the task as specified exceeds the ~400 authored
  line heuristic as a single unit. **F02a** is the project foundation: packaging, the
  locked dependency set, typed configuration and secret-safe logging, with the
  acceptance tests for configuration validation. **F02b** is the shared contracts and
  the injection boundaries: event/enrichment/dialogue schemas plus clock, HTTP, bus,
  store and model protocols with in-memory fakes. F02a must land first because it
  establishes the package, the lock file and the test harness that F02b builds on.
- **Packaging: `uv` with `pyproject.toml` and a committed `uv.lock`.** Verified working
  on this machine before the task started.
- **Python: system 3.14.4, verified by a real install** — every wheel resolves,
  including a prebuilt `pydantic_core` for cp314, so nothing compiles from source.
  `requires-python = ">=3.12"` with `.python-version` pinned to 3.14; **the declared
  floor is a compatibility claim that F12's CI must actually exercise**, since only
  3.14 was run here.
- **HTTP client: `httpx`, at 0.28.1.** `httpx2` is rejected deliberately: `google-genai`
  pins `httpx>=0.28.1,<1.0.0`, so using `httpx2` would leave `httpx` in the tree
  anyway and give the project two HTTP stacks and two connection pools for one job.
- **Configuration: `pydantic` plus `pydantic-settings`**, since `pydantic` is already a
  hard transitive dependency of `google-genai` and the extra cost is one small package.
- **Test runner: `pytest`, synchronous only in F02.** Every F02 acceptance criterion is
  a synchronous validation test; an async plugin is deferred to F03, where the async
  boundaries first get real implementations.
- **Layout: `src/f1show/`**, so tests import the installed package rather than the
  working directory and no accidental shadowing is possible.
- **Endpoints have documented defaults and are overridable; model IDs and the
  commentary language have NO defaults and must be supplied.** The distinction is the
  point: an unset model ID or language is a configuration error, never a silent
  fallback to whatever the SDK or a hardcoded string happens to offer.
- **`latest` is rejected as a session selector in replay mode.** OpenF1 documents it
  as a live convenience; in a replay it would silently make a run non-deterministic.
  Replay session selectors must be explicit positive integers.
- **Timestamps must be timezone-aware.** Naive datetimes are rejected at the boundary,
  which is the direct antidote to the inconsistent-timestamp defect found in the
  original corpus.
- **Deliberately not included:** a linter or formatter. The plan does not ask for one
  and adding tool config is not this task's scope; revisit at F12 when CI lands.
- **Native review.** The first attempt over the whole unit was refused by the
  controller with `lens_context_budget_exceeded`: the candidate's reviewer evidence
  exceeded the native context budget, **no review authority was created**, and the
  refused attempt is safe to retry or replace. The unit was therefore delivered as a
  chain — packaging and lock committed first, authored modules reviewed separately —
  because a generated 824-line lock file must not crowd the code out of review
  attention. The reviewed candidate was the six authored files (`src/f1show/*` and
  `tests/*`, 758 lines) at lineage `review-41562a9623e79220`, **medium** tier, one
  consolidated `review-reliability` lens. Outcome: **approved**, authority burned under
  `gentle-ai.review-acknowledged/v1`.
- **Five review findings, all non-blocking, recorded as follow-ups — not corrections.**
  The provider classified every one as `informational`; none opened a correction and
  none reopens this candidate, so they must **not** be treated as a reason to re-run
  review on it. Two are WARNING severity and bite the acceptance criterion directly,
  because both are paths where a secret can still reach a log sink:
  `R3-redaction-exc-info-leak` (`src/f1show/redaction.py:92-93` — only `exc_text` is
  redacted, not `exc_info`, so a secret inside an exception message can still be
  rendered by a formatter) and `R3-redaction-nested-args-leak`
  (`src/f1show/redaction.py:96-101` — `_redact_value` handles `str`, `list` and `tuple`
  but not a container nested inside them). Three are SUGGESTION severity:
  `R3-bytes-secret-mangled` (`redaction.py:22-29`, bytes secrets are stringified rather
  than matched), `R3-empty-credential-path-untested` (`config.py:124-129`, the
  empty-string-is-missing path has no test) and `R3-window-no-ordering-check`
  (`config.py:132-136`, a `since` later than `until` is not rejected). **F02b must close
  the two WARNING findings, and the redaction-installation question the writer raised,
  before F08 logs real provider traffic** — secret-bearing log output is an explicit F02
  acceptance criterion and these are its remaining holes.
- **F02 is complete.** F02a, F02b-1, F02b-2, F02b-3 and F02b-4 are all closed and
  natively reviewed. Depends on F01 (closed).
- **Two carried advisories from the F02b-4 review**, both `informational`, registered
  rather than fixed because another review cycle costs more than they are worth, and
  neither reopens that candidate: `Provenance.source_url` rejects the empty string but
  still accepts a whitespace-only one — the same strictness gap just closed for
  `Turn.model_id` — and the fail-closed container reconstruction uses a broad
  `except Exception`, which is deliberate because it fails toward *more* redaction, but
  would also swallow an unrelated error raised while rebuilding a container. Close both
  if either file is touched again.
- **Next: F03**, explicitly authorized after F02 publication. It writes real data
  paths: the SQLite WAL store behind the `Store` port, immutable Parquet session
  snapshots and the `sync` writer with historical and injectable live adapters.

### F03 — Implement source adapters and replay/session lifecycle

- [ ] Build the sync writer's source adapters, the SQLite WAL store with Parquet
  snapshot export, deterministic replay and explicit session selection; seed mid-session
  state and handle end/cancel/reset without mixing sessions.
- Acceptance/checks: fake HTTP/clock tests cover history vs live auth, timeouts,
  429/backoff, empty data, invalid responses and per-endpoint watermarks/overlap.
- Depends on F02 (closed).

**Work units, planned before the first source write (2026-10-09):**

- **F03a — the SQLite store behind the `Store` port. Done** (commits `6df4def` and
`318bec9`; suite 131 → 151). Schema for source records and
  watermarks, create-if-absent, WAL mode, upsert semantics that deduplicate by family,
  session and record identity, deterministic read windows by observation time, and
  `close()`. Tests run against a real temporary database, fully offline. A store-path
  setting joins the typed configuration, with the same rule as elsewhere: a documented
  default for the path, no default for anything that identifies a model or a secret.
  The port's contract is fixed already, so this unit must satisfy it rather than reshape
  it — a test asserts the implementation is substitutable for the in-memory double.
- **F03b — Parquet snapshots and deterministic replay. Done.** Dependency commit
  `2165b64` pins DuckDB 1.5.6; behavior commit `6d3a907` exports per-session Parquet,
  returns a SHA-256, refuses unintended overwrite and provides deterministic replay
  with explicit session selection. `Store.read_source_records` now returns
  `(observed_at, record)` pairs in both implementations, retaining inclusive windows;
  the shared parity body proves the time channel. Seeding partitions retained rows by
  observation time, **not full historical positions/stints/lap reconstruction**: upserts
  keep the latest row per identity, and endpoint-specific derivation belongs to F04.
  Writer RED: 21 failed, 30 passed, no collection errors; GREEN: 164 full-suite tests,
  51 focused. Three parent time-channel mutations were caught, with byte-exact
  restoration and 164 passing afterwards. Native review `review-355e17c45ef3ad37`
  accepted the complete 772-line, ten-file candidate at medium risk; approved and
  acknowledged, authority burned. Its four informational findings do not reopen it.
- **F03b-1 — Snapshot publication and replay boundary hardening. Done.** Commit
  `3ec02ea4ea670baa764e27f727061c5fe1739ef5`, published on the feature branch. New,
  separately authorized work unit for those four findings: atomic same-directory
  publication without unintended overwrite; reject an empty family declaration;
  align UTC boundary validation; prove mixed-session refusal. Route: delegated explorer
  (multi-module mapping), one delegated writer (multiple non-trivial files), delegated
  independent verification spot check. Forecast: about 200–400 authored diff lines
  for the complete follow-up versus `6d3a907`, not the correction delta or file lengths;
  retain useful tests/docs even if that advisory estimate is exceeded.
  - Explorer `mv1d5odw-g-yzn3` confirmed a direct-to-target COPY failure hazard plus a
    check-then-write overwrite race. Mixed-session refusal already works and needs
    coverage only. Naive UTC in the Parquet TIMESTAMP versus aware UTC in replay is
    intentional; share validation in a small internal helper, retaining explicit
    conversion at the Parquet boundary. Do not refactor store/fakes/config in this unit.
  - Edit surfaces: `src/f1show/snapshot.py`, `src/f1show/replay.py`, new
    `src/f1show/_time.py`, `tests/test_snapshot.py`, `tests/test_replay.py`.
  - Acceptance: failed/cancelled export leaves no partial target; failed explicit
    overwrite preserves previous bytes; a competing publisher is not overwritten
    without permission; handled failures clean staging files. Atomic visibility is
    required, not an unverified power-loss durability guarantee.
  - Reject `families=()` before filesystem mutation; timestamp boundaries must reject
    naive/invalid aware datetimes and compare equivalent offset instants consistently;
    a mixed-session Parquet file is refused, not filtered into apparent validity.
  - Preserve byte-identical exports, observation-time partitioning, deterministic
    tie-breaks, deep-copy behavior and existing session/overwrite rules. Distinguish
    genuine RED from coverage-only tests that pass against the baseline.
  - Writer `mv1dbgol-h-sd84` returned five allowed files, **605 authored diff lines**
    (509 additions + 54 deletions tracked, plus 42 new helper lines); the estimate was
    exceeded by failure/race/UTC tests, not scope expansion or cosmetic compression.
    Reported RED: snapshot 8 failures and replay 1, zero collection errors; coverage-only
    passes named separately. Reported GREEN/refactor: focused 29, full 180 tests. It also
    fixed DuckDB's empty `executemany` rejection so declared zero-row families can export.
  - Verifier `mv1dmx4o-i-0b51` independently passed focused 29/full 180 and corroborated
    race/failure/UTC/session tests, but **failed acceptance**: cleanup-only unlink errors
    are silently swallowed because `sys.exc_info()` inside `except OSError` sees that
    cleanup error, not the caller's prior state. It also found staging-path ownership
    lost if `os.close` fails before `_staging_path` returns. No closure is claimed.
  - [x] **F03b-1-R1 — Correct cleanup exception context and staging ownership.** Continue
    the same writer, narrowed to `snapshot.py` and `tests/test_snapshot.py`; add genuine
    RED for cleanup-only failure and initial-close failure, preserve any primary export
    failure, and do not blindly retry a possibly closed descriptor. Document unavoidable
    cleanup failures and a completed target remaining valid if post-publication cleanup
    fails. Independent revalidation must pass before native freeze and commit.
    Writer follow-up `mv1dsbab-j-n1ui` reported three assertion-level RED failures,
    then focused 34/full 185 passing. Explicit per-call primary capture avoids both
    cleanup-handler and already-handling-caller contamination; secondary unlink errors
    are noted on the preserved primary. Initial-close failure removes the owned name
    without unsafe close retry. Caller-contamination mutation was caught and source
    SHA-256 restored byte-exactly. Complete candidate is **774 authored diff lines**
    (679 additions + 53 deletions tracked, plus 42 helper lines); independent verifier
    follow-up `mv1dz637-k-8da5` settled: focused 34/full 185 passed; the independent
    probe now surfaces cleanup-only errors and preserves/notates the primary object.
    It confirmed initial-close ownership recovery and all non-regression checks.
    R1 closed with the unit's observed native approval/acknowledgement and `3ec02ea`.
  - Native assessment remained unassessable for the untracked helper and returned mandatory
    independent verification (high-risk fallback); that plan is fulfilled by the verifier's
    observed 34/185 tests and cleanup probe, not by a native approval claim.
  - [x] **F03b-1-RDD — Fresh native review and exact acknowledgement.** Previous two
    consent expiries created no authority and were never replayed. On the user's return,
    fresh consent created `review-202a61df64e578a0`: medium risk, all five intended paths,
    774 authored diff lines. First reviewer produced no text (`stopReason: length`);
    fresh bound STATUS reoffered the exact slot, and one forecasted retry approved.
    Exact acknowledgement returned **authority burned**; no STATUS followed the burn.
    The staged Git tree matched reviewed tree `7b9a8616bc1c8389920f4b0bcd96bda7cc11ab9b`
    exactly before the source/test commit. No correction transition was offered.
  - [x] **F03b-1-PUB — Authorized feature-branch publication.** Normal push published
    `3ec02ea` on `origin/feat/f03-source-adapters`; independent `git ls-remote` matched
    the local SHA. Local and remote `main` remained `fc30084` before/after. No force-push,
    PR or merge. Final task-closure metadata follows under this same delivery grant.
  - **Five new informational advisories**, all non-blocking and not reasons to reopen
    this approved review: `R3-addnote-floor` (`snapshot.py:183`, SUGGESTION),
    `R3-global-close-patch` (`tests/test_snapshot.py:575-579`, WARNING),
    `R3-hash-memory` (`snapshot.py:280`, SUGGESTION),
    `R3-staging-suffix-drift` (`tests/test_snapshot.py:91`, SUGGESTION),
    `R3-writer-instant-coverage` (`snapshot.py:239`, SUGGESTION). Registered for later
    scoped work; none was silently fixed outside the reviewed candidate.
  - Authorized findings: `R3-nonatomic-snapshot-write` (`snapshot.py:120-145`, WARNING),
    `R3-empty-families-silent-fixture` (`snapshot.py:96-101`, SUGGESTION),
    `R3-duplicate-utc-helper-divergent` (`replay.py:38-44`, SUGGESTION),
    `R3-mixed-session-refusal-unproved` (`replay.py:72-77`, SUGGESTION).
- **F03c — Historical sync. Authorized and in progress.** User: "ok, pasemos a F03c".
  Baseline `e7247b7`, 185 tests. Explorer `mv1hctp2-l-sfku` mapped ports/ownership.
  Public docs were consulted, not data APIs: `https://openf1.org/docs`, `/auth`, and
  HTTPX 0.28.1 first-party docs. No OpenF1 pagination contract was found; use supported
  filters, never invented `limit/offset`. Observation checkpoints are **not source date
  cursors**. Static families resume by re-query/upsert; no fake date filtering from
  `Clock.now()`. Source models currently cover sessions/drivers only; any extension
  needs an explicit, evidenced family adapter. No cross-family atomicity is promised.
  Four bounded units, planned before source writes; roughly 1,450–2,250 authored diff
  lines total, split by behavior, not a hard limit. Existing auto-chain/feature-branch
  strategy applies; **no F03c push was authorized by the original planning grant**.
  The later F03c-1/F03c-2 publication grant and proof are recorded below; F03c-3 publication
  remains separately gated. One writer; tests-first offline.
  - **F03c-1 — HTTP response/adapter. Done, reviewed and locally committed.**
    Independent verifier `mv1ir20g-n-ov7w`: 86 focused/233 full tests PASS, but FAIL on
    primary-error masking, raw cleanup-only errors and unbounded close after deadline/
    cancel (`http.py:146-148`). Existing tests used no-op close. Native review not started.
    Machine-counted candidate: 1,016 additions +17 deletions = **1,033 diff lines**
    (forecast 450–650 exceeded; seven planned paths, tests retained). ASSESS remains
    unassessable for undeclared new files: high-risk fallback. Static checks unverified.
    **F03c-1-R1 implemented; independent reverification in flight, not accepted.**
    Writer `mv1j7w77-o-lggk` reports RED 9 failed/37 passed, then 95 focused/242 full
    (baseline 185). User shell independently re-ran the focused file: 46 passed, and
    `-k close` 9 passed/deselected 37 — user-run evidence, not independent verification.
    Pinned candidate at HEAD `0b8cb9f`, empty index, seven paths: 1,430 additions +17
    deletions = **1,447 diff lines** (2.23× the 450–650 forecast; overage accepted by the
    parent, tests not trimmed). `http.py` 343 and `test_http.py` 766; sha256 pinned:
    `http.py:e49fe5d1…`, `test_http.py:b105dde7…`. Verifier `mv1tlpc8-s-3yux` re-probes
    the four original failures, measures the real `timeout_seconds + min(timeout,1s)`
    bound, attacks the `is_closed` reclassification heuristic in both false-positive and
    false-negative directions, and mutation-tests the 9 regressions on a `/tmp` copy with
    proof of the imported module path. Static checks remain unverified (no ruff/mypy).
    **Independent reverification `mv1tlpc8-s-3yux`: 7 of 8 criteria PASS, one proven
    contract defect; NOT accepted.** Re-ran 95 focused/242 full (baseline 185) and
    `-k close` 9/37 on the pinned bytes, and reproduced the four original failures as
    fixed. Measured the real bound: stalled read plus stalled close returned in 0.602s at
    timeout 0.3 (`timeout_seconds + min(timeout,1s)`, no hidden wait beyond that); a
    synchronous closer took 1.000s at timeout 0.2 and is an honest, documented,
    unboundable case. Sanitization held (`_target` strips query and userinfo). External
    cancel: done + cancelled, no lingering task, and no `create_task`/`ensure_future`
    anywhere in `src`. The `is_closed` heuristic survived a two-directional attack
    (`is_closed` is True when httpx awaits `stream.aclose()` after EOF) with no
    reproducible false positive or negative. Mutation testing on a `/tmp` copy with the
    imported module path proven: allowance cap → 1 failed, reclassification → 2 failed,
    `add_note` dropped → 2 failed, so the 9 close cases assert behavior, not internals.
    **Proven defect, in scope:** a custom injected transport raising a NON-httpx
    exception mid-read with the response still open escapes `get_json` raw and untyped,
    contradicting the module docstring. Real httpx transports raise `httpx.*` and are
    typed correctly, so reachability is narrow — but the adapter accepts an injected
    transport by design, and F03c-2's retry policy must classify typed errors. Corrective
    **F03c-1-R2** normalizes only transport-origin exceptions from the send and the
    streamed body read, keeps `HttpDecodeError` for our own parse failures so an internal
    bug is never masked, keeps cancellation propagating, and states the contract
    precisely. Re-verification on the new bytes is required before acceptance.
    Re-pinned: the candidate is measured against HEAD `b592ae5` (docs-only concurrent
    commit); the seven source bytes are unchanged by it.
    **F03c-1-R2 implemented; re-verification in flight, still not accepted.** Writer
    `mv1tz6c2-t-m8eu` normalized foreign transport exceptions at exactly two loci —
    `_send` and the streamed read in `_read_bounded` — through
    `_is_foreign_transport_failure`, which excludes `HttpError`, `httpx.HTTPError`,
    `TimeoutError` and cancellation. That keeps the size and decode errors from being
    re-wrapped and lets `KeyboardInterrupt`/`SystemExit` propagate raw. Close-failure
    detection runs before normalization and the close helpers and bounds are byte-identical.
    RED 2 failed/5 passed with the predicate forced False, then GREEN 100 focused/247 full;
    three of the five new tests are disclosed coverage-only over-wrapping guards. One
    previously verified R1 test was ADAPTED because it encoded the raw escape; parent
    structural readback confirms it still asserts cause identity, no message or note leak
    and type-only annotation, and the mutation round must prove the guarantee survived.
    Whole candidate is now +1606/−17 = **1,623 diff lines** against `b592ae5`. Static
    checks remain unverified except two cleared pi-lens I001 findings.
    **R2 independently re-verified: PASS on every criterion, no open defect.** Verifier
    `mv1ujie7-u-cl34` recomputed +1606/−17 = 1,623; focused 100 / full 247; the prior probe
    set held (worst case 0.602 s at timeout 0.3; sync closer 1.000 s documented; no
    `create_task` in `src`). The new normalization passed a raw-vs-typed matrix in both
    directions: foreign send and read errors become typed with the cause preserved, malformed
    JSON stays `HttpDecodeError`, an over-bound body stays `HttpResponseTooLargeError`, the
    privileged base exceptions propagate raw, and close detection demonstrably precedes
    normalization. Five mutations of the new machinery were all caught (predicate disabled,
    cause chain dropped, allowance cap removed, reclassification disabled, note dropped), and
    the adapted test retained every R1 guarantee. Ruff is genuinely unavailable on this
    machine, so the I001 formatting claim is the one item that stays unverified.
    **Native review approved and burned.** A plain START created lineage
    `review-28a0fc5740cbe93d` (medium, seven files, 1,623 lines, one lens
    `review-reliability`, correction budget 200). Lesson recorded: passing `lineageId` to a
    NEW ordinary START projected only the five tracked files and its consent binding expired;
    `lineageId` belongs to status/advance, not to a fresh start. Forecast: one model run over
    `pi_host_relay`. The first reviewer run failed `pi-host-relay-transport-failure` /
    `reviewer-empty-output` (`stopReason: length`, 604 s, no mutation, no findings); fresh
    STATUS reoffered the same slot, and the retry closed `approved`. Acknowledgement burned
    authority: consumed revision `sha256:feea4e3e…`, `burn_evidence
    gentle-ai.review-acknowledged/v1`, delivery under ordinary repository policy. No STATUS
    was issued after the burn.
    **Committed as `32a55aa7949a38408163618772922b5ae2115aca`.** `git write-tree` before the
    commit and the commit tree both equal the reviewed tree
    `9b92cacdbaa82880722385cba752654897150a97`, so the reviewed bytes are exactly the
    committed bytes: seven files, +1606/−17. Not pushed.
    Three informational advisories carried as separate later work, none blocking and none
    reopening this review; the closure envelope named them without descriptions:
    `R3-001` (`src/f1show/http.py:286-293`, WARNING), `R3-002` (`src/f1show/fakes.py:81-85`,
    SUGGESTION), `R3-003` (`src/f1show/http.py:186-190`, SUGGESTION).
    Grow the single `get_json` contract to a typed status/headers/payload response;
    migrate the fake, add scripted outcomes,
    an owned httpx adapter and shared parity tests. Clock stays unchanged. Scope:
    `src/f1show/{ports,fakes,http,__init__}.py`, `tests/test_{http,fakes,ports}.py`.
    Estimate 450–650 diff lines; verify hard timeout, bounded JSON body, status/header
    visibility, malformed success vs non-JSON error response, no implicit credentials,
    deep-copy parity and idempotent close. No retry implementation in this unit.
  - **F03c-2 — Pacing/retries. Done, reviewed and locally committed.**
    User explicitly authorized: "ok, continua con F03c-2". Existing plan and allowed
    surfaces preceded source writes; no new dependency, config wiring or live calls.
    Separate `MonotonicClock.monotonic()/sleep()` from UTC `Clock.now()`: the shared
    `RateLimiter` owns one monotonic source for pacing and backoff; UTC is used only
    to derive a duration from an HTTP-date `Retry-After`.
    `PacingPolicy` defaults to 3/second and 30/minute with both rolling windows enforced
    globally across endpoints. `RetryPolicy`: three total attempts including the first,
    exponential backoff 0.5s capped at 8s, no jitter, admitted retry wait at most 60s;
    statuses 408/429/500/502/503/504 and typed transport/timeout errors are retryable.
    Every attempt must pass the limiter. Retry waits take the maximum of backoff and
    valid server advice; invalid advice falls back to backoff, and over-budget advice
    never causes an early retry. Exhausted/over-budget statuses return the last response;
    exhausted/over-budget transport errors re-raise. Decode, size and cancellation never
    retry. Wrapper close delegates once and refuses requests after closure.
    Seven narrow surfaces: `src/f1show/{ports,fakes,request_policy,__init__}.py` and
    `tests/test_{request_policy,fakes,ports}.py`; the reviewed `http.py` is untouched.
    Writer `mv2eorwl-v-pave` reported **115 focused/313 full tests**, baseline 247;
    claimed RED was an import/collection error, **not an observed behavioral RED**.
    Coverage-only validation variants were disclosed; no retrospective TDD claim is made.
    Whole candidate reported **924 additions +3 deletions = 927 diff lines** versus
    `4dc1e9e`, including both new files (304 policy/515 test lines). Original 350–550
    estimate exceeded by the required test matrix; tests must not be trimmed to fit it.
    ASSESS is unassessable until new files are declared natively; its returned high-risk
    fallback requires independent command-running verification before acceptance.
    **Independent verifier `mv2f7w1r-w-x88s`: FAIL on two proven defects.** Observed
    focused 115/full 313, +924/−3 = 927, all eight source pins unchanged and index empty.
    Both rolling windows (half-open intervals), shared/concurrent endpoint budgets,
    early-wake recomputation, cancellation, response/error identity and fake/adapter parity
    passed. Six isolated mutations were killed; they are efficacy evidence, not historical RED.
    D1: RFC-valid delay-seconds with 309+ digits overflows `float()` to infinity, becomes
    absent advice and retries after 0.5s instead of returning the over-budget response
    (`request_policy.py:293-294`; `/tmp/f03c2_probe/probe1_retry_after.py`).
    D2: multiplying by `2**(failed_attempt-1)` before capping raises `OverflowError` at
    failed attempt 1025 with max_attempts 1100, replacing the promised typed transport
    error (`request_policy.py:263`; `/tmp/f03c2_probe/probe3_retries.py`).
    - [x] **F03c-2-R1 — Preserve huge server advice and cap exponential arithmetic safely.**
      Independent functional verification, native closure and exact-byte unit commit observed.
      Continue one bounded writer on only `src/f1show/request_policy.py` and
      `tests/test_request_policy.py`. First add regressions and observe actual assertion/
      operation failures on the current defective bytes; collection failure is not RED.
      Valid integer server advice must never become absent through overflow or Python's
      integer-string digit limit; include long leading-zero and all-zero forms. Backoff
      must reach its existing cap without first evaluating an overflowing exponential.
      Preserve existing defaults, status-as-data, exception identity, cancellation, both
      windows and parity; do not trim tests or fix unrelated advisories. Reverify the new
      bytes independently before fresh native inspect/START/acknowledgement/local commit.
    **R1 writer `mv2fui68-x-uccu` returned only the two permitted paths.** New regressions
    first ran against the defective source: **7 failed/5 passed**, zero collection errors;
    four huge-advice assertions and three high-attempt overflow operations are genuine RED.
    Five already-passing parser guards are coverage-only. Corrective set then passed 12;
    reported GREEN **127 focused/325 full**, baseline 313. The original R0 TDD gap remains.
    ASCII integer advice strips leading zeros and uses significant-digit admission before
    conversion, with infinity denoting over-budget rather than absent advice; invalid
    numeric extensions and HTTP-date paths remain unchanged. Backoff doubles only until
    the existing cap, without unbounded exponentiation or restricting `max_attempts`.
    Writer reran the original D1/D2 probes: huge advice returned 429/one call/no sleeps,
    and 1100 transport failures raised the original typed error instead of OverflowError.
    Parent re-pinned the complete candidate: **1139 additions +3 deletions = 1142 diff
    lines**, policy 343/test 691 lines, other five source paths and reviewed `http.py`
    unchanged. New SHA256 pins: policy `6c35023e57c4ef0030da0085011a7050e3135fce3f82517d515faf03e0e9eeb9`,
    test `4cbf717abe1912ac0d1086a832acf87641319c38175122d77fb28c36eff33160`.
    Parent active LSP on the two R1 paths reported no primary findings and three auxiliary
    numeric-parse/typo findings, not an all-checks-clean claim. Ruff/mypy remain unavailable
    to the child; no static tools installed. Fresh ASSESS still returned unassessable for
    untracked files and the exact high-risk independent-verifier plan.
    **Independent R1 reverification `mv2g6blq-y-uepo`: PASS, no proven defect.** Observed
    focused 127/full 325, +1139/−3 = 1142 and all eight pre/post pins unchanged; the
    independent-verifier fallback is fulfilled, not a native approval substitute.
    Original D1/D2 probes now preserve server advice, response/error identity and the cap:
    309/400/5000-digit advice returns 429/one call/no wait; 1100 retries reach the last
    503 or original typed error, no post-exhaustion sleep. Long zeros, exact/fractional
    budgets, dates, extreme finite/subnormal bases/caps and existing windows/concurrency/
    cancellation/parity all passed. Original RED logs corroborate 7 failed/5 passed with
    zero collection errors; a faithful old-parser mutant recreates four failures and an
    old-pow mutant recreates three. Five final mutants killed, including minute-window,
    retry-pacing and min-advice controls. A first incomplete old-parser mutant survived;
    it omitted the defective non-finite-to-absent branch and was excluded, not hidden.
    A pathological `10**5000` configured ceiling raises OverflowError during validation;
    no specific rejection type is promised and it never reaches retry operations. Retain
    as an edge observation, not a new corrective scope. Native review/acknowledgement and
    source commit remain pending; no F03c-2 lineage started or source staged.
    Child static tools were unavailable, but a parent active LSP probe covered all seven
    changed paths: four primary findings (pre-existing root `SnapshotResult` export warning
    and three errors in untouched fake tests), plus auxiliary Protocol-ellipsis/numeric-
    parse/typo findings. This is not a clean static result; no tools were installed.
    `SnapshotResult` missing from root imports is pre-existing at HEAD and HEAD~1 and
    stays a separate follow-up. Concurrent close-vs-wait semantics remain unspecified;
    neither observation silently expands this corrective unit.
    **Native review approved and exactly acknowledged; authority burned.** Fresh inspect
    selected both new files; plain ordinary START created `review-23515ec290540af0`
    (medium, seven files, 1142 lines, one `review-reliability` lens, correction budget 200).
    Forecast of one model run over `pi_host_relay` was relayed before capture. The first
    run prepared/submitted one reviewer and closed approved; no retry/correction needed.
    Fresh bound STATUS offered the exact acknowledgement; its returned envelope consumed
    revision `sha256:407096f0481044d71031c2c52742a7d561d1d5f1603ba5834340976963ad3731`,
    authority `burned`, evidence `gentle-ai.review-acknowledged/v1`. No STATUS after burn.
    **Source unit committed as `badfa5421153d04f4c27cf0d3a9b86c8d2f03386`**, message
    `feat(http): add global pacing and bounded retry`. Reviewed tree, staged `git write-tree`
    and committed tree all exactly `d4f44ce8dbd085316e1b74eb68d6452e1cdea13f`; seven files,
    +1139/−3. Post-commit worktree clean. No push, PR, merge or main update.
    Three informational native suggestions, descriptions absent from the closure envelope,
    registered for separate later work and never reasons to reopen this approved candidate:
    `R3-1` (`request_policy.py:109-122`), `R3-2` (`fakes.py:63-71`),
    `R3-3` (`request_policy.py:314-322`), all SUGGESTION/non-blocking.
  - [x] **F03c-PUB — Publish the reviewed HTTP/pacing advance.** Explicit user grant on
    2026-10-10. Normal push advanced remote `feat/f03-source-adapters` from `e7247b7`
    to `3f52c33889dd02ab63eecfce1880a0cc8f448fb5`, 14 commits. Parent required expected
    root/branch/HEAD/origin, clean worktree/index and remote ancestor; before/after
    `git ls-remote` matched the intended tip and proved remote main stayed `fc30084`.
    No force-push, main update, PR or merge. Evidence: `/tmp/f1show_push_f03c_refs_before.txt`
    and `/tmp/f1show_push_f03c_refs_after.txt`. Future source publication is a new decision.
  - [x] **F03c-2-ADVICE — Read-only registered-region review completed, with a limit.**
    Complete explorer handoff `mv2hming-10-u3ah` found no reviewer RESULT bodies in the
    inspected clone artifacts: only old candidate data and terminal-consumption receipts;
    repo references contain the same name-only IDs. Original native intent remains
    unverified outside this local scope. The following are independent code observations,
    **not reconstructed native messages**: `RetryPolicy` admits any positive retry status
    integer (defaults valid; low-risk follow-up), the monotonic fake models exact waits
    rather than early wakes (limiter recomputation already independently verified), and
    date/float advice paths remain consistent with downstream wait caps (existing coverage).
    None is required for F03c-3. No fixes, authority STATUS or reopened review.
  - **F03c-3 — Ingest/checkpoints. Authorized; split into two cohesive work units.**
    User explicitly requested continuation on 2026-10-10 after publication/advisory review.
    Scout mapped only evidenced `SessionRecord`/`DriverRecord`, source identities and
    per-batch atomic Store writes with separate watermarks. A single whole-unit 350–550
    estimate was understated (scout 650–830); preserve tests and split by behavior.
     - [x] **F03c-3a — Single-endpoint validation, persistence and observation checkpoint.**
      Closed locally: independent PASS, native approval/burn and exact-tree source commit.
      Source `aca17e2b81eb9589ae97970d93f5fe869be1b473`, Conventional Commit
      `feat(ingest): add endpoint ingestion and observation checkpoints`, 3 paths +864/−1.
      Reviewed = staged = committed tree `2e33953b9d5dea2945a478b53535cdc0e0db3ad6`;
      all three source hashes checked before staging; clean worktree after commit, no push.
      Native `review-aed203157651fcdd`, medium/reliability/865 lines/budget 200, approved
      on the first reviewer run; exact bound STATUS/ack returned authority **burned**.
      Consumed revision `sha256:e148770b3e1ba63ca8517632e8f019f09455739146f91e96cd994927ae018a13`;
      burn evidence `gentle-ai.review-acknowledged/v1`; never query/reopen this lineage.
      Informational advisories (bodies absent; do not infer/fix): R3-001 ingest.py:126-128,
      R3-002 ingest.py:218-225, R3-003 test_ingest.py:520. Approval stands; later scope only.
      Writer `mv2i885h-11-842l` reports scaffold assertion RED 33 failed/0 passed, zero
      collection errors; GREEN/refactor 33, focused 48/full 358 (baseline 325). A large
      shared parity body stops at its first RED assertion, so all tests failing does not
      prove every later assertion/variant was exercised; verifier must distinguish this.
      Original candidate 858 additions +1 deletion = 859 exceeded the 450–650 forecast.
      Follow-up `mv2it6uo-12-wb8x` added only six explanatory lines and three argument-line
      `pyright: ignore[reportArgumentType]` directives, preserving inputs/assertions/types.
      Parent confirmed AST equality (69,113 characters) against the preannotation copy,
      empty index, three paths, **864 additions +1 deletion = 865** total diff lines
      (module 266/test 595; exports +3/−1), source and root pins unchanged.
      SHA256: ingest `d86b48ff5151324258088404cfb566878a7269b4759c4f2f444b3d5d170513c9`,
      test `e50229ea765f9159997bb879ed96e283406ed834a1726cb116e4d8129606b66b`.
      Independent `mv2jke8c-13-znju` **PASS**: 48 focused/358 full on Python 3.14.4;
      exact scope/pins/index unchanged before/after; control2 39 passed (33 + proof + 6 probes).
      Nine isolated semantic mutant runs: **8/8 viable assertion-killed**, zero collection
      errors; one equivalent claimed-ID mutant excluded because model `extra="ignore"`
      removes `record_id` before projection. A viable driver-ID prefix mutant was killed.
      Other killed changes: mixed-session acceptance, first-row-only validation, checkpoint
      before write, second Clock read, skipped empty checkpoint, swallowed cancellation,
      zero rather than unknown write-failure count. Same-process import proof recorded.
      **Probes only, not shipped CI tests:** empty checkpoint from a distinct prior stamp,
      checkpoint-await cancellation, direct-await KI/SystemExit, no-prior-watermark write
      failure, drivers input immutability/mixed-session refusal. No concurrent/crash proof.
      Direct await establishes process-control propagation at ingestion; nested-task cancel
      observations do not prove KI conversion or ingestion swallowing. No historical RED added.
      Logs: `/tmp/f03c3a_verify/{focused,full,control2}.log`, `mut_*/result.log` and probes.
      Parent active LSP: no new primary errors; base `SnapshotResult` warning/NED typo carried.
      Ruff 0.16.3/harness config: new module/test clean; root I001 reproduced at HEAD.
      Exact worker Pyright 3.12 command **with CLI `-t` typeshed** corroborated: test 0/0.
      Its no-venv config on all three files has one unresolved pydantic import + base warning;
      dependency-aware verifier config (venv/3.13/explicit typeshed) gives 0 errors/base warning.
      Omitting `-t` caused resolution artifacts, not proof 3.12/Pyright unsupported. No project
      lint config added; declared Python 3.12 runtime floor remains untested.
      ASSESS was unassessable for new files; mandatory independent high-risk path completed.
      Native/exact-byte local closure is recorded above. Accepted F03c-3a, not all F03c;
      probes-only CI gaps/base warnings remain disclosed and source publication ungranted.
      Surfaces: new `src/f1show/ingest.py`, new `tests/test_ingest.py`, additive exports only
      in `src/f1show/__init__.py`. Other source/tests/config/ports/fakes remain untouched.
      Public `ingest_endpoint(store, clock, *, endpoint, session_key, payload)` supports
      canonical `sessions`/`drivers` only, derives family/record IDs, validates the complete
      list through existing models and refuses any other session before mutations.
      Use existing model JSON projection (`extra="ignore"`); no lossless raw-archive or
      F04 event-normalization promise. Valid `[]` is an empty successful observation,
      not a missing-session failure; null/non-list/invalid/mixed-session batches fail.
      Capture one aware UTC observation stamp for valid batches, write records before
      watermark with the same stamp, never derive provider filters from that checkpoint.
      `EndpointOutcome`: ok/empty/failed, explicit failure stage and safe exception type,
      checkpoint-written flag, optional timestamp/count when unknown. Checkpoint failure
      retains the acknowledged record count and leaves the checkpoint false; write failure
      does not pretend a known zero persisted count. No false aggregate-success flag.
      Caller owns Store; no close/delete/new transaction API. Cancellation/process-control
      exceptions propagate. Repeat after failed checkpoint re-upserts idempotently.
      Checks: genuine behavior RED after collection-compatible scaffold (collection failure
      recorded separately), shared fake/SQLite parity, whole-batch/session refusal, empty
      checkpoint, write/checkpoint faults, repeat/ownership/UTC/cancellation and full suite.
      Forecast 450–650 total diff lines including tests/exports; retain meaningful evidence.
      Independent/native checks and local source work-unit commit complete, not published.
    - [x] **F03c-3b — Fixed sessions/drivers HTTP composition. Closed locally.**
      Source `d4e1bc4186b5401454413c39abc3b0ac905df143`, Conventional Commit
      `feat(ingest): compose fixed session endpoint sync over HTTP`, 3 paths +831/−7 = 838.
      Reviewed = staged = committed tree `097f3bf7f7e6aaef71f10597c6f8718a2123c20a`;
      all three source hashes checked before staging; clean worktree after commit, no push.
      Native `review-af79c3ab0d550c27`, medium/reliability/838 lines/budget 200, approved on
      the first reviewer run after one pre-lineage consent expiry (that attempt created no
      lineage, attempted no invocation and mutated nothing; the exact provider follow-up was
      a fresh START, never a replayed binding).
      Exact bound STATUS/ack returned authority **burned**; consumed revision
      `sha256:551a025b0be6edf7a6a6635ae2edc16632a923363c9f094adfa8dbd5ac8a69b5`;
      burn evidence `gentle-ai.review-acknowledged/v1`; never query this lineage again.
      Informational advisories (bodies absent; do not infer/fix): `R3-empty-base-url`
      ingest.py:329, `R3-fetch-catch-breadth` ingest.py:336-342. Approval stands.
      Writer `mv2le0ri-15-l6k5` returned implementation, not acceptance. Parent confirms
      three modified tracked paths, empty index and HEAD `faa116c4`, protected files unchanged.
      Candidate **831 additions +7 deletions = 838** total diff lines: source +107/−2,
      tests +722/−3, exports +2/−2. Above 300–450 forecast by 388 at the upper bound;
      parity/transport/error/partial/cancel matrix and test-local helpers retained, no new area.
      Actual combined 3a/3b authored size is 1703, not the earlier prospective 1165–1315.
      SHA256 source `ef372e9b35975fec534bdeb5c5bc2fce661334c617bcf857784421149bc7b25a`,
      test `75eecddb07778885e9baeead62053b81478c7034318b5afdf026e1a5fd4afd52`,
      root `141622b78a30d16ae44bc3b571d8e3b4aca66ba97359b0a2a68a28ae10e5415e`.
      Writer tests: **86 focused/396 full**, existing 48/358 preserved; HTTP/policy 124.
      Import RED exit 2/one collection error recorded separately, not behavioral evidence.
      Collection-compatible scaffold RED **38 failed/48 passed**, zero collection errors;
      later in-body freeze/hash/other assertions were unreached at RED, not backdated.
      GREEN matrix passed; no additional refactor change. Logs `/tmp/f1show_f03c3b_*.txt`.
      Writer Fake/MockTransport proves 429 recovery/1s wait, ordered queries, no duplicate
      checkpoint, explicit core-stage partial counts, caller ownership/cancel/type-only errors.
      Composition exhaustion cases use max_attempts=1, not a new multi-retry exhaustion proof;
      underlying published retry tests cover exhaustion. Real provider behavior unverified.
      **ASSESS medium / runtime large writer:** self-verification stands, structuralReadbackOnly
      false, independentVerifier **false**; follow exact returned plan, not 3a's former high
      fallback. RDD on/outcome unknown/candidate unconsumed; reviewDue slice_budget_reached.
      Native continuation relayed unchanged: `gentle-ai review status --cwd=/home/s/dev/projects/work/F1Show --contract=gentle-ai.review-integration/v2 --next-transition=true`.
      Parent source spot-check confirms fixed loop/query, one delegated ingest call, no new
      retry/ownership/watermark query behavior. Active LSP: no new primary errors; base
      SnapshotResult warning/NED typo carried. Writer cached Ruff/base I001 and dependency-
      aware Pyright/base warning are config-specific; no project lint/floor-runtime claim.
      Native approval/acknowledgement and the exact-byte local work-unit commit are recorded
      above; writer/independent-style evidence below is the historical record for this unit.
      3a closed before this bounded writer; source/test hashes above form its baseline.
      Same allowed surfaces only: `src/f1show/ingest.py`, `tests/test_ingest.py`, additive
      exports in `src/f1show/__init__.py`; other source/tests/config/ports/fakes untouched.
      Add frozen `SessionSyncResult(session_key, outcomes)` with an ordered tuple of two
      EndpointOutcomes (sessions then drivers), no aggregate-success flag. Public async
      `sync_session(http, store, clock, *, session_key, base_url=DEFAULT_OPENF1_BASE_URL)`.
      Validate requested identity before effects; GET each fixed endpoint once via caller's
      published HttpClient, `session_key` string query only, delegate admitted 2xx payloads
      once to existing ingest_endpoint. Non-2xx/regular fetch errors produce failed outcomes
      with known zero writes/no stamp/no checkpoint, safe stable type/code and stage `fetch`.
      Minimally extend failure-stage literal; preserve every existing 3a pipeline invariant.
      Continue the second endpoint after an ordinary first failure; propagate cancellation/
      process-control exceptions with no fabricated result. Caller owns HTTP client and Store.
      Reuse published RetryingHttpClient/RateLimiter externally in integration tests, never
      add retries/rate policy, open/close clients, read checkpoints as provider filters, or
      invent paging, optional family registries, config wiring or lifecycle behavior.
      Observe behavioral RED on the new sync behavior (collection-compatible scaffold if
      needed), GREEN/refactor; distinguish later unreached assertions/coverage-only cases.
      Tests use scripted fake and MockTransport chains, retry exhaustion/429 recovery,
      status/null/malformed/partial outcomes, exactly-once checkpoint and caller ownership.
      Shared backend parity where meaningful; cancellation/BaseException and no-error-text
      leakage remain explicit. No real calls. ASSESS decides any separate verifier; this
      medium/large candidate requires writer self-verification plus native/local closure.
      Forecast 300–450 total diff lines including tests/exports. With 3a's actual 865, the
      prospective combined size is 1165–1315, replacing the earlier 750–1100 estimate;
      forecasts are not caps or permission to expand areas; preserve meaningful tests.
    Session query empty-vs-404 behavior is not live-verified; valid empty remains accepted
    and non-2xx remains failure. F03c-4 owns lifecycle; future source publication is separate.
  - **F03c-4 — Session lifecycle. Closed locally.**
    Requirement: explicit end/cancel/reset, fixed per-run session identity, late-response
    isolation and partial-family outcomes, caller-owned Store, no delete/transaction API.
    `ARCHITECTURE.md:46` already assigns "session lifecycle" to the `sync` service, so this
    unit is the seam F03d/F10 will drive rather than a new subsystem.
    **Design decision (parent, derived from that requirement):** a new module
    `src/f1show/session.py` whose run identity is supplied by the caller — no hidden
    entropy, uuid or clock read — so behavior stays deterministic and testable.
      - Frozen `SessionRunIdentity(run_id, session_key)`; `run_id` is a non-empty caller
        string. No provider field, no store column, no schema change.
      - `RunState` vocabulary `active`/`ended`/`cancelled`, reported as data.
      - `SessionRun(identity, generation)`: `generation` changes only through this object's
        own transitions so a superseded run is distinguishable from a live one.
      - `async run.sync(http, store, clock, *, base_url=DEFAULT_OPENF1_BASE_URL)` uses the run's
        own `identity.session_key` and performs exactly ONE `sync_session` per call: repeat
        calls are the ~3s live cadence, not an error. It returns the `SessionSyncResult`
        unchanged, preserving the fixed identity and the ordered partial-family outcomes.
      - `run.end()` and `run.cancel()` are terminal. `cancel()` requests isolation rather than
        reaching into the caller's task: it marks the run terminal so an in-flight `sync` can
        no longer commit, while the caller still owns its task and any `CancelledError`
        propagates unchanged.
        `run.reset(session_key, run_id)` returns a NEW `SessionRun` with the caller-supplied
        `run_id` and advanced generation, and never reads, rewrites, deletes or truncates
        committed store rows. The design shorthand omitted the `run_id` parameter; the
        implementation resolves it as `reset(session_key, run_id)` because the new identity is
        caller-supplied by contract, not generated by this layer.
      - Refusal is typed data: a `sync` after `end`/`cancel`, or under a superseded
        generation, raises a distinct `RunNotActiveError` **before any fetch or persistence
        effect**, and never carries a payload, URL, secret or message text.
      - Late-response isolation: a sync whose run was ended, cancelled or superseded while
        its request was in flight must not commit. `sync_session` receives a run-scoped
        `Store` view that refuses `write_source_batch`/`set_watermark` with a stable
        `StaleRunError` once the run is not active, so the honest `failed` outcome with
        `failure_type="StaleRunError"` is reported instead of a committed write. The view
        never closes or replaces the caller's store and never exposes a delete/transaction
        API; `CancelledError`/`BaseException` still propagate.
      - Two runs sharing one `session_key` stay independent: a late response from run N can
        never advance run N+1's checkpoint or records.
      Checks: behavioral RED on the new lifecycle behavior (collection-compatible scaffold if
      needed; collection failure recorded separately), then GREEN/refactor. Cover repeated
      active syncs and end/cancel/reset transitions with idempotence; refusal before effects
      with zero fetch/write/checkpoint calls; stale-write isolation raced against `reset` and
      `cancel`; cancellation/BaseException propagation with no fabricated outcome; unchanged
      `SessionSyncResult` partial outcomes and honest counts; caller ownership of HTTP and
      Store; no schema/deletion/transaction surface; no text or serialized-payload leakage.
      Offline only, reusing the published fakes, `MockTransport` and shared limiter. 3a/3b
      reviewed bytes (`ingest.py`, `test_ingest.py`) are protected and must stay unchanged.
      Independent/native review and local unit commit due.
      Forecast 300–500 total diff lines including tests and exports.
      **Writer `mv2q1o7v-16-qn54` returned implementation; this is not acceptance.** Parent
      confirms two untracked new files plus one additive tracked edit, index identical to HEAD
      and HEAD `1b6eb92` unchanged; the writer's forbidden `git add -N` left no residue
      (`git diff --cached` empty, protected/reviewed paths byte-identical).
      Candidate **917 additions + 0 deletions**: new `src/f1show/session.py` 254 lines,
      new `tests/test_session.py` 653 lines, additive `__init__.py` exports +10. Overrun vs the
      300–500 forecast by more than double, disclosed; the matrix was ordered by the parent
      brief and no meaningful test was trimmed. F03c authored total is now 865 + 838 + 917=2620.
      SHA256: session `ad6134a90a22ceb977c58ee9012586fdde724c39f8c8df8d5122b1e94efb9fb6`,
      test `a4c162e10fbbdeb5d5a667a910242e7c3d150104720a540ca4c3157ccf77906f`,
      root `719e297427d9fb2fe9c955788e45faa170205d427fe395ef08ab48c9313c69f9`;
      reviewed `ingest.py`/`test_ingest.py` pins unchanged (`ef372e9b…`, `75eecddb…`).
      Writer tests: **121 focused/431 full** (baseline 396 green). Collection RED recorded
      separately (module import error, exit 2), then collection-compatible scaffold behavioral
      RED **34 failed/1 passed/35**; the single pass is a constants-only assertion and every
      later in-body assertion was unreached at RED, not backdated. GREEN then refactor with no
      behavior change. Logs `/tmp/f1show_f03c4_{red_collection,red_behavioral,focused,full}.txt`.
      Reported proofs: cancel/reset/end mid-flight → honest `failed`/`write`/`StaleRunError`
      with `records_written=None`, zero store writes, rows and watermarks empty, zero closes;
      refusal after end/cancel/superseded → `RunNotActiveError` with empty `args` and zero
      fetch/clock/store calls; end/cancel idempotent and first-terminal-wins; `CancelledError`
      and `KeyboardInterrupt` propagate with nothing written; caller store reusable and never
      closed. Public names: `RunState`, `SessionRunIdentity`, `SessionRun`, `RunNotActiveError`,
      `StaleRunError`, `StoreOwnershipError`.
      ASSESS is again **unassessable** for undeclared new files, so its mandatory high-risk
      fallback applies: writer self-verification **and** a separate independent verifier.
      Writer static claims are configuration-specific: cached Ruff clean on both new files with
      the base root I001 only, and cached Pyright 0 errors + the base `SnapshotResult` warning.
      No active LSP was available in the writer; the parent probe saw two clean paths and one
      inconclusive timeout, to be re-probed. No Python 3.12 runtime proof; tests ran on 3.14.4.
      **Independent verifier `mv2qfl09-17-b9o9`: PASS, with qualifications that stand.**
      Confirmed 121 focused/431 full on Python 3.14.4 and the 917 additions/0 deletions count;
      scope, index and pins identical before and after its work; reviewed 3a/3b bytes untouched.
      53 independent probes (its own harness, not the shipped tests) passed, plus **6/6
      mutants assertion-killed** with a pristine control of 36 passing and no survivor:
      dropped state check, bypassed run-scoped view, stale `set_watermark` allowed, `reset`
      not terminating the old run, `close()` delegating to the caller store, and a stale write
      inventing a count. Logs under `/tmp/f03c4_verify/`.
      **Qualifications carried, not smoothed over.** The generation-mismatch branch is
      *publicly unreachable*: the public API cannot change a live run's generation, so it is
      exercised only through a stand-in run — that proves the invariant is coded, not that any
      public flow reaches it. The mid-flight race tests are *scripted*: hooks run synchronously
      inside `get_json` before the response is processed, so they prove refusal of responses
      arriving after the terminal flip and prove **nothing** about a write already delegated to
      the store when `end()`/`cancel()` fires, which under true concurrency could still commit.
      The `set_watermark` staleness guard is likewise only killed through the stand-in branch.
      The constants-only start test and the structural view-surface assertion could pass against
      a stub; the mutants are what make the suite require real logic.
      TDD is judged **partly scaffold-shaped**: the 15 `DID NOT RAISE ValueError` failures are
      meaningful behavioral RED for admission validation, while the async lifecycle tests failed
      through scaffold `NotImplementedError`, so their in-body assertions were never observed
      RED on real logic. Their efficacy rests on the mutations above, not on TDD; nothing was
      backdated and the writer's RED logs were not independently re-observed.
      Static, configuration-scoped: cached Ruff clean on both new files with a base-only `I001`
      on `__init__.py` reproduced identically on a HEAD copy; cached Pyright 0 errors and the
      pre-existing `SnapshotResult` `reportUnsupportedDunderAll` warning only. The timed-out LSP
      path was re-probed with Pyright scoped to all three files (`session.py` clean) — that is a
      substitute, not the same probe as the parent's LSP tool. No Python 3.12 runtime proof.
      ASSESS was unassessable for the undeclared new files, so the mandatory high-risk plan
      (writer self-verification **plus** a separate independent verifier) is now satisfied.
      No real-concurrency evidence exists anywhere in this unit.
      Closed locally as `a0a3683e39e8fa071355d3d3934ed729337c5a50`, Conventional Commit
      `feat(session): add run-scoped session lifecycle with stale-run isolation`, 3 paths
      +917/−0. Reviewed = staged = committed tree `5a5e578d6f46d846848d6c198af35ea0b3402a83`;
      all five hashes (three candidate plus the two protected reviewed files) checked before
      staging; clean worktree after the commit; no push. Native `review-57365f025766ea65`,
      medium/reliability/917 lines/budget 200, approved on the first reviewer run.
      The consent path cost three expired bindings carrying **no lineage and no mutation**
      before the human answered the host prompt; the relief was human, not retries, and the
      third attempt had shown a ~38-minute blocked wait rather than an instant failure.
      One resubmission was rejected as `capture-group-rejected` **without mutation** because
      the binding had been re-typed by hand instead of passed verbatim; resubmitting the
      provider's exact stored string succeeded in 235 s. Exact bound STATUS/ack returned
      authority **burned**; consumed revision
      `sha256:88908440fd210a9670b9ac2bfcb2d89e639fea7777f764c14eb0fb5443203b24`; burn evidence
      `gentle-ai.review-acknowledged/v1`; never query this lineage again. Informational
      advisory (body absent; do not infer/fix): `R3-001` tests/test_session.py:511-529.
      That advisory is now **actioned as a bounded follow-up**, not absorbed into this unit:
      the provider never returned its text, so the parent inspected the named region itself and
      found the genuine gap a reliability lens would flag there — that one test asserted the
      refused endpoint's status and failure label but not its honest-partial fields
      (`records_written is None`, `checkpoint_written is False`, a real `observed_at` stamp) or
      the run state or the absent drivers records, while sibling tests do assert those fields.
      The hardening is test-only and its correctness was checked against `ingest.py`'s actual
      write-failure branch before editing. It cannot be claimed to match the provider's unstated
      intent; it is verified as correct and load-bearing for the refused-write contract.
      **Closed** as `f13757b64c9fb2f668f9511c65f1aebeb6e24b`, Conventional Commit
      `test(session): assert honest partial fields on the refused endpoint`, 1 path +9/−0;
      reviewed = staged = committed tree `a180bb216066cd3947acf7c602dc733eee852a57`.
      Independent verifier `mv2ucsd7-18-bsr6` PASS: 121 focused/431 full unchanged; candidate
      `4e59c7ef3d22f4b0e97561a2d001146b992a849aaf1734b9be4f3dba1f22de4a` (662 lines);
      **three mutants killed**, each failing the hardened test by name — `records_written=0`
      (`assert 0 is None`), `observed_at=None` (`assert None is not None`) and
      `checkpoint_written=True` (`assert True is False`) — with a pristine control at 122 and the
      shadow's `ingest.py` restored to its pinned hash. The verifier also reported, honestly,
      that HEAD moved mid-run (`bee9881a`→`d2cf6da`, docs-only, the parent's commit) rather than
      hiding it. Native `review-3717be5e3cd796bb`, medium/1 file/9 lines/budget 5, approved on
      the first run in 25 s; exact bound STATUS/ack returned authority **burned**; consumed
      revision `sha256:a3d889bc877d85b44353a518b811fcf55657e647ec04382e93ded78cc05eb09c`; never
      query it again. The reviewer raised a NEW non-blocking suggestion we did not anticipate,
      `R3-observed-at-assertion-weak` at `tests/test_session.py:535`, judging the added
      `observed_at is not None` assertion weak. That is a fair point — a stronger assertion
      would compare the stamp to the clock's actual value — and it is carried as later work
      rather than reopening this candidate or rewriting approved bytes.
  Per-unit checks: scoped pytest then full `uv run --frozen pytest -q`, observed
  RED/GREEN with coverage-only passes disclosed, native work-unit review under the
  user's enabled switch, local Conventional Commit and task/mirror/todo evidence.
- **F03d — the live seam, in two bounded units.** The documented live contract is now
  first-party verified (documentation reading only — no subscription, purchase, credential use
  or live/authenticated call was made): `POST https://api.openf1.org/token` with
  `Content-Type: application/x-www-form-urlencoded` and `username`/`password` form fields,
  returning `{"expires_in": "3600", "access_token": "…", "token_type": "bearer"}` — the
  documented `expires_in` is a **string**, which strict parsing must accept without inventing
  a different type. Authenticated REST requests add `Authorization: Bearer <token>`, and
  tokens expire after one hour, so the client must refresh rather than fail silently.
  The same page recommends **MQTT/WebSocket** for live data (`mqtt.openf1.org:8883`,
  `wss://mqtt.openf1.org:8084/mqtt`, token as the password) and calls it the more efficient
  option. **That streaming path is deliberately not adopted here**, because the project fixed a
  ~3 s REST polling cadence and streaming would add a new transport, dependency and lifecycle;
  the recommendation is recorded as an unadopted alternative for F10/F13 rather than silently
  ignored or silently implemented. `config.py` already carries
  `CredentialsSettings.openf1_username`/`openf1_password` as `SecretStr`, so no new credential
  configuration is invented.
  The obstacle is the reviewed `HttpClient` port: `get_json(url, *, params=…)` has no header
  parameter and the port has no form POST, so neither an authenticated GET nor a token exchange
  can be expressed without extending it. Instead of turning that into one large multi-area
  change, F03d is split into two units, each with its own independent/native review and local
  commit:
    - **F03d-1 — HTTP boundary extension.** Additive `headers` support on `get_json` plus one
      form-POST method, forwarded by the retrying wrapper and mirrored by the fake, with every
      existing retry, pacing, cleanup and error contract preserved and only the new surface
      tested. Surfaces: `src/f1show/{ports,http,fakes,request_policy}.py` and
      `tests/test_{http,fakes,request_policy}.py`. These bytes were reviewed before, but the
      burned F03c-1/F03c-2 authorities are never reused: this is a new candidate and a new
      review. Secrets or credential values must never appear in these files or their tests.
      **Implementation returned; independent verification in flight.** Writer `mv2undvu-19-zgla`
      produced ten modified paths, **+1050/−40 = 1090** total against the 250–450 forecast
      (2.4×, disclosed, no test trimmed); focused 243 / full **496** (baseline 431 + 65).
      The writer disclosed three process weaknesses honestly rather than hiding them:
      (1) **RED was reconstructed, not observed** — tests were authored first but the first
      pytest run happened after implementation, so RED came from running the new tests against
      base sources in a /tmp tree (75 failed/168 passed: 124 `AttributeError`, 24 `TypeError`,
      2 `DID NOT RAISE`), preceded by a collection error (`ImportError: copy_form_fields`) and a
      no-logic stub that **masked two helper-rule cases**; (2) the shared-path extraction
      (`_perform`/`_run`) landed on the GREEN implementation with no separate pre-refactor
      snapshot; (3) the protocol growth **structurally broke 18 Pyright errors in files it was
      not allowed to touch**.
      The parent confirmed the third point independently with its own active LSP and treated it
      as a defect of this unit rather than carried debt: fixing after review would invalidate the
      candidate and burn a human consent round, and asking a reviewer to look at bytes already
      known to be statically wrong wastes the reviewer. Follow-up `mv2v6cvj-1a-gcfv` conformed
      five local doubles by signature only — `headers` forwarded on `get_json`, `post_form_json`
      forwarding for wrappers and a loud `NotImplementedError` naming the double for the
      exploding ones — with counts unchanged at 121/496, the R3-001 hardening assertions
      untouched, and the 18 errors reduced to **0**, with the same 18 reproduced against the base
      copies to prove the cause was the protocol growth. The parent's re-probe now shows only the
      **3 pre-existing** `tests/test_fakes.py` errors and the two base `I001` findings, so the
      static state did not regress. Pins: `tests/test_session.py`
      `47466f3c34e5c3b5ddd9251c72a4b017c6e66db4420b1373ff88535b7ef1ca02`, `tests/test_ingest.py`
      `5fba8a28202dbff369f8c579dec98a63bdd37a2443f6b872823f8e3ff327701b`.
      ASSESS returned medium/10 paths/1090 lines, and its plan does **not** require a separate
      verifier; the parent runs one anyway, because with a reconstructed RED the unit would
      otherwise rest entirely on the writer's self-report. Logs `/tmp/f1show_f03d1_*.txt`; the
      verifier works under `/tmp/f03d1_verify/`. Honest caveats carried into review: a retried
      POST may be sent more than once, which is an **unverified provider assumption** and not a
      proven property, and there is no Python 3.12 runtime proof.
      **Closed** as `d807cbcddcc1112197ec5e02961e7603ac638b33`, Conventional Commit
      `feat(http): add request headers and form POST to the HTTP boundary`, ten paths
      **+1050/−40 = 1090**; reviewed = staged = committed tree
      `1e9ca9d6b4d088ceab66150bfa20b27d6d746a63`; clean worktree after the commit; no push.
      Independent verifier `mv2v9og5-1b-t0dn` **PASS**: 243 focused/496 full, thirteen tracked
      hashes identical at start and end, the ten-path scope confirmed, and **7/7 mutants killed
      with no survivor** — no header forwarding, lowercased header names, POST following
      redirects, POST skipping the shared limiter, overwriting a caller-supplied content type,
      embedding a header value in a transport error, and the fake's form path reading the GET
      script — each named with the test that caught it, control 244 passing before and after.
      It also confirmed the header-non-leakage assertion is **non-vacuous** (the placeholder is
      asserted present on the wire before its absence is asserted) and that the two
      previously masked helper rules are now genuinely asserted (`tests/test_ports.py:184-198`),
      so the reconstructed RED does not establish TDD but the rules are covered. It judged the
      three narrow `S105` suppressions appropriately scoped.
      Native `review-b2c24c7f0978166b`, medium/10 files/1090 lines/budget 200, approved on the
      first reviewer run in 224 s; exact bound STATUS/ack returned authority **burned**;
      consumed revision `sha256:9837983512df6d0d8a4e1b39e845990eb2d71a5798c2306d66b1da36d6c00424`;
      never query it again. It raised three informational suggestions with no correction opened
      and no bodies provided, carried as later work: `R3-fake-form-registration-shape`
      (`fakes.py:159-190`), `R3-form-content-type-fallback` (`http.py:227-228`) and
      `R3-port-header-retention-wording` (`ports.py:130-138`). The third independently matches
      the verifier's own observation that the "no client-level default header" wording is
      slightly overstated because httpx still attaches its own defaults — a real, if cosmetic,
      inaccuracy in a docstring, not in behavior.
    - **F03d-2 — authentication and the live seam. Concrete design registered before writes.**
      New module `src/f1show/auth.py` (no change to `config.py`; `CredentialsSettings` already
      carries `openf1_username`/`openf1_password` as `SecretStr`, and no new configuration is
      invented) plus its tests and additive exports. Design decisions, derived from the verified
      first-party contract and from the port F03d-1 just published:
      - `DEFAULT_OPENF1_TOKEN_URL = "https://api.openf1.org/token"` lives in the new module, not
        in `config.py`.
      - A token response model accepting the documented **string-or-int** `expires_in` and a
        case-insensitive `bearer` type, refusing an empty/missing `access_token` and an expired-
        or-negative lifetime, and treating unknown extra fields as ignorable external input the
        way source records already are. No message, body or credential may appear in a failure.
      - A token value holding the secret through the project's existing redaction/`SecretStr`
        machinery so `repr`, `str` and formatting cannot reveal it, and so a diagnostic can name
        the token's state without its value.
      - A provider that exchanges credentials by calling `post_form_json` on the caller's raw
        client exactly when there is no valid cached token, caches until
        `issued_at + expires_in − skew` (skew a documented constant, and the arithmetic done with
        the injected `Clock`, never a private clock), performs at most one in-flight exchange so
        concurrent callers await the same one, and adds no retry policy of its own because the
        injected client may already be the paced retrying wrapper. Typed failures for non-2xx,
        decode and validation problems; the password is read from the secret only when the form
        is built and is never stored, logged or cached.
      - An auth-injecting client that adds exactly ONE `Authorization: Bearer <token>` header to
        `get_json`, refuses a caller who supplied their own `Authorization` header rather than
        silently mixing credentials, forwards `post_form_json` unchanged (the token endpoint
        authenticates with credentials in the body, never with a bearer header), and neither
        opens, closes nor replaces caller-owned objects — following the existing wrapper
        convention in `request_policy.py` and documenting which object owns the inner client.
      - Checks: a scripted fake and `MockTransport` only, offline. Cover the documented
        string `expires_in` and integer form, rejection of a bad type/empty token/unknown token
        type, refresh exactly at the skew boundary and not one call earlier, at-most-one
        in-flight exchange under concurrent callers, a non-2xx and a malformed exchange body
        becoming typed failures, no credential or token value reachable from any raised error,
        `repr` or outcome, exactly one header added and no duplicate, the caller-supplied
        `Authorization` refusal, and caller ownership. Honest limit unchanged: the real
        exchange, the real expiry behaviour and real live responses stay unverified without the
        paid subscription, and live validation belongs to F13.
      **Implementation returned; independent verification in flight.** Writer `mv2vrc25-1c-yjv4`
      produced `src/f1show/auth.py` (416 lines), `tests/test_auth.py` (431) and additive
      `__init__.py` exports (+16/−0): **863 total** against the 300–500 forecast (1.73×,
      disclosed, no test or docstring trimmed). Focused 52 / full **548** (baseline 496), on
      Python 3.14.4. Pins: `auth.py`
      `f23d28aed9991363455a98de251b6a9aeb1554580994555badddd0c41b271337`, `tests/test_auth.py`
      `f505541c76e0528ddb96ea58c7a786d4c8b94e2a3639532b10a302a8e77c9cc1`, `__init__.py`
      `b3fad40a20a7ad304a50323298184a6d8dfc6c425d32956e8b0922bc053e489a`.
      **Parent design decision, resolving an ambiguity the parent brief created.** The brief both
      told the writer to follow `request_policy.py`'s convention and forbade closing
      caller-owned objects. The writer asked, and the reading is confirmed: during a request
      nothing is opened, closed or replaced, and the single ownership act is `close()`, which
      releases the adopted inner client exactly once and is safe to repeat — exactly the
      documented precedent at `request_policy.py:289-294`. The class docstring states this
      precisely. The composition caveat stays honest and unstated in code: nothing prevents a
      provider from sharing the same inner client as the auth client, in which case closing the
      auth client makes the provider unusable, so **the caller owns its composition**. That is
      recorded here rather than patched into a docstring now, because one sentence would cost a
      full re-verification and re-review cycle.
      **Auxiliary static judgement.** The parent's LSP found only the pre-existing
      `SnapshotResult` warning plus two auxiliary `unchecked-numeric-parse-python` warnings at
      `auth.py:104` and `:143`, judged **false positives**: `expires_in` is guarded by
      `str.isdigit()` before `int()`, and `_positive_seconds` validates before `float()`. The
      same auxiliary pattern already exists in `http.py`, `fakes.py` and `request_policy.py`.
      The writer's reported `f1show.auth` unresolved import was a **stale index artifact**: the
      parent's LSP resolved the module and returned findings.
      **TDD honesty carried into review.** Collection RED was separate
      (`ModuleNotFoundError`). The behavioural RED was stub-shaped — 50 failed / 1 passed / 1
      **deselected** — where the single pass was the structural `isinstance` test that a
      no-logic stub satisfies by exposing method names, every failure stopped at its first
      exercised call so later in-body assertions were unreached, and the **single-in-flight
      concurrency test was deselected because it hangs under the stub**. The first GREEN attempt
      was 51 passed / 1 failed from a test-side missing `params=` registration and that interim
      log was overwritten. The consequence is explicit: the concurrency proof has **no RED
      evidence at all**, and a hang instead of a failure is itself a hazard the verifier is
      asked to judge rather than repair.
      **Independent verification of the returned bytes: PASS, with two findings it did not hide.**
      Verifier `mv2weiqx-1d-5jqc` confirmed 52 focused/548 full on Python 3.14.4, candidate pins
      identical at start and end, **863 added / 0 deleted**, and the refresh boundary as
      skew-correct rather than off by one. Ten faithful mutants, **nine killed**, and it reported
      the fourth thing a self-report would have missed:
      (1) **A confirmed hang hazard.** It removed the gate's `started.set()` and the concurrency
      test was killed by `timeout 20` with **exit 124** at `test_auth.py:280` — a suite that
      hangs instead of failing. (2) **One surviving mutant (m9).** Deleting `_require_open()`
      from `post_form_json` was not caught, because after `close()` the adopted inner client
      also refuses; the guard **is** present at `auth.py:404`, so this was a **coverage gap, not
      a behaviour defect** — the double refusal masked the wrapper's own guard.
      (3) It **refined a parent judgement**: the parent had called the `unchecked-numeric-parse`
      warnings false positives because `isdigit()` supposedly makes `int()` infallible, and the
      verifier probed that `'²'.isdigit()` is True while `int('²')` raises. The verdict stands
      (the raise happens inside a pydantic validator and becomes a typed, value-free error) but
      **the parent's stated rationale was imprecise**, and that is recorded rather than smoothed.
      (4) It **declared its own deviation** instead of hiding it: in-process `pytest.main` did not
      observe mutated file edits (proven with a marker probe), so each mutant ran as an isolated
      frozen pytest process rather than literally in the same one.
      It also confirmed that the single-in-flight property had **zero RED evidence** — the only
      RED was that test's deselection — and supplied that evidence itself via the m3 kill and a
      live five-caller gated proof.
      **Test-only correction `mv2wr5ji-1e-c0ss`, with both fixes proven load-bearing.**
      `tests/test_auth.py` moved 431→457 lines and `f505541c…`→`b26381f7…` while `auth.py` and
      `__init__.py` stayed byte-identical; no test was added, so the count stays 52. The
      concurrency test now bounds both waits with `asyncio.wait_for(..., timeout=5.0)` and
      `pytest.fail` naming the hazard — the writer re-ran the never-starting probe and it now
      **fails in 5.16 s with exit 1 instead of hanging** — and the after-close assertion now
      demands the wrapper's own message (`AuthenticatedHttpClient is closed`) for **both**
      methods, which the writer showed kills m9 in a `/tmp` shadow (`Actual message:
      'FakeHttpClient is closed'`). The follow-up disclosed one residual honestly: the bound is a
      fixed wall-clock wait, so a pathologically slow but correct exchange would fail as a
      hazard; for in-process fake-driven work that trade is accepted. A focused independent
      re-verification of these new bytes is in flight.
      **Focused re-verification of the corrected bytes: PASS.** `mv2wv6hv-1f-lz4d` reproduced both
      fixes independently: the corrected concurrency test failed in 5.15 s with the hazard-naming
      message instead of hanging (exit 1, never exit 124) while the unmodified control passed in
      0.38 s; and in a shadow with `_require_open()` removed from `post_form_json` the tightened
      assertion failed on the wrapper's own message (`Actual message: 'FakeHttpClient is closed'`)
      while the pristine control passed with the import proof. It confirmed 52 focused/548 full,
      static cleanliness on the three paths, and judged the fixed 5 s bound a reasonable trade
      (~12× headroom over a ~0.4 s control, with the only other wait test-controlled). It also
      **misread one thing, and the parent caught it**: it reported a non-empty index, but a
      re-check showed the index clean — the verifier had measured the worktree against HEAD while
      a parent documentation edit was still uncommitted. The observation was real; the label was
      not.
      **Closed** as `30f4fa4fad54d708f0e47df013749341441ae2b5`, Conventional Commit
      `feat(auth): add OAuth2 token handling and an authenticated HTTP client`, three paths
      **+889/−0**; reviewed = staged = committed tree `06b15a031a7f960523786b5a87e25eacef228634`.
      Native `review-aedd0260ee5d2fd7` was tiered **high** (hot path: authentication) and ran
      **four lenses** — risk, resilience, readability, reliability. The first capture died with
      `reviewer-empty-output` on `review-risk` (stopReason `stop`, 116 s, **nothing prepared,
      nothing submitted, no mutation**); a fresh bound STATUS reoffered the byte-identical
      four-lens group and the retry approved in 165 s with four reviewers prepared and submitted.
      Exact bound STATUS/ack returned authority **burned**; consumed revision
      `sha256:1bda6145f2cbfc6081a0666e73f8adb957b2f1f2ab28bc6383c6cbc494e58c5f`; never query it
      again. **Fourteen informational findings, no correction opened and no bodies returned**
      (six `WARNING`s, eight `SUGGESTION`s). They are carried as later work and **not**
      reconstructed: `R1-001` auth.py:391-394, `R1-002` :263-264, `R1-003` :140-148,
      `R3-001` :211-222, `R4-retry-amplification` :283-292 and `R4-stale-token` :305-311 are the
      warnings; `R2-exchange-lifecycle` :272-295, `R2-post-except-raise` :168-173,
      `R2-repr-secret-materialization` :193-200, `R3-002` :279-291, `R3-003` :282-288,
      `R3-004` :405-415, `R3-005` :256-269 and `R4-transport-taxonomy` :325-335 are suggestions.
      **The warnings cluster on authentication material, retry amplification and token staleness,
      which is precisely the material that matters once this code runs against the live service**,
      so retrieving those bodies is real later work rather than bookkeeping.
      **F03-cleanup, opened after publication at the user's request.**
      (1) **The finding bodies are not recoverable, and that was proved rather than assumed.**
      The terminal-consumption receipt in `.git/gentle-ai` is **259 bytes** holding only
      `lineage`/`repository`/`schema`/`target`; **no provider state directory exists** on this
      machine; and a bounded filesystem search for the finding ids found **only the parent's own
      mirror file**, which mentions them because the parent wrote them there. The reviewer
      results were relayed as **opaque bytes** and only their metadata survives the closure.
      `review reopen-results` is **not** a retrieval path: it is a maintainer-authorized
      same-lineage **quarantine for unusable reviewer results**, requiring an uncorrected
      validating/correction-required revision plus an authorization emitted by `--prepare`, and
      this lineage is approved and burned — invoking it would be an abuse and would return no
      narrative anyway. `inspect-candidate` inspects the candidate, not the results. The durable
      consequence: **finding bodies are ephemeral by design, so the location list is the only
      durable signal, and this will recur for every future advisory.**
      (2) **The declared Python 3.12 floor is now proven, not asserted.** Verifier
      `mv2xtob9-1h-rkjv`: `uv run --frozen --python 3.12 pytest -q` → **548 passed** on CPython
      **3.12.13**, and the same suite under **3.13.13** → **548 passed**; both exit 0, no failures
      to classify, with `pyproject.toml`, `uv.lock` and `.python-version` hashes identical before
      and after. `--frozen` was respected (no lock re-resolution); uv downloaded two wheels absent
      from the cache (`duckdb`, `pydantic-core`) and rebuilt the gitignored `.venv`, which is the
      disclosed side effect of the authorized command. A version-gated API audit found only
      `asyncio.timeout` (3.11+), consistent with the floor, and every one of the 36 installed
      distributions declares a floor at or below 3.12, so the lock is coherent with the claim.
      **The honest limit stands:** this proves the floor is runnable today, not that a future
      dependency bump preserves it, and no CI in this repository enforces it — a matrix job
      pinning 3.12 would be needed to keep the claim honest over time.
      (3) **Auth hardening closed as `8b17df23a619eca3b34f7039aa7187651b441c8a`.** Conventional Commit
      `fix(auth): consume abandoned exchange failures and sanitize transport errors`, three paths
      **+261/−18 = 279**; reviewed = staged = committed tree
      `78fc6d6b1c7bd752fba65f270a079cdadb0165df`. The parent's own analysis of the flagged
      locations, **not** retrieved provider intent, drove four self-standing changes: `repr`/`str`
      now emit a fixed mask and never unwrap the secret; `asyncio.shield` is replaced by a manual
      relay whose done-callback always consumes the exchange's exception; a new
      `TokenTransportError` brings transport, timeout and oversized-body failures into the
      `AuthError` taxonomy with a sanitized message; and the composition caveat is documented.
      The relay was a **design correction to the parent's brief**: the original mechanism could not
      pass the original proof, because `asyncio.shield` reports an abandoned shielded failure
      regardless of retrieval — the writer stopped without editing rather than improvise, which is
      exactly the behaviour the brief asked for on an unplanned fork.
      Independent verification PASS (59 focused/555 full): candidate hashes matched at start and
      end, `odd/tasks/f1show.md` re-derived as **clean** (two separate reports had mislabelled a
      committed diff as a pending modification), and mutants for the relay, the mask and the
      sanitization were killed. One mutant **survived** — dropping the exception branch's
      `_exchange` clearing — and the honest classification is that it is a **behaviourally
      equivalent** mutant rather than a coverage gap worth chasing: the next call's done-discard
      path performs the same clearing, so only private-state introspection would observe the
      difference, and a test that pokes a private attribute would couple the suite to internals.
      Two relay paths (waiter cancelled after completion, exchange already done at attach) are
      code-verified only, with no dedicated test. Native `review-3ed008e4aa1a106b` tiered **high**
      (auth hot path) and ran four lenses, approving on the first attempt with four reviewers;
      its first capture required no retry. Exact bound STATUS/ack returned authority **burned**;
      consumed revision `sha256:143aadb1590e0fed0e96e9544656ce8e240c15d1c0b6062b7b3115be6af338b2`;
      never query it again. Three informational findings with no correction opened and **no bodies
      returned**, carried as later work and not reconstructed: `R4-001` a **warning** at
      `auth.py:347`, `R3-001` a suggestion at `auth.py:375-383`, and `R2-magic-yield-count` a
      suggestion at `tests/test_auth.py:558-559`.
  Honest limit unchanged: without the paid subscription the real exchange, the real expiry
  behaviour and real live responses remain unverified; a fake transport proves only our
  handling, and live validation belongs to F13 under its own authorization.
- **Decision carried from F01:** the store is SQLite in WAL mode with DuckDB over
  Parquet, not DuckDB as the live store, because DuckDB supports one read-write process
  or many read-only processes and every Compose service is a separate process.
- **F03a lesson, and the rule it produced.** A parity pass aligned the double's upsert and
  its identity rejection but **missed batch atomicity**, and the review caught it. Partial
  alignment is worse than none: it makes "substitutable" look true when it is not. **The
  rule now applied to any port with more than one implementation: the shared semantics are
  demonstrated by one parameterized test that runs the same body against every
  implementation**, because an assertion written once per implementation is exactly how the
  missed semantic survived a review. F03b reads from the store and inherits that test.
- **F03a also closed a silent-failure risk worth remembering.** `PRAGMA journal_mode =
  WAL` was executed with its result ignored. On a filesystem that cannot support WAL,
  SQLite keeps another mode **without saying so**, and the one-writer/many-readers
  assumption the architecture rests on would have been false in production while every
  test stayed green. The mode is now read back and a non-`wal` mode is refused.

## MVP cut, decided 2026-10-10

The user asked how far the project is from an MVP, whether the remaining tasks should be reduced,
and chose **option A**: prove the product's promise before building more plumbing. They also chose
**free mode** — no subscription — so nothing on the MVP path may require authenticated or
real-time access.

**Honest position first.** F00–F03 delivered roughly 5,700 lines of verified plumbing and **zero
user-visible capability**: nothing in this repository produces commentary. F03d in particular
— 883 lines of OAuth2 and authenticated-client code — was built **ahead of need** for a live path
free mode cannot exercise. It is reviewed and tested, but it is the clearest symptom of building
bottom-up without a product check, and this cut is the correction.

**The MVP is:** one session's data → deterministic events → **two distinct, evidence-grounded
personas** → a visible transcript, reproducible offline from recorded fixtures. Its acceptance is
that a reader can see the two-persona commentary and a replay re-produces it.

**MVP units, in order:**
1. **Record the fixtures** (blocking step). Only `sessions` and `drivers` response shapes have ever
   been observed, so honest collector work needs recorded fixtures from the **free, unauthenticated
   historical API**. That is an actual OpenF1 call, so it needs its own small grant. The fixtures
   are the production artifact: the same immutable snapshots serve as replay input and as the
   regression corpus.
   **Granted by the user on 2026-10-10.** Concrete plan, registered before the first request:
   - **Read-only, unauthenticated, free tier.** No credentials, no subscription, no OAuth2, no
     bearer header. Historical data only. The recorder stops on any non-200 and records what it
     saw rather than retrying its way around a refusal.
   - **Pacing is real, not decorative.** The free tier is documented at 3 requests/second and
     30/minute, so the whole recording stays inside one minute's budget by keeping the endpoint
     count small; every request is paced and the actual elapsed time is reported.
   - **Endpoints, with paths now verified from the first-party docs rather than guessed.** The
     documented URL paths are `/v1/sessions`, `/v1/drivers`, `/v1/position`, `/v1/laps`,
     `/v1/intervals`, `/v1/pit`, `/v1/stints`, `/v1/race_control`, `/v1/overtakes`,
     `/v1/session_result`, `/v1/starting_grid`, `/v1/weather` and others. The MVP recording takes
     the event-relevant subset: `sessions` (to choose the session), `drivers`, `position`, `laps`,
     `intervals`, `pit`, `stints`, `race_control` — eight requests. **Deliberately excluded:**
     `car_data` and `location` (both ~3.7 Hz and enormous), `team_radio`, and the championship
     endpoints. Reading a documented path is still not the same as observing a shape, so the
     recording is what turns a documented path into a recorded fact.
   - **One session, chosen so the families are actually available.** `intervals` and `overtakes`
     are documented as race-only, and `pit.stop_duration` exists only from the 2024 United States
     Grand Prix onwards, so the recording targets a **2024 race session at or after that event**.
   - **Bounded size.** Measure before committing: if a family is large enough to bloat the
     repository, bound it with the endpoint's documented date filters and record the exact filter
     plus the resulting first and last timestamps. Nothing is trimmed silently, and an excluded or
     bounded family is stated in the provenance file.
   - **The artifact is self-describing.** Each recorded response lands as raw JSON, and a
     provenance file records the exact URL and query, the HTTP status, the byte size, the SHA256,
     the record count, the request timestamp, and that the responses are unauthenticated
     free-tier historical data. `docs/EXTERNAL-CONTRACTS.md` is updated by the parent, not the
     recorder, once the shapes are actually known.
   - **The recorder script is not committed.** It runs from `/tmp`; the provenance file records
     the exact requests so the recording is reproducible by hand. A committed recorder is a
     separate decision, not a side effect of this step.
   **Recorded 2026-10-10.** Eight unauthenticated free-tier families, all HTTP 200 on the first
   attempt, written verbatim into `fixtures/openf1/` with a provenance file: `sessions` 123,
   `drivers` 20, `position` 403, `laps` 1059, `intervals` 21041, `pit` 23, `stints` 43 and
   `race_control` 120 records — **3,599,681 bytes** total, eight of the twelve authorized requests,
   minimum inter-request gap 0.764 s against the documented 3/s and 30/min. Session `session_key`
   9617, Austin 2024-10-20 race, `meeting_key` 1247, chosen by the registered rule. The parent
   re-verified integrity itself: every file parses as a JSON list, every on-disk SHA256 appears in
   the provenance, the non-allowed trees are byte-identical, the index was empty and the paths are
   not gitignored.
   **The size gate was settled by measurement, not by preference.** `intervals` measured
   **2,965,644 bytes**, above the pre-agreed ~2 MB family gate, and the writer **stopped and
   reserved the decision** instead of trimming. The deciding fact was its own measurement: only
   **1 of 21,041** rows predates the session start, so the documented `date>=` bound would remove a
   single row. A bound that changes nothing is **worse than none**, because it looks like a
   mitigation while doing nothing. Per-driver bounding would drop part of the grid — the opposite
   of a regression corpus — and withholding would lose a family F04's acceptance names. So it stays
   **whole and unreshaped**, with that reasoning recorded in the provenance file.
   **Three shape facts carried into F04**, recorded both in the provenance and in
   `docs/EXTERNAL-CONTRACTS.md`: there is **no uniform timestamp field** (`date` only on
   `position`/`intervals`/`pit`/`race_control`, `date_start` on `sessions`/`laps`, and none at all
   on `drivers`/`stints`); **`laps` has one null `date_start` out of 1059**, so no code may assume
   every lap is dated; and free-tier history is a **snapshot**, so these hashes are point-in-time
   rather than evergreen. The contract file was updated by the parent, as planned: the six newly
   exercised paths are now asserted as **observed** while the remaining documented-only paths stay
   explicitly unasserted.
   Commits: fixtures `d5a1132`, contract update `a2e243c`. **Native review was deliberately skipped
   for this unit**: the artifact is raw JSON plus a provenance document — non-executable data and
   documentation — which is the passive case the provider's entry rule carves out, and running the
   risk, resilience and reliability lenses over a recording would produce noise rather than signal.
   That judgement is stated rather than hidden, and F04's own review will cover the code that
   consumes these fixtures.
2. **F04 — deterministic events.** A **subset of families** that the recorded fixtures can
   actually support, rather than all 18 endpoints. Deduplicate updates, keep evidence timestamps
   and source fields, and prove no false first-lap record and no inferred overtake from a position
   change alone.
   **Design registered before the first write, grounded in the recorded fields rather than assumed
   ones.** The parent inspected every family's real keys and value types, and four of the findings
   are blocking constraints rather than trivia:
   - **`intervals.gap_to_leader` is not uniform**: 19,604 numbers, 106 nulls and **1,331 strings**
     (`+1 LAP`). Any code that casts it to a number is wrong. `interval` is numeric or null, with no
     strings.
   - **`laps` is partial**: `lap_duration` null twice, `date_start` null once, sector 1 null three
     times, sector 3 once, and **846 of 3,177 segment arrays contain nulls**. The very first record
     is a lap-1 row with null `date_start` and null `lap_duration` — the first-lap trap the
     acceptance names, sitting in the data rather than in theory.
   - **`pit` carries three different durations** — `lane_duration`, `pit_duration` and
     `stop_duration` — and they are not the same number; the sample row has 34.983, 34.983 and 12.5.
     Conflating them would misreport a stop.
   - **`stints`, `drivers` and `position` differ in timestamping**: `stints` and `drivers` have no
     timestamp field at all, `position` has `date`, `laps` has `date_start`.
   **Event families for the MVP, each carrying its source evidence** (session key, driver number,
   the actual timestamp field name and value, and the source record identity): `position_changed`
   from `position`; `lap_completed` from `laps` where a duration exists; `pit_stop` from `pit` with
   the three durations kept distinct; `stint_started` from `stints`; and race-control entries from
   `race_control`, preserving `category`, `flag`, `scope`, `sector`, `lap_number` and the provider
   `message` **as evidence, never as instruction** (the recorded categories are `Other` 71, `Flag`
   42, `Drs` 3, `SessionStatus` 2, `SafetyCar` 2, and the flags are dominated by `BLUE` at 20 of
   42, so a naive "flag event" would be noise).
   **What the MVP deliberately does not claim.** No `overtake` event: nothing in these fixtures
   proves an on-track pass, and a position change can come from a pit stop, a penalty, a retirement
   or a car being lapped. No fastest-lap or record claim: a record needs a comparison corpus that
   does not exist, sector data is partial, and lap 1 is a standing start — so lap 1 is excluded from
   any lap-time comparison rather than silently winning one. `intervals` is **normalized but derives
   no events** in the MVP, because gap semantics (`+1 LAP` versus numbers) and their tactical reading
   belong to the deferred F06; the large fixture is used for normalization coverage rather than
   speculation.
   **Determinism and honesty requirements.** Identical fixtures must produce an identical event
   sequence, byte for byte, in a fixed order. A missing value is represented as **unknown**, never
   coerced to zero or dropped silently — not the 106 null gaps, not the two null lap durations, not
   the one null `date_start`, not the partial segment arrays. Deduplicate repeated updates by source
   identity and observation time rather than by guessing intent. Acceptance: a replay over the
   recorded session yields a stable event stream; lap 1 never appears as a lap-time record; a
   position change never surfaces as an overtake; and every event can be traced back to the exact
   fixture record that produced it.
   **Implementation returned 2026-10-10; independent verification in flight.** Writer
   `mv2z47jv-1m-vms1` produced `src/f1show/collector.py` (272 lines), `tests/test_collector.py`
   (294) and additive root exports (+8): **574 additions, 0 deletions**, within the 300–600
   forecast. Focused 18 / full **573**, with the 555 baseline green. Public surface:
   `collect_session_events(session_key, payloads)` plus `classify_gap(raw)` as the intervals
   normalization helper, with `DetectedEvent`, `GapKind`, `GapReading` exported additively. That
   helper carries a **named future consumer and an expiry condition**, recorded in the F06 section
   below rather than left as an intention: the risk it holds is not deferred-scope creep but
   **orphan code**, since pure normalization with no MVP caller can pass a review *by looking like
   normalization* and then prove nothing about any behaviour. F06 must consume it or it is deleted.
   Ordering is documented as a total order — timestamped events first by
   `(timestamp_value, family_rank, record_index)`, untimestamped after by
   `(family_rank, record_index)` — which matters because `stints` and `drivers` carry no timestamp
   at all. Over the real fixtures it emits **1,648 events**, and the writer's evidence shows no
   `overtake` event of any kind, lap 1 carrying no lap-time claim, all 1,331 `+1 LAP` strings
   classified without a numeric cast, the three pit durations kept distinct, and the null
   durations, null `date_start` and 846 partial segment arrays surviving as explicit unknowns.
   **The writer declined to modify `events.py` and said why**: `EventEnvelope` requires an aware
   `event_time`, which cannot represent a stint (no timestamp field) or the null-`date_start` lap
   without inventing a clock, so the collector owns its own `DetectedEvent` and reuses `EventType`.
   That is the right call, and it is recorded because editing an already-approved file to fit new
   code is exactly the kind of drift this project keeps refusing.
   **Two interpretation decisions the brief left open, disclosed rather than buried**: a
   null-duration lap **still emits** a completion event carrying `lap_duration` as unknown instead
   of being filtered out (reading "where a duration exists" as "no timed claim"), and position
   events are emitted **per deduplicated record** with no cross-record previous-position state and
   no cause claimed. Both are defensible against the registered design and both are the likeliest
   review contention, so they are named here.
   **The evidence weakness, stated plainly.** The collection RED was an `ImportError` recorded
   separately, and the behavioural RED was **18 tests failing with `NotImplementedError` at their
   first call against a no-logic stub** — so **no assertion in any test was ever observed failing
   against a real implementation**. Disclosed by the writer, not discovered by the parent. It makes
   this the weakest RED evidence in the project so far, and it means the acceptance tests' efficacy
   rests entirely on the independent verifier's mutation testing rather than on any RED. Dedup has
   the same shape of problem in miniature: it is **unexercisable on the real fixtures** because no
   family repeats an update, so it is proven only synthetically.
   **Independent verification PASS, 8/8 mutants killed with no survivor.** Verifier
   `mv2ze9ly-1n-fguu` confirmed the three pins unchanged at start and end, the **574 additions / 0
deletions** count, `events.py` and the `fixtures/` tree byte-identical, 18 focused and 573 full,
   two runs byte-identical, the documented total order exactly as written, and **all 1,648 events
   tracing back to their exact source record**. On the real fixtures it independently reproduced the
   non-claims: no overtake spelling anywhere, position evidence exactly `{"position"}` with no cause
   claim, 20 lap-1 completions with no lap-time record to enter, and the unknown-preservation for the
   two null durations, the null `date_start` (with a stated reason rather than a borrowed clock) and
   the 846 partial segment arrays. It also **confirmed the parent's static judgement** that the two
   auxiliary numeric-parse warnings are false positives, with the nuance that Unicode decimal digits
   pass `\d` but `int()` accepts them, so nothing breaks. It read both interpretation decisions as
   **consistent with the registered design**, not departures. Kills by mutant: overtake emission,
   lap-1 record, gap coercion, pit-duration collapse, null coercion, order change, dedup removal and
   foreign-session attribution.
   **One real robustness hole it found, and the fix is underway before review.**
   `classify_gap(10**400)` — an **oversized integer**, which a corrupt payload could genuinely carry
   because JSON parses a long integer literal into a Python `int` — raises **`OverflowError`** from
   `float(raw)` at `collector.py:196` instead of returning an unknown reading. That contradicts the
   design's own spine, that a missing or unusable value stays **unknown** rather than crashing, so it
   is being fixed rather than carried: the guard must catch the overflow and yield `UNKNOWN`, with a
   test proving the huge-int case does not raise. It is **not** fixture-reachable, which is why it
   survived the writer's own testing, but "not reachable today" is not "cannot happen".
   **Thinness noted, not fixed:** three of the eight mutants were killed by exactly **one** test each
   (null coercion, dedup, foreign session), and the untimestamped tail order is pinned only through
   a final-element assertion — effective but thin, which belongs with the probe-promotion work in
   issue #8 rather than in this unit.
   **Correction applied and re-verified, inside the same uncommitted unit.** The overflow hole was
   fixed rather than carried: `collector.py` `2be54125…`→`d5d2fe23…` and `tests/test_collector.py`
   `50b5c2cd…`→`fa83fa15…`, five tests appended, **23 focused / 578 full** on the 573
   pre-correction total. **This correction produced the genuine RED the original unit lacked**: on
   the pre-fix source the oversized-integer tests failed with the real `OverflowError` and the
   non-finite test failed on `SECONDS` versus `UNKNOWN` — 3 failed / 20 passed before, 23 passed
   after. A non-finite numeric now classifies as unknown as well; that is a **parent decision, not
   the verifier's finding**, and it is labelled as such in the source comment, both docstrings and
   the test comment so the record does not misattribute it.
   Focused re-verification `mv2zsp18-1p-7ehx` PASS, and it went beyond the brief: it rebuilt the
   pre-fix collector in a shadow and showed the new tests fail there with the real `OverflowError`
   while the fixed control passes, and — because the earlier verifier's pre-fix copy **survived under
   `/tmp`** — it could prove the test change is **strictly append-only: 0 lines removed, 67 added**,
   with the collector diff confined to `import math`, one module-docstring line, the `classify_gap`
   docstring and the guard body. It confirmed the total-order and dedup code untouched, the
   classification deterministic across two passes over all 21,041 interval values, the
   parent-decision labelling present and unmisattributed, and the writer's disclosed docstring slip
   fully repaired: both files parse, `inspect.getdoc` is well-formed, indentation correct, no
   trailing whitespace.
   **A trap worth carrying forward.** Its first shadow attempt silently imported the **original**
   module, because copying the repository's `.venv` baked the original paths into the launcher, and
   the outcome was a **false pass of 23 tests**. It caught that with an import proof and switched to
   a `.venv`-free tar shadow. The lesson generalises: a shadow test without an import proof can pass
   while proving nothing, which is precisely why every shadow instruction in this project demands
   that proof.
   **Native review and closure.** Native `review-d4ba1e2b466ba724`, medium / one reliability lens /
   3 files / 657 lines / budget 200, approved on the **first** reviewer run; exact bound STATUS/ack
   returned authority **burned**; consumed revision
   `sha256:67058111919ffbd55e420d1ee0816e6dea3f2e63f8550ef17c9700a99f2a680b`; never query it again.
   Local unit commit **`893fa5b521ac894e23ab9ae707fe4a6cef8c2bf9`**, Conventional Commit
   `feat(collector): derive deterministic session events from recorded fixtures`, three paths,
   **+657/−0**, with reviewed = staged = committed tree
   `93782d7536fe7174a1c58c444a15fa51c9b60874`.
   Four informational findings, no correction opened and **no bodies returned**, carried rather than
   reconstructed: `R3-unhashable-identity` a **warning** at `collector.py:245-249`,
   `R3-gapreading-cross-kind` at `:121-131`, `R3-fromisoformat-version-tail` at `:170-175` and
   `R3-fixtures-outside-candidate` at `tests/test_collector.py:26-33`.
   **The warning was reproduced by the parent in one line and is being fixed, not carried.** The
   dedup key is a member of a `set`, so a payload whose identity field holds a **list or a dict**
   raises `TypeError: unhashable type` against the committed module. It is reachable precisely
   because the signature declares `Mapping[str, object]` values and JSON can put a list or an object
   anywhere, so the function is not total over the input type it advertises. That is the **same
   defect class as the overflow**: a corrupt payload crashing the collector instead of being
   handled, against a design whose spine is that unusable values stay unknown. The other three
   suggestions are carried as informational, since they describe type-level invariants and a
   version-dependent `fromisoformat` tail and none is a demonstrated defect.
   **The warning's correction is committed as `cfbe6148202d8d7328b88b90f15807319d8b055f`**,
   `fix(collector): make the dedup identity hashable for any payload value`, two paths
   **+164/−2**, with reviewed scope checks clean and the non-allowed trees byte-identical. The
   identity field is now a **type-tagged token**: the type name plus the value when it hashes, and
   plus a canonical `json.dumps(..., sort_keys=True)` rendering otherwise. The type tag also closes
   a latent conflation the raw key had, where `1`, `True` and `"1"` were the same identity, and the
   **raw value still appears in the event evidence**, so a corrupt record is no longer fatal but is
   not hidden either. No validation, skipping or refused-record concept was added.
   **No native review was run for this correction, and the reason is the provider's own gate.**
   ASSESS returned medium with **`reviewDue: false`, `reviewDueReason: under_budget`** at 166
   changed lines, and `independentVerifier: false`. Following that returned plan rather than
   over-riding it is deliberate: spending a reviewer on a bounded correction of a warning that a
   reviewer already raised is exactly the workload the gate exists to avoid. Stated openly so the
   omission is a decision on the record, not a gap discovered later.
   **What the parent established itself, since no third party did.** It reproduced the crash before
   the fix and confirmed both one-liners now emit an event instead of raising; it confirmed the new
   auxiliary lint warning at `collector.py:253` is the same guarded-regex false-positive class as
   before, now at a new line number; and it proved the behaviour claim **element by element** rather
   than by digest: a `/tmp` shadow built from the pre-fix collector at `893fa5b` (with an import
   proof, `d5d2fe23`) and the current module both produce **1,648 events, identical
   element-by-element**, so the correction changes nothing about the recorded stream.
   **A false negative the parent nearly accepted, worth recording.** The first comparison used the
   parent's own invented canonicalization and **the digests did not match** (`495caf2d…` against the
   writer's `bb845138…`). That was a serialization difference, not a behaviour difference: comparing
   two different canonical forms proves nothing in either direction. Redoing it against the same
   objects element by element is what settled it, and the lesson is that a digest comparison is only
   meaningful when both sides share the exact canonical form.
   **Residuals disclosed, not fixed:** a value whose own `__hash__` raises something other than
   `TypeError` still propagates, deliberately narrow because it is unreachable from JSON; and the
   `repr` fallback is insertion-order sensitive, so two equal dicts with **mixed-type** keys need not
   deduplicate, while every `str`-keyed payload goes through `json.dumps` and does.
3. **F08 — Gemini gateway**, exercised against a fake provider, with one separately granted real
   generation to prove the wiring. One model call is a budget decision, not an assumption.
4. **F09 — the two-person booth.** Lead and colour personas, explicit turn order, bounded context,
   evidence-only sourcing, degradation that is neutral rather than invented.
5. **Thin F10 — CLOSED as `20af86f9139d28e6be4ea8b15890b10a8b9551b1`; the closure record with its
   evidence is under "Current next step".** One command that runs
   replay → events → booth → a transcript, in one process. Not the multi-service shape: no Redis, no
   bus, no venue.
   - **New module `src/f1show/run.py`** plus `tests/test_run.py` and additive root exports. The
     composition entry point takes its dependencies **injected** — the replay source, the store, the
     clock and a model client — so the whole path is exercisable offline with a fake provider and
     stays deterministic. Nothing here builds its own HTTP client, opens a store or reads a clock of
     its own.
   - **`main()` must make a live call impossible by accident.** It takes an explicit, **required**
     provider selection with no default, so the offline path is chosen rather than fallen into and a
     real call cannot happen by omission. The fake path is exercised by tests end to end; the gateway
     path is not, because a real generation needs its own grant.
   - **The registered composition requirement is part of this unit, as a proof and not a claim**: the
     base URL is derived **per dialect in memory** — stripping a trailing version segment before the
     native SDK appends its own — and the derivation is exercised against **both** declared forms, one
     carrying `/v1` and one carrying no version segment, as two parameterised cases whose composed URL
     is **captured from the wire** rather than rebuilt. A normalisation written only for today's shape
     would fail silently the day an operator changes the declared value and land back on the 404 that
     took three rounds to diagnose. The declared value itself is **not** changed by this unit: its `/v1`
     is load-bearing for the gateway's OpenAI-compatible surface.
   - **No model id may appear in code or configuration.** It is supplied at runtime; the enumerated ids
     are gateway aliases and not provider contracts.
   - **The transcript is the deliverable**: the two personas' turns in order, with the evidence each
     turn used, so a reader can see the product's claim rather than infer it. Degradation stays neutral
     — a provider outage produces a stated absence, never invented commentary.
   - Checks: offline end-to-end over the **recorded fixtures** through replay, events and booth, with a
     fake provider, asserting turn order, evidence propagation and a stable transcript; the two base-URL
     cases with wire-captured URLs; refusal of a missing provider selection; and that no live call is
     reachable without the explicit selection. Forecast 250–500 lines, to be read as a lower bound.
   - F10 does **not** carry the F09 review's carried findings into its diff: they are registered with
     owner and trigger instead.

**Deferred from the MVP, with the reason:** **F05** Redis fan-out is infrastructure for services
that do not exist in a single-process MVP; **F06** tactical analysis is value added on top of
rather than a precondition for commentary; **F07** Jolpica enrichment adds historical colour but
not the core claim; **F11** Docker packaging is deployment, not demonstration; **F12**'s CI job is
tracked as issue #7; **F13** live is gated on a purchase the user declined for now. F03d's auth and
live seam sit **off the MVP path entirely** under free mode.

**Forecasts are lower bounds.** This project has overrun them consistently — F03c 2,620 against
~1,000, F03d-1 998 against 450, F03d-2 883 against 300–500 — so the MVP estimate must be read with
that multiplier in mind, and each unit still runs its own verification, native review and commit.

### F04 — Implement deterministic collector and event detection

- [ ] Normalize positions, laps, sectors, flags, intervals and pit/stint data;
  deduplicate updates and preserve evidence timestamps/source fields.
- Acceptance/checks: replay proves fastest laps/sectors, position changes, flags,
  SC/VSC and pit events; no false first-lap record or inferred on-track overtake
  from a position change alone. Split event families into units when necessary.
- Depends on F03. Commit/checks: pending.

### F05 — Implement Redis Streams delivery and fan-out

**Deferred from the MVP** (see the MVP cut above): single-process fan-out is not needed to prove
the two-persona commentary claim.

- [ ] Define stream names, versioned envelopes, separate consumer groups for
  analyst/historian, acknowledgements, idempotency, recovery and retention limits.
- Acceptance/checks: local Redis tests show both enrichers receive each event,
  bounded backlog, duplicate safety and recovery after crash/pending messages.
- Depends on F02/F04. Commit/checks: pending.

### F06 — Implement deterministic tactical analysis

**Deferred from the MVP** (see the MVP cut above): tactical alerts add value on top of commentary
but are not a precondition for it.

**A named handoff, not a promise.** F04 ships `classify_gap(raw)` — a pure classifier turning one raw
`gap_to_leader`/`interval` value into absent, unknown, seconds or laps — and **F06 is its intended
consumer**: the tactical reading of gaps is exactly what F06 defers today. The specific case F04
pre-validates against the real fixture is the **`+1 LAP` string form** (1,331 of the 21,041 interval
values, alongside 19,604 numbers and 106 nulls), which is the one that would otherwise be mis-cast
to a number by a naive implementation.

**The condition attached to it, recorded before it can be forgotten.** F06 must either consume this
classifier or **delete it**. That is not a stylistic preference: the danger is not scope creep but
**orphan code** — pure, plausible-looking normalization with no MVP caller can survive a review
precisely *because* it looks like normalization, and then sit in the tree forever with tests that
prove nothing about any behaviour. Naming the recipient converts it from a promise into a handoff
with a deadline. If F06 lands and does not use it, removing it is the correct outcome, not keeping it
out of politeness.

- [ ] Calculate contextual gap/pace/stint alerts with configurable circuit/session
  parameters. Treat tyre-life and pit-loss estimates as assumptions, not facts.
- Acceptance/checks: qualifying cutoffs follow the selected season/session rules;
  tests cover boundary values, lapped/null intervals, missing telemetry, pit
  interference and stale data. No hardcoded Monza or unqualified strategy claims.
- Depends on F04/F05. Commit/checks: pending.

### F07 — Implement evidence-grounded historical enrichment

**Deferred from the MVP** (see the MVP cut above): historical colour is not the core claim, and its
Jolpica pagination work is unrelated to proving the booth.

- [ ] Query Jolpica-style archives with verified driver/circuit mappings, bounded
  caching and source/as-of attribution. Remove fabricated circuit defaults.
- Acceptance/checks: fixture-backed stats, pagination and identifier tests; unknown
  records stay absent, failures skip trivia, caches remain session/circuit-safe.
- Depends on F01/F05. Commit/checks: pending.

### F08 — Implement the current Gemini gateway and safeguards

- [ ] Use async `google-genai` with explicit verified model IDs, output bounds,
  request timeout, bounded retries/concurrency and measured usage accounting.
- Acceptance/checks: fake provider tests cover 429/5xx, timeout, missing/invalid
  responses and the **measurement and alerting** path. **Corrected by F01: this task
  does not implement a spend ceiling.** Per-session spend is uncapped by user decision
  and the pilot total is approved at F13, so F08 measures, reports and alerts, and its
  output must state plainly that reported token usage is not a hard spend limit and
  that no hard cost stop exists before F13.
- Depends on F01/F02. Commit/checks: pending.

**Parallel track, authorized 2026-10-10: F08 runs in an isolated linked worktree.**
The fixture recording (MVP step 1) is committed on its own branch in the main worktree, so
F08 must not touch that tree: it works in `../F1Show-f08` on branch `feat/f08-gemini-gateway`,
cut from `0b1f0c7`. This is a side track, not a chain slice — F08 declares no dependency on
the fixtures and reads none of them. Every commit stages **explicit paths**, never
`git add -A`, so untracked or committed fixture artifacts are never swept into an unrelated
commit. The shared task file and its Engram mirror are the collision surface: the parent edits
this file on its own branch and records the F08 track under `f1show/f08-gemini-gateway` rather
than rewriting the split tasks mirror while the step-1 session owns it.

**Concrete design, registered before the first write.**

- **Two classes in one new module, `src/f1show/gemini.py`, both implementing the existing
  `ModelClient` port.** `GoogleGenAIClient` is the thin adapter over an **injected** async
  `google-genai` client: the caller constructs `genai.Client(api_key=...)` at wiring time from
  `CredentialsSettings.gemini_api_key`, so this module never reads, stores or formats a
  credential (composition-ownership precedent: `auth.py`). `SafeguardedModelClient` wraps any
  inner `ModelClient` and owns timeout, bounded attempts, bounded concurrency and usage
  accounting, mirroring the wrapper convention of `request_policy.py`. Splitting them is what
  makes the safeguards testable offline: the whole policy layer runs against scripted doubles,
  and only the adapter's mapping touches the SDK.
- **Attempt budget reuses `RetryPolicy`** from `request_policy.py` for `max_attempts`,
  `base_backoff_seconds` and `max_backoff_seconds`, so the backoff arithmetic, the no-jitter
  rule and the attempt accounting are not re-implemented. Its HTTP-only fields
  (`retryable_statuses`, `max_retry_after_seconds`) are unused on this path, and that is stated
  in the code rather than papered over with a parallel policy type; retryability is decided by
  the **typed** errors below, not by an HTTP status. Waits are spent through the injected
  `MonotonicClock.sleep`, never a private clock, so tests observe exact virtual durations.
- **Timeout is enforced once**, by `asyncio.timeout(request.timeout_seconds)` around a single
  attempt, and becomes `ModelTimeoutError`. No second SDK-level timeout knob is invented: two
  budgets would be two behaviours to reason about.
- **Bounded concurrency** is an `asyncio.Semaphore` of caller-supplied size, with no default
  that silently serialises or silently unlimits. Every concurrency test bounds its waits with
  `asyncio.wait_for(..., timeout=...)` plus `pytest.fail` naming the hazard, because the
  F03d-2 lesson is that an unbounded wait turns a suite that should fail into one that hangs.
- **Typed, sanitized failures**, all exported, under a `ModelError` base:
  `ModelTimeoutError`, `ModelRateLimitedError` (429, carrying an optional server-advised
  delay), `ModelServerError` (5xx), `ModelTransportError` and `ModelResponseError`. Retryable:
  rate-limited, server, timeout, transport. Not retried: a malformed or blank response, on the
  `HttpDecodeError` precedent. **No raised error, `repr` or log line may carry the prompt text,
  the API key or the raw provider payload.**
- **Output bounds**: `max_output_tokens` from the request is mapped into the SDK generation
  config, and a missing, blank or non-text response becomes `ModelResponseError` instead of an
  empty turn. `ModelResponse.model_id` **echoes the requested id**; the provider's own model
  naming is never trusted or rewritten into our transcript.
- **Usage accounting and alerting**: a new pydantic `ModelUsage` (model id, input, output,
  total, attempts) plus an in-process accumulator, an optional `on_usage` observer called once
  per successful call, and a warning through the redacting logger when a caller-supplied token
  threshold is crossed. The threshold is a constructor argument, not a new configuration
  section, so `config.py` and its tests are untouched. **Measured usage is not a hard spend
  limit and no cost stop exists before F13** — that sentence belongs to the module's own
  documentation, not only to this file.
- **Model IDs stay injected.** `model_id` has no default and no literal appears in this module
  or its tests, per the standing rule that no model ID may enter code or configuration before
  account enumeration and current documentation verify it; the earlier enumeration attempt
  (401 with `GEMINI_API_KEY`, `IndexError` through the local proxy) did not verify one. The
  separately granted real generation that proves the wiring stays a future grant.
- **Offline checks, with the honest limit stated.** The policy layer runs against
  `ScriptedModelClient` plus local scripted failing doubles and `FakeMonotonicClock`; the
  adapter runs against a local fake with the SDK's async surface, plus one **contract probe**
  that imports the installed `google-genai==2.29.0` and asserts the callables and config fields
  this mapping depends on exist. That probe is a version-pinned assumption about a third party,
  not proof: real 429 shapes, `usage_metadata` presence and truncation semantics stay
  unverified offline and belong to F13.
- **Allowed edit surfaces** for the writer: `src/f1show/gemini.py` (new),
  `tests/test_gemini.py` (new), and additive exports in `src/f1show/__init__.py`. **Do not
  touch** `config.py`, `ports.py`, `fakes.py`, `request_policy.py`, the fixture artifacts, or
  any other module. No new dependency and no lock change: `google-genai==2.29.0` is already
  pinned and installed.
- **Forecast**: 350–550 authored diff lines. The recorded history of this project is that
  forecasts are lower bounds, so an oversize diff is disclosed rather than compressed by
  dropping tests or documentation. Verification, native review and the work-unit commit follow
  the usual path.

**Implementation, verification and native review (observed). Status: implemented, independently
verified and natively reviewed on the fake-provider path, and NOT closed** — the verified model ID
and the separately granted real generation remain pending, so this task keeps its unchecked box.
No live call, credential or purchase was made for this unit.

- Writer `mv2z2j6g-1-oq1i` (`gentle-ai-worker`, background) returned three paths:
  `src/f1show/gemini.py` **567** lines, `tests/test_gemini.py` **1191** lines and
  `src/f1show/__init__.py` **+21/−2** — **1758 authored lines against the 350–550 forecast
  (3.2×, disclosed, no test or docstring trimmed)**.
- **RED was observed, not reconstructed.** Stage (a) collection: `1 error in 0.34s`,
  `ModuleNotFoundError: No module named 'f1show.gemini'`, zero tests collected. Stage (b) with the
  module present as signatures only raising `NotImplementedError`: **54 failed / 2 passed**, and the
  writer **named the two trivial passes** (the installed-SDK contract probe and the export-shape
  test) instead of presenting the whole RED as behavioural. GREEN: focused 57, full **612**
  (baseline 555).
- **Parent spot check** (required): the three file hashes identical to the writer's report, 612
  passed, the nine public names resolve from the package root, no model ID literal and no credential
  read anywhere in the candidate, and additivity confirmed — the `f1show.gemini` import block and the
  `__all__` lines are purely additive and correctly ordered, with the only replaced lines being the
  module docstring the writer legitimately extended.
- **A discrepancy the parent found, and resolved without smoothing it over.** The writer's "ruff
  check: all checks passed" claim is **not reproducible**, because this repository **commits no ruff
  configuration at all**, so the verdict depends on the rule selection each caller chooses. The
  parent's probe on the two new files returns one `RUF100` (`tests/test_gemini.py:68`, an unused
  `# noqa: S105`), which is established house style in six other files and part of 56 findings the
  tree already carries under ruff's defaults. Recorded here as a **configuration gap** (F12
  territory, where the linter decision was deferred) — **not** as a defect of this candidate, and
  deliberately not fixed inside it.
- Independent verifier `mv2zugyb-2-3y6w` **PASS**: counts reproduced (focused 57, full 612 in the
  worktree), the three candidate hashes byte-identical before and after its work, and **10/10 named
  mutants killed with no survivor and no behaviourally equivalent mutant** — the per-attempt timeout
  guard, attempts off-by-one, an unbounded gate, dropped output tokens, a blank answer accepted, a
  non-retryable failure retried, a rate-limited failure not retried, constant instead of doubling
  backoff, the alert firing on every call, and a provider exception chained into the raised error.
  It also turned the writer's two "covered by code reading only" declarations into **observations**:
  the gate slot really is released while the client sleeps in backoff (real clock, two callers,
  time-bounded probe, sensitivity validated against a shadow mutant that holds the slot), and an
  expired deadline produces `ModelTimeoutError` with `__cause__`/`__context__` both `None` and no
  prompt text anywhere in the walked chain. Its method note is worth keeping: **a copied
  `.venv/bin/pytest` shebang points back at the source worktree's interpreter**, so copy-based
  experiments silently test the original tree unless they run `python -m pytest` against the copy —
  its first mutant runs were invalid for exactly that reason and it said so.
- Native review `review-12ddb2c2a11e69e8`, tier **medium**, **one** consolidated lens
  (`review-reliability`), 3 files, **1781** changed lines, correction budget 200. Its forecast was one
  host-relay model run, acknowledged, and the review **approved on the first reviewer run with no
  correction opened**. The exact acknowledgement **burned** authority (`consumed_revision
  sha256:1d9d59b9114c1fae10ddf2435c702e19ccf5390534c17f7989ffcfec4dcf91c9`,
  `gentle-ai.review-acknowledged/v1`) and no STATUS was issued after the burn. Three informational
  findings with **no bodies returned**, carried as later work and not reconstructed: `R3-001`
  (WARNING) `src/f1show/gemini.py:479-482`, `R3-002` (SUGGESTION) `tests/test_gemini.py:932-959`,
  `R3-003` (SUGGESTION) `src/f1show/gemini.py:562-563`. The acknowledgement was deliberately deferred
  until the independent verifier returned, because a correction after a burn costs a fresh review
  round.
- **Committed** as `b56a2fee771791e282890c15d766f4f57efea34c`, Conventional Commit
  `feat(gemini): add the Gemini gateway with bounded retries and usage accounting`. Reviewed =
  staged = committed tree `11dc44c76062630fd9ad187fbffe5eb7d957d275`, identical to the tree the
  controller froze; clean worktree after the commit; 612 passed afterwards; no push.
- **Two hardening recommendations from the independent verifier, carried as later work and not
  silently applied**: honour `max(retry_after, backoff)` clamped to a documented ceiling before
  F13's live calls — the server advice is already parsed and carried, so only the policy decision is
  missing, and repeated early contact could extend a real quota lockout — and escalate a run of
  consecutive observer failures instead of logging the class name only, so that a persistent usage
  sink failure cannot under-report silently while the answer still returns.
- **Honest limits carried into the record.** Real provider 429 body shapes, whether
  `usage_metadata` is always present, and truncation semantics remain unprovable offline; the two
  contract probes are version-pinned assumptions about `google-genai==2.29.0`, not proof. Measurement
  is incomplete **by port design**: thinking tokens never reach `ModelUsage`, and a response without
  usage metadata records zero — an under-report, never an invented number. The gate wait sits outside
  `request.timeout_seconds`, so a caller needing a total deadline must bound `generate` itself. The
  usage observer's failure is swallowed by design so a reporter can never discard a paid answer. And
  because **no model ID is verified**, `model_id` stays injected with no default: the separately
  granted real generation that proves the wiring is still pending and is not claimed here.
- **Integration handoff, agreed with the step-1/F04 session.** This track lives on
  `feat/f08-gemini-gateway`, cut from `0b1f0c7`. At integration **their version of this file wins**
  and this block is re-applied by cherry-picking this track's **three documentation commits**
  (`11f78c8`, `f7e7412` and the one that adds the rules below) in order during that resolution
  (their document still carries the exact anchor, so they apply cleanly in sequence);
  `src/f1show/__init__.py` is the only shared file and both changes are additive; the split Engram
  task mirror stays with them and they fold this evidence in.
- **Two project rules this track produced, recorded here because an anecdote does not survive.**
  (1) **A copy-based verification must prove which source it imported.** Two independent sessions hit
  the same trap in one day: copying `.venv` bakes the original worktree's paths into the launcher, so
  `pytest` silently imports the original package — the F04 track's re-verifier passed **23 tests in
  false** before an import proof caught it, and this track's verifier discarded its first mutant runs
  for the same reason. Any shadow or copy used for mutation must print the imported module path
  (`inspect.getsourcefile`) before its results count. (2) **A lint claim must name its rule
  selection or it is not evidence.** This repository commits no ruff configuration, so the effective
  rule set lives outside it, in whatever selection each caller's harness provides: the same tree
  either "passes all checks" or reports findings depending on that selection, and every
  `# noqa: S105` directive reads as unused without `S` selected. Tracked in issue #7.
- **A second review pass over byte-identical content, and what it found.** The step-1/F04 session
  reviewed the integrated range — their resolution plus these bytes — and it approved, producing
  **six informational findings, all in `gemini.py`** and none in the resolution or the documentation:
  `R3-001` (WARNING) `:484-488`, `R3-002` `:477-480`, `R3-003` `:348-354`, `R3-004` `:258-259`,
  `R3-005` `:488`, `R3-006` `:559-566`. No bodies were returned and none are persisted, so the parent
  read the regions rather than inventing provider intent; **the readings below are ours, not the
  provider's**:
  - `:477-480`, `:484-488` and `:488` (the WARNING): the retry loop catches the builtin `TimeoutError`
    — which is also the OS and transport timeout, not only our deadline — and relabels it as
    `ModelTimeoutError`; and it re-raises the captured failure with a bare `raise failure`, discarding
    the original exception and its traceback. The taxonomy stays typed and sanitized, but a caller
    debugging a live failure loses the cause. Carried, not fixed: these bytes are approved and burned,
    so any change here is a new candidate with its own review.
  - `:258-259`, and this one is **checkable rather than a guess**: `_classify_provider_failure` reads
    `getattr(exc, "code", None)` and requires an `int`. The installed SDK's own source
    (`google.genai.errors.APIError.__init__`) sets `self.code = code if code else
    self._get_code(response_json)`, and `_get_code` passes through whatever the response JSON carries —
    so a provider returning `"429"` as a **string** yields `code == "429"`, the classifier declines to
    classify, and the failure is re-raised **without being retried**. Our offline tests cannot see it
    because the scripted doubles construct the error with an integer. Recorded as the most
    consequential of the six and as live-path work (F13), where a rate limit is exactly what must be
    retried.
  - `:348-354`: `_to_model_response` refuses blank text but stores the provider's text **unstripped**,
    unlike `dialogue.Turn`, which strips. Cosmetic today and invisible until a provider pads.
  - `:559-566`: the threshold warning latches once per wrapper while its message names a model, so a
    second model crossing the same threshold inside one wrapper never warns. Consistent with the
    documented "a crossed threshold is a state, not a repeated event", but the wording and the latch
    disagree about scope.
  - **Worth recording as a fact about our process**: our own verification (10/10 mutants) and this
    review examined byte-identical content and the review still produced six findings the mutant
    matrix did not. That is not a defect in either method — it is evidence that a mutant matrix tests
    the invariants we already thought of.
- **The granted real call, and what it did and did not prove (2026-10-10).** The remainder of this
  task was granted as one metadata call plus one minimal generation, and it completed. The configured
  endpoint is a **loopback gateway** (`http://127.0.0.1:8317/v1`, no credentials embedded in the URL).
  Its **OpenAI-compatible** surface answered `GET /v1/models` with **200 in 0.02 s** and twelve model
  ids (`claude-opus-4-6-thinking`, `claude-sonnet-4-6`, `gemini-3.7-flash-high`, `gemini-3.8-flash-high`,
  `gemini-3.1-flash-image`, `gemini-3.1-flash-lite`, `gemini-3-flash`, `gemini-pro-agent`,
  `gemini-3.1-pro-low`, `gpt-oss-120b-medium`, `gemini-3.5-flash-lite`), and
  `POST /v1/chat/completions` with `gemini-3.5-flash-lite` returned **200 in 0.82 s**, the text `ok`,
  usage 8/1/9 and a `model` field echoing the requested id. **Two** HTTP requests in total, no retries,
  no other host; the credential was read by line-splitting in a subprocess and never printed, hashed
  or logged. The failed first attempt is part of the record too: it requested
  `{base}/v1beta/models`, but the configured base already carries `/v1`, so the path doubled and the
  server answered 404 in 0.02 s **without any provider being contacted** — the ambiguity was the
  parent's brief, not the gateway, and the same defect was found by measuring the base instead of
  assuming it.
  **What this does not prove, and it matters**: those ids are **gateway aliases** — the `-high`/`-low`
  suffixes encode the gateway's own effort tiers — so they are not first-party model ids and none may
  enter configuration until the first-party documentation and this list are reconciled; the `model`
  field is gateway-reported, so the wiring works while the serving weights stay unverified; the list is
  what the gateway reaches **today**, not a stable contract; and **our `GoogleGenAIClient` was never
  exercised**, because it speaks the native Gemini dialect, whose correct path on this gateway remains
  unprobed while the route that worked is the OpenAI-compatible one. That native-dialect compatibility
  is the one remaining wiring unknown, and it belongs to F10's composition rather than to this unit.

### F09 — Implement the two-person commentary booth

**MVP-critical.** Its dependency line below is superseded by the cut: the booth depends on F08 and
on whatever event families F04 actually delivers, **not** on the deferred F06/F07.

- [ ] Implement lead/color personas, explicit turns, bounded history and structured
  transcript output using only current events and attributed enrichment.
- Acceptance/checks: fake-model tests prove ordering, evidence propagation,
  repetition suppression, stale-context exclusion and neutral outage behavior.
  Generated text quality still needs a separately authorized real-model trial.
- Depends on F06/F07/F08. Commit/checks: pending.

**Assigned to this track on 2026-10-10 by the step-1/F04 session**, which reserves the integration of
F08 into the shared branch and then thin F10. The F09 branch is therefore cut from **their integrated
tip**, not from the F08 side track, so the booth lands on the same tree as the F04 events and the
already-integrated gateway, and nothing (least of all `b56a2fe`) is cherry-picked twice. The design
below is registered while that tip is pending, because it depends on no code.

**Concrete design, registered before the first write.**

- **One new module, `src/f1show/booth.py`**, plus `tests/test_booth.py` and additive root exports.
  Allowed surfaces for the writer: those three paths and this document. **Not touched**:
  `collector.py`, `test_collector.py` and `fixtures/` (the F04 track's), `gemini.py` and the other
  F08 modules (frozen and already approved), and `dialogue.py`, whose `Speaker`, `Turn` and
  `Transcript` contracts are consumed as they stand rather than reshaped.
- **The booth composes, it does not transport.** Its inputs are injected: a `ModelClient` (the F08
  gateway already satisfies that port, but nothing here imports it), an ordered sequence of
  `DetectedEvent` from the F04 collector, `BoothSettings` for the model ID and the language — both
  required with no default, and the language is exactly the F01 gate item that had to be settled
  before F09 — and the bounds below. Wiring them together is F10's job, not this unit's.
- **Two distinct personas as data, not as prose inside code paths.** A `Persona` record carries its
  seat (`Speaker.lead` / `Speaker.color`), a display name and the register instruction that
  differentiates it. The differentiation is asserted by test, not claimed in a docstring.
- **Turn order is explicit and deterministic.** Lead first, then strict alternation, with a priority
  band (flags and incidents) that lets the lead take the next slot instead of waiting its turn. No
  randomness and no clock-driven choice, so one input always produces one order offline.
- **Context is bounded, and the bound is a constructor argument**: the current event with its
evidence, plus at most N prior turns and a character budget over their text. The immediately previous
  turn is always included; anything older is dropped whole, never truncated mid-turn.
- **Sourcing is evidence-only and structurally enforced.** Every emitted `Turn` carries a non-empty
  `evidence` tuple taken from the event's own evidence references and from attributed enrichment. A
  model answer that names no reference, or names one that was never supplied, is **refused** rather
  than emitted with a guessed citation, and the prompt is assembled from the supplied references only.
- **Repetition suppression and stale-context exclusion are acceptance behaviour, not polish.** A
  candidate that repeats the immediately previous turn is dropped, and an event older than the
  bounded window never reaches the model at all.
- **Two F04 constraints are hard rules here.** There is **no overtake event**, so the booth must never
  describe an on-track pass from a position change — it may report the position change itself and
  nothing more. And **lap 1 is excluded from every time comparison**, so no fastest-lap or gap claim
  may be anchored on it.
- **Neutral degradation, never invented.** On any `ModelError` (timeout, rate limit, server,
  transport, malformed or refused answer) the booth emits **no** turn for that event and records a
  typed degradation outcome that stays observable. No filler, no apology, no fabricated attribution:
  the transcript shows fewer turns, never a source that does not exist.
- **Offline checks against a scripted model**: persona differentiation, the explicit and
  priority-banded order, the bounded-window truncation rule, evidence propagation plus the refusal of
  an uncited or invented citation, repetition suppression, stale-context exclusion, and one scripted
  `ModelError` per family proving the neutral outcome. Every concurrency or ordering test bounds its
  waits, per the F03d-2 lesson. A real generation to judge text quality needs its own grant, and
  **no live call is authorized here**.
- **Review-candidate rule learned the hard way, and it applies to this track too.** The controller
  **refused** the F04 track's whole unpublished range with `lens_context_budget_exceeded` because the
  candidate carried the 3.6 MB of fixtures. So **fixtures never enter a review candidate**, candidates
  stay small, and an explicit `baseRef` is used instead of an accumulated range.
- **Forecast**: F08 delivered 1758 lines for a smaller surface, so read any estimate here as a lower
  bound — expect 500–900 authored lines, disclosed if exceeded rather than compressed.

**Correction C1, registered before the edit. Found by independent verification, reproduced by the
parent, after the review had already approved the first candidate.**

- **The violation, with the exact input.** With a model answer of
  `EVIDENCE: position[0].position\nEVIDENCE: position[99].invented\nVerstappen is P3 on track.` the
  booth returns `OutcomeKind.TURN`: the aired turn's `evidence` is `('position[0].position',)` and its
  **text contains the never-supplied reference verbatim**. Reproduced by the parent against the
  shipped doubles, importing from the worktree and printing the imported module path.
- **Why it is a defect and not a nit.** The module's own contract says an answer citing a reference
  that was never supplied is refused. Only the first line is parsed and validated; every later line is
  treated as commentary and airs unvalidated. A model that ignores the one-citation-line rule is
  exactly the shape the refusal layer exists not to trust, so the unit's central structural
  guarantee — evidence-only sourcing — is false for that input.
- **Decision: the answer protocol requires exactly one citation line.** Any additional line whose
  stripped form starts with the citation marker makes the answer a **protocol violation**, and the
  turn is **refused with a typed, distinguishable reason** instead of airing partial validation.
  Refusal is the fail-closed direction and matches the module's existing stance (blank, uncited and
  invented references are all refused). The alternative — merging the extra citations — was rejected
  because it would accept an answer whose commentary boundary is undefined, and validating
  citations mid-prose would require inventing a parser this unit does not need.
- **Required tests, genuine RED first**: the exact two-line case above; an invented reference in the
  second line (must refuse, never air); a second line carrying an otherwise *supplied* reference (must
  still refuse as a protocol violation, not be accepted as an extra citation); and — so the fix does
  not over-refuse — a commentary line that merely *mentions* the marker mid-sentence after the first
  citation line must still air as commentary. The marker check must use the same marker the
  acceptance path uses, so the two cannot drift apart.
- **Surfaces**: `src/f1show/booth.py`, `tests/test_booth.py`, and additive exports in
  `src/f1show/__init__.py` only if a new public name is introduced.
- **Non-regression**: the full suite (691) stays green, and the ten independent mutants that were
  killed against the previous bytes must still be killed by the corrected bytes.
- **Review status**: the approved review `review-e102f9481318fa6f` is **superseded and deliberately
  never acknowledged** — an approval for bytes that are about to change is not a licence to commit
  them. The corrected bytes are a **new candidate with its own review**.

**Correction C2, registered before the edit. Found by the independent re-verification of C1.**

- **C1 is verified**, not merely implemented: the registered defect is now `OutcomeKind.REFUSED` with
  `BoothReason.MULTIPLE_CITATION_LINES` and **zero** turns, a second citation line carrying an
  otherwise *supplied* reference is refused too rather than merged, a single citation line still airs,
  the three refusal reasons are distinguishable, and **all ten mutants from the first verification
  still die** against the corrected bytes, including the two that target the parse path.
- **What C1 left unpinned, measured rather than argued.** C1 put the marker in one constant **for the
  parser**, but the prompt — the one place the model learns the marker — still wrote `EVIDENCE:` as two
  string literals. The re-verifier demonstrated the drift in both directions on copies: changing the
  prompt literals alone left the suite at **58 passed, silently**, which is a mass-refusal waiting to
  happen at runtime; changing the constant alone was caught only **accidentally**, because the test
  fixtures hard-code the marker inside their scripted answers. **No test pinned prompt↔parser
  agreement**, so the module's own "the two cannot drift" reading was too strong.
- **Decision**: the prompt interpolates the parser's marker constant, so the format taught and the
  format accepted have one source, and one test pins the agreement **in both directions** — the
  captured prompt must contain the parser's marker, an answer built with that marker must be accepted,
  and an answer built with a different marker must be refused. The drift experiment that previously
  passed silently must now fail.
- **Recorded, deliberately not corrected: the residual commentary channel.** A bullet-prefixed marker,
  `EVIDENCE :` with a space, a mention mid-line and a bare reference with no marker at all all air
  with the never-supplied string inside `turn.text` — while the **evidence tuple stays fully validated
  in every aired turn**. That is the boundary, and it is a real trade: prose is not structurally
  validatable, a stricter "any line containing the marker" rule would over-refuse, and one existing
  test deliberately pins a mid-line mention as legitimate commentary. Tab-indented, lowercase and
  CR/LF-joined variants *are* caught. The declarative remedy is already in the prompt's own rules, and
  the semantic half remains F13's authorized trial.
- **Surfaces**: `src/f1show/booth.py` and `tests/test_booth.py`. Non-regression: the full suite stays
  green and the ten mutants still die on the final bytes.

**Correction C3, registered before the edit. Test-only, and both items come from the final
independent verification of the pins C2 added.**

- **(a) The prompt-agreement pin is partial, and that is the same silent-drift class C2 existed to
  close.** It asserts that the marker appears somewhere in the rendered prompt, so **one**
  interpolated occurrence satisfies it. The verifier changed only the rule line back to a literal
  while the section header still interpolated the constant, and the suite stayed at **62 passed**: the
  prompt would teach two different markers while the parser accepts only one, which is exactly the
  mass-refusal mode at runtime. The pin must **count** the marker occurrences in the rendered prompt
  rather than find one, so a partial drift fails. Required evidence: after the change, the
  rule-line-only drift must fail a named test.
- **(b) `F09_EXPORTED_NAMES` asserts nothing about itself.** Setting it to `()` made the export test
  pass with **zero checks** (verified live). The list must be asserted non-empty and free of
  duplicates before it is used, the same standard the step-1/F04 session applied to its own `__all__`
  sweep.
- **Surfaces**: `tests/test_booth.py` **only**. If a production change turns out to be needed, stop
  and report it rather than making it: the production bytes are already verified and a change there
  invalidates everything above.
- **Non-regression**: focused stays green, the full suite stays green, and the two mutations above
  must now fail in `/tmp` copies while nothing else changes.

**Implementation, verification and native review (observed). Status: implemented, independently
verified in three rounds and natively reviewed on the fake-provider path.** The behavioural half of
the two F04 rules and every live-provider property remain F13's, and no live call was made here.

- Writer `mv318z31-3-4aat` delivered `src/f1show/booth.py` (**581** lines before corrections, **615**
  after), `tests/test_booth.py` (**746** → **1066**) and `src/f1show/__init__.py` **+13** additive —
  about **1694** changed lines against the 500–900 forecast, disclosed and not trimmed.
- **RED was observed at the writer's hand**: collection-stage `ModuleNotFoundError: No module named
  'f1show.booth'` with zero tests collected, then a signatures-only stub giving **42 failed / 1
  passed**, with the single pass **named as trivial** instead of presented as behavioural.
- **Independent verification ran three rounds**, every one of them on copies with an import proof
  (`inspect.getsourcefile`) pointing inside the copy — a copied `.venv` bakes the original worktree's
  paths into its launcher, and one round lost its first mutant runs to exactly that trap:
  1. `mv31qhn0-6-ru5j`: **10/10 structural mutants killed** — and it found the **citation-protocol
     defect** the review had not: a second `EVIDENCE:` line citing a never-supplied reference aired
     with that reference verbatim in `turn.text`.
  2. `mv34kzb6-9-usms`: after C1, **10/10 mutants still killed**; the corrected defect is refused
     with `MULTIPLE_CITATION_LINES` and **zero** turns; it measured the residual commentary channel
     and demonstrated the **silent prompt↔parser drift** (prompt literals changed alone → suite still
     green at 58 passed).
  3. `mv354vr0-b-v0nw`: on the final bytes, 10/10 mutants killed, the drift and export mutations
     reproduced **independently**, the **rendered** prompt inspected (exactly two marker occurrences,
     both from the constant), hygiene confirmed, and it found the two partial pins that C3 closed.
- **Three corrections, each from a measurement rather than a hunch**: C1 the citation protocol — a
  real defect against the unit's central claim; C2 the prompt interpolating the parser's constant —
  a silent drift path; C3 hardening the two partial pins, so the prompt pin now **counts**
  occurrences and the export list asserts non-empty and duplicate-free. The parent reproduced all four
  C3 mutations itself in a fresh `/tmp` copy with **its own** venv, where the import proof pointed at
  the copy and the four mutations failed in both directions.
- Native review of the **first** candidate `review-e102f9481318fa6f` (medium, one lens, 1340 lines)
  approved and was then **superseded and deliberately never acknowledged**: an approval covers exactly
  the bytes it covered, and those bytes changed. The final candidate was reviewed fresh as
  `review-25573bd84c132770` — tier **medium**, one lens `review-reliability`, **1694** changed lines,
  candidate tree `6b35c7067b138bc8564c13ba02f7ae74d71f111a`. One host-relay run, its forecast relayed
  **before** the acknowledgement (the order F08 got backwards), **approved on the first reviewer run
  with no correction opened**; the exact acknowledgement **burned** authority
  (`consumed_revision sha256:087bc92c…`, `gentle-ai.review-acknowledged/v1`), and no STATUS was issued
  after the burn.
- **Four informational findings, no bodies returned**, carried as later work and not reconstructed:
  `R3-bound-guards-uncovered` (`tests/test_booth.py:1039-1050`), `R3-persona-validator-uncovered`
  (`src/f1show/booth.py:116-122`), `R3-positive-seconds-overflow` (`src/f1show/booth.py:337`),
  `R3-render-repr-determinism` (`src/f1show/booth.py:318-321`).
- **Committed** as `52ab80f209aeceae153e3fae37df9a71e5517ba6`, Conventional Commit
  `feat(booth): add the two-person commentary booth with evidence-only sourcing`. The check that makes
  that sentence meaningful: the pre-commit `HEAD` tree equals the controller's `base_tree`
  (`b0f5e6b4…`), the **staged tree equals the reviewed candidate tree** `6b35c706…`, and the committed
  tree equals both — so the reviewed bytes **are** the committed bytes, established by tree identity
  rather than by reading a diff. Clean worktree afterwards, **705 passed**.
- **Honest limits carried into the record**: the semantic half of the two F04 rules stays unprovable
  offline (F13's trial); the residual commentary channel still airs a bullet-prefixed marker,
  `EVIDENCE :`, a mid-line mention and a bare never-supplied reference **while the evidence tuple
  stays validated in every aired turn**; duplicate-citation collapsing is behaviourally correct but
  untested; the prompt pin counts exactly two sites, so a legitimate third site fails until the count
  is updated; and the export pin encodes intent rather than completeness, since shrinking the list
  still passes.
- **Integration handoff**: five documentation commits (`718ff96`, `5b67fb6`, `9b01d88`, `bb5a6a9`,
  `7c01797`) plus this evidence commit, all touching only `odd/tasks/f1show.md`, and **one** source
  commit `52ab80f` with the three paths. The other session's version of this document wins at
  integration and its author re-applies these blocks at their anchors in order;
  `src/f1show/__init__.py` is the only shared file and both changes are additive.

### F09b — Close the residual citation channels

**Assignment received in writing from the step-1/F04 session on 2026-10-10**, with allowed surfaces
`src/f1show/booth.py` and `tests/test_booth.py` only, and the branch based on this track's own tip
`b1990de` so it does not depend on when that session integrates F09. No new features, no new personas,
no `collector.py`, no `fixtures/`, and no `src/f1show/__init__.py` — the hardening adds no public name,
because the new reason rides on the already-exported `BoothReason`.

**The objective, stated precisely enough to be checkable.** The assignment names four measured escape
channels — a bullet-prefixed marker, `EVIDENCE :` with a space before the colon, a mention mid-line,
and a bare reference with no marker — and forbids the third option of leaving them airing "because the
evidence tuple stays validated". The reframing that makes **one** rule close all four: **the guarantee is
about tokens, not lines.** What must never happen is a **reference-shaped token that was never supplied
reaching the aired text**. Every channel is an instance of that, and validating line *shapes* can never
cover the cases whose shape is undefined.

**Three decisions, each with its reason, and one new rule.**
1. **The violation check gets a tolerant predicate; acceptance does not widen.** A second line that is
   *citation-shaped* under a tolerant reading — an optional leading bullet, optional spaces before the
   colon, any case — is `MULTIPLE_CITATION_LINES`. Reason: a later-line escape is unambiguously a second
   citation attempt, and refusing it names the precise failure instead of the vaguer text rule, while
   acceptance keeps the exact shape the prompt teaches.
2. **A never-supplied reference-shaped token anywhere in the aired text is refused with its own typed
   reason** — a new `BoothReason` member (`UNSUPPLIED_REFERENCE_IN_TEXT`). Reason: this *is* the
   invariant, and it is the only rule that reaches a bare reference and a mid-line escape. The token
   shape is derived from the supplied references (`<family>[<index>].<field>`), not invented, and
   supplied references are never flagged.
3. **The deliberate over-refusal pin survives, and that is recorded rather than assumed.**
   `test_commentary_that_merely_mentions_the_marker_mid_sentence_still_airs` mentions the marker with
   **no reference token**, so it must keep airing: the new rule is content-based, not marker-based.
   Reversing a deliberate pin would need a stated reason, and this design does not reverse it.
- **Declared cost, fail-closed on purpose**: prose that coincidentally matches the reference shape and
  was never supplied is refused. That is the price of closing the channel, and it is the direction the
  assignment demands; the alternative — airing text we cannot validate — is the hole.

**The two pins the final verification asked for belong in this unit.** The duplicate-citation collapse
already works (`dict.fromkeys`) and no test covered it: pin order preservation and collapsing. And the
two pins that encoded intent rather than completeness: the prompt pin's residual is a literal
**identical** to the constant, which no runtime check can see, so it is pinned at the **source** level
(`booth.py` must contain no `EVIDENCE:` literal outside the constant), and the export pin must fail when
the list **shrinks** — whatever derivation is chosen, the observable requirement is that removing a name
from `F09_EXPORTED_NAMES` now fails.

**Required evidence.** RED **per channel**, reproduced **before** the fix on a copy whose import proof
points inside the copy, one named failing test per channel; then GREEN; the full suite green; and
mutation proofs for both pins (removing a name from the list, and reintroducing a marker literal). Every
ordering or concurrency test keeps its bounded wait, per the F03d-2 lesson.

**Order of work, and it is not negotiable**: implementation → parent spot check → **complete independent
verification** → native review → acknowledgement → commit. The previous unit paid a wasted model run for
running the review in parallel with verification.

**Implementation, verification and native review (observed).** Five writer passes, every one driven by a
measurement rather than by polishing: the objective; a real residual found by attacking the rule (a
fragment glued to a supplied reference); **my own dot-rule over-refusal** of a sentence boundary; the
invisible-character leaks an independent verifier found by attack (zero-width space, NBSP, newline); and
a pass that only pinned the measured cost. Plus two parent-made docstring edits. Final bytes:
`src/f1show/booth.py` **763** lines (`77181ad8…`), `tests/test_booth.py` **1685** (`e9a8e84d…`),
`src/f1show/__init__.py` untouched (`458afd4c…`), full suite **736** (baseline 705).

- **RED per channel, reproduced before the fix with the escape observed**: a bullet-prefixed marker
  carrying a never-supplied reference; `EVIDENCE :` with a space before the colon; a mid-line escape; and
  a bare reference. Later REDs: glued `[99].evil` and `.evil`; a non-numeric index; an empty bracket; ZWSP,
  NBSP and newline splits; the sentence-boundary false refusal; and `word [ ]`.
- **Three independent verifications**, each on copies with an import proof (`inspect.getsourcefile`
  inside the copy, because a copied `.venv` silently tests the original tree): the first killed all ten
  structural mutants and **found the invisible-character leaks by attack**; the second killed the ten
  again, re-derived the whole shape table itself, and produced the two documentation flags; the third
  re-checked the documentation-only delta, audited the docstring's **five claims** one by one (none
  unsupported), and stated plainly that "documentation-only" is *supported by sampling, not proven*,
  because the previous certified bytes exist nowhere.
- Native review `review-ea289bc02bcd76fd`: tier **medium**, one lens, 2 files, **789** changed lines,
  candidate tree `102ee9047af110350fcc06f8ed4f06de38829b34`; **approved on the first reviewer run with no
  correction opened**; the exact acknowledgement **burned** authority (`consumed_revision
  sha256:c46dbe18…`, `gentle-ai.review-acknowledged/v1`). Two informational findings with **no bodies**,
  read and **measured by the parent** instead of reconstructed:
  - `R3-bracket-continuation-leak` (WARNING, `booth.py:375-377`) — measured: `position[0].position.[99].evil`,
    `position[0].position.[99]` and `position[0].position [99].evil` all **air**. Mechanism: the
    attached-bracket check fires only for a bracket *immediately* after a matched token, and `finditer`
    consumes the word a later bracket fragment would need, so a dot or a space between them defeats both
    rules. What airs is a **fragment** — never a complete never-supplied reference token — so the
    guarantee holds and this is the already-declared dotted-suffix boundary with a concrete instance.
  - `R3-bullet-commentary-false-refusal` (SUGGESTION, `booth.py:299-302`) — measured: `- Evidence: the gap
    closed by four tenths.`, `Evidence: the gap closed by four tenths.` and `* evidence: tyres are gone`
    are all refused as `MULTIPLE_CITATION_LINES`. Mechanism: the violation predicate matches the marker
    **word** with an optional bullet and any case, so a commentary line opening with the very word the
    prompt uses as a section header is read as a second citation attempt. This is an **undeclared**
    over-refusal that discards a legitimate answer, and it is the stronger of the two for a follow-up.
  - **Carried with owner and trigger, not with a promise**: the bracket-fragment instance → trigger, the
    next unit touching the scanner or a live trial showing a fragment in a transcript; the undeclared
    over-refusal → trigger, the first live trial that observes model output style (F13) or any unit
    touching `_CITATION_SHAPED`. Both are recorded **with the measurement**, not with the intent.
- **Committed** as `a43d0ff8951e2b5198fca4c7c483a281c97f411d`, Conventional Commit
  `feat(booth): refuse unsupplied reference tokens in aired commentary`. The pre-commit `HEAD` tree equals
  the controller's `base_tree` (`df3b8b06…`), the **staged tree equals the reviewed candidate tree**
  `102ee904…`, and the committed tree equals both — so the reviewed bytes are the committed bytes, checked
  by tree identity rather than by reading a diff. Clean worktree afterwards, 736 passed.
- **A consent fact worth keeping**: the host-owned consent binding has a **ten-minute** window, and this
  unit's first binding expired while the verifications ran. The diagnostics said explicitly *not* to resend
  it but to re-run START for a fresh envelope, which is what happened; the lineage was created only on the
  fresh binding, and `lineage_created` was `false` for the expired one.

**Integration by the step-1/F04 session (parent), measured rather than accepted.** Three cherry-picks in
order: `f535350` (design), `7dc3f8b` (source), `4122c85` (evidence). **All three applied with no
conflict**, including the evidence block whose anchor line does not exist verbatim in this copy — git found
a fuzzy match, so the placement was **verified by structure** instead of assumed, and the section sits
between the F09 material and `### F10`, with exactly one `### F09b` heading and no conflict markers. The
document delta is exactly 102 insertions and 0 deletions, the 52 + 50 the two commits claimed.
**Identity verified by measurement, not by report**: `src/f1show/booth.py` and `tests/test_booth.py` are
**blob-identical** to the reviewed tree `102ee9047af110350fcc06f8ed4f06de38829b34`, and
`src/f1show/__init__.py` is **untouched** (`4f6669c4…`) because this source commit does not modify it at all
— so the additive-export conflict surface that F08 and F09 both presented **does not exist here**. Suite
**761 passed** on the integrated tree, which is 730 + 31: **exactly** the delta this unit added to its own
baseline (705 → 736), two independently produced numbers agreeing. The range's own arithmetic reconciles
too: the review's **789** changed lines are 778 insertions plus 11 deletions, and `170` in the peer's
diffstat is that file's *changed* lines, not its insertions.
**The peer's two findings were re-measured by the parent on the integrated bytes, and one came back
sharper.** Both are registered in `docs/CARRIED-FINDINGS.md` with owner and trigger. The sharper half: of the
three false-refusal cases, the unbulleted one was **already** refused by the exact reading that shipped
before, and only the **bullet and case forms are newly** refused — because the unit closed those escape
channels by widening the violation predicate. That is a failure mode the hardening introduced, and its own
review caught it; the integration review then **re-surfaced it independently under a fresh id**, one line from
the unit's own location, which is the size-based gate re-reviewing approved bytes — now observed rather than
predicted.
**`R3-004` was closed by two PINS, and this record asserted the opposite for a while.** The pre-F09b
`booth.py:288-294` holds `cited = tuple(dict.fromkeys(item.strip() for item in ... if item.strip()))` — the
**duplicate collapse** and the **silent drop of empty items**, a **coverage** subject — and the unit closed it
with `test_duplicate_citations_are_collapsed_and_their_order_is_preserved` plus an empty-item tolerance pin.
Both pass, and both **passed before the change**: pins, with **no RED**, a weaker evidence class than closed by
change. **The mechanism of the error is the lesson worth keeping: a `sed -n '286,295p'` window was printed and
read as if it were the cited range `288-294`** — a real measurement of a **different object** than the row
asserts; the predicate is at `:286-287`, one line above.
**The correction took two rounds because agreement is not corroboration.** The peer first corrected this
record properly, then accepted the parent's wrong version as better than its own **without measuring it**,
when it had the bytes at hand. The rule that came out of it is mutual and blunt: **a claim about bytes is
measured before it is conceded, whoever asserts it** — conceding quickly is not humility, it is the same
unmeasured claim pointing the other way.
**A fourth closure class came out of this, and it is the dangerous one.** Closures are by **change** (bytes
moved, a test went red first), by **pin** (a test added that also passes before the change: no RED), as a
**dead record** (no future condition), and now as **superseded by a rewrite**, where the location no longer
holds the subject at all. The last one is special because it **depends on coordinates and can therefore be
asserted without measuring** — which is exactly how the error above was born. That is why the register now
requires a **subject descriptor** on every row and a **mechanical staleness trigger**, the line-count delta
from the revision a location was recorded against. Applying that trigger at this closure flagged `auth.py`
(+70 lines since its review) and `collector.py` (+42) as never re-derived, and found a second wrong booth row
— the persona validator sits at `:143-150`, not `:117-123` — inside a section whose own note had claimed that
every anchor was re-measured.
**And the trigger itself was upgraded on the peer's reasoning, which arrived labelled as reasoning and not as
a measurement.** A line-count delta is **necessary but not sufficient**: a refactor that adds and removes the
same number of lines, a reorder or a rename leaves the length untouched, and every row in that file would read
as current without ever having been re-derived — **a false green, which is the worst class of result because it
looks measured**. The key is now the file's **blob OID** at the recorded revision, compared against
`git rev-parse HEAD:<path>`, recorded per file in the register's **Staleness keys** section. Measured when the
rule was upgraded: the false green it prevents **had not occurred** in this repository — no file changed bytes
with an unchanged length — and the hash still found two files the line audit had missed,
`tests/test_auth.py` (+172 lines) and `tests/test_collector.py` (+120) — because the audit had been run over
the source files only, while the register also carries rows in the test files. That is a gap in how the audit
was applied rather than in the rule, and it is the second time in this round that applying a rule found more
than the case that motivated it.

### F09c — Declare the fifth airing shape

**Assignment received in writing on 2026-10-10**, surfaces `src/f1show/booth.py` and
`tests/test_booth.py` only, **no behaviour change**, no `__init__.py` (no new public name), and
`_CITATION_SHAPED` plus the violation predicate explicitly untouched. Branch based on this track's own
`da5cf79`.

- **The finding**: the integration review left `R3-docstring-omits-bracket-fragment-leak` (SUGGESTION,
  `booth.py:53-54`). The module docstring declares **four** shapes deliberately left airing plus one
  known leak (`U+034F`); the **bracketed fragment separated from a clean reference** is not among them
  except by a generous reading of "a dotted suffix is prose". Measured before writing: the separated
  forms `position[0].position.[99].evil`, `position[0].position.[99]` and
  `position[0].position [99].evil` **air**, while the *attached* forms `position[0].position[99]` and
  `position[0].position[99].evil` are **refused**.
- **Decision: (a) — a fifth declared shape, not an instance of the dotted-suffix boundary.** Reason, and
  it is the crux of the ambiguity: the two do not coincide. The dot-separated fragment could pass as a
  dotted suffix, but the **space-separated** form (`position[0].position [99].evil`) contains no dot at
  all, so calling the whole family a dotted suffix would be false for one of the three measured cases and
  would relocate the ambiguity instead of removing it. The fifth shape is therefore described by its
  **mechanism**: the attached-bracket rule requires the bracket to be *immediately* after the matched
  token, and `finditer` consumes the word a later fragment would need, so a fragment separated by a dot
  or by whitespace defeats both rules.
- **The docstring must say it is deliberate and that closing it is a product trade**, not an oversight:
  closing it costs false refusals, and the trade is tied to `R3-marker-word-false-refusal`, which already
  carries two independent reviewers. That trade belongs to the user, so this unit **declares and pins**
  and does not change behaviour.
- **The pin**: one parametrized test in `tests/test_booth.py` covering **every** declared airing shape —
  the four existing, the new fifth, and the known `U+034F` leak — one case each, asserting the shape
  airs with the supplied evidence intact. The docstring's list is written as an explicit enumeration so
  the count and the items cannot disagree, and a declared shape with no case exercising it is an
  unsupported claim rather than a boundary.
- **Evidence, and the RED is declared absent rather than manufactured**: a docstring change has no
  behavioural RED, and this unit says so plainly. Instead: (i) the pin has teeth **by mutation** — in a
  `/tmp` copy, extend the attached-bracket check to skip whitespace and dots so the fragment is refused,
  and the new pin must go **RED**, then restoring it must go green; (ii) **every changed line in
  `booth.py` lies inside the module docstring**, which is how "no behaviour change" is checked rather
  than asserted; (iii) the full suite stays green.
- **Docs placement**: this block sits after the F09b evidence block and before `### F10`; the other
  session's F09b integration record will sit between them in its copy, and on conflict its document wins.
- **Placement in this copy (parent)**: the block landed **after** the parent's F09b integration record and
  **immediately before the next-units block**, because that anchor is unique in this copy. The peer's own copy
  has no integration record, which is why its anchor differs; **no content of the block was changed**, only its
  position. (An earlier version of this bullet said it landed before `### F10`; that was wrong, and it is
  corrected here rather than quietly deleted — a placement note that misstates the placement is the same defect
  this register keeps catching.)

**Integration by the parent, measured rather than accepted — and this time the disposition is NO native review,
on two measured grounds.** Three cherry-picks over the F09b integration: `6352234` (design), `bde8d5f`
(source), `221a445` (evidence). The design block conflicted and was resolved **mechanically rather than by
retyping**: this copy's side was kept, and the peer's block was **extracted from its own commit `4adec49`** and
re-inserted, so no transcription error can enter a record about transcription errors. The two later commits
applied with no conflict.
**Identity, measured**: `src/f1show/booth.py` and `tests/test_booth.py` are **blob-identical** to the peer's
reviewed tree `84d7c65bc073abbe31812ce701a844137a424117`, `__init__.py` is untouched (`4f6669c4…`), and the suite
is **778 passed** — 761 plus **exactly 17**, the number of parameters the new pin adds, two independently produced
numbers agreeing. The "no behaviour change" claim was **checked, not asserted**: the source commit is a single
hunk, `@@ -49,14 +49,46 @@`, entirely inside the module docstring.
**Why no native review, and this is a decision on the record rather than an omission.** `ASSESS` on the range
returned **`reviewDue: false`** with reason **`under_budget`** for 288 changed lines — and independently of that,
the candidate's source bytes are **blob-identical to a tree the peer had already natively reviewed and
approved**, so a review here would re-review approved bytes under a fresh id: the cost this register exists to
document rather than to repeat. `inspect` did offer `review.start`, as it does for **any** unreviewed target;
the offer is not the obligation, and the harness's own assessment is. The F03-cleanup formatting unit was
recorded the same way at 11 changed lines.
**What the parent re-measured rather than accepted**: the tip and the three commits with their tree OIDs, the
reviewed-tree chain (`090012fb` base, `84d7c65b` source tree), the blob set in **sha256 compared against
sha256** and never against git blob OIDs, the single docstring hunk, the 17 collected parameters, and the
**+32 re-derivation of every `booth.py` register row by subject** rather than by arithmetic — four of four
recorded tokens consistent, which is why the shift is stated rather than assumed. The peer's own honesty note is
also carried: it measured the second-to-third verification delta itself, so the **third** pass is the one that
certifies the deliverable.

**Next units, assigned in writing after the F09b closure (2026-10-11).** Two, split on file ownership so
that neither session edits a file the other owns — the peer raised this itself, correctly: this register
exists in `main` and **not** in its branch, so editing it there would create a competing creation of a file it
does not own and turn a clean cherry-pick into a reconciliation.
1. **The scanner's declared boundaries — the peer's.** Surfaces `src/f1show/booth.py` and
   `tests/test_booth.py`, branch based on its own `feat/f09b-citation-channels`, whose `booth.py` is
   **blob-identical** to main's `0d1191c626fc`, so the cherry-pick applies cleanly again and `__init__.py`
   stays untouched. Objective: declare the **fifth airing shape**, the bracket fragment, and pin it, closing
   the integration review's `R3-docstring-omits-bracket-fragment-leak`. Measured by the parent: the module
   docstring declares **four** shapes plus one known leak (`U+034F`), while `position[0].position.[99].evil`,
   `position[0].position.[99]` and `position[0].position [99].evil` all air and `position[0].position[99]` with
   its controls is refused. The peer must choose **explicitly** between reading the fragment as a fifth shape
   or as an instance of the dotted-suffix boundary; the ambiguity itself is what the finding is about.
   **Hard limit: no behaviour change** — the rule already airs it, and if the analysis suggests the rule should
   change, the unit stops, because that trade belongs to the user and is tied to the finding below. Evidence
   demanded: a **mutation proof** that the pin has teeth (invert the code, the pin goes red), every declared
   shape exercised by a test that makes it air, the full suite, and the identity chain. A docstring has no
   behavioural RED, so the peer is asked to **say that** rather than manufacture one.
2. **The register's per-subject re-derivation — the parent's. COMPLETED and published as PR #18 =**
   **`c8a0d9d0`.** Surface `docs/CARRIED-FINDINGS.md`. Every row now carries a **coordinate and a subject**, and
   every stale file's rows were re-derived by reading the recorded revision and finding the same subject in the
   current file. Verified on `main` rather than in the working tree: the four false claims this round produced
   (`superseded by measurement`, "every anchor below was re-measured", "subjects have not been derived",
   "windows collapsed onto one line") each return **zero** occurrences across `docs/` and `odd/`.
   **The pass corrected the parent twice, which is the point of doing it by measurement.** First, the
   `collector.py` "collapsed windows" claim was wrong: it came from matching lines against the **F04 tree**
   while those rows were recorded against the **post-correction file**, and re-read against the right revision
   **three of them are exactly current** inside `_canonical_rendering` — `:197-200` (the `default=repr` /
   `repr(value)` pair), `:198-199` (the canonical `json.dumps`) and `:199-200` (the `except (TypeError,
   ValueError)` branch) — one small function, three rows told apart by subject. Two more moved by exactly one
   line, and the closed row is closed **by change**, with the code's new home recorded (`_identity_token`
   `:203-220`, `_canonical_rendering` `:187-200`) instead of a new number for the old one. Second, the blob's
   over-flagging got an **instance** rather than an argument: `tests/test_auth.py` is STALE by blob while its
   one row — the `for _ in range(50): await asyncio.sleep(0)` yield count at `:558-559` — sits at **exactly**
   its recorded coordinate in a file that grew by 172 lines.
   **What remains, and it is real work rather than an edit**: `auth.py:347` (**R4-001**) is **NOT FOUND**. It is
   a different finding from staleness — the line no longer exists at all, arithmetic cannot re-point it, and
   deciding from the subject whether the row is closed needs a human. The grouped auth row's seven anchors are
   **not paired to its seven ids**, because the bodies are unrecoverable and that pairing cannot be measured.
   And the per-symbol hash remains the next refinement, unadopted, for the reason recorded in **Staleness
   keys**: the blob is file-level and therefore over-flags.
**The debt plan, decided by the user on 2026-10-11, and it supersedes the paragraph that stood here.** The
over-refusal `R3-marker-word-false-refusal` is **no longer held**: the user authorized redesigning it, **with
native review**, sequenced **after the peer's in-flight boundary unit** because both touch `booth.py` and there
is one writer per file. **The parent had recommended waiting for the live trial, and that recommendation was
too conservative** — the design does not need F13, because the scanner's own principle, stated in its module
docstring and measured by the parent, settles it: *the guarantee is about **tokens**, not lines*. A later line
that is marker-shaped but whose remainder carries **no reference-shaped token** is therefore not a citation
attempt, and refusing it is the deviation. The candidate rule is that the violation predicate requires the
**marker plus a reference-shaped remainder**; the four closed channels all carry a reference token and stay
refused as regression pins, the content rule is untouched (it is what catches a bare reference), and the
measured false-refusal cases become the RED. What F13 would have added is the empirical weight; the design is
safe **by construction** instead.
**The per-symbol hash is rejected with its measurement, not deferred.** The blob's over-flagging has cost exactly
one row-check so far (`tests/test_auth.py`, whose row was UNMOVED, found by one grep), while adopting the symbol
costs a stored field per row plus resolving the enclosing symbol at every re-derivation. It revives if a single
change ever forces re-deriving **more than five rows in one file where only one or two moved**.
**Tier 0 is complete with this record**: `R4-001` was re-anchored from the dead `:347` to **`:410-423`** — the old
coordinate was a blank line inside the `AuthenticatedHttpClient` docstring, so its subject was always a
**documented lifecycle contract** rather than a branch — with its F13 trigger intact, because a documented
adoption/`close` promise is witnessed only by a real call. The register now has **zero rows in NOT FOUND** and
**zero decisions left pending**.
**Tier 2, authorized in this order.** (1) **F12 / issue #7** — offline CI, a committed lint configuration, a
Python **3.12** matrix and a PR template — which retires the two standing caveats that the 3.12 floor is proven
but unenforced and that every Ruff claim is scoped to a file outside this repository. (2) **The F13 pilot plan,
drafted with no calls made**: about ten carried findings have "the first live call" as their trigger, and a
written plan (model, spend report, prompt set, what to observe) is what turns them into checkable items the day
a subscription exists. (3) **F05 + F11 as a pair**, transport before packaging, since F11 is empty before F05.
(4) **F06 before F07**, because F06 consumes `classify_gap` — which this register already flags — while F07 is
enrichment with its own network care. Each of those needs its own registered design and its own authorization
before a first write; this paragraph authorizes the **order**, not the implementations.

**F12 / issue #7 — design registered before the peer's first write (2026-10-11).** Objective: make the repository
able to sustain what it says about itself, retiring the two standing caveats that ride on **every** claim this
project makes — that the declared `>=3.12` floor is proven runnable but **nothing enforces it**, and that **no
lint configuration is committed**, so each "Ruff clean" claim is scoped to an artifact outside this repository
whose version differed three ways between agents in a single session (`0.16.1`, `0.16.3`, `0.16.8`).
**Surfaces**: `.github/workflows/ci.yml` (new), the committed lint configuration (`ruff.toml` new, or
`[tool.ruff]` inside the existing `pyproject.toml` — the one shared file, to be declared if taken), and
`.github/pull_request_template.md` (new). Nothing else: not `src/`, not `tests/`, and not this document.
**Limits, which are the substance of the unit**: no behaviour change in `src/` or `tests/`, so if the committed
configuration surfaces real findings they are **reported and never fixed silently**, because most are carried
findings with owners and triggers in the register and fixing them quietly breaks the rule they were carried
under; the Ruff **version is pinned explicitly**, since a configuration without a version is a new caveat wearing
the shape of a fix; the 3.12 job must **run** the suite rather than declare it; nothing may need credentials or
network beyond the runner's normal behaviour; and **a CI that is red on merge is worse than no CI**, so the rule
selection must be one the tree passes, with the deliberately disabled rules listed and their reason given.
**Acceptance**: the job set enumerated; proof that the committed rule selection is what is claimed (rule set plus
finding count, new findings separated from zero); the 3.12 result shown locally or the gap stated plainly — a
measured precedent exists, 548 passed under 3.12.13 in the F03-cleanup unit; the PR template rendering and
naming the project's **real** checks (`uv run --frozen pytest`, the committed lint configuration, and native
review under RDD); the pinned versions; and the rules deliberately left off. **Branch**: based on `main`, not on
the peer's older unit branch, because the CI configuration belongs to the tree as it stands today.

**F12 integrated, measured, and published with the register rows its own configuration demands (2026-10-11).**
One cherry-pick, `dbcd58c`, over `main`: the source commit `cbf27d32`, whose stage, review and commit trees are
all `cffa7b5c`, with **all three blobs identical** to the reviewed tree on the integrated side — new paths, so
there was no conflict surface at all. Native review at **tier high with four lenses** (a reviewer sees a
workflow as shell and a configuration that launches processes), approved on its first run and **burned**.
**What the unit retired**: the two caveats that rode on *every* claim this project made. The declared `>=3.12`
floor is now **enforced by a matrix job** and was proven **locally** rather than deferred to CI — 778 passed on
3.12.13 and on 3.14 — and a lint configuration is **committed** with its version pinned to `0.17.0`, so
"Ruff clean" now names a file inside this repository rather than one outside it. The agent harness's
configuration stays a **tool, not the yardstick**.
**The parent changed the SHAPE of the exceptions, and this is the part worth keeping**: the peer had proposed a
flat five-entry `ignore`; measuring **where** each rule fires changed the shape. `S101` fires **1552 times, all
in `tests/` and none in `src/`** — a global ignore would have hidden an `assert` in production code, which has
real weight because **asserts compile out under `-O`** — while `UP042` fires only in `src/` and `I001` only in
`tests/`. So two rules stay global (they fire in both trees) and three are **per-file scoped**, and the scoping
was verified **behaviourally in both directions** on the delivered bytes: a planted `assert` in `src/`
**reports**, the same `assert` under `tests/` is **silenced**, and the enforcement command run from the worktree
root discovers the committed configuration and passes.
**The five register rows shipped in the same pull request, and they could not ship earlier because of the
configuration's own rule**: a row about a file that is not committed yet would be a claim about a future state.
One row per silenced rule, each with its count, revision, version, owner and the trigger that removes it, keeping
the distinction between **mechanical** (`UP017`, `I001`) and **needs behaviour tests** (`UP042`), with `S101`
stating **where** it is silenced and where it is not. The cross-cutting row about having no committed lint
configuration is **closed**.
**Two review findings, both raised by two independent lenses and neither fixed here**: no `timeout-minutes` on
the CI jobs, and the enforcement step that would fail when an ignored rule has no row. The second one's trigger
**fires with this very commit**, and it cannot ride this integration because it would change the `ci.yml` bytes
that were just approved — so it is the next small CI unit, registered with its trigger already fired.

**F12b integrated and reviewed (2026-10-11).** One cherry-pick, `d0d7d5b`, of the peer's `7f1c7be` over `main`:
two paths, **78 insertions and 16 deletions**, with **both blobs identical** to its reviewed tree `5aeffb41`.
**What it closes**: the two findings the F12 integration deliberately left open. `timeout-minutes` now bounds all
three jobs — tests 15, lint 10, register 10, where GitHub's default is **360 minutes** a job — and a **`register`
job** fails, naming the rule, when an ignored rule has no row in this register. The obligation the configuration
states is therefore **enforced** rather than promised, and the caveat row is closed.
**Verified by the parent before conceding anything**, by extracting the guard out of the workflow and running it:
green on the committed tree naming all five silenced rules; **red** with a planted `B904` that has no row; and the
**configuration data identical** between F12 and F12b when both are parsed with `tomllib` — so the unit adds a
check without re-deciding a single silence. An **independent verifier** then reproduced all of it with **its own**
planted rule (`RET504`), plus the 3.12 suite at 778 and valid YAML. The peer's own note about that guard is worth
keeping: it removed `setup-uv` from the `register` job because a verifier called it a dead step — "needs no
network" was true of the **step** and false of the **job**.
**What the guard is, and what it is not**: deliberately dumb, and it says so in its own comment — it reads the
ignored rules out of the configuration and checks that each code **appears** in this file; it does **not** parse
the register, because this file is human prose and a parser here would be a second thing to keep correct. Its
limits are now rows of their own: the **substring false-green** (a rule named only inside a sentence passes — and
the verifier found a worse variant, where deleting just the `[lint]` header leaves the guard **green with three
rules**), the job name that claims more than the check performs, the **hardcoded path** to this file, and timeout
values nobody explained.
**And the honest gap the verification measured**: **nothing in this repository tests the guard or the
workflow.** Neutering it (`if missing:` → `if False:`) passes the whole suite, and deleting a `timeout-minutes`
passes everything; the guard's only safety net is CI running it. Recorded as a coverage gap with an owner and a
trigger, not smoothed over.
**Review**: four lenses at high tier, approved on its first run, authority burned — and it **re-surfaced two of
the unit's own findings under fresh ids at the same locations**, the **sixth** measurement of that mechanism in
this round, which is why this register's identity is the location and not the finding id.

**F12c integrated and published (2026-10-11).** One cherry-pick, `8f405d4`, of the peer's `081e2a6` over
`main`: two paths, **262 insertions and 2 deletions**, both blobs **identical** to its reviewed tree `5f6ba2f7`.
**What it closes**: the **COVERAGE GAP** — *before this unit the workflow and the guard were not repository code
as far as the suite was concerned: you could delete them entirely and everything stayed green.* Now
`tests/test_ci_config.py` mirrors the guard against this register, runs it in sandboxes, asserts every job
carries `timeout-minutes`, and guards against empty passes; and the guard's missing-`[lint]` default fails **with
its own prefix** instead of defaulting to an empty list.
**Verified three ways before any acceptance.** The parent reproduced the three load-bearing mutations, all
**KILLED** — both guard branches and a deleted timeout. The unit's own verifier did it with **its own** mutants
(planting `W291`) and confirmed the **converse independence** in both directions. The parent's verifier then
measured the closure **by deletion**, which is the strongest form: removing the whole `register` job gives
**exactly five reds**, not one; the empty-pass guards work; and **the readability assertions are the killer** —
without the `register guard:` prefix assertion the mutant survives on the `KeyError` path, because a `KeyError`
also exits non-zero.
**Review**: tier **high** by `shell_source`, **four lenses**, approved on its first run, authority **burned**
(`consumed_revision sha256:165857d7…`). Ten findings, all informational and all registered — including one the
verifier had **already probed independently**: a job key outside `[a-z][a-z0-9-]*` is **invisible to both
scans**, so a job with no timeout passes all ten tests. A false green inside the test that exists to stop false
greens, and **a row two independent parties found separately**, which is what raises its weight.
**And the round's method rules came out of this thread**, all now in the register: the **write path** decides
the writer profile (a change written by a shell command carries no attribution and buys an independent
verifier); a committed range is measured with a **clean tree**, and **the leak has a direction** — contamination
favours the candidate, so the permissive verdict is the one to distrust; an assess plan belongs to the
**measurement event** and is never cited as precedent; **measure facts now, name boundaries and defer them**
with their experiment; and a rule found by two independent measurements is a rule, while one two sessions merely
agree on is a **convention**.
**One datum the publication records rather than resolves**: this candidate reported `writerProfile: large` /
`runtime` on a **clean** tree, because the parent had just written those docs **with the tools** — a counter-datum
to the simpler rule sent earlier. The honest reading is that the profile follows the tool-written work **recorded
for the root**, pending or recent, and that a **fresh root always falls back**; the exact window is unmeasured and
recorded as such rather than smoothed.
**F12d and F12e integrated and published together (2026-10-11).** Two units on one file, both verified by an
independent verifier and **neither needing a native review** — which is the measured consequence of keeping
`.github/workflows/ci.yml` out of the diff.
**F12d** (`0ba3e67c` → `21e382a`, 244 lines): the two gaps the F12c verification had found. The **charset false
green** is closed — the scans read job keys **permissively by indentation** and a **test** rejects the charset,
so a malformed key fails loudly instead of hiding from both scans — and the **m1 survivor** is dead: the mirror
comparison became `missing_register_rows(config_text, register_text)` and neutering it now kills exactly one
test. Verified three times over: I reproduced the three load-bearing mutations (all KILLED), the unit's own
verifier did it with its own mutants and confirmed the converse independence, and my verifier measured the
closure **by deletion** — removing the whole `register` job gives **exactly five reds** — and proved that the
**readability assertions are the killer**.
**F12e** (`879e3b5` → `5923015`, 114 lines): **the class closed, four instances to zero.** `R2-assignment-context-leak`
was not a line but a **pattern** — citing the unit that produced something instead of the property it protects —
and the criterion fixed here is that **the class is citing the UNIT**, a referent that dies at the merge, while
citing a **measured state of the code IS evidence** and fully so when it **names the revision**. That is why five
sibling phrases **stay**. Its most valuable finding is the discriminator at a **second level**: a mutant that
replaces the refusal's **subject** with a generic phrase keeps the prefix AND the exit code, and **survived the
earlier review of that file** — the prefix was the right carrier against a `KeyError` and **insufficient**
against a generic message from the same guard. Two findings were closed **by characterisation**, with the reason
written rather than "no longer applies", because their bodies are unrecoverable and the harness never returns
them.
**And the round's method rules came out of these units**, all now in the register: the discriminator has **two**
failure modes and one repair (assert the subject), and **a new message can silently weaken an existing
assertion**; **the object of the claim determines the obligation** (existing bytes: measure now, whoever the
author; future bytes: label the candidate and re-measure when they exist); a store record is **reliable as an
execution and never as authority**; and the review **budget** is a second knob from the threshold, with tier and
size **confounded** in every point we have. Four boundaries were named with their experiments and deliberately
not run, and the reading rule for the fourth was **pre-registered before the datum existed**.
**Two residual gaps stay open** with owners and triggers: an inner-colon job key (`a:b`) escapes **both** scans on
planted texts, with a **measured candidate fix** recorded as a candidate rather than as a fix; and the charset
test's assertion is **vacuous over the real tree** with no other test calling it, so neutering its body is
uncatchable — **a property of the tree, not of the test**.

**First live exercise of the product's data path (2026-10-11, authorized by the user).** The free OpenF1 API
was driven **through the project's own path** — its HTTP boundary, its shared rate limiter, its retry policy
and its collector — for **one Grand Prix only**. `GET /sessions?year=2026` returned **131 sessions**, and the
most recent race **with a past `date_start`** was **Singapore / Marina Bay 2026, `session_key` 11388**
(`2026-10-11`). The five collector families all answered **200**, and the collector derived **1,863 events**
from payloads it had never seen: position 396, laps 1,240, pit 25, stints 47, race_control 155 — one event per
in-scope record, **22 distinct drivers**, **1,816 timestamps known** and **47 explicitly unknown** with the
reason `family_carries_no_timestamp_field` (the stints family has no timestamp field), and **no overtake event**
because the enum has no such type. **Six requests in ~6 s, ~1 req/s**, paced by the project's own limiter — well
inside the published free tier (3/s, 30/min), with no credentials, no gateway and no authenticated endpoint.
**Two findings the recorded corpus could not have produced**: the sessions listing includes **scheduled rounds
with no data yet** — 6 of 25 races in 2026 were in the future, and selecting by `max(date_start)` picked one whose
families all answer **404**, which the collector handled by deriving **zero events and inventing nothing**, so the
defect is in the **selection** — and the stints family's absent timestamp field is now confirmed **live** rather
than only against fixtures. Nothing was written into the repository: the live payloads and the summary live under
`/tmp/f1show_live/`.

**First live MODEL exercise, and the finding that blocks live commentary (2026-10-11, authorized by the user).**
The recorded Austin 2024 race (9617) was driven through the project's own composition — `_model_client` over the
operator's gateway with the **version-less base URL derived in memory**, and the credential parsed literally
from the operator's file and **never printed** — for the window chosen: **`SESSION STARTED` (19:03:48) → the
last lap-5 completion (19:12:17)**, 8.5 minutes of race, **206 events**. The model id was chosen **at runtime
from the gateway's own native listing** (`gemini-3.5-flash-lite`, of 12 advertised).
**The run completed: 206 model calls, 135,660 input and 16,374 output tokens, 203 s, mean latency 0.99 s,**
producing the finding this round was waiting for: **the model copies what the prompt shows, at three levels of
fidelity.** 58 citations used the **listed reference** and aired; 93 used the **event identity** (`laps[3]`) and
aired only because the probe normalised them; and **55 copied the reference with its value**
(`laps[6].lap_duration = 105.091`), exactly as the `EVIDENCE` block prints it, and were **refused as
`invented_reference`**. **With the shipped protocol only 28% of the events can air**, and the cause is the
prompt's own formatting: it teaches `- <reference> = <value>` while the instruction says *exactly*
`EVIDENCE: <reference>`.
**Two things this establishes.** The pipeline **does** support live-like generation — the feed is the
collector's chronological order, one turn per event, the booth alternates lead and colour, and the commentary is
evidence-grounded (sector times, trap speeds, lap times, all taken from the evidence). And the blocker is a
**citation-format decision**, not the model, the gateway or the data. **And the over-refusal did not bite**: 206
samples, **zero** `MULTIPLE_CITATION_LINES`.
**No fix was applied**: the normaliser lived in the probe, the repository is untouched, and the two candidate
fixes are registered as product decisions.

### F09e — Accept measured citation shapes and integrate the prompt format

- [ ] **Authorized; in progress (2026-10-12).** User: "ok retomemos como recomiendas."
  This grant resumes the delivered citation-format correction, its mechanical test-client
  integration, checks and local integration. Names, championship context, language changes,
  new live/model calls and publication are outside this unit. The branch's historical
  `f13-citation-format` name does not authorize checklist F13's separate live pilot.
- **Delivery:** `bed049979b51f63d1e873d4d9f551f9cd54f7134`, base
  `440b8634fbf21b2503e217d5f2b03c63ba2fe628`, tree
  `15d802f82c0bf8ad3312a2564fd3a2b8f2dbc420`, two files, **228 additions + 12 deletions
  = 240 authored lines**. The previously reported 228 was not total review workload.
  Parent `9e8702e88469fd4f9298695902d4b09832767e27` and the delivery worktree are clean.
  Main's advance to `e86593f0c574709577b3a57e5661224c1115fe32` changes none of the
  three affected source/test paths (observed name-only diff).
- **Goal:** separate citable references from their values in the prompt; accept the exact
  current event identity by expanding it to that event's supplied references; preserve the
  supplied-reference boundary and existing refusal/content channels.
- **Three stages, one coherent work unit:**
  1. Reproduce the reported test-client failures, adapt only `tests/test_run.py` to the
     reference-only prompt shape, and observe focused/full GREEN with import-path proof.
     Existing deterministic failing cases provide RED; add a narrow regex boundary pin if useful.
  2. Independently inspect the parser's acceptance boundary and re-derive only affected
     carried findings by subject, including current blob keys and the live citation-form row.
     The delivery's reported 123 focused / 805 passed + 5 failed are not fresh verification.
  3. Assess the final bounded candidate, complete the provider-offered native review and exact
     acknowledgement under RDD on, then locally integrate with identity evidence and final
     applicable checks. No push, PR, merge to main, credentials or external calls.
- **Routing:** mapping delegated to `gentle-ai-explore` (`mv4p76qc-1-rrjv`, completed);
  bounded test adaptation to one `gentle-ai-worker`; command verification to
  `gentle-ai-verify`. Multi-file integration, preparation and verification triggers apply.
  Peer A performs one scoped read-only acceptance-boundary challenge; peer B maps register
  subjects/coordinates. They do not write, run tests, change Git/ODD or native authority.
- **Allowed writer surface:** `tests/test_run.py` in
  `/home/s/dev/projects/work/F1Show-f13`. Delivered `booth.py`/`test_booth.py` remain
  unchanged unless a corroborated defect requires a separately bounded correction.
  Parent owns `odd/tasks/f1show.md`, `docs/CARRIED-FINDINGS.md`, Git and review authority.
- **Writer report, not accepted artifact:** `mv4qb5z7-2-v090` settled, reporting
  the five deterministic RED failures repaired, 148 focused / 811 full GREEN, Ruff clean,
  import proof under `PYTHONPATH=src`, and missing child LSP coverage. It reported
  `tests/test_run.py` **+49/-2**, SHA256
  `79074a10e2a8f2f7e39350d4b0c0f8dc378c7bfc911fe5c96da01b23c6001263`.
- **F09e-I1 — active artifact-identity incident, read-only:** parent readback instead
  observes **+127/-21**, SHA256
  `9ed90d6e73c0ebdc89c749135fd524839c3a5c033495394b873456619b0924fd`.
  The native settled handoff repeats the smaller artifact. Production `booth.py` and
  `test_booth.py` remain unchanged, the index is empty, and only `test_run.py` is dirty.
  Preserve the live file; no culprit or cause is established. Delegate a separate
  `gentle-ai-explore` incident diagnosis. Source edits, acceptance, native freeze and
  integration are paused; the reported GREEN does not certify different bytes.
- **Peer B map received:** `F09E-B-REGISTER-01` is completed read-only and B is unassigned.
  Its anchors are delivered-revision evidence, not functional closure. Exact parent
  numstat is `booth.py` +61/-10 and `test_booth.py` +167/-2; the reported per-test-file
  count was wrong. Peer A's `F09E-A-BOUNDARY-01` static challenge is now complete.
- **Peer A findings, source-derived and not executed:** emitted references remain
  current-event/supplied-only, but `item.partition("=")` ignores all RHS tokens although
  the docstring claims both shapes refuse unsupplied tokens. Commas in copied JSON values
  are split before value removal. A second marker carrying a bare event identity can
  reach commentary. Identity expansion intentionally cites all event references; the
  older test-name promise must be understood as explicit-field-only.
  A's clean `test_run.py`/missing-F09e note is an old committed/sibling-doc snapshot,
  not this canonical parent task file or the current dirty integration-test artifact.
- **F09e-V1 — next, delegated read-only functional verification:** preserve source;
  prove reflow equivalence with AST (remove only the added pin and restore only the
  old regex), recompute fingerprints before/after, reproduce immutable HEAD's old
  test-client RED with imports pinned to F13, then focused/full GREEN on current bytes.
  The incident explorer's original RED-log import/census inference is not established.
  Run scalar/header positive controls and these exact parser probes, reporting actual
  outcomes rather than assuming that source-derived traces are execution:
  - allowed `position[0].position`, identity `position[0]`: RHS
    `position[99].invented`, another supplied reference, and another identity after `=`.
  - allowed `laps[4].segments_sector_1`, identity `laps[4]`: copied value
    `[20480, 20481, 0]`; also comma-bearing JSON strings/dicts and comma-free controls.
  - valid first field citation followed by `EVIDENCE: position[0]` (and an unknown
    bare identity), comparing old production acceptance when feasible to classify cause.
  - Full-reference citation excluding uncited fields versus intentional identity expansion.
  Use `PYTHONPATH=src`, cached offline runners, no environment installs or credentials.
  Scratch controls/logs under `/tmp` are permitted for functional verification only;
  no source/Git/index/ODD/config writes or native reviewer-context transport.
  Commands: `PYTHONPATH=src uv run --offline --frozen --no-sync pytest
  tests/test_booth.py tests/test_run.py -q`; the same runner with `pytest -q`;
  `uvx --offline ruff==0.17.0 check --config ruff.toml src/f1show/booth.py
  tests/test_booth.py tests/test_run.py`. Redirect bulk output to unique logs; pin imports
  and report warning/LSP coverage separately. A reproduced parser gap is returned to
  the parent; it does not authorize a verifier fix or a new product trade.
- **F09e-V1 complete — verification evidence (read-only, repository unmutated):**
  verifier `mv4scpqx-4-f4ud` re-read status and fingerprints at the end of its run. Live
  artifact: `tests/test_run.py` modified, **+127/-21 = 148**, SHA256
  `9ed90d6e73c0ebdc89c749135fd524839c3a5c033495394b873456619b0924fd`, HEAD `bed0499…`,
  empty index, `diff --check` clean; `booth.py` `d5433560f…` and `test_booth.py`
  `154c79bee…` byte-identical to the delivered revision. **AST equivalence proven, not
  inferred:** the current file equals the committed baseline plus the single added pin
  function and the `_PROMPT_REFERENCE` literal change, with zero differing AST nodes after
  those two transforms, so the extra lines are comment and whitespace reflow. The old
  regex matches **0 of 981** real recorded prompts while the new one matches **8,563**
  reference lines across all 981 (0 unmatched prompts), and the old client's failure
  reproduces verbatim. Focused **148**, run-only **25**, full **811**, Ruff 0.17.0 clean;
  the pin adds exactly one collected case (24→25). Active LSP is unavailable and
  inconclusive and is **not** reported as clean. Child Engram was unavailable; the parent
  persisted these findings.
- **F09e-I1 closed by measurement, cause unattributed.** The writer-reported +49/-2 and
  SHA256 `79074a10e2a8…` **do not exist** in the worktree; the live artifact is the
  AST-equivalent reflow above. The leading hypothesis, unverified, is a post-measurement
  auto-format reflow; a pi-lens auto-run notice was reported but not confirmed. Method
  rule now recorded: **a child's reported artifact hash is not evidence of the bytes it
  delivered** — the parent recomputes fingerprints and proves equivalence.
- **Executed acceptance-boundary probes (A–F), actual outcomes:** (A)
  `position[0].position = position[99].invented` is **accepted** and the right-hand token
  is ignored and never validated; (B) a second supplied reference right of the `=` is
  **lost**; (C) `position[0] = position[1]` is **accepted** by identity expansion and the
  other event's identity is discarded; (D) the comma-bearing copied value
  `laps[4].segments_sector_1 = [20480, 20481, 0]` is **refused `invented_reference`**
  while the comma-free scalar control is accepted, because the header is split on commas
  before the `=` truncation; (E) a second line `EVIDENCE: position[0]` **airs as
  commentary**, supplied or not, while a token-bearing second line is refused
  `multiple_citation_lines`; (F) a supplied-shaped reference the event does not own is
  still refused. The docstring sentence *"an unsupplied token on either shape is still
  refused"* is **refuted by execution** for the right-hand side.
- **F09e-C1 — in-unit correction pass, authorized here.** (1) Validate the reference side
  of a copied value **independently of commas inside the value** by cutting at the first
  `=` before splitting, test-first from the measured refusal; (2) replace the false
  docstring claim with the **measured** boundary; (3) pin the measured right-hand-side
  behaviours, labelled honestly as pins rather than RED. Surfaces:
  `src/f1show/booth.py` plus `tests/test_booth.py`; `tests/test_run.py` must stay
  byte-identical. Carried with owner and trigger rather than fixed here: probe E, a bare
  event identity on a second line is not a citation attempt, and the untested
  reference-shaped right-hand side.
- **F09e-C1 independently verified.** Verifier `mv4sxg5q-6-0kxc`, read-only, mutated
  nothing. Parent-measured live artifact: `booth.py` +54/-31 SHA256 `f0fde318…`,
  `test_booth.py` +438/-64 SHA256 `7f8993bc…`, `test_run.py` unchanged `9ed90d6e…`.
  **AST confinement observed:** `booth.py` differs from HEAD in exactly three regions, the
  two docstrings and `_parse_answer`'s cut-at-first-`=` plus the removal of the per-item
  partition, and `test_booth.py` keeps 120/120 original nodes identical with 8 additions
  (7 tests and one helper), no removal and no modification; every deletion is comment or
  reflow. **RED causality proved** on a scratch copy of HEAD's production code: the three
  comma-value tests fail there with `invented_reference`, the zero-turn unpack explains the
  reported `ValueError`, and the comma-free control passes. **Probes on the live bytes:**
  comma list, dict and comma-bearing string values accepted with only the reference in the
  evidence tuple and no value leaking into the aired text; multi-reference left side kept;
  unsupplied and not-owned left tokens refused; reference-shaped right-hand token ignored;
  identity expansion intact; the no-`=` path unchanged; carried probe E still airs. Commands:
  focused **133**, run-only **25**, full **821**, Ruff 0.17.0 clean, and the correction adds
  exactly ten cases. Active LSP remains unavailable and inconclusive, never clean. Carried
  gap: a **supplied** reference used as the right-hand value is still unpinned.
- **Both artifact mismatches explained, not mysterious.** pi-lens autoformat is on by
  default with `format.mode` deferred and its documentation states that formatting for an
  `edit` runs at `agent_end`, after the child measured its hash. So both writers' reported
  hashes and sizes describe pre-format bytes (I1: +49/-2 versus +127/-21; I2: +32/-18 and
  +236/-0 versus +54/-31 and +438/-64). Method rule recorded: **a child's reported artifact
  hash is a pre-`agent_end` claim**, so the parent re-measures after the child settles and
  binds acceptance, commits and review to the parent-measured bytes.
- **Native review complete and burned.** `review-64713b02cce78401`: tier **medium**, one
  `review-reliability` lens, 3 files, **921 original changed lines**, correction budget 200,
  base tree `1a871cdb…`, candidate tree `5c1f0748…`, target `sha256:caf14bc2…`. The first
  START attempt timed out ambiguously and one target-scoped STATUS reconciled it as `start`
  over an empty candidate, after which the exact offered START created the lineage. The
  reviewer run was forecast (one host-relay model run, no mutation) and then authorized; the
  capture closed **approved** with a single non-blocking advisory finding,
  `R3-copy-shape-truncation` (`booth.py:542-548`, SUGGESTION, informational). The
  acknowledgement was executed unchanged: `authority: burned`, `consumed_revision
  sha256:d663513e…`, `gentle-ai.review-acknowledged/v1`. No STATUS was issued after the
  burn; delivery remains ordinary repository policy.
- **Budget datum (measured):** 921 authored changed lines at **medium** returned
  `reviewDue: true` with reason **`slice_budget_reached`** and budget 200, so the slice
  budget fires at medium as well as high. Recorded as a third measured point; the earlier
  threshold band is unchanged.
- **Integrated locally, not published.** The three work units were cherry-picked onto
  `feat/f03-source-adapters` as `e0e6089` (the peer's citation-shape delivery),
  `c38af4e` (the offline test client) and `fe4dda3` (this correction). Committed blobs equal
  the reviewed candidate tree exactly: `booth.py d6e56ea8…`, `test_booth.py 34ef0009…`,
  `test_run.py 8aaa35e8…`. Post-integration checks on the integrated branch: the import path
  resolves inside the parent worktree, focused **158 passed**, full **821 passed**. Review
  workload note, stated honestly: of the 921 lines roughly 379 are harness formatter reflow
  rather than authored logic.
- **Documentation closure complete.** The re-anchoring arrived from the read-only peer at
  `fe4dda3` and every affected row was re-derived **by subject** before it was written: twelve
  coordinates re-anchored, the three staleness keys updated (`booth.py d6e56ea8…`,
  `test_booth.py 34ef0009…`, `test_run.py 8aaa35e8…`), the live citation-form row **closed for
  its deterministic half** with its live-rate half left historical and unmeasured, the
  `R3-copy-shape-truncation` row added from the approved review, and the method rule recorded
  that a child's artifact hash is a pre-`agent_end` claim. Landed as
  `b556abdcc3c25520c9900fbf51de6170be3086f9`, Conventional Commit
  `docs(odd): close F09e and re-anchor the register by subject`, which also carries this task
  document. The parent branch is **ahead 4** and clean: three source work units plus this docs
  commit.
- **Unit state: closed.** Verified, natively reviewed and approved, authority burned,
  integrated locally and documented. Nothing was pushed, and push, pull request and merge remain
  the user's decision. The next unit — names and teams, then the championship context, then
  salience and the two modes — is **registered as design and awaits explicit authorization**,
  because the earlier grants do not authorize later-unit implementation.

### The show: what the profession says, what the data says, and the design

**Research, 2026-10-11, first-party sources read.** The rules below are the practitioners' own words, and the
academic work confirms the structure rather than replacing it.

- **The two roles, defined by F1 TV's own lead commentator (Alex Jacques).** *"My job is to inform the viewer
  what is happening in real time — **identifying cars, calling overtakes**… The narrative part involves
  **distilling the elements of each driver and team's weekend into short segments**… aided by my
  co-commentators telling us **why** the action is happening whilst they weave in their personal experience."*
  The booth already has the two seats; **it does not have the division of labour** — both seats currently
  recite telemetry.
- **The climax rule, from F1 TV's executive producer (Anthony Ellis).** *"It's about breaking down stories…
  and, when there's an **overtake or a magic moment, we've got to make it look epic**."*
- **Economy, from Jacques on Barry Davies.** *"His **economy of words to impact ratio**… a narrative-led
  commentator."*
- **Tone, from Jacques on Murray Walker.** *"Peerless ability to convey information with such clarity and
  emotion… his attitude to **emphasise the positive and not to score points or punch down**."*
- **Pacing, from F1 TV's lead presenter (Laura Winter).** *"I have to know **when to let it breathe**… and then
  when to bring it back."*
- **The two-mode structure, from the prosody research.** Live radio football commentary uses two speech styles
  with distinct prosodic features — **"building up suspense"** and **"presenting a climax"**
  (*The prosody of live radio commentary of football matches*). So narration has **two modes**, not one.
- **Salience is measurable — and biassed unless declared.** Broadcast studies measure salience as **clock-time
  and name mentions** (NBC Olympic telecasts), and the same studies show networks favour the local or star
  athlete **without saying so**. A salience rule is therefore something this project must **state**.

**What the data already carries, free and offline.** The recorded corpus holds the 20 drivers with
`full_name`, `name_acronym`, `broadcast_name`, `team_name` and `team_colour` (10 teams). The collector ignores
`drivers` because it derives no event, and the prompt shows only `driver_number: 4`. **The join is available
offline**: `4` → `Lando Norris (McLaren, #4)`.

**The salience of the window we ran, measured** (start → lap 5, Austin 2024):

| reason to mention | who, and the datum |
| --- | --- |
| biggest gain | **ZHOU Guanyu** (Kick Sauber) 19 → 14, **+5** |
| biggest losses | **Fernando ALONSO** 5 → 10 (**−5**), **Esteban OCON** 13 → 18 (**−5**) |
| busiest, with a long stop | **Alexander ALBON**: **13 position changes** and a **34.9 s stop on lap 3** |
| next busiest | Lewis HAMILTON (10 changes) |
| the start's drama | a **DOUBLE YELLOW in sector 3** at 19:04:04 → yellow → clear |
| the turn at the end | **on lap 5 the whole field drops ~66 s** (100 s → 166-168 s): a safety car period |
| fastest lap | Carlos SAINZ 99.923 (lap 2), VERSTAPPEN 99.991, LECLERC 100.341 |

**The window's story in one sentence**: *a start with an incident in sector 3; Alonso and Ocon lose five places
while Zhou gains five; Albon, damaged, changes position thirteen times and stops for 34.9 s; and on lap 5 the
safety car freezes the race.* That is what the commentary should be **about**, instead of reciting twenty
drivers' sector times.

**The declared salience rule** (a decision taken here and reversible, recorded so it is not inherited): a driver
or moment is salient by **magnitude of position change**, **involvement in a flagged sector or a race-control
message**, **a pit stop**, and **a lap-time outlier either way** — and the rule **excludes nationality, team
affiliation and championship standing**, which this project has no data for and will not invent. The
alternative considered and **not** chosen: prioritise the front of the field (leader and podium). Both are
defensible; what is not defensible is leaving it unsaid.

**The design, in units, sequenced by what unblocks what.**

1. **The citation format — must go first, because until it lands nothing airs** (measured: only 28% of events
   could air). Two parts, both with the measured basis: **(a) render the `EVIDENCE` block unambiguously**, since
   the prompt teaches `- <reference> = <value>` while the instruction says *exactly* `EVIDENCE: <reference>`, and
   55 of 206 calls copied the value too; and **(b) normalise a cited event identity to that event's supplied
   references**, since 93 calls cited `laps[3]` — a faithful name for a real event, admitted by mapping it to the
   references the event owns, so the evidence tuple stays valid and no unsupplied token can air.
2. **Names and teams in the prompt**: `driver: Lando Norris (McLaren, #4)`, with `broadcast_name` for the
   register and `team_colour` for flavour, joined from the recorded drivers payload.
3. **Salience as context**: the prompt receives the window's **stories** — who is gaining, who is losing, who
   stopped, which sector is flagged, who set the fastest lap — so the colour seat can answer *why*.
4. **Two modes, declared per turn**: a routine lap is **build** (one line, context); a position change of two or
   more places, a flag, or a pit stop is **climax** (short, emphatic) — the prosody structure and Ellis's rule.
5. **The start aggregation**: the twenty lap-1 events become **one "start" turn**, with the individual laps
   summarised per lap afterwards, because twenty near-identical sentences are not a start.
6. **Economy and tone**: the lead one or two sentences, the colour the detail; emphasise the positive.

**The championship context, measured (2026-10-11), and it is light.** Three paths the contract had listed as
documented-only now answer, and the whole championship picture of a race weekend is **53 rows**: 23 in
`championship_drivers`, 10 in `championship_teams` and 20 in `session_result`. The first two carry **both
checkpoints in one call** — `position_start`/`points_start` before the session and `position_current`/
`points_current` after it — so the "before and after every race" cadence is the **source's own shape**. Both are
**race-session-only**, so a practice or qualifying session has none, and an **in-race provisional** table still
has to be **derived** from the live positions plus the season's points rules, which are a small **declared
per-season** dataset (the fastest-lap point existed in 2024 and does not in 2025; sprints award their own points).
**Nationality and team need no separate job at all**: `drivers?session_key=X` is the **session's entry list** and
already carries `country_code`, `team_name` and `team_colour`, so the join refreshes itself at every race
weekend — a yearly refresh would name the wrong team for the rest of the season the moment a seat changes.

**The language variant, researched (2026-10-11), and it is a product decision.** The booth already **requires**
a language with no default, so the variant is the natural extension of a decision the product already makes.

- **The market is split, and measurably so.** ESPN holds F1 rights through **2028** for **18 Spanish-speaking
  countries** (South America, Central America and the Caribbean), and that deal **excludes Mexico**, which has
  its own broadcaster. **Spain** is exclusive to **DAZN F1**, with a long-running, strongly characterised team
  (Lobato narrating, de la Rosa and Cuquerella analysing).
- **The industry convention for a pan-regional product is `español neutro`** — the exportable variant born in
  Mexican and Puerto Rican dubbing studios — and the literature is explicit that its value is **portability**,
  with the cost that it sounds **artificial everywhere**. That is a real trade, not a synonym for "generic".
- **And F1 is a particular case**: the **Argentine relato was the regional voice** for decades. Fernando
  Tornello narrated the category *"para Hispanoamérica"* with iconic greetings of his own, so `es-AR` is **not a
  niche in this sport** — it has regional F1 pedigree that most markets do not.
- **Therefore**: the variant is a **first-class setting with a declared default and a declared lexicon**.
  Recommendation: default **`es-419` (neutral)** for a pan-regional product, with **`es-AR`**, **`es-MX`** and
  **`es-ES`** selectable, and each variant **declaring its register** rather than leaving it to the model:
  voseo for `es-AR`; the lexical pairs that actually differ in motorsport (coche / auto / carro, neumáticos /
  llantas, gasolina / nafta, boxes / pits, *safety car* vs *auto de seguridad*); and how each variant renders a
  driver's name.
- **It is an audience claim, so it is testable** — the pilot can run **the same window in two variants** and
  compare. Until then the choice is **declared, not assumed**, which is this project's own rule.
- **And it cannot touch the guarantee**: the citation protocol is **language-independent** — the evidence is a
  list of references, not prose — so the variant can change the words and never what is allowed to air.

**Implementation, verification and native review (observed).**

- **The decision, and why (a) rather than (b)**: shape 5 is declared as a **fifth shape described by its
  mechanism**, not as an instance of the dotted-suffix boundary. The two do not coincide: the
  space-separated form (`position[0].position [99].evil`) contains **no dot**, so calling the family a
  dotted suffix would be false for one of the three measured cases and would relocate the ambiguity
  instead of removing it. While registering the unit the parent also corrected its own first draft of
  the enumeration, which named `U+314F` instead of `U+034F` — caught before the commit.
- **Final declaration**: the module docstring now enumerates **six** shapes left airing, defines shape 5
  as *anything that is not a word character* with the measured separators as **examples, not the
  definition** and the family declared **open**, adds shape 6 (a bracket-leading token with no family
  word, invisible because the scanner's derived grammar requires `word[`), and states that closing them
  is a **product trade belonging to the user**. The normalization boundary declares the leak as **a
  family** — any character that survives normalization and is neither a word character nor whitespace,
  with `Mn`/`Mc`/`Me` as the common cases — and names `U+034F` as the pinned **representative**, with
  `U+0301`, `U+0308` and `U+0903` behaving the same way and the representative-versus-original
  distinction disclosed where a reader sees it.
- **Four writer passes**, every one driven by a measurement: the unit's objective; the **open separator
  family** (hyphen, comma, colon, slash, parenthesis, apostrophe all air — the verifier's sharp probe,
  which also found shape 6); the **combination-mark family** (`Mc`/`Me` defeat the scanner exactly like
  `Mn`); and one pass that only pinned the measured cost. Plus parent-made wording and one parameter
  each. **No behavioural RED is claimed anywhere in this unit** — it declares and pins existing
  behaviour, and that was said instead of manufacturing a red.
- **Documentation-only in `booth.py`, proven by inspection**: one hunk, the module docstring spanning
  `1–113`, and the bytes after the docstring identical between `da5cf79` and the delivered revision.
- **Independent verification, three passes**: the first certified the six-shape declaration and found
  the `Mc`/`Me` gap; the second certified the reworded sentence, the category table (`Mn`, `Mc`, `Me`
  air; `Cf` refused; word characters refused), the count reconciliation and both pin-teeth mutants; and
  the third certified the **final bytes** in a separate worktree holding byte-identical copies, because
  the harness refused child launches pointed at this worktree. **Independence note, stated plainly**:
  between the second and third independent passes the parent measured the delta itself (docstring-only
  proof, category probe, both mutants), so the third pass is what certifies the delivered revision.
- **The space-separator question, settled by measurement**: a plain space does **not** by itself defeat
  the scanner; the discriminator is whether a **family word survives unconsumed** immediately before the
  bracket. `position [99].invented` is a complete fabricated citation whose own family word starts a
  match across the space joint, so it is refused; the shape-5 whitespace case airs because the earlier
  clean-reference match consumed the word the fragment would need. The docstring states that mechanism
  and its two statements are consistent; the parent's probe expectation was the thing that was wrong.
- Native review `review-5ef4944728b40676`: tier **medium**, one lens, 2 files, **173** changed lines,
  candidate tree `84d7c65bc073abbe31812ce701a844137a424117`; **approved on the first reviewer run with no
  correction opened**; the exact acknowledgement **burned** authority (`consumed_revision
  sha256:f19b026e…`, `gentle-ai.review-acknowledged/v1`). Two informational findings, no bodies, read by
  the parent rather than reconstructed: `R3-doc-stale-leak-placement` (`booth.py:56-57`) — the clause
  "no exact placement was recorded" uses *placement* for what was unrecorded about the **character**,
  while the docstring itself defines the place (inside a structural joint), so the noun is stale; and
  `R3-shape5-whitespace-tolerance-scope` (`tests/test_booth.py:1124-1127`) — the `space` parameter's id
  and comment suggest the separator is the mechanism, while the measured discriminator is the consumed
  family word, so the test's framing is narrower than the rule it exercises. Both are wording and
  coverage observations, neither changes behaviour, and both are carried with owner and trigger: the
  next unit touching the scanner or the declaration.
- **Committed** as `fe5894734daa6e86cb285246e69e397d464bd4d8`, Conventional Commit
  `docs(booth): declare every airing shape and pin each one`. Pre-commit `HEAD` tree equals the
  controller's `base_tree` (`090012fb…`), the **staged tree equals the reviewed candidate tree**
  `84d7c65b…`, and the committed tree equals both. Blobs: `booth.py` `a6984018…` (795 lines),
  `test_booth.py` `1c629d19…` (1810), `__init__.py` untouched at `458afd4c…`. Suite **753 passed**
  (the F09b tip was 736).
- **The ten structural mutants, listed here so a later verifier does not have to ask** (a verifier had
  to ask, because the F09b record named the result without the set): (1) the priority band emptied in
  `_speaker_for`; (2) alternation derived from the event index instead of the turns that aired;
  (3) the character budget dropped in `_bounded_context`; (4) the always-include-the-previous-turn rule
  dropped; (5) an uncited answer accepted in `_parse_answer`; (6) a never-supplied reference accepted;
  (7) repetition suppression removed in `run`; (8) the stale comparison `>` narrowed to `>=`;
  (9) degradation emitting a turn instead of a typed outcome; (10) the no-overtake prompt rule removed.
  All ten were killed on these bytes, none required tuning, and the hash was restored after each.
- **Carried, with owner and trigger**: the two review findings above; **`Me` is named in the docstring
  but has no dedicated pin** (its behaviour was probed, not pinned — the docstring claims only that
  `Mn`/`Mc`/`Me` are common cases, so nothing is overstated, but a future unit could pin one); and the
  certification's sharp probe found `position]99[.invented` (reversed brackets) airing, covered only by
  the general out-of-scope sentence rather than the numbered enumeration — enumerating it would be a
  **seventh shape** and therefore a decision, not a tidy-up.

### F10 — Wire bounded end-to-end orchestration

- [ ] Correlate enrichment by event/session/version, apply bounded join deadlines,
  prioritize flags/incidents and expire obsolete commentary before dispatch.
- Acceptance/checks: offline replay covers missing/late enrichment, bursts,
  duplicate/out-of-order delivery and session reset; historian outages do not
  stop fresh factual calls. Queue size, timeouts and degradation are observable.
- Depends on F05/F09. Commit/checks: pending.

### F11 — Package the services and Redis in Docker Compose

**Deferred from the MVP** (see the MVP cut above): packaging is deployment, not demonstration, and
it depends on the deferred F05/F10 multi-service shape.

- [ ] Build `sync`, collector, analyst, historian and booth images, plus Redis and the
  local SQLite store volume; configure internal networking, persistence,
  readiness/health checks and clean shutdown.
- Acceptance/checks: Compose config/build/smoke with fixture sources and fake
  provider; non-root application containers, no embedded credentials or default
  public Redis port, readiness rather than depends_on-only startup assumptions.
- Depends on F10. Commit/checks: pending.

### F12 — Verify integrated replay, observability and CI

- [ ] Ship offline regression CI, operator instructions and end-to-end fixtures
  for race, qualifying/sprint qualifying and practice, including failures.
- Acceptance/checks: reproducible container replay, metrics for data age/end-to-end
  latency/queue/usage, sourced transcripts and graceful API/Redis/provider outage.
  Record all failed, skipped and pending checks; define measured acceptance limits.
- Depends on F11. Commit/checks: pending.

### F13 — Run one separately authorized live pilot

- [ ] Confirm subscription/credentials, session availability and a human-approved
  request/token/cost/time ceiling; verify known enforcement limitations first.
- Acceptance/checks: one bounded real session/model observation with timestamps,
  usage and transcript evidence; stop on the agreed failure/budget conditions.
  No automatic retries beyond the grant, purchases, broadcasting or publication.

**The pilot plan, written before any call is made (2026-10-11), so that about a dozen carried findings become
checkable items the day a subscription exists.** This is a **plan, not a grant**: it authorizes no call, no
credential and no purchase, and the pilot still needs the user's own explicit request.

**Preconditions, in order — and the first one has already cost a call.** (1) **Reconcile the gateway's
advertised aliases against Google's official model list** and record the chosen id as a **decision rather than a
discovery**: the twelve advertised ids are the gateway's **own aliases**, and no id may enter code or
configuration as a provider contract without that reconciliation. (2) Confirm the credential source is the
declared one (`.env.private/clients.env.sh`; `GOOGLE_GEMINI_BASE_URL` plus `GEMINI_API_KEY`, never a fallback)
and that the base-URL derivation is the version-less one — the first granted probe returned **404** because the
declared `/v1` composed a doubled version segment. (3) Agree a **ceiling**: the product decision on record is
per-session spending without a hard cap, but the pilot is the first real spend, so the grant itself states a
bounded request, token and wall-clock ceiling. (4) **Choose a session that already has data, and the first
live test found the trap**: the free listing includes rounds that are **scheduled but not run** — for 2026 it
returned 25 rows named `Race`, of which **19 had a past `date_start` and 6 were in the future** — and selecting
the most recent by `max(date_start)` picked `2026-12-06` (Abu Dhabi, `session_key` 11436), whose five collector
families **all answered 404**. The selector must therefore **filter to past or completed sessions** —
`pick_most_recent_completed_race(sessions, now)` — or tolerate the 404 explicitly. It is recorded **here rather
than as shipped code** because **no repository code selects a session by date**: the product takes an explicit
`session_key`, validated as a positive integer, and the date-based selector was the parent's throwaway probe.
**And the free historical path itself was exercised live on 2026-10-11**: Singapore / Marina Bay 2026,
`session_key` 11388, **1,863 events** derived from payloads the collector had never seen — one event per in-scope
record, 22 distinct drivers, 1,816 timestamps known and 47 explicitly unknown because the stints family carries
no timestamp field — in **6 requests at ~1 req/s**, paced by the project's own limiter, with no credentials and
nothing written into the repository. So what the pilot adds is the **authenticated/live** half, **not** the data
path.

| step | what the pilot sends | which carried findings it retires or sharpens |
| --- | --- | --- |
| A | one trivial prompt through `GoogleGenAIClient` on the corrected base | re-confirms the route and captures the **raw usage payload** the spend report needs |
| B | one **real booth turn** — the actual commentary prompt the product builds, with evidence | `R3-marker-word-false-refusal` (does a real model open a line with the marker's own word?) and `R3-docstring-omits-bracket-fragment-leak`, which needs a live transcript showing a fragment |
| C | three to five turns with a **retry forced** by a transient condition | `gemini.py:484-488` — usage is recorded **per attempt**, so a retried call records usage more than once, and only a real quota shows it — plus `R4-retry-amplification` |
| D | a deliberately **invalid model id** | the error shape: how the provider **types** the status code (`gemini.py:258-259` tests `isinstance(code, int)`, so a provider sending `"429"` as a string would not be retried), and what a body looks like with a credential in the same payload |
| E | one call with a **tiny `timeout_seconds`** | `gemini.py:348-354` — the SDK call receives **no timeout from configuration**, so whether any bound exists is unverified |
| F | one call with a **revoked or rotated** credential | issue #4, the 401/403 invalidation path, deliberately unimplemented |

**What to capture, and in what form.** The **wire-captured URL** for every call — a reconstructed string is not
an observation, and that rule already cost this project a wrong diagnosis; the raw usage fields per call; the
**sanitized** error shape for step D (status, class, and whether the message echoes anything back); the model id
as a recorded decision; and the spend report in **tokens, not currency**, until pricing is reconciled from
Google's documentation as its own step — measured usage is **not** a cost, and `gemini.py:559-566` already says
it out loud: **no cost stop exists before F13**.
**Stop conditions, agreed before starting**: a credential or token appearing in output or logs; spend beyond the
agreed ceiling; a provider error whose body echoes the prompt back; or a call hanging past the agreed wall-clock
bound (which is itself the answer to step E).
**What the pilot will not establish, stated so nobody reads it as more**: one session, one model and a handful of
prompts prove the route, the usage fields and the error shape — not streaming, not multimodal input, not
stability under load, not the other eleven aliases, and not any general claim about commentary quality. Every
claim above rests on the **evidence captured**, not on a successful run.
- Depends on F12 and fresh explicit live permission. Commit/evidence: pending.

## Current next step

F00–F02 are closed and published on main through `fc30084`. F03a, F03b and F03b-1 are
reviewed, committed and published on `origin/feat/f03-source-adapters`. F03b-1 closed in
`3ec02ea`, independently verified at 34 focused/185 full-suite tests and native-approved/
acknowledged, with five informational advisories carried separately. Main is unchanged.

Active: **the plan's tiers are done; what remains is scope the user has not opened.** F12c closed the last unit
of Tier 2.1/2.2 — the repository now commits its lint selection, enforces the Python floor with a 3.12/3.14
matrix, and asserts the workflow and the guard **from the suite**, so the two caveats that rode on every claim
this project made are retired. `main` sits at `afdc2618` after PR #30. **Tier 1 is closed too**: the over-refusal
that two independent reviewers found is fixed by a **behaviour** change (`e39c5f9`, published as PR #27) — all
five false refusals now air and all four escape channels stay refused, each with the test that covers it. The
peer session has **no open unit**: it has its next assignment offered in writing, split by file because the tier
signal **travels with the path** — the `tests/test_ci_config.py` findings in a medium unit with **no native
review**, and the `ci.yml` findings in **one** high unit, since any unit touching the workflow lands at high with
four lenses and batching saves **rounds** rather than tier. What stays unopened is scope the user has not
authorized: **F05 + F11** as a pair (transport before packaging), **F06 before F07**, and **F13**, gated on a
purchased subscription and its own explicit grant, with its plan already written and **no call made**. The
register carries **zero rows in NOT FOUND** and a set of method rules that each cost an error to learn; the ODD
mirror is six records and the splitter handles any number of parts.

**F10 closed: the command, the derivation and the two proofs.** `20af86f9`, three paths, **991 additions and
0 deletions** — `run.py` 335 lines, `test_run.py` 643, and 13 additive lines in `__init__.py`. Suite
**730** (706 + 24), Ruff 0.16.1 clean on the three paths under the harness config (isort included), Pyright
0 errors. Native review `review-0114285928bfdd2d`, **medium tier, a single `review-reliability` lens**, 991
lines frozen against a 200-line correction budget, approved on its first run and its authority **burned**
with `consumed_revision sha256:4e76235a…`. Independent verification `mv37vvl9-1z-bker` PASS, six targeted
mutants with five killed, and it **named the survivor instead of smoothing it**: removing the
provider-disagreement refusal was undetected, because the test used a message-blind
`pytest.raises(ValueError)` and the removed refusal falls through to the credential guard, which raises a
*different* `ValueError` of the same type. The parent closed that hole rather than carrying it — the test
now asserts the refusal's own message, and the kill was **re-proved in the verifier's shadow**, with the
shadow confirmed as the module under test (`f1show.run.__file__` and sha256 `ab244f03d9fcad1d`). That is
the pattern worth remembering from this unit: **an assertion that names a guarantee and is satisfied by a
different failure is a guard that reads as coverage without being coverage** — the same shape as the
`SnapshotResult` export that survived five units behind a familiar warning.
**The two registered requirements were proved, not asserted.** The base-URL derivation was exercised
against **both** declared forms — one carrying `/v1` and one carrying none — as two parameterised cases,
each with the composed URL **captured from the wire** through a recording transport with zero network I/O;
both captures are the identical string `http://127.0.0.1:8317/v1beta/models/<id>:generateContent`, with one
`v1beta/` and one `models/`, which is exactly the requirement the operator-gateway record above set and the
requirement the first failed probe taught. And a live call cannot happen by omission: `main`'s provider
selection has **no default**, and a selection that disagrees with `settings.booth.provider` is refused in
**both directions** before any client is built. The loader reads exactly the collector's five event-bearing
families and refuses a missing directory, a missing family file or an absent session with a **typed** error
rather than a silently empty payload list, and the parent reproduced the strong claim itself:
`collect_session_events(9617, load_recorded_session(9617))` equals the same call over the raw fixtures event
for event — **1,648 events, equal** — with every row carrying session 9617 and the counts matching the
recorded provenance (position 403, laps 1059, pit 23, stints 43, race_control 120). The verifier added the
MVP's own acceptance criterion in the strongest available form: two full offline runs produced transcripts
and printed output **byte-identical** at 127,060 characters, and the `repr`-fallback damage registered for
`booth.py` is **not reachable** from recorded evidence, since every evidence value comes from `json.loads`.
**Four informational findings, and a register reconciliation that this unit forced.** The review left R3-001
(WARNING) at `run.py:123-128` and three suggestions at `:243-255`, `:286-316` and `:168-173`; their bodies
are unrecoverable, so the register records the **location as the identity**, the subject as the parent's
reading of that location, and the owner and trigger as the parent's inference, labelled as such. More
useful: **the same commit reached four previously registered triggers owned by F10, and three of them did
not fire.** F10 chose a dialect and a base URL and promoted nothing else into the engine — `main` calls
`run_session` without the bound parameters, so every bound keeps its signature default, and no timestamp
parse is fed from configuration. Each of those entries now says so **at its own location** rather than in a
summary, so a reader can check the claim without trusting this paragraph. One nuance the verifier reported
honestly and worth keeping: the recorded corpus is single-session per family, so the loader's `session_key`
filter is caught by the unknown-session refusal rather than by a count change.
**Parallel track, coordinated 2026-10-10.** A second session implements **F08** (the Gemini gateway)
in an isolated worktree `/home/s/dev/projects/work/F1Show-f08`, branch `feat/f08-gemini-gateway`,
based on `0b1f0c7`, registering its own design in that branch's copy of the F08 section. Verified
state at coordination time: two writers total — this session and that one — plus a third
`git worktree` entry that is **not** a writer at all but the review integrator's frozen detached
candidate view under `.git/gentle-ai/candidate-views/`, which is worth knowing because it looks like
a third agent in `git worktree list`. The merge-conflict surface between the two branches is exactly
two files: `src/f1show/__init__.py`, which **both** modify additively and which the parent resolves
on integration because this branch carries the tip, and this task document, which both modify and
where the parent's version wins with the F08 design block re-applied on top. `feat/f03-source-adapters`
is **never rewritten**: only fast-forward pushes (`3f52c33`→`ce7d113`→`7b56e49`) and PR merges have
ever landed on it, never a force-push, squash or rebase. At that moment the remote sat at `7b56e49`
while the local tip was `e999a10`, six commits unpublished, and the F04 source was still uncommitted
pending verification — both facts were disclosed to the other session rather than left implicit.

**F09 integrated, and its closure was verified by identity rather than by report.** The peer's final data:
tip `b1990deae61684ca3b2028e3788066ad4fa654d5`, seven commits over `ed41add` — five design and correction
documents, the source commit `52ab80f209aeceae153e3fae37df9a71e5517ba6`, and the evidence commit. The
parent measured the tip itself because the peer's message had left a literal placeholder in its place,
and then verified the identity chain the peer claimed: the source commit's tree **is** the reviewed tree
`6b35c7067b138bc8564c13ba02f7ae74d71f111a`, its parent's tree **is** the controller's frozen `base_tree`
`b0f5e6b48757a161f6a5341d11ae4de0c46fb009`, the scope is exactly three paths, and every documentation
commit touches only `odd/tasks/f1show.md`. File sha256 at that commit — `booth.py` `c8b18f4a…`,
`test_booth.py` `1d5ee7d7…`, `__init__.py` `458afd4c…` — all match the peer's report.
**A false alarm the parent caught by logic rather than by asking**: those three values were first compared
against git **blob OIDs** and appeared not to match. A tree match is logically impossible with differing
content, so the error had to be in the comparison — the peer quotes **sha256** while the parent was reading
blob OIDs, two different functions over different byte streams. That confusion has now appeared three times
in one round, and this was the first time the parent caught it unaided.
**The integration itself**: seven cherry-picks in order, and the source commit applied with **no conflict
at all** — git merged the additive export block by itself. A clean merge proves nothing, so the parent
verified the result instead: `booth.py` and `test_booth.py` now hash **exactly** to the reviewed tree,
`__init__.py` holds **101 exports** with **zero duplicates**, **both** export sets present, and **zero
advertised names that fail to resolve** — which both explains the peer's earlier 101 measurement and shows
the new public-surface guard covering the peer's eight names without a line of extra work. The suite is at
**706 passed**: this branch's 644 plus the booth's 62.
**What F09 declined to call capability**, and where it goes: the semantic half of F04's rules belongs to
F13; the residual citation channels — a leading bullet, `EVIDENCE` with a space before the colon, a mid-line
mention, and a bare reference, all of which escape while the evidence tuple stays validated — are the
peer's next assigned unit; the duplicate-citation collapse works but has no test, so it is a pin rather
than a change; and two pins encode intent more than completeness. The peer ran **three independent
verification rounds**, each killing 10 of 10 mutants with copies guarded by import proofs, and the first
round found the citation-protocol defect the native review had missed — the fourth time in this session
that verification found what the author and the reviewer did not. Its first candidate's review
(`review-e102f9481318fa6f`) stayed **superseded and unacknowledged**, because it approved bytes that were
then corrected; the final review `review-25573bd84c132770` approved on its first run and its authority is
**burned**. That ordering — complete verification before the native review, never in parallel — is the lesson
that cost the peer a wasted model run, and it is recorded with its price attached.
**Delivery state.** `main` sits at `2c83a150` and contains all nine F03 units, merged through PR #1
and PR #2. The feature branch is ahead of it with the F03-cleanup work, the recorded fixtures and
F04, all unpublished: the remote is at `7b56e49` while the local tip has moved past it, and F04's
source is still uncommitted pending review. Publication of any of it remains a separate human
decision. The native authorities for F03c-1, F03c-2, F03c-3a, F03c-3b, F03c-4, F03d-1, F03d-2 and
the advisory follow-up are **burned**; never query or reuse them. Two earlier advisory regions were
examined read-only, with native descriptions never found locally and the observations explicitly
labelled as the parent's own rather than the provider's intent.

**Standing constraints.** Writes stay single-threaded. No model ID may enter configuration or code
until account enumeration and current documentation verify it. **No live, model, purchase or
deployment call is authorized**, and no subscription exists: the project runs in **free mode**, so
real-service correctness remains an F13 question and the live gaps are tracked as issue #3.

**Operator gateway, observed 2026-10-10, recorded for F10.** The endpoint the project actually talks
to is a **local loopback gateway**, not Google: the configured base URL is
`http://127.0.0.1:8317/v1` and the credential is a single API key. Details that change how F10 must
be written: **the `/v1` is already part of the base URL**, so appending another one duplicates the
path and returns a 404 — a trap that has already cost a debugging cycle. **Both surfaces answer on
that gateway**: the OpenAI-compatible one returned `GET /v1/models` 200 in 0.02 s and
`POST /v1/chat/completions` 200 in 0.82 s with usage 8/1/9, while the native one returned
`GET /v1beta/models` 200 in 0.002 s in native shape and advertised **the same twelve entries**. So
the native route **exists** and `GoogleGenAIClient` has a real endpoint there — which downgrades the
risk raised when only the OpenAI-compatible surface had answered. What remained **unproven is a
native-dialect generation**, and matching listing shape is necessary but not sufficient — that question
was later **closed with a positive result** by two granted probes, recorded below. And the advertised ids are **gateway
aliases** whose `-high`/`-low` suffixes are the gateway's own effort tiers, so **no id from that
enumeration may enter configuration as a provider contract** before reconciling with Google's
documentation. The full record lives in `docs/EXTERNAL-CONTRACTS.md`. A hygiene note worth keeping:
a generated summary of that enumeration listed eleven entries while the raw artifact held twelve,
the missing one being `gemini-3.6-flash-high` — **read the artifact, not the summary.**

**The granted native generation was attempted once and FAILED — with a precise cause, which is the
valuable part.** Verifier `mv33f9o2-1s-obwt` exercised the published `GoogleGenAIClient` over a real
`google-genai` client with the base URL **exactly as declared**: typed provider refusal, **HTTP 404** in
0.071 s, one call, no retry, no fallback, the declaration deliberately **not** repaired to make it
succeed. The cause is a **composition collision**, confirmed offline from the installed SDK source
rather than by spending a second call: when an `api_key` is set the SDK appends its **own versioned
path** (`v1beta/...`) to any custom base URL, so a declared value already ending in `/v1` composes to
`http://127.0.0.1:8317/v1/v1beta/models/models/gemini-3.5-flash-lite:generateContent` — a **doubled
version segment** that the gateway answers with 404, while the good native routes sit at the host root.
A second, independent trap was **claimed here and has since been REFUTED**: the record said `models/`
appeared twice because the adapter passes a model id through while the SDK prefixes the resource path.
That is **wrong**, and the peer session caught it with lines from the installed source; the parent then
re-verified it independently rather than accepting it: `google.genai._transformers.t_model` on the
non-Vertex path does `if model.startswith('models/'): return model`, so the prefix is **idempotent**, and
`_api_client.join_url_path` with the declared base composes `/v1/v1beta/models/<id>` with a **single**
`models/`. The doubled `models/` came from a **reconstruction in the previous report, not from the SDK**.
So the model-id shape is not a trap and F10 must not trim or normalise the prefix for it. **The lesson is
the one this session keeps meeting from another angle: a rebuilt string is not an observation.** The
previous report's URL was assembled rather than captured, and it reached this document as a fact. Any
future composed URL must be **captured from the wire**, or explicitly labelled as reconstructed. The parent had predicted exactly this class of finding when it noticed the declared `/v1`
against the working `/v1beta`, and its decision to keep the declared value and forbid a repair is what
turned a probable false success into a precise diagnosis. **What it establishes:** the declared
configuration is the blocker at the URL layer, and the failure happened before the dialect or the
adapter's mapping could be exercised at all — so it says nothing against either. **What it does not:**
whether the gateway's native `generateContent` route works under a correctly composed URL, nor anything
about response mapping, usage accounting or other aliases. Consequence for **F10**: wiring must not pass
the declared value straight into the SDK — supply the base URL without its version segment, override the
version through `http_options`, or use the OpenAI-compatible surface with a different adapter — and the
`models/` prefix trap has to be settled with it. Until one of those is exercised, **no native-dialect
capability may be claimed**. Credentials: the file was only read (SHA256 identical before and after),
never sourced or eval'd, and no secret was printed. **Closing this needs one more granted call** with a
corrected composition; the first grant is spent and was not stretched.

**The second grant closed it, and the native route WORKS.** A second granted probe succeeded: a native
Gemini generation through the published `GoogleGenAIClient`, with the base URL derived **in memory** by
stripping the declared trailing version segment, returned `text='ok'` in **1,015.6 ms** with usage 8
input / 1 output token against the alias `gemini-3.5-flash-lite` chosen at runtime from the native
listing. **And this time the composed URLs were captured from the wire** — through a recording transport
with a fabricated response, zero network I/O, the grant untouched — which is exactly what the previous
report failed to do. The declared base composes
`http://127.0.0.1:8317/v1/v1beta/models/<id>:generateContent` and 404s, while the corrected one composes
`http://127.0.0.1:8317/v1beta/models/<id>:generateContent` and returns the generation. **Both carry a
single `models/`**, independently confirming that the doubled one was a reconstruction artifact rather
than the SDK's doing. **What is established:** the gateway does serve native Gemini generation and the
published adapter composes correctly there **provided the base URL carries no version segment** — so the
declared configuration is a defect to fix, not a limitation of the dialect or the adapter. **What is not
established, and must not be claimed:** the `-high`/`-low` effort-tier aliases, streaming, multimodal
input, error-shape fidelity for timeouts, refusals and rate limits, thinking-configuration passthrough,
latency or stability under load, and correctness for the other eleven aliases. One alias with a trivial
prompt proves the route, not the surface. **Action — and a correction to the parent's own framing.** The
first version of this record called the declared value a defect to fix, and that recommendation was
**wrong and would have been harmful**: the peer session spotted that the `/v1` is **load-bearing for the
gateway's other surface** before the bad advice settled. The parent then verified it directly from the
operator's configuration, reading assignment names and value shapes only: `CLIPROXY_BASE_URL` and
`ANTHROPIC_BASE_URL` are the bare root, while `OPENAI_BASE_URL` and `GOOGLE_GEMINI_BASE_URL` carry `/v1` —
and `{GOOGLE_GEMINI_BASE_URL}/models`, which is `/v1/models`, returns **200**. So changing the declared
value to satisfy the Gemini SDK would break the OpenAI-compatible route that is already proven. What
exists is **one declared value facing two consumers with different conventions**: the OpenAI-compatible
surface wants the version in the base URL, while `google-genai` appends its own `v1beta` and needs a base
without one. Therefore: **derive the base per
dialect, in memory, and leave the declared value to the operator.** An earlier version of this record
asserted that normalising in F10 "works under either declaration and costs nothing" — the peer session
correctly flagged that as an **unproven property**, and this project does not record unproven properties
as facts. **F10's requirement, not yet met:** the derivation must be exercised against **both** base forms
— one carrying `/v1` and one carrying no version segment — as two parameterised cases, each with the
composed URL **captured from the wire**. The reason is the failure mode: a normalisation written only for
today's `/v1` shape, such as one that always strips the last path segment, would **fail silently** the
moment an operator changes the declared value and land back on the same 404 that took three rounds to
diagnose. General form worth keeping: **when one configured value serves two consumers with different
conventions, that is a composition problem, not a configuration defect** — and the sharper version, since
the same pattern bit this project three times in one round (a `/v1` appended by hand, a `models/` prefix
reconstructed, a declared base assumed self-contained), is that **each one was a value whose context was
assumed instead of measured.** The dialect question remains settled in favour of the native route, so
**F10 can use the already-published adapter** instead of needing a new one.

**A blocker that was carried, questioned, and then cleared on the user's instruction.** The automated
lens check reported `src/f1show/__init__.py:13 I001` as a blocker every time that file was touched.
It was **pre-existing**: the same finding appeared on `origin/main` (13:1) and on `0b1f0c7` (9:1), a
commit from before this session introduced anything, and the line had only moved because the
integration added four docstring lines. The parent carried it with the reasoning recorded on issue #6
and a pointer to #7 — the line-length half of that rule comes from a configuration that **lives
outside this repository**, and conforming the repo to an invisible config would settle the symptom and
leave the cause — and the check kept firing, which made the standoff itself a cost. The parent then
put the choice to the user rather than either ignoring the tool or fixing silently, and the user
chose to fix it and close the loop.
**Done as a formatting-only unit**, `59f3ad0508355f963e1c615c95c3f3bcca064579`,
`style(init): sort the package import block`, one path **+8/−3**: it wrapped the over-length
`from f1show.ingest import ...` line and reordered `HttpClient` ahead of `HttpDecodeError`/`HttpError`
and `RetryingHttpClient` ahead of `RetryPolicy`. Verified rather than assumed: the **imported name set
is identical** before and after (93 names, none added or removed, proved by an AST comparison against
the published version), the full suite stayed at **643 passed**, both the `--select I` rule and the
whole harness config report *All checks passed!*, and the module still exports 93 names with spot
checks on both parties' symbols. ASSESS returned **`reviewDue: false`, `under_budget`** at 11 changed
lines, so no native review was run for it — a decision on the record, not an omission. It is
**unpublished** work awaiting its own delivery decision.

**Issue #6 closed, and it hid a real defect behind a familiar warning.** The line the parent had been
reporting as "the pre-existing `SnapshotResult` warning" for several units was in fact a **broken public
export**: the name was listed in `f1show.__all__`, the class existed at `src/f1show/snapshot.py:86`, and it
was **never imported**, so `from f1show import SnapshotResult` raised `ImportError` and a wildcard import
raised `AttributeError` — on published code. A warning repeated often enough stops being read, and
boilerplate is where real findings hide. The fix is one additive import line; the three other findings
were genuinely cosmetic and took narrow per-line annotations with reasons, none of which widened a
signature or weakened an assertion. **A peer session independently reproduced the defect in a second
worktree and measured its shape**: of all the names in `__all__`, this was the **only** unresolvable one,
and no test walked the list, which is why it survived. That produced the durable half of the fix: a new
`tests/test_public_api.py` reading the real `__all__`, refusing an empty or duplicated list, and resolving
every listed name — so the **next** decorative name fails the suite instead of living for years.
Independent verification PASS: the direct import and the wildcard both work and the object is the same
class; **all 93 names resolve with zero unresolvable**; the guard is load-bearing, proved by removing the
import in a `/tmp` copy and watching it fail while the pristine control passes; the suite is at **644**;
and the verifier **reproduced the pre-change contrast** from `git archive HEAD` to show the four errors
and the warning genuinely existed rather than reporting a clean result it could not contrast.
**Two boundaries are declared rather than left to inference.** The guard asserts only the forward
direction (`__all__` → module) and deliberately not the inverse, because `__all__` constrains only a
wildcard import and a reverse check would need a hand-maintained exception list on a surface that grows.
And the verifier found that its `getattr`-based resolution is in fact **stricter** than the language: a
real `from f1show import name` additionally falls back to importing a submodule of that name, which
`getattr` does not, so a name exported only as a submodule could false-positive fail. That is a gap in the
strict direction, not a weak one. **Both the verifier and the reviewer flagged it independently**, which
upgraded it from one agent's pedantry to something worth fixing, and it was fixed rather than carried —
because "carried as informational" is precisely how the broken export survived five units. The guard now
resolves through `getattr`, and on `AttributeError` falls back to `importlib.import_module`, which is what
the language itself does. **Proved in both directions**: in a copy whose `__all__` lists a submodule-only
name that nothing imports, the previous `getattr`-only logic **failed** (a false failure on a name that
imports fine) while the corrected guard **passes**, with an import proof that the copy was the module
under test. Committed as `test(api): mirror the import-system submodule fallback in the surface guard`.
Independent verification PASS on those bytes: pins identical before and after, the strict-direction
asymmetry reproduced in a copy whose `__all__` lists a submodule-only name while pinning
`f1show.__file__` per tree to defeat the editable-install `.pth` trap, and — the half that matters most —
**the teeth confirmed intact**, because a fix that removed the bite would be worse than the asymmetry: a
mutant naming a symbol that exists nowhere is still rejected with the mirrored `ImportError`, and the
pristine copy passes. Suite 644, Ruff clean with isort enabled. The verifier judged the docstring honest —
the implementation is literally the from-import algorithm — and **named two residual gaps instead of
smoothing them**: the mirrored `ImportError` replaces the underlying `ModuleNotFoundError` message (the
original survives as `__cause__` but is not shown), and a submodule that exists yet raises at import time
propagates a non-`ImportError`, so the guard reaches the same verdict through a different message shape.
Both are informational, because in every case examined the pass/fail outcome matches what a real import
does; they matter only to whoever reads the error text. Also worth keeping: the peer counted
**101** entries in `__all__` against this branch's **93**, and the difference is simply that its tree
carries eight booth exports — **the third time this session that two apparently conflicting numbers
turned out to be two trees**, so a per-tree count must always travel with its tree.
