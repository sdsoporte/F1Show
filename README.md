# F1Show

F1Show is a replay-testable, real-time Formula 1 commentary system. It turns public
timing and telemetry data into an evidence-grounded text commentary stream delivered
by a simulated two-person broadcast booth.

The design goal is a booth that sounds like television coverage without inventing
facts: every claim a commentator makes is backed by a deterministic observation or an
attributed historical record, and the whole pipeline can be replayed offline from
recorded data before it is ever pointed at a live session.

## Target system

The system separates *finding out what happened* from *talking about it*:

- Three **deterministic roles** derive facts from data and make **zero LLM calls**:
  a collector (normalizes OpenF1 timing, laps, positions, intervals, race control),
  a tactical analyst (contextual gaps, pace, stint and pit-window signals), and a
  historian (attributed historical records for drivers and circuits).
- Two **Gemini commentator personas** — a lead play-by-play announcer and a color
  analyst — are the only components that call an LLM, and they may use only events
  and enrichment that the deterministic roles already produced.
- A single **sync writer** is the only component that talks to OpenF1, writing to a
  **local store** (SQLite in WAL mode, with DuckDB over immutable Parquet snapshots)
  that the services read locally. **Redis Streams** remains the event transport
  between services — the store serves state, context and history, not events.
- The roles run as application services — collector, analyst, historian and the
  commentary booth — fed by the sync writer and connected through **Redis Streams**.

Replay comes first. OpenF1 states the split verbatim: "Historical data (from 2023
onwards) is free and accessible without authentication. Real-time data requires a paid
subscription." (<https://openf1.org/docs/>) The pipeline is therefore developed and
regression-tested against recorded sessions, and **real-time access is never assumed
to be free**: the live tier is published at €9.90 per month. The validated tiers,
prices, quotas and schemas are recorded in
[`docs/EXTERNAL-CONTRACTS.md`](docs/EXTERNAL-CONTRACTS.md); see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full target design and its
explicit scope boundaries.

## Current status

**A replayable commentary pipeline runs today, entirely offline, and the CI enforces it.**

Snapshot at `c7727f9` (the close of F09g): **957 tests passing** on Python 3.12 and 3.14, Ruff 0.17.0
pinned, and the register-row guard green.

What exists, all of it offline from recorded fixtures with fake providers and an injected clock:

- a **deterministic collector** that turns recorded OpenF1 payloads into events across five families;
- a **two-person booth** — lead and colour, explicit turns — whose citation protocol admits only the
  references an event actually supplies, with every airing shape declared and pinned;
- a prompt that carries the **window's stories** (biggest gain and loss, the busiest driver, pit stops,
  flags, a derived fastest lap), a declared **mode** per turn (build or climax), the **driver's name,
  team and number**, and a bounded **championship context**;
- a **standings derivation** validated against the source's own before-and-after checkpoints;
- `f1show.run.main`, which runs one replay session and prints its transcript reproducibly.

What is **not** here, and why: Redis delivery and Docker packaging (deferred as a pair), tactical
analysis and historical enrichment, the start aggregation, economy and tone, and the language variant —
all registered as design rather than missing. The live pilot is gated on a purchased subscription and has
made zero calls. [`docs/PROJECT-STATE.md`](docs/PROJECT-STATE.md) draws the whole picture in one map.

Audio, dashboards, social posting, multi-session operation and cloud deployment remain deliberately out
of scope for this delivery.

## Repository layout

| Path | Purpose |
| --- | --- |
| [`docs/`](docs/) | Current project documentation. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) is the target design; [`docs/SOURCE-REVIEW.md`](docs/SOURCE-REVIEW.md) assesses the original corpus against it. |
| [`docs/EXTERNAL-CONTRACTS.md`](docs/EXTERNAL-CONTRACTS.md) | Validated external contracts: OpenF1 tiers, prices, quotas and observed schemas, Jolpica, `google-genai`, the identity mapping and the open unknowns. |
| [`docs/PROJECT-STATE.md`](docs/PROJECT-STATE.md) | The project state map: what is built and delivered, what remains and why, what is carried with an owner and a trigger, and the workflow every unit goes through. |
| [`docs/CARRIED-FINDINGS.md`](docs/CARRIED-FINDINGS.md) | The register of carried findings — location, owner, trigger — and the staleness keys that decide when a row must be re-derived. |
| [`origis/`](origis/) | The ten original Word documents, archived byte-for-byte with [provenance and integrity hashes](origis/README.md). Historical evidence, not specifications and not executable source. |
| [`odd/`](odd/) | The ODD plan and task backlog. [`odd/tasks/f1show.md`](odd/tasks/f1show.md) is the authoritative scope and task list. |

## Planned stack

- **Python, async** — an `asyncio` application; the three deterministic roles are
  plain Python and use no agent framework.
- **httpx** — async HTTP client for the OpenF1 and historical-data adapters, used by
  the sync writer and historian.
- **Local store** — SQLite in WAL mode for live state (one writer, many concurrent
  cross-process readers), plus DuckDB over immutable per-session Parquet snapshots
  for analysis and replay fixtures. A single sync writer is the only component that
  talks to OpenF1.
- **Redis Streams** — the event bus between services, with consumer groups,
  acknowledgements and bounded retention.
- **`google-genai`** — the maintained Google GenAI SDK, used only by the commentary
  service. Final model IDs and dependency versions must be verified against current
  provider documentation before coding; nothing in this repository should be read as
  naming a supported model.
- **Docker Compose** — packaging for the application services, the sync writer and
  Redis.

## Open prerequisites

These are unresolved and are tracked as explicit tasks rather than assumptions:

- OpenF1 live access requires a paid subscription. Its tiers, prices, quotas and the
  observed `sessions` and `drivers` schemas are recorded in
  [`docs/EXTERNAL-CONTRACTS.md`](docs/EXTERNAL-CONTRACTS.md); the remaining OpenF1
  unknowns are the other endpoints' schemas and the live OAuth2 token lifecycle.
- The historical archive is Jolpica (`https://api.jolpi.ca/ergast/f1/`); its rate
  limits and observed response shapes are recorded. The driver and circuit identity
  mapping to OpenF1 must still be built and frozen as a dated fixture, and its
  coverage boundaries sampled.
- Available Gemini model IDs and GA status must be confirmed by enumerating with the
  account and checking current documentation before any commentary code is written.
  Model IDs are never guessed, and no price is attributable to a named model yet.
- The commentary language default and the pilot ceiling that becomes the first hard
  cost stop at F13 must be approved by the user. The audience is fixed as the
  technical Formula 1 fan.
