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
- The roles run as **four application services** that communicate through
  **Redis Streams**: collector, analyst, historian and the commentary booth.

Replay comes first. Historical OpenF1 data is free and unauthenticated, so the
pipeline is developed and regression-tested against recorded sessions. **Real-time
OpenF1 access requires a paid subscription and is never assumed to be free.** See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full target design and its
explicit scope boundaries.

## Current status

**Repository bootstrap only — no application code exists yet.**

This repository currently contains project documentation and the archived original
design documents. There is:

- no application code;
- no tests, Docker files or dependency manifests;
- no working pipeline, and no live or replay data flowing.

The target architecture below is a plan, not a description of what runs today. The
first delivery is scoped to a text/CLI transcript; audio, dashboards, social posting,
multi-session operation and cloud deployment are deliberately out of scope for it.

## Repository layout

| Path | Purpose |
| --- | --- |
| [`docs/`](docs/) | Current project documentation. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) is the target design; [`docs/SOURCE-REVIEW.md`](docs/SOURCE-REVIEW.md) assesses the original corpus against it. |
| [`origis/`](origis/) | The ten original Word documents, archived byte-for-byte with [provenance and integrity hashes](origis/README.md). Historical evidence, not specifications and not executable source. |
| [`odd/`](odd/) | The ODD plan and task backlog. [`odd/tasks/f1show.md`](odd/tasks/f1show.md) is the authoritative scope and task list. |

## Planned stack

- **Python, async** — an `asyncio` application; the three deterministic roles are
  plain Python and use no agent framework.
- **httpx** — async HTTP client for the OpenF1 and historical-data adapters.
- **Redis Streams** — the event bus between services, with consumer groups,
  acknowledgements and bounded retention.
- **`google-genai`** — the maintained Google GenAI SDK, used only by the commentary
  service. Final model IDs and dependency versions must be verified against current
  provider documentation before coding; nothing in this repository should be read as
  naming a supported model.
- **Docker Compose** — packaging for the four application services plus Redis.

## Open prerequisites

These are unresolved and are tracked as explicit tasks rather than assumptions:

- OpenF1 live access requires a paid subscription, and its current quotas, schemas
  and endpoint guarantees have not been verified here.
- The historical-data source, the exact mappings between its driver/circuit
  identifiers and OpenF1's, and its coverage boundaries are unverified.
- Available Gemini model IDs and the SDK surface must be confirmed before any
  commentary code is written. Model IDs are never guessed.
- The commentary language, target audience and sink, and any measurable latency or
  cost ceiling must be approved by the user before a live broadcast is accepted.
