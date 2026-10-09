# F1Show target architecture

> **Not implemented.** This document describes the architecture F1Show is being built
> toward. No application code, service, container or pipeline exists yet. Nothing here
> describes something that currently runs. See the [project status](../README.md#current-status).

This is the **target** design. Where it makes a commitment, it is a decision the
project has taken; where it describes something external, it is stated as a
prerequisite to verify rather than a guarantee. The external facts — prices, quotas,
endpoint schemas and package versions — were validated on 2026-10-09 and are recorded
with their sources in [`EXTERNAL-CONTRACTS.md`](EXTERNAL-CONTRACTS.md). This document
states the decisions taken on that evidence.

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
| 1 | **Collector** (deterministic) | **Zero** | Normalizes timing/laps/positions/intervals/race-control into schema-validated events, deduplicates updates, preserves source timestamps and provenance, and publishes to the bus. It reads the data source **through the local store**, which is filled by the dedicated sync writer — the only component that talks to OpenF1. |
| 2 | **Tactical analyst** (deterministic) | **Zero** | Turns normalized events into tactical signals — contextual gaps, pace trends, stint and tyre state, pit-window candidates, qualifying cutoffs. Estimates (tyre life, pit loss) are labeled as assumptions, not facts, and circuit/session parameters are configuration, not hardcoded. |
| 3 | **Historian** (deterministic) | **Zero** | Resolves driver and circuit identity and retrieves attributed historical records for the current event, with bounded caching and explicit source/as-of attribution. Unknown records stay absent; a failed lookup skips trivia rather than inventing it. |
| 4 | **Lead play-by-play persona** (Gemini) | Yes | Calls the current action in short, high-tempo turns and hands off to the analyst. |
| 5 | **Color analyst persona** (Gemini) | Yes | Responds with tactical and historical depth drawn only from the enrichment it is given. |

Roles 1–3 are deterministic and must remain so. Roles 4–5 are **the only components
in the system permitted to call an LLM.**

## Services and bus

The five logical roles run as **four role services plus a sync writer and Redis**:

| Service | Contains | Notes |
| --- | --- | --- |
| `sync` | Ingestion | **The only component that talks to OpenF1.** Owns the source connection, session lifecycle and the ~3 second live cadence, and writes to the local store. Not an LLM caller. |
| `collector` | Role 1 | Reads the local store, derives events from it and publishes to the bus. Holds no source credentials. |
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

## Local store and the sync role

**The local store replaces direct per-agent API access.** A single sync process is the
only component that talks to OpenF1; every other service reads locally.

- **SQLite in WAL mode is the live store.** One writer with many concurrent
  cross-process readers is precisely what WAL is for.
- **DuckDB is the analytical engine over immutable per-session Parquet snapshots.**
  Those snapshots double as the replay fixtures.
- **Event transport is unchanged.** Agents keep consuming events over **Redis
  Streams**; the local store serves **state, context and history**. This is not a
  switch from push to polling.
- **Live sync cadence is approximately 3 seconds**, matching the documented source
  update delay.
- DuckDB may additionally attach the SQLite file read-only through its official
  `sqlite` extension (`INSTALL sqlite; ATTACH 'file.db' (TYPE sqlite)`, documented at
  <https://duckdb.org/docs/current/core_extensions/sqlite.html>), with the honest
  caveat that attached SQLite scans run through SQLite's row-based engine, so DuckDB's
  columnar advantage applies to Parquet, not to a SQLite attach.

### Why DuckDB is not the live store

DuckDB's own documentation (<https://duckdb.org/docs/current/connect/concurrency>)
defines only two modes: **one process that reads and writes, or multiple processes
that may only read**. A maintainer states in
<https://github.com/duckdb/duckdb/issues/1119> that across host processes **only
multiple read-only connections are supported** — the multi-writer MVCC behaviour is
in-process only. Every Compose service is a separate process, so a sync container
holding the DuckDB file read-write would make that file **unopenable by the agent
containers**. SQLite WAL is used for the live store for exactly that reason; DuckDB is
kept where its columnar engine pays off — over Parquet.

### Why a sync writer is structural, not a cost preference

OpenF1 documents `car_data` at ~3.7 Hz. Polling it per driver across ~20 drivers is
**about 74 requests per second**, roughly **25× the free tier** and **12× the live
tier**, and OpenF1's own documentation advises MQTT or WebSocket over polling for live
data, describing it as "the recommended method" (<https://openf1.org/auth.html>). Per-agent direct polling was never viable at any tier. The arithmetic is
recorded in
[`EXTERNAL-CONTRACTS.md`](EXTERNAL-CONTRACTS.md#why-the-rate-limits-force-a-single-sync-writer).

## Replay first

OpenF1 states the free/paid split verbatim: **"Historical data (from 2023 onwards) is
free and accessible without authentication. Real-time data requires a paid
subscription."** (<https://openf1.org/docs/>) Free, unauthenticated historical access
from the 2023 season onwards is what makes offline development possible, and it is the
mode the system is built and regression-tested in first.

- A **replay source** and a **live source** sit behind the same adapter boundary, so
  the rest of the pipeline cannot tell them apart.
- Replay drives session choice explicitly and seeds mid-session state, so a run can
  start partway through a session with correct positions, stints and lap history.
- The clock, the HTTP boundary and the model boundary are injectable, so tests use a
  fake clock, recorded fixtures and a fake provider. **No live calls run in CI.**
- **The replay fixtures are the production artifact.** Each session's immutable
  Parquet snapshots are both the analytical input and the recorded fixtures the
  regression suite replays, so a live session and a replayed session are the same
  shape of data.

### Live data is not free

OpenF1 states it verbatim: **"Historical data (from 2023 onwards) is free and
accessible without authentication. Real-time data requires a paid subscription."**
(<https://openf1.org/docs/>) The live tier is published at **€9.90 per month** on
<https://openf1.org/> and adds
live REST, MQTT and WebSocket access at up to 6 requests per second and 60 per minute;
the free tier allows 3 per second and 30 per minute and carries no live data at all.
Tier, billing and OAuth2 details are in
[`EXTERNAL-CONTRACTS.md`](EXTERNAL-CONTRACTS.md#openf1).

The project does not promise free live data anywhere, does not purchase subscriptions
as part of development, and treats live operation as a separately authorized milestone
with its own access, quota, cost and time ceilings. Historical free access must never be
presented as if it extended to the live feed.

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

## Latency, audience and cost policy

These are decisions, not aspirations:

- **Latency budget.** End-to-end latency is **sync interval + derivation + enrichment
  join + model call** — of the order of **5–8 seconds** from source event to emitted
  commentary. The measurable acceptance limit F12 targets is **≤ 8 seconds**.
- **Audience: the technical Formula 1 fan.** A data-dense register in which every
  claim is tied to session evidence.
- **Commentary language: configurable, with no default fixed yet.** It is modelled as
  typed configuration; its default is chosen before F09.
- **Model spend per session is not capped.** The system **measures and reports** usage;
  it does not enforce a per-session ceiling. The pilot ceiling is **approved at F13**
  against measured usage now that the subscription price is known.
- **There is no hard cost stop of any kind until F13.** F08's acceptance is therefore
  corrected from enforcing a "budget stop" to **measurement plus alerting**, with the
  F13 pilot ceiling as the first real stop. Reported token usage is not a spend limit.

## Prerequisites and open unknowns

External facts and their sources are in
[`EXTERNAL-CONTRACTS.md`](EXTERNAL-CONTRACTS.md), validated 2026-10-09; that file also
lists the resolution action for each unknown. **No endpoint schema, quota, latency
guarantee or model ID in this repository should be treated as confirmed.** The items
that still gate this architecture are:

- **Gemini model availability** — enumerate with `client.models.list(...)` and confirm
  GA status against current provider documentation before coding. **Model IDs are
  verified, never guessed**, and none is named here.
- **Price-to-model attribution** — the cost envelope in the contracts file is not
  attributable to a named model; the pricing page must be re-read when a model is
  chosen.
- **Live access and OAuth2 lifecycle** — live access requires a paid subscription, and
  its token flow has not been exercised. No purchase is authorized by this document.
- **Live cadence and latency** — the documented ~3 second source update delay was not
  measured live; the ≤ 8 second target is confirmed at F12 and measured at F13.
- **Per-endpoint OpenF1 schemas** — only `sessions` and `drivers` were observed; the
  other endpoints' fields and incremental-update semantics are unverified.
- **Jolpica coverage** — coverage boundaries, and object schemas beyond the observed
  driver record and results envelope, were not sampled. The driver record itself was
  observed and **does** expose `dateOfBirth`; an earlier revision of this design
  claimed otherwise.
- **Cost and quota policy** — request/token/concurrency bounds, retry and backoff, and
  the correction above that no hard stop exists until F13. Reported token counts alone
  do not constitute a hard spend limit.
- **Commentary contract** — the language default (before F09) and output sink; the
  audience is fixed as the technical F1 fan, and any measurable cost acceptance limit
  beyond the ≤ 8 second latency target is approved at F12/F13.
