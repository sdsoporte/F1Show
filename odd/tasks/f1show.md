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
  - **F03c-4 — Session lifecycle. Design registered before writes; implementation pending.**
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
        `run.reset(session_key)` returns a NEW `SessionRun` with a new caller-supplied
        `run_id` and never reads, rewrites, deletes or truncates committed store rows.
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
  Per-unit checks: scoped pytest then full `uv run --frozen pytest -q`, observed
  RED/GREEN with coverage-only passes disclosed, native work-unit review under the
  user's enabled switch, local Conventional Commit and task/mirror/todo evidence.
- **F03d — the live seam, and its honest limit.** Live access needs an OpenF1 OAuth2
  token, which requires the paid subscription the project has not bought. So this unit
  can deliver the live adapter behind an injectable transport and the authentication
  handling, exercised by a fake transport — **but its correctness against the real
  service cannot be established here**. Record that plainly rather than implying the
  live path is proven; the real validation belongs to F13, under its own authorization.
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

F00–F02 are closed and published on main through `fc30084`. F03a, F03b and F03b-1 are
reviewed, committed and published on `origin/feat/f03-source-adapters`. F03b-1 closed in
`3ec02ea`, independently verified at 34 focused/185 full-suite tests and native-approved/
acknowledged, with five informational advisories carried separately. Main is unchanged.

Active: **F03c-4 session lifecycle**, one bounded writer after this closure/design/mirror/todo
reconciliation. F03c-3b source `d4e1bc4` is closed locally: 86 focused/396 full/124 HTTP-policy,
ASSESS medium/large accepted the writer record, native approval and exact acknowledgement with
reviewed/staged/committed tree equality; the two informational suggestions have no returned
bodies and are not fixes here. F03c-3a source `aca17e2` likewise closed, burned, tree-matched.
Probes-only CI gaps, the base `SnapshotResult` warning, the harness Ruff I001 and the unverified
Python 3.12 floor are carried, not fixed. No new source push. F03c-4 implementation, checks,
native review and local unit commit remain; F03d follows under the same F03 authorization.
The three registered advisory regions were examined read-only; native descriptions were
not found locally, observations are explicitly independent, no fixes authorized or made.
Published approved source/tracking remains `3f52c33`, remote main unchanged. F03c-1/F03c-2
review authorities are burned; never query/reuse them. Keep writes single-threaded and
limit 3a to ingest.py/test_ingest.py/additive package exports, with genuine behavior RED,
shared Store parity, records-before-observation-checkpoint and honest partial outcomes.
Future source publication remains a separate human decision.
F03c-3/4 and F03d injectable live seam remain pending and authorized for implementation.
Their publication is a separate decision. F04 onward requires a new implementation grant.

The user now authorized publishing this reviewed advance to `origin/feat/f03-source-adapters`
only, not to `main`; future units need their own delivery decision. No model ID may enter
configuration or code until account enumeration and current documentation verify it.
No live/model calls, purchases or deployment are authorized; real-service correctness
remains pending F13.
