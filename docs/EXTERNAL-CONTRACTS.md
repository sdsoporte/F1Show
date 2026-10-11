# External contracts and operating limits

> **Validated 2026-10-09 against first-party sources and two direct observations.**
> Prices, rate limits, endpoint schemas and model catalogues change without notice.
> Re-validate the relevant section before relying on it, and carry the validation
> date with every fact below. This file is the F01 evidence record for the external
> dependencies and the input to the architecture decision recorded in
> [`ARCHITECTURE.md`](ARCHITECTURE.md).

F1Show reads Formula 1 data from **OpenF1** and historical archives, and talks to
Gemini through **`google-genai`**. This document records what those external systems
actually promised on the validation date, what was observed directly, and what
remains unknown. It exists so that no later document has to guess at a quota, a
field name, a price or a package version.

## How to read this document

Facts carry one of three labels:

- **VERIFIED (first-party)** — read on the validation date from the provider's own
  published documentation, PyPI metadata published by the package owner, or its
  live API, with the URL or the exact observation recorded here.
- **VERIFIED (observed)** — a direct request executed during validation, recorded
  with its exact URL, status and response shape.
- **UNKNOWN** — not established by this validation. An unknown is never resolved by
  inference, and never filled in from the original Word corpus or from a search
  result. Every unknown is listed again in the [open unknowns](#open-unknowns) table
  with the specific action that would resolve it.

Everything below is **first-party or observed**. No third-party summary, blog post or
search snippet is treated as evidence anywhere in this file. Where a value came from
the provider's own documentation it is cited; where it came from a live response it
is marked observed. When a third-party source could be the only support for a claim,
the claim is written as an unknown instead.

Nothing here authorizes a purchase, a subscription or a live API call. The project
does not buy access and does not call live endpoints by default; see the pilot
boundary in [`ARCHITECTURE.md`](ARCHITECTURE.md).

## OpenF1

### Access model

**VERIFIED (first-party)** — <https://openf1.org/docs/> states verbatim:

> Historical data (from 2023 onwards) is free and accessible without authentication.
> Real-time data requires a paid subscription.

Two consequences follow directly, and they are the ones the rest of the project
depends on:

- **OpenF1's documented historical coverage begins with the 2023 season.** Earlier
  seasons are outside the documented historical access, so pre-2023 history must come
  from the archive in the [Jolpica section](#jolpica--ergast-compatible-archive).
- **Historical access needs no credentials at all.** Development, replay and
  regression testing can therefore run with no account and no secret.

### Tiers, prices and rate limits

**VERIFIED (first-party)** — the tier table published on <https://openf1.org/>:

| Tier | Price | What it includes | Rate limits |
| --- | --- | --- | --- |
| **Personal use — Free / forever** | Free | All 18 endpoints; all historical sessions since 2023; JSON and CSV output; no authentication required | up to **3 requests per second** and **30 requests per minute** |
| **Historical + Live data — Personal use** | **€9.90 per month** | Everything in the free tier, plus live data during sessions over REST, MQTT and WebSocket | up to **6 requests per second** and **60 requests per minute**; up to **10 concurrent MQTT/WebSocket connections** |

The live tier is the only documented way to obtain real-time data. Its rate limits
are exactly double the free tier's, and its MQTT/WebSocket allowance is what makes
event-driven live consumption possible at all — see the
[rate-limit arithmetic](#why-the-rate-limits-force-a-single-sync-writer).

### Billing and credentials

**VERIFIED (first-party)** — from <https://openf1.org/account/>:

- Billing is handled by **Stripe**, and the billing portal is where payment method,
  invoices and cancellation are managed.
- **Credentials are emailed** when a subscription is created; the account page
  instructs the subscriber to search their mailbox for the OpenF1 email. The billing
  portal **does not show the API credentials**, so they cannot be read back from the
  account page.
- **Cancellation takes effect at the end of the current billing period**, and the
  credentials **keep working until then** — access is not revoked mid-cycle.
- **Live access uses an OAuth2 access token**, documented at
  <https://openf1.org/auth.html>.

### Endpoint inventory

**VERIFIED (first-party)** — 18 documented endpoints on <https://openf1.org/docs/>:

`car_data`, `drivers championship` (beta), `teams championship` (beta), `drivers`,
`intervals`, `laps`, `location`, `meetings`, `overtakes`, `pit`, `position`,
`race control`, `sessions`, `session result`, `starting grid`, `stints`,
`team radio`, `weather`.

These are the documented names as published. During the original validation only
`/v1/sessions` and `/v1/drivers` were exercised, so no other URL path was asserted.

**Later, exercised.** The MVP fixture recording (2026-10-10, see [the recording
section](#mvp-fixture-recording-2026-10-10)) additionally exercised `/v1/position`, `/v1/laps`,
`/v1/intervals`, `/v1/pit`, `/v1/stints` and `/v1/race_control`, so those six paths are now
asserted as **observed** rather than only documented. The remaining paths — `car_data`,
`location`, `meetings`, `overtakes`, `session_result`, `starting_grid`, `team_radio`,
`weather`, `championship_drivers` and `championship_teams` — remain documented-only and are
**not** asserted here.

### Documented cadence and availability

**VERIFIED (first-party)** — behaviours that constrain what the pipeline can assume:

- `car_data` samples at approximately **3.7 Hz**.
- `location` also updates at approximately **3.7 Hz**.
- `intervals` update **approximately every 4 seconds**, and **only during races**.
- `drivers championship` and `teams championship` are available **only for race
  sessions**.
- **Location segments are not available during races.**
- `pit.stop_duration` exists **only from the 2024 United States Grand Prix onwards**;
  earlier pit records do not carry it.
- `overtakes` is available **only during races** and **may be incomplete**.
- Real-time data typically updates **about 3 seconds after the live event**.

The last point is the source-side half of the end-to-end latency budget recorded in
[`ARCHITECTURE.md`](ARCHITECTURE.md): a ~3 second source update delay plus local
processing and a model call is what a live commentary consumer actually experiences.

### Observed requests

The observations below were executed unauthenticated against historical data. The first two
came from the original validation; the third is the MVP fixture recording. Together they are
the OpenF1 response shapes this project has seen first-hand, and the first two are the reason
the identity mapping exists at all. Nothing here was authenticated, and nothing here proves
anything about live behaviour.

#### Sessions, 2024 season

```text
GET https://api.openf1.org/v1/sessions?year=2024
→ HTTP 200, application/json, 123 records
```

Fields present on the records:

```text
circuit_key, circuit_short_name, country_code, country_key, country_name,
date_end, date_start, gmt_offset, is_cancelled, location, meeting_key,
session_key, session_name, session_type, year
```

The records cover `2024-02-21T07:00:00+00:00` through `2024-12-08T13:00:00+00:00`.
`session_key` and `meeting_key` are integer identifiers that consistently identify a
session and a meeting across the observed records; `date_start` and `date_end` are
the time fields. This is the shape the session-lifecycle code must
key on, and it confirms that explicit session selection is possible without
ordering assumptions.

#### Drivers, one session

```text
GET https://api.openf1.org/v1/drivers?session_key=9462
→ HTTP 200, 20 records
```

Fields present on the records:

```text
broadcast_name, country_code, driver_number, first_name, full_name,
headshot_url, last_name, meeting_key, name_acronym, session_key,
team_colour, team_name
```

**There is no `driverId` and no `driver_id` field.** `driver_number` is per-session
and `name_acronym` is the only stable-looking human identifier OpenF1 exposes. This
is the whole reason the identity mapping below has to be built rather than looked
up.

## Jolpica / Ergast-compatible archive

#### MVP fixture recording, 2026-10-10

**OBSERVED (unauthenticated free tier).** Eight families were recorded for one race session into
[`fixtures/openf1/`](../fixtures/openf1/PROVENANCE.md), which carries the per-endpoint URL, HTTP
status, byte size, SHA256, record count and request timestamp. The session is `session_key` 9617
(Austin, 2024-10-20, `meeting_key` 1247), chosen as the earliest 2024 race on or after the United
States Grand Prix, because `pit.stop_duration` exists only from that event onwards.

```text
GET https://api.openf1.org/v1/sessions?year=2024             → 200,   123 records
GET https://api.openf1.org/v1/drivers?session_key=9617       → 200,    20 records
GET https://api.openf1.org/v1/position?session_key=9617      → 200,   403 records
GET https://api.openf1.org/v1/laps?session_key=9617          → 200,  1059 records
GET https://api.openf1.org/v1/intervals?session_key=9617     → 200, 21041 records
GET https://api.openf1.org/v1/pit?session_key=9617           → 200,    23 records
GET https://api.openf1.org/v1/stints?session_key=9617        → 200,    43 records
GET https://api.openf1.org/v1/race_control?session_key=9617  → 200,   120 records
```

Three shape facts that constrain any consumer, recorded because they surprised the recording:

- **There is no uniform timestamp field.** Only `position`, `intervals`, `pit` and `race_control`
  carry `date`; `sessions` and `laps` carry `date_start`; `drivers` and `stints` carry no
  timestamp field at all.
- **`laps` is not uniformly dated:** 1058 of 1059 records carry `date_start` and one is null, so
  no code may assume every lap has a date.
- **`intervals` is by far the largest family** — 2,965,644 bytes for 21,041 records, roughly one
  sample per driver per six seconds. Only 1 of those rows predates the session start, so the
  volume is genuine race-window sampling rather than padding, and a `date>=` bound would remove a
  single row. It is therefore kept whole rather than bounded to look smaller.

**Point-in-time, not evergreen.** Free-tier history is a snapshot and upstream may revise a past
session's payload, so these hashes describe what was served on that date and nothing more. No
fixture here proves anything about live or authenticated behaviour.

### Base URL and role

**VERIFIED (first-party)** — the canonical Ergast-compatible base URL is
**`https://api.jolpi.ca/ergast/f1/`**. Jolpica is the successor to Ergast, providing
backwards-compatible endpoints for the soon-to-be-deprecated Ergast API, as stated at
<https://github.com/jolpica/jolpica-f1/blob/main/docs/README.md>. It is the source for
pre-2023 history and for the stable driver identifiers OpenF1 does not have.

### Observed requests

```text
GET https://api.jolpi.ca/ergast/f1/2024/drivers.json
→ HTTP 200
```

The response carries an `MRData` envelope with `limit` / `offset` / `total` paging
(**default limit 30**; `total` 25 for this request). Each driver exposes:

```text
driverId (e.g. "albon"), permanentNumber, code (e.g. "ALB"),
givenName, familyName, dateOfBirth, nationality, url
```

One complete observed record, quoted so the shape is not re-summarised later:

```text
{"driverId": "albon", "permanentNumber": "23", "code": "ALB",
 "url": "http://en.wikipedia.org/wiki/Alexander_Albon",
 "givenName": "Alexander", "familyName": "Albon",
 "dateOfBirth": "1996-03-23", "nationality": "Thai"}
```

```text
GET https://api.jolpi.ca/ergast/f1/2024/1/results.json
→ HTTP 200, RaceTable / Races shape, total 20
```

`driverId` and `code` are the fields the mapping below wants, and **`dateOfBirth`
and `nationality` are present** on the observed record and therefore available as
disambiguators. An earlier revision of this file claimed `dateOfBirth` was absent;
that claim came from a truncated observation and was wrong. It is corrected here
rather than quietly dropped, because the "how to read this document" rule above
exists precisely to stop a summary from being mistaken for an observation.

### Rate limits

**VERIFIED (first-party)** — from Jolpica's own documentation at
<https://github.com/jolpica/jolpica-f1/blob/main/docs/rate_limits.md>:

- Burst: **4 requests per second**.
- Sustained: **500 requests per hour**.
- The documentation states these limits **"will decrease in the future"** as token
  access rolls out, so they are a decreasing, not a fixed, entitlement.
- Exceeding a limit returns **HTTP 429 with "Request was throttled"**.
- Documented guidance: **cache results** and **prefer filters and offsets over
  per-item requests**.
- **API token access is still being implemented** — there is no token path to
  authenticate against yet.

The 500-per-hour sustained limit is the binding constraint for archival enrichment:
it is far below what a naive per-driver or per-race lookup pattern would need, which
is why the historian must page deliberately and cache by session and circuit.

### Ergast differences that matter to a consumer

**VERIFIED (first-party)** — Jolpica's documented intentional differences at
<https://github.com/jolpica/jolpica-f1/blob/main/docs/ergast_differences.md>:

- **XML responses are not supported**; only JSON is available. Any client written
  against Ergast's XML mode will not work here.
- **Only the last of duplicated filters is honoured**, where Ergast returned HTTP
  400 for a duplicated filter. A request with two conflicting filters silently
  takes the second rather than failing.
- **Standings require a year to be specified**; yearless standings requests are not
  accepted.
- **Sprint session naming changed**: `SprintShootout` for 2023 and
  `SprintQualifying` from 2024 onwards.
- **Results are ordered by count instead of `statusId`.**
- **From the 2025 season, only an enumerated status list is used.** All retirements
  and accidents are collapsed into **"Retired"**, because Jolpica has no data source
  that distinguishes them.

The last two are the ones most likely to produce a subtly wrong historical claim: a
"retirement" count from 2025 onwards cannot be decomposed into mechanical failure
versus accident, and must not be presented as if it could.

## `google-genai`

### SDK and version

**VERIFIED (first-party)** — PyPI metadata for the package `google-genai`
(<https://pypi.org/project/google-genai/>):

- Latest published version at validation: **2.29.0**, uploaded **2026-10-07**.
- `requires-python >=3.10`.
- A **2.11.0** copy exists on the development machine inside an unrelated
  virtualenv. It is **stale and must not be treated as the target version**; the
  version is pinned from resolved dependencies at F02, not inherited from any
  existing environment.

### The legacy package is deprecated

**VERIFIED (first-party)** — the legacy `google-generativeai` package must not be
used:

- Version **0.8.6** (<https://pypi.org/project/google-generativeai/>), and its own
  published description begins with
  **"# [Deprecated] Google AI Python SDK for the Gemini API"**.
- Corroborated by <https://ai.google.dev/gemini-api/docs/migrate> and the archived
  repository `google-gemini/deprecated-generative-ai-python`.

The original corpus used this package throughout; see
[`SOURCE-REVIEW.md`](SOURCE-REVIEW.md) for the replacement rationale.

### Enumerating available models

**VERIFIED (first-party)** — see <https://ai.google.dev/api/models> for the
`models.list` reference and <https://github.com/googleapis/python-genai> for the
Python client. The programmatic enumeration method is **`client.models.list(...)`**,
or **`await client.aio.models.list(...)`** for the async client. It returns a pager
of `Model` objects exposing:

```text
name, display_name, description, version, endpoints, labels,
input_token_limit, output_token_limit, supported_actions, thinking
```

There is **no GA/preview status field**. General-availability status therefore has
to be read from the current documentation, not from the API, and the model a given
account can actually call is discovered by enumerating with that account.

**No model ID is named anywhere in this repository as current, recommended,
available or default.** The documented prerequisite is: authenticate, enumerate,
then confirm GA status in the documentation, before any model ID is written into
configuration or code.

### Operator-configured gateway, observed 2026-10-10

The endpoint this project actually talks to is a **local loopback gateway**, not Google directly: the
configured base URL is `http://127.0.0.1:8317/v1` and the credential is a single API key. The
observations below used only that key, with no automatic retries.

- **The `/v1` is already part of the base URL.** Appending another `/v1` duplicates the path and
  returns a 404, which has already cost one debugging cycle here. Treat the configured value as a
  complete prefix rather than a bare host.
- **Two surfaces answer on the same gateway.** The OpenAI-compatible surface returned
  `GET /v1/models` → 200 in 0.02 s (twelve entries) and `POST /v1/chat/completions` → 200 in 0.82 s
  with usage 8/1/9 and the text `ok`. The native surface returned `GET /v1beta/models` → 200 in
  0.002 s with the native shape — `{"models": [{"name": "models/…"}]}` plus `displayName`,
  `description`, `supportedGenerationMethods` and modality fields.
- **Both surfaces advertise the same twelve entries**, so a native-dialect client does have a real
  endpoint on this gateway. What remains **unexercised is a generation in the native dialect**;
  matching listing shape is necessary but not sufficient, so that stays an open question for F10
  and F13 rather than an established capability.
- **The advertised ids are gateway aliases, not first-party model ids.** Suffixes such as `-high`
  and `-low` are the gateway's own effort tiers. **No id from this enumeration may enter
  configuration or code as though it were a provider contract** until it is reconciled against
  Google's documentation — the same rule this file already applies to every model id.
- The catalogue itself is recorded in the ODD task document; it is a measurement of one gateway on
  one date, not a compatibility guarantee.

**A hygiene note for any enumeration here.** A generated summary disagreed with its own raw
artifact: the prose listed eleven entries while the file held twelve, the missing one being
`gemini-3.6-flash-high`. Read the artifact, not the summary, before acting on a count.

### Authentication paths

**VERIFIED (first-party)** — from <https://ai.google.dev/gemini-api/docs/api-key>
and <https://github.com/googleapis/python-genai>:

- **API key** — `genai.Client(api_key=...)`, with the environment variable
  `GEMINI_API_KEY` or `GOOGLE_API_KEY`. **`GOOGLE_API_KEY` wins** if both are set,
  so **set only one**; a stray duplicate makes the effective credential
  non-obvious.
- **Enterprise** — `enterprise=True` together with a project and a location, using
  the environment variables `GOOGLE_GENAI_USE_ENTERPRISE`, `GOOGLE_CLOUD_PROJECT`
  and `GOOGLE_CLOUD_LOCATION`.
- In this SDK version, **`vertexai` is the legacy flag and setting conflicting flags
  raises `ValueError`**, and the platform is now named **"Gemini Enterprise Agent
  Platform (formerly Vertex AI)"**. Any configuration name containing `VERTEXAI` is
  therefore version-dependent and must not be treated as stable across SDK
  releases.

### Dependency floor

**VERIFIED (first-party)** — from the `google-genai` package metadata published at
<https://pypi.org/project/google-genai/>:

```text
httpx>=0.28.1,<1.0.0
pydantic>=2.12.5
google-auth
tenacity
anyio
websockets
Python >=3.10
```

One trap worth recording explicitly: a **separate distribution named `httpx2`
(2.13.1, published 2026-09-23)** exists and is **not the same package as
`httpx` 0.28.1**. The HTTP client dependency must be chosen deliberately at F02 and
the choice recorded in the lock file, not resolved by whichever name looks familiar.

### Cost envelope

**VERIFIED (first-party)** — from <https://ai.google.dev/gemini-api/docs/pricing>,
usable for planning **only as an envelope**, not as a per-model price:

- A **Flash-class standard tier** is **$0.75 per 1M input tokens and $3.75 per 1M
  output tokens**. That pricing holds through **2026-12-31** and **doubles on
  2027-01-01**.
- A cheaper **Lite class** sits at roughly **$0.25–0.30 per 1M input tokens** and
  **$1.50–2.50 per 1M output tokens**.
- There is a **free tier with limited access to certain models, whose content is
  used to improve Google's products**. Any use of it is a data-handling decision,
  not only a cost decision.
- **Price-to-model attribution is NOT reliable from this validation.** The
  model-name headings did not survive extraction, so no model can be tied to a
  price. **No model should ever be quoted together with a price from this file.**
  When a model is chosen, the price must be re-read from the current pricing page
  and recorded together with the model, its class and the date.

The class labels "Flash-class" and "Lite class" above are pricing classes quoted
from the source, not model IDs and not recommendations.

## Identity mapping between the two data sources

**There is no shared key between OpenF1 and Jolpica.** OpenF1 exposes no driver
identifier beyond the per-session `driver_number` and the 3-letter `name_acronym`
(the observed driver shape has no `driverId`/`driver_id`). Jolpica exposes
`driverId`, `permanentNumber` and `code`. A mapping must therefore be **built and
owned by this project**, **frozen as a dated fixture with a source URL per row**,
and **never looked up at runtime**.

- **`name_acronym` ↔ `code`** is the most promising join: both carry the 3-letter
  FIA code. `dateOfBirth` and `nationality`, both present on the observed Jolpica
  driver object, are the available disambiguators.
- **`driver_number` is not a stable identity across seasons.** It is per-session,
  and the reigning champion takes #1, so keying historical enrichment on it would
  silently corrupt multi-season lookups.
- **Unresolved pairs stay absent rather than being guessed.** A missing enrichment
  is a skipped trivia line, never an invented fact.
- The failure mode to avoid is already documented in this repository's own corpus
  review: a **name-slug fallback over a hand-written alias map**. See the naive
  identifier mapping in [`SOURCE-REVIEW.md`](SOURCE-REVIEW.md).

Circuit identity has the same shape of problem: OpenF1's `circuit_key` comes from its
`/sessions` records while the archive keys circuits its own way, so the circuit
mapping must be built and dated alongside the driver mapping. It is tracked as an
open unknown above.

## Why the rate limits force a single sync writer

The arithmetic is the architectural argument, and it is worth stating plainly:

- OpenF1 documents `car_data` at approximately **3.7 Hz**. Polling it per driver
  across a roughly 20-driver field is **about 74 requests per second**.
- That is roughly **25× the free tier's 3 requests per second** and roughly **12×
  the €9.90 live tier's 6 requests per second**.
- OpenF1's own documentation advises **preferring MQTT or WebSocket over polling**
  for live data, described as "the recommended method" at
  <https://openf1.org/auth.html>.

So **per-agent direct polling was never viable at any tier**: no on-offer tier
absorbs ~74 requests per second, and OpenF1's own guidance is MQTT/WebSocket for live
data. A single component that owns the source connection and writes to a local store,
with everything else reading locally, is therefore a **structural necessity rather
than a cost preference** — it is not a way to save money on a workable push
architecture, it is the only shape that fits the documented limits at all.

At a ~3 second sync cadence the request rate stops being the binding constraint.
**For live data the binding constraint is the monthly entitlement itself, not
throughput** — the subscription is what grants any live access at all, and the
per-second limits are then comfortably sufficient. That is why the architecture
budgets live access as a subscription decision at F13, not as a throughput-tuning
problem.

## Open unknowns

| Unknown | Why it is unresolved | Action that would resolve it |
| --- | --- | --- |
| Which Gemini models this account can call, and which are GA | The API exposes no GA/preview status field | Authenticate, run `client.models.list(...)`, then confirm each candidate's GA status on the current provider documentation. Required before F08. |
| Price for the chosen model | Price-to-model attribution did not survive extraction, so no model may be tied to a price here | Re-read the current pricing page when the model is chosen, and record model + class + price + date together. |
| Exact `google-genai` version to pin | 2.29.0 was latest on the validation date; the target pin is a dependency-resolution decision | Re-check PyPI at F02 and pin the resolved version in the lock file. |
| Which HTTP distribution wins: `httpx` or `httpx2` | A separate `httpx2` 2.13.1 distribution exists and is not `httpx` 0.28.1 | Decide deliberately at F02 and record the resolved distribution in the lock file. |
| OpenF1 OAuth2 token lifecycle for live access | The auth page describes the token but this validation read no token flow against a subscribed account | Read <https://openf1.org/auth.html> with a subscribed account; record issuance, expiry, refresh and failure modes before F13. |
| Per-endpoint OpenF1 field schemas beyond `sessions` and `drivers` | Only two endpoints were observed | Fetch each of the 18 endpoints for a known historical session and diff against a recorded fixture. |
| Whether OpenF1 exposes a stable cross-source driver identity anywhere | No identifier beyond `driver_number` and `name_acronym` was observed | Inspect all 18 endpoint schemas for an identifier field; if none exists, the mapping is permanently ours to own. |
| Jolpica object schemas beyond the observed driver record | Only the `drivers.json` driver record and the results envelope were observed first-hand | Fetch representative race, qualifying, circuit and lap-time records and record each complete field set before they become join inputs. |
| Jolpica coverage boundaries and sprint result shapes | Coverage and the renamed sprint sessions were documented but not sampled | Fetch representative 2023, 2024 and 2025 sessions, including sprints, and record the shapes. |
| Jolpica token access and whether the free limits decrease | Token access "is still being implemented" and the docs say rates "will decrease in the future" | Re-read `docs/rate_limits.md` at F03/F07 before fixing the historian's request budget. |
| OpenF1 ↔ Jolpica circuit identity mapping | Two independent namespaces, not yet mapped | Build the dated mapping fixture with a source URL per row, alongside the driver mapping. |
| Commentary language default | Configurable by decision; no default fixed yet | User decision before F09. |
| Model spend ceiling for a session and the pilot total | Per-session spend is uncapped by decision; the pilot ceiling is approved at F13 | Measure usage during F08-F12, then approve the pilot ceiling at F13. Until then there is **no hard cost stop of any kind**. |
| Live cadence and update latency as experienced end to end | Documentation states ~3 s source update delay; it was not measured live | Measure during the separately authorized live pilot at F13. |
