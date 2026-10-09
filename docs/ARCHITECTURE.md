# F1Show target architecture

> **Not implemented.** This document describes the architecture F1Show is being built
> toward. No application code, service, container or pipeline exists yet. Nothing here
> describes something that currently runs. See the [project status](../README.md#current-status).

This is the **target** design. Where it makes a commitment, it is a decision the
project has taken; where it describes something external, it is stated as a
prerequisite to verify rather than a guarantee.

## Design principle: facts and talk are separate

The system splits into two halves that are never mixed:

1. **Deterministic roles** establish what is true from data. They are ordinary Python
   and make **zero LLM calls**. They must be reproducible: the same input produces the
   same output, and every fact they emit carries its source fields and timestamp.
2. **A commentary layer** decides how to say it. Only here is a language model used.

The purpose of the split is evidence discipline. If a commentator states a fact, that
fact must already exist in a deterministic event or an attributed historical record.
The models add language, turn-taking and tone — never data.

## The five logical roles

| # | Role | LLM calls | Responsibility |
| --- | --- | --- | --- |
| 1 | **Collector** (deterministic) | **Zero** | Polls the data source, normalizes timing/laps/positions/intervals/race-control into schema-validated events, deduplicates updates, preserves source timestamps and provenance, and publishes to the bus. |
| 2 | **Tactical analyst** (deterministic) | **Zero** | Turns normalized events into tactical signals — contextual gaps, pace trends, stint and tyre state, pit-window candidates, qualifying cutoffs. Estimates (tyre life, pit loss) are labeled as assumptions, not facts, and circuit/session parameters are configuration, not hardcoded. |
| 3 | **Historian** (deterministic) | **Zero** | Resolves driver and circuit identity and retrieves attributed historical records for the current event, with bounded caching and explicit source/as-of attribution. Unknown records stay absent; a failed lookup skips trivia rather than inventing it. |
| 4 | **Lead play-by-play persona** (Gemini) | Yes | Calls the current action in short, high-tempo turns and hands off to the analyst. |
| 5 | **Color analyst persona** (Gemini) | Yes | Responds with tactical and historical depth drawn only from the enrichment it is given. |

Roles 1–3 are deterministic and must remain so. Roles 4–5 are **the only components
in the system permitted to call an LLM.**

## Services and bus

The five logical roles run as **four application services** plus Redis:

| Service | Contains | Notes |
| --- | --- | --- |
| `collector` | Role 1 | Owns the connection to the data source and session lifecycle. |
| `analyst` | Role 2 | Consumes collector events; emits tactical enrichment. |
| `historian` | Role 3 | Consumes collector events; emits historical enrichment. |
| `booth` | Roles 4 and 5 | Consumes events plus enrichment; produces the transcript. Only service with model credentials. |
| `redis` | — | **Redis Streams** event bus: stream names, versioned envelopes, separate consumer groups for analyst and historian, acknowledgements, idempotency, recovery of pending messages, and bounded retention. |

Redis Streams is a decision, not one option among several. The original drafts
mentioned Pub/Sub, RabbitMQ and Kafka, or plain in-process queues; the target uses
Redis Streams specifically because it gives durable, replayable, multi-consumer
delivery with acknowledgements inside one dependency.

Consumer-group separation matters: the analyst and the historian each see **every**
event independently, and one of them being slow or down must not stop the other or
stall fresh factual calls. Service startup uses readiness/health state, not a bare
`depends_on` ordering assumption.

## Replay first

Historically, **OpenF1 historical data is free and unauthenticated**; this is what
makes offline development possible and it is the mode the system is built and
regression-tested in first.

- A **replay source** and a **live source** sit behind the same adapter boundary, so
  the rest of the pipeline cannot tell them apart.
- Replay drives session choice explicitly and seeds mid-session state, so a run can
  start partway through a session with correct positions, stints and lap history.
- The clock, the HTTP boundary and the model boundary are injectable, so tests use a
  fake clock, recorded fixtures and a fake provider. **No live calls run in CI.**

### Live data is not free

**Real-time OpenF1 access requires a paid subscription.** The project does not promise
free live data anywhere, does not purchase subscriptions as part of development, and
treats live operation as a separately authorized milestone with its own access,
quota, cost and time ceilings. Historical free access must never be presented as if it
extended to the live feed.

## The commentary booth

- **Two personas with explicit turns**: the lead calls the action, then hands to the
  analyst. Turn order is deterministic even though the text is generated.
- **Bounded context**: each turn receives only the current event, the relevant
  enrichment, and a bounded slice of recent dialogue. Stale context is excluded rather
  than accumulated.
- **Evidence only**: personas may use only the events and attributed enrichment they
  are handed. They cannot introduce statistics, records or incidents from nowhere.
- **Degradation is neutral**: a model outage, timeout or rate limit produces a
  restrained fallback or a gap in commentary — never fabricated excitement.

## Output

The first delivery produces a **plain text/CLI transcript**: the commentary stream,
sourced, written to standard output or a file. This is the only output the first
delivery targets.

## Out of scope for the first delivery

These are deliberately excluded and are separate future scope, not incomplete work:

- **Audio and TTS** — no speech synthesis or multi-speaker voice output.
- **Dashboards and web UI** — no graphical or real-time visual interface.
- **Social posting and publication** — no automated posting to any platform.
- **Multi-session operation** — one session at a time; concurrent sessions are not
  supported.
- **Cloud deployment** — local Compose only; no hosted or managed deployment.
- **Application implementation itself** — this document is design, and the repository
  contains no code.

## Prerequisites and open unknowns

Nothing below may be assumed; each is an item to verify before the dependent code is
written. **No endpoint schema, quota, latency guarantee or model ID in this repository
should be treated as confirmed.**

- **OpenF1 access** — current authentication model for live vs. historical, per-endpoint
  schemas and field names, incremental-update semantics, cadence, rate limits and
  quotas. The original documents asserted several of these as fixed values; they are
  unverified and partly obsolete.
- **Historical data source** — which archive is used, its coverage, pagination and
  identifier mapping to and from OpenF1's driver and circuit identifiers, and how
  records are attributed with an as-of date.
- **Gemini gateway** — the maintained `google-genai` SDK surface, the model IDs
  actually available to this project, and their limits. **Model IDs are verified
  against current provider documentation before coding, never guessed.**
- **Cost and quota policy** — request/token/cost ceilings, concurrency bounds, retry
  and backoff policy, and how usage is measured and enforced. Reported token counts
  alone do not constitute a hard spend limit.
- **Commentary contract** — broadcast language, target audience and output sink, and
  any measurable latency or cost acceptance limits, to be approved by the user before
  a live broadcast is accepted.
