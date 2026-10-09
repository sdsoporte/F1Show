# Source review: original corpus vs. the target design

> This review assesses the ten original Word documents now archived in
> [`../origis/`](../origis/). It records what the drafts got right, what is wrong or
> obsolete, and what each file contributes to the target described in
> [`ARCHITECTURE.md`](ARCHITECTURE.md). The originals are historical evidence, not
> current specifications.

## How this review was done

Each document's text was extracted and read against the target architecture. Findings
are attributed to the file they came from so that a reader can go back to the source.
The corpus is a set of overlapping drafts rather than a consistent set: several code
documents repeat the same modules with small differences, and `Development Code -
Multi-Agent F1 Commentary System.docx` is the superset of the numbered variants.

This review deliberately separates two things that the originals blur together:
**code that exists inside a Word document** is draft material, and **prose describing a
system** is a proposal. Neither was ever a runnable repository.

## What the drafts got right

These ideas survive into the target, in some cases reworked:

- **The five-role decomposition** — collector, tactical analyst, historian, and two
  commentator personas — is the right shape for the problem.
  (`Architecture Design_ Real-Time Multi-Agent F1 Commentary System.docx`,
  `Multi-Agent F1 Live Commentary System - Model Specifications & Architecture.docx`,
  `Development Code - Multi-Agent F1 Commentary System.docx`)
- **The dual-persona booth with explicit turn handoff** from lead play-by-play to
  color analyst is a sound structure, and the two personas are genuinely distinct in
  intent. (`Architecture Design_…docx`, `Development Code - …docx`)
- **The historian is naturally deterministic.** The reference implementation in
  `Development Code - Multi-Agent F1 Commentary System(3).docx` is an HTTP client with
  caching that makes no model call at all — which is precisely what the target
  historian is. The same is true of the analyst's arithmetic.
- **The collector/analyst module split**, and the idea of emitting structured event
  dictionaries instead of coupling components directly, is a reasonable first cut of
  the pipeline boundary. (`Development Code - Multi-Agent F1 Commentary System(1).docx`)
- **A standalone runnable collector loop with an explicit `main()`** is a useful
  development affordance, and it is what makes replay-first buildable.
  (`Development Code - Multi-Agent F1 Commentary System(2).docx`)
- **The event lifecycle and enrichment merge** — event, tactical card, historical
  payload, then a booth turn — is the correct data flow.
  (`Architecture Design_…docx`, `Development Code - …docx`)
- **Qualifying cutoff pressure and undercut-window detection** are the right *classes*
  of tactical signal, even though the constants behind them were fabricated.
  (`Development Code - …(1).docx`, `Development Code - …(3).docx`)
- **The Advanced-vs-API-key distinction** is correct and important: a Gemini Advanced
  subscription does not provide an API key, and credentials must live in a secret
  manager and never be committed.
  (`Acceso y Llamadas a la API de Gemini - Sistema Multi-Agente.docx`)
- **The four-service-plus-Redis topology** with per-service images and environment
  configuration is the deployment shape the target keeps.
  (`Docker & Cloud Emulation - Multi-Agent F1 Commentary System.docx`)
- **The endpoint catalogue and coverage list** are a usable starting checklist for
  validation. (`OpenF1 API - Real-Time Formula 1 Monitoring Guide.docx`)

## What is wrong or obsolete

### 1. In-process queues where the target requires Redis Streams

Every code draft transports events over a plain `asyncio.Queue`:

- `Development Code - Multi-Agent F1 Commentary System(1).docx` — `run(self, event_queue: asyncio.Queue)`
- `Development Code - Multi-Agent F1 Commentary System(2).docx` — `queue = asyncio.Queue()` in `main()`
- `Development Code - Multi-Agent F1 Commentary System(3).docx` — same collector loop
- `Development Code - Multi-Agent F1 Commentary System.docx` — same, and its topology
  table states "feeds `asyncio.Queue`"

`Architecture Design_ Real-Time Multi-Agent F1 Commentary System.docx` proposes a bus
but leaves it open ("Redis Pub/Sub, RabbitMQ, or Kafka"), and
`Docker & Cloud Emulation - Multi-Agent F1 Commentary System.docx` declares a Redis
service the code never connects to. The result is a documented bus and an implemented
in-process queue: an `asyncio.Queue` gives no durability, no replay, no consumer
groups and no cross-process delivery, so the "distributed" system was never actually
distributed. The target commits to Redis Streams with versioned envelopes, separate
consumer groups for analyst and historian, acknowledgements, idempotency, pending-message
recovery and bounded retention.

### 2. Deterministic code is labelled as an LLM, and LLM roles are misassigned

The code for the analyst and historian is pure Python arithmetic and HTTP. There is no
prompt and no model call in either. Yet:

- `Development Code - …(1).docx` and `Development Code - …(3).docx` head Module 2 as
  "Model: Gemini 1.5 Flash" and Module 3 as "Model: Gemini 1.5 Pro".
- `Multi-Agent F1 Live Commentary System - Model Specifications & Architecture.docx`
  assigns an LLM to **all five** roles, including the collector.
- `Acceso y Llamadas a la API de Gemini - Sistema Multi-Agente.docx` recommends
  Gemini 1.5 Flash for the analyst and 1.5 Pro for the historian.
- `Docker & Cloud Emulation - …docx` injects `GEMINI_API_KEY` into the analyst and
  historian containers even though those modules never read it.

The target reverses this: the collector, analyst and historian make **zero** LLM calls,
and only the booth requires model credentials. This also removes the entire
per-aggregation cost of the original design.

### 3. The historian hardcodes Monza for every circuit

`Development Code - Multi-Agent F1 Commentary System.docx` and
`Development Code - Multi-Agent F1 Commentary System(3).docx` both default
`enrich_event(..., current_circuit: str = "monza")`. In `get_circuit_records`, a
`CircuitRecord` is constructed with literal values — lap record `1:18.149`, driver
"Max Verstappen", year 2021, "Lewis Hamilton" with 8 wins, pole-to-win conversion
58.5% — and those defaults are returned **for any circuit id** when the lookup fails or
is skipped. The demo in the superset document then prints Monza trivia ("the Temple of
Speed", a "78%" conversion rate that appears nowhere in the record object) as if it
were retrieved. The target deletes fabricated circuit defaults: values are looked up
with attribution, and an unknown record stays absent rather than inventing a plausible
number.

### 4. Session selection via `sessions[-1]` does not establish an active session

`Development Code - …(1).docx`, `(2).docx`, `(3).docx` and the superset all do:

```python
active_session = sessions[-1]
```

The last entry returned by `/sessions?year=…` is not necessarily the currently active
session — it is last by whatever ordering the source uses, and it ignores dates, session
type and whether anything is running. There is no explicit session selection and no
handling of session end, cancel or reset, so a pipeline could silently attach to the
wrong session. The target requires explicit, user-visible session selection and clean
session lifecycle handling.

### 5. Inconsistent timestamps and unseeded record state

- **Timestamps are inconsistent or missing.** `PURPLE_SECTOR` and `FASTEST_LAP` events
  carry no timestamp at all; only `OVERTAKE` gets `entry.get("date")`. The dialogue
  turns stamp `datetime.now()` before generation, so the timestamp precedes the text it
  labels.
- **The incremental filter is written, then immediately defeated.**
  `run()` sets `self.last_poll_timestamp = now()` *before* polling, then uses that value
  as the `date>` / `date_start>` parameter — so each cycle requests records after a
  moment that is already later than the data it is about to fetch. Updates can be
  skipped entirely. The two endpoints also use different cursor fields (`date>` for
  position, `date_start>` for laps) against one shared cursor.
- **Record state is unseeded.** `best_lap_time` starts `None` and `best_sectors` start
  at `inf` with no history loaded. On the first observed lap of a session — or on any
  mid-session start — the code unconditionally emits `FASTEST_LAP` and three
  `PURPLE_SECTOR` events for lap one, because nothing better is known yet. The target
  seeds mid-session state and refuses to call a lap a session best without a real
  comparison.
- There is no as-of or provenance field on any event, so downstream consumers cannot
  tell how old an observation is.

*(All four points from the four code documents, chiefly
`Development Code - …(1).docx`, `(2).docx`, `(3).docx` and the superset.)*

### 6. No staleness, dedup, retry or cost policy

- **No dedup.** Re-polling overlapping windows re-emits the same record as a new event;
  nothing keys on a record identity, so duplicate `FASTEST_LAP`/`PURPLE_SECTOR` events
  are the normal case, not the exception.
- **No staleness bound.** An event that is minutes old is treated exactly like a fresh
  one.
- **No retry, backoff or 429 handling.** Every HTTP call is wrapped in a bare
  `except Exception: logger.error(...)` that swallows the error and returns an empty
  result. There is no timeout policy, no rate-limit handling and no backoff.
- **No cost policy.** Nothing counts requests, tokens or spend, and nothing can stop
  the pipeline on a budget. `Acceso …docx` mentions a free tier and pay-as-you-go but
  sets no ceiling.
- **No SLA or budget.** Neither `Multi-Agent F1 Live Commentary System - Model
  Specifications & Architecture.docx` nor `Architecture Design_…docx` states a latency
  target, an availability target or a cost budget; both assert that Flash/Pro are
  "ultra-low-latency" and "cost-efficient" without any measurement.

*(All code documents; the policy gaps are most visible in
`Development Code - …(1).docx` and the superset.)*

### 7. No distributed implementation

The bus is documented, the Docker topology is documented, and neither is real. No
document contains a Redis client call, a stream name, a consumer group, an envelope
schema, an acknowledgement, an idempotency key or a retention rule. Even the Compose
file that starts Redis leaves it unused by every service.

*(`Architecture Design_…docx`, `Docker & Cloud Emulation - …docx`, all code documents.)*

### 8. No test suite

There are no tests. What exists is demo code that prints:

- `test_broadcast_stream()` in `Development Code - Multi-Agent F1 Commentary System.docx`
  calls the **real** GenAI API against hardcoded Monza trivia and prints the result.
- `test_trivia()` in `Development Code - …(3).docx` calls the **real** historical
  endpoint.
- `main()` in `Development Code - …(2).docx` prints events from a live OpenF1 poll.

These require network access and credentials, assert nothing, and cannot run in CI.
The target replaces them with offline fixtures, a fake clock, a fake HTTP boundary and
a fake model provider, and runs no live calls in CI.

### 9. Gemini 1.5 and the legacy `google-generativeai` package are obsolete

- `Acceso y Llamadas a la API de Gemini - Sistema Multi-Agente.docx` uses
  `import google.generativeai as genai`, `genai.configure(...)` and
  `genai.GenerativeModel("gemini-1.5-flash")` / `"gemini-1.5-pro"`.
- `Development Code - Multi-Agent F1 Commentary System.docx` uses the same package with
  `model_name="gemini-1.5-pro"`.
- `Docker & Cloud Emulation - …docx` pins `google-generativeai>=0.8.0`.
- `Multi-Agent F1 Live Commentary System - Model Specifications & Architecture.docx`
  builds its whole model-selection rationale on Gemini 1.5 Flash and 1.5 Pro.

The target uses the maintained **`google-genai`** SDK, asynchronous, with explicit
model IDs that are **verified against current provider documentation before any coding**
— never guessed and never copied from these drafts. Wrapping the synchronous
`generate_content` in `asyncio.to_thread` (as the superset does) is also discarded;
the gateway is async, with request timeouts, bounded retries and bounded concurrency.

### 10. The OpenF1 guide promises free live data and states unverified guarantees

`OpenF1 API - Real-Time Formula 1 Monitoring Guide.docx` claims the API is an
"open-source, free-to-use REST API that provides **live** and historical" data. The
project's position is the opposite for the live feed: **historical access is free and
unauthenticated; real-time access requires a paid subscription.** The document must not
be used to promise free live data.

The same file also presents as fixed facts a 2–4 s timing cadence, 200–300 ms
telemetry, "latency within a few seconds of the live broadcast feed", a full per-endpoint
field list, and an example `/sessions?year=2026`. None of these is verified here, and
the target treats endpoint schemas, cadence, quotas and latency as **prerequisites to
measure**, not guarantees to rely on.

### 11. Smaller defects worth recording

- **Fabricated fallback commentary.** `Development Code - …docx` returns invented
  broadcast lines when the model fails, including a "purple sector two" claim, and
  presents them as commentary. The target's degradation output is neutral, never
  invented fact. (Also a fabricated "remarkable commitment through sector two" fallback.)
- **Naive identifier mapping.** `_normalize_driver_id` falls back to
  `driver_name.lower().replace(" ", "_")` and relies on a short, hand-written alias map
  that omits most of the current grid. (Superset, `(3)`)
- **Pagination ignored.** The historian counts `starts` as `len(races)` from a single
  `limit=1000` response and derives podiums from it, so totals are wrong for any driver
  with more races than one page. (Superset, `(3)`)
- **Fabricated milestones.** `check_milestone` reports a "FIRST EVER career Pole
  Position" whenever the cached pole count is zero — including when the lookup simply
  failed and returned the zero-initialized default. (Superset, `(3)`)
- **Unbounded dialogue history.** `CommentatorDuoOrchestrator.dialogue_history` grows
  without limit for the life of the process. (Superset)
- **Pacing coded as `asyncio.sleep(0.5)`** to "simulate announcer pacing" — a magic
  delay in the production path, not a tunable. (Superset)
- **Container and Compose hygiene.** Redis published on the host at `6379`; services
  run as root; no health checks, so `depends_on` is an ordering guess; obsolete
  `version: "3.9"`; no dependency lockfile; `restart: unless-stopped` used as the sole
  resilience strategy. (`Docker & Cloud Emulation - …docx`)
- **Recommended agent frameworks are unnecessary.**
  `Architecture Design_…docx` suggests LangGraph, CrewAI or AutoGen; the specified
  topology needs no agent framework. The target uses plain async Python for the
  deterministic roles.
- **Project Notes is empty.** `Project Notes - Multi-Agent F1 Commentary System.docx`
  has no body text and contributes nothing.

## Per-file disposition

| Original file | What survives | What is replaced | What is discarded |
| --- | --- | --- | --- |
| `Acceso y Llamadas a la API de Gemini - Sistema Multi-Agente.docx` | The Advanced-vs-API-key distinction and the "secret manager, never commit" rule. | `google-generativeai` and `genai.GenerativeModel` usage → async `google-genai` with verified model IDs; the per-role model table → deterministic roles make zero calls. | Spanish prose against the English-only rule; `gemini-1.5-flash`/`gemini-1.5-pro` IDs; free-tier hand-waving with no budget. |
| `Architecture Design_ Real-Time Multi-Agent F1 Commentary System.docx` | Five-role decomposition; dual-persona booth with explicit handoff; the event-lifecycle and enrichment-merge flow; persona intent. | Open bus options → Redis Streams decision; framework recommendation → no framework; fixed 2–4 s cadence → configurable and verified; optional TTS → explicitly out of scope. | LangGraph/CrewAI/AutoGen; Redis Pub/Sub, RabbitMQ and Kafka as alternatives; ElevenLabs/OpenAI Realtime TTS; treating audio output as part of the core system. |
| `Development Code - Multi-Agent F1 Commentary System(1).docx` | Collector/analyst module split; structured event dicts; the qualifying-cutoff and undercut-window *concepts*; the capability-table framing. | `asyncio.Queue` → Redis Streams; hardcoded tyre life, cliff (85%), pit loss (22.5 s) → configurable circuit/session parameters treated as assumptions; "Gemini 1.5 Flash" analyst label → deterministic. | `sessions[-1]`; the pre-poll cursor bug; events without schema, version or timestamp; incrementing tyre laps per event rather than from stint data. |
| `Development Code - Multi-Agent F1 Commentary System(2).docx` | A standalone runnable collector loop with an explicit `main()`, as a development affordance. | In-process queue pipeline → bus consumer with watermarks and overlap handling; live polling → replay/live adapter behind one boundary. | Catch-all error swallowing; no retry/backoff; no tests; no session reset. |
| `Development Code - Multi-Agent F1 Commentary System(3).docx` | The historian as a **deterministic** HTTP client with caching — the direct ancestor of the target historian; the career-stats / milestone / rivalry payload shape. | Hardcoded Monza defaults → attributed per-circuit lookups that stay absent when unknown; naive alias map → verified identifier mapping; unbounded in-memory cache → session/circuit-safe bounded cache. | Fabricated projected-pole milestones; counts that ignore pagination; the `http://localhost:8000/historical_f1` hardcode; `current_circuit="monza"` defaults. |
| `Development Code - Multi-Agent F1 Commentary System.docx` | The two persona prompts and their distinct voices; the `BroadcastDialogueTurn` shape; merging event + tactical card + historical payload into a booth turn; the overall five-module topology. | Synchronous legacy SDK → async `google-genai` with timeouts, bounded retries and usage accounting; unbounded global history → bounded per-turn context; Monza demo → replay fixtures. | Fabricated fallback commentary lines; `asyncio.sleep(0.5)` as production pacing; the non-asserting "simulation" as a substitute for tests; `enrich_event`'s Monza default. |
| `Docker & Cloud Emulation - Multi-Agent F1 Commentary System.docx` | Four services plus Redis; per-service images; environment-variable configuration; Compose as the local runtime. | `google-generativeai` pin → verified, locked dependencies including `google-genai`; root images with no health checks → non-root, health-checked, readiness-driven services; publicly published Redis → internal-only networking. | Obsolete `version: "3.9"`; `GEMINI_API_KEY` injected into the deterministic analyst and historian; `depends_on` as the startup contract; `restart: unless-stopped` as the only resilience. |
| `Multi-Agent F1 Live Commentary System - Model Specifications & Architecture.docx` | The role-to-responsibility mapping and the two distinct booth personas. | "One LLM per role" → deterministic roles make zero calls and only the booth uses Gemini; Gemini 1.5 Flash/Pro → model IDs verified at implementation time. | Unmeasured latency and cost claims; the assertion that the model "accurately grounds historical anecdotes … without hallucinating" as a property to rely on. |
| `OpenF1 API - Real-Time Formula 1 Monitoring Guide.docx` | The endpoint catalogue as a validation checklist; the coverage list (practice, qualifying, sprint, race); session-init and driver-mapping as pipeline steps; incremental `date>` filtering as a concept; the qualifying-cutoff trigger idea. | "Free live" → historical free and unauthenticated, live requires a paid subscription; asserted cadence, latency and field lists → prerequisites to verify against the live API. | Unverified guarantees (2–4 s cadence, 200–300 ms telemetry, "within a few seconds of broadcast"); the `/sessions?year=2026` example; social-update and voice-feed suggestions as first-delivery output. |
| `Project Notes - Multi-Agent F1 Commentary System.docx` | Nothing. | Nothing. | Nothing — the document is empty. |
