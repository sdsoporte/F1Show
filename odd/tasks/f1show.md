# F1Show: complete distributed commentary system

## Outcome and current authorization

Build a replay-testable, real-time Formula 1 commentary system with five logical
roles: deterministic collector, tactical analyst and historian, plus two Gemini
commentator personas. Run four role services plus a dedicated sync writer, and Redis,
with Docker Compose.

**Authorization is per task and does not accumulate.** Repository bootstrap,
source-document preservation, current documentation and this ODD plan were authorized
together with preparation and closure commits and the initial push to `main` after
verification; that initial publication happened at F00 and **nothing has been pushed
since**. F01 (external-contract validation) was separately authorized and closed on
2026-10-09. **Application implementation remains unauthorized**: F02 onward needs a new
explicit grant, and live API or model calls, paid subscriptions, deployment, later
pushes, pull requests and automated merges are not authorized by anything recorded
here.

## Baseline and decisions

- Workspace: `F1Show`; local Git repository, `main` created at the bootstrap commit.
- Preparation branch: `feat/f1show-bootstrap`; public GitHub repository:
  `sdsoporte/F1Show`, created with the existing SSH/gh configuration.
- Repository-local Git identity (user-selected; no global identity exists on this
  machine): `sdsoporte <211432262+sdsoporte@users.noreply.github.com>`.
- **Publication.** `main` was fast-forwarded to F02's tip and pushed on 2026-10-09:
  `413a75d..8cbe94b`, 15 commits, no merge commit. `main` and `origin/main` both report
  `8cbe94b`. An independent read-only audit of the published tree was delegated to
  confirm the remote ref, the published file set, the absence of local artifacts and
  credentials, and that the published blobs match the reviewed ones.
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

1. Reconcile this file, the full Engram mirror `odd/f1show/tasks` and the visible
   todo projection before resuming. Keep stable IDs and one active task.
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
8. Update this file, its full mirror and todo after each actual task transition.
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
- **Next: F03**, needing fresh explicit authorization. It is the first unit that writes
  real data paths: the SQLite WAL store behind the `Store` port, the immutable Parquet
  session snapshots, and the `sync` writer with its historical and live adapters.

### F03 — Implement source adapters and replay/session lifecycle

- [ ] Build the sync writer's source adapters, the SQLite WAL store with Parquet
  snapshot export, deterministic replay and explicit session selection; seed mid-session
  state and handle end/cancel/reset without mixing sessions.
- Acceptance/checks: fake HTTP/clock tests cover history vs live auth, timeouts,
  429/backoff, empty data, invalid responses and per-endpoint watermarks/overlap.
- Depends on F02 (closed).

**Work units, planned before the first source write (2026-10-09):**

- **F03a — the SQLite store behind the `Store` port.** Schema for source records and
  watermarks, create-if-absent, WAL mode, upsert semantics that deduplicate by family,
  session and record identity, deterministic read windows by observation time, and
  `close()`. Tests run against a real temporary database, fully offline. A store-path
  setting joins the typed configuration, with the same rule as elsewhere: a documented
  default for the path, no default for anything that identifies a model or a secret.
  The port's contract is fixed already, so this unit must satisfy it rather than reshape
  it — a test asserts the implementation is substitutable for the in-memory double.
- **F03b — Parquet snapshots and the deterministic replay source.** Export immutable
  per-session Parquet snapshots with DuckDB, and a replay source that reads them and
  drives session choice explicitly, seeding mid-session state so a run can start partway
  through with correct positions, stints and lap history. The snapshots are the replay
  fixtures, so their determinism is the acceptance criterion, not their speed.
- **F03c — the `sync` writer, historical path.** Paginated historical reads over the
  `HttpClient` port with a per-endpoint watermark, resume and overlap handling,
  timeouts, 429 and 5xx backoff, empty and malformed responses, and session
  end/cancel/reset that never mixes two sessions. Exercised with the in-memory HTTP
  double and the frozen clock, so the suite stays offline and deterministic.
- **F03d — the live seam, and its honest limit.** Live access needs an OpenF1 OAuth2
  token, which requires the paid subscription the project has not bought. So this unit
  can deliver the live adapter behind an injectable transport and the authentication
  handling, exercised by a fake transport — **but its correctness against the real
  service cannot be established here**. Record that plainly rather than implying the
  live path is proven; the real validation belongs to F13, under its own authorization.
- **Decision carried from F01:** the store is SQLite in WAL mode with DuckDB over
  Parquet, not DuckDB as the live store, because DuckDB supports one read-write process
  or many read-only processes and every Compose service is a separate process.

### F04 — Implement deterministic collector and event detection

- [ ] Normalize positions, laps, sectors, flags, intervals and pit/stint data;
  deduplicate updates and preserve evidence timestamps/source fields.
- Acceptance/checks: replay proves fastest laps/sectors, position changes, flags,
  SC/VSC and pit events; no false first-lap record or inferred on-track overtake
  from a position change alone. Split event families into units when necessary.
- Depends on F03. Commit/checks: pending.

### F05 — Implement Redis Streams delivery and fan-out

- [ ] Define stream names, versioned envelopes, separate consumer groups for
  analyst/historian, acknowledgements, idempotency, recovery and retention limits.
- Acceptance/checks: local Redis tests show both enrichers receive each event,
  bounded backlog, duplicate safety and recovery after crash/pending messages.
- Depends on F02/F04. Commit/checks: pending.

### F06 — Implement deterministic tactical analysis

- [ ] Calculate contextual gap/pace/stint alerts with configurable circuit/session
  parameters. Treat tyre-life and pit-loss estimates as assumptions, not facts.
- Acceptance/checks: qualifying cutoffs follow the selected season/session rules;
  tests cover boundary values, lapped/null intervals, missing telemetry, pit
  interference and stale data. No hardcoded Monza or unqualified strategy claims.
- Depends on F04/F05. Commit/checks: pending.

### F07 — Implement evidence-grounded historical enrichment

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

### F09 — Implement the two-person commentary booth

- [ ] Implement lead/color personas, explicit turns, bounded history and structured
  transcript output using only current events and attributed enrichment.
- Acceptance/checks: fake-model tests prove ordering, evidence propagation,
  repetition suppression, stale-context exclusion and neutral outage behavior.
  Generated text quality still needs a separately authorized real-model trial.
- Depends on F06/F07/F08. Commit/checks: pending.

### F10 — Wire bounded end-to-end orchestration

- [ ] Correlate enrichment by event/session/version, apply bounded join deadlines,
  prioritize flags/incidents and expire obsolete commentary before dispatch.
- Acceptance/checks: offline replay covers missing/late enrichment, bursts,
  duplicate/out-of-order delivery and session reset; historian outages do not
  stop fresh factual calls. Queue size, timeouts and degradation are observable.
- Depends on F05/F09. Commit/checks: pending.

### F11 — Package the services and Redis in Docker Compose

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
- Depends on F12 and fresh explicit live permission. Commit/evidence: pending.

## Current next step

F00 and F01 are closed and published. F02–F13 remain unstarted and need fresh explicit
user authorization: the grants so far never covered application implementation, and this
backlog alone does not grant it.

Next is F02 (Python foundation and shared contracts) — the first task that writes real
source code, so it needs an explicit implementation authorization first. F02 must pin
the `google-genai` version resolved at that time (2.29.0 was latest on 2026-10-09),
decide the `httpx` versus `httpx2` question deliberately rather than by habit, and keep
SQLite behaviour behind a store boundary. **No model ID may be written into
configuration or code** until it is enumerated with the account and its GA status
confirmed in current documentation, and no price is attributable to a named model yet.
