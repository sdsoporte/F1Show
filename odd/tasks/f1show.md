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

- [ ] Create packaging/locked dependencies, typed configuration, event/enrichment/
  dialogue schemas and injectable clock, HTTP, bus, store and model boundaries. The
  store boundary must not expose SQLite-specific behaviour to the roles, so a later
  move off the single-writer model is a swap and not a rewrite; commentary language
  and model IDs come from typed configuration with no hardcoded defaults.
- Acceptance/checks: offline tests reject malformed data, missing credentials in
  live mode, wrong session IDs, invalid timestamps and secret-bearing log output.
- Depends on F01. Commit/checks: pending.

### F03 — Implement source adapters and replay/session lifecycle

- [ ] Build the sync writer's source adapters (httpx for historical and REST, MQTT or
  WebSocket for live), the SQLite WAL store with Parquet snapshot export, deterministic
  replay and explicit session selection; seed mid-session state and handle
  end/cancel/reset without mixing sessions.
- Acceptance/checks: fake HTTP/clock tests cover history vs live auth, timeouts,
  429/backoff, empty data, invalid responses and per-endpoint watermarks/overlap.
- Depends on F02. Commit/checks: pending.

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
