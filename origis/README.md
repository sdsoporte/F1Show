# Archived original source documents

This directory preserves the ten original Word documents that seeded the F1Show
project. They were the project's design and reference material, produced during the
initial planning phase before any implementation work. Nine documents had their text
extracted for planning (the extracts are not tracked here); the tenth, **Project
Notes**, is an empty document with no body text.

## Warning

These files are **historical source documents preserved byte-for-byte**. They are:

- **Not authoritative current specifications.** Terminology, endpoint claims, SDK
  names, model IDs and quotas in these documents are unverified and, in several
  cases, already obsolete. The current specifications live in [`../docs/`](../docs/).
- **Not executable source.** The Python listed inside the `.docx` files is draft
  material embedded in prose, was never a complete or runnable repository, and is
  not imported, built or tested by this project.
- **Not to be edited.** Do not open, re-save, re-encode, re-zip or "tidy" these
  files. Their byte-for-byte integrity is the point of keeping them. Re-saving a
  `.docx` with Word or LibreOffice rewrites its ZIP container and destroys the hash.

For the honest assessment of what is salvageable from each file, see
[`../docs/SOURCE-REVIEW.md`](../docs/SOURCE-REVIEW.md).

## Integrity

Every file below was moved with a plain filesystem `mv` (not `git mv`) from `docs/`
into this directory during the repository bootstrap (ODD task F00). Content was not
modified. Each archived file was re-verified against a SHA-256 digest and byte count
recorded before the move; all ten matched and are listed below.

| Original filename | Bytes | SHA-256 | Content | Known defects |
| --- | ---: | --- | --- | --- |
| `Acceso y Llamadas a la API de Gemini - Sistema Multi-Agente.docx` | 862180 | `988508a3795189c96f1f52ff777b92da4c147fde88b02c746e44994eb7c67cf4` | Spanish-language guide to obtaining a Gemini API key and configuring the SDK, with a per-role model table. | Legacy `google.generativeai` SDK and obsolete `gemini-1.5-flash`/`gemini-1.5-pro` IDs; assigns an LLM to the deterministic analyst and historian roles; mentions a free tier but sets no budget, quota or cost policy; authored in Spanish against the English-only documentation rule. Its Advanced-vs-API billing distinction is accurate and worth keeping. |
| `Architecture Design_ Real-Time Multi-Agent F1 Commentary System.docx` | 863255 | `3cbef14925f79b350079f677b762c4c353daaf41acf4adb5f09080d8fb31e16d` | English architecture narrative with a five-role breakdown, an event lifecycle table, and persona system prompts. | Recommends LangGraph/CrewAI/AutoGen although the target topology needs no agent framework; lists Redis Pub/Sub, RabbitMQ and Kafka as interchangeable instead of committing to Redis Streams; treats 2–4 s polling and TTS output as settled fact; no stream envelopes, consumer groups, retention, cost ceiling or SLA. |
| `Development Code - Multi-Agent F1 Commentary System(1).docx` | 13867 | `48f5f18c3b78c8f3dd69f7d979abefe9bdd3f93f60f8bd0375a7b4658d9dab1a` | Draft code for Module 1 (collector) and Module 2 (tactical analyst), with capability tables. | `asyncio.Queue` instead of Redis Streams; selects a session with `sessions[-1]`; sets `last_poll_timestamp` before polling, so the incremental filter skips the data just fetched; no dedup or stale-data handling; tyre cliff (85%), pit loss (22.5 s) and stint lengths hardcoded as facts; the analyst is described as "Gemini 1.5 Flash" yet the code makes zero LLM calls; session type defaults to QUALIFYING. |
| `Development Code - Multi-Agent F1 Commentary System(2).docx` | 531580 | `e0b7b22a10bfb7e3e0b422a204c3489dd364a9fc15674c714cef36e09745402f` | Collector-only variant with an explicit `asyncio.Queue`-based `main()` runner and a capability table. | Same `sessions[-1]` selection and pre-poll timestamp bug as (1); single-process `asyncio.Queue` pipeline; catch-all exception handling with no retry, backoff or 429 handling; no tests; no session reset or multi-session handling. |
| `Development Code - Multi-Agent F1 Commentary System(3).docx` | 327178 | `c0fdc0344d72c35d0b2b524821acccd0d8b62e0485daaabe1c93e0533d48a370` | Draft code for Modules 1–3 (collector, analyst, historian) with a historian demonstration pipeline; omits the commentary module. | Inherits the collector/analyst defects above; the historian defaults `current_circuit="monza"` (the demo uses `"silverstone"`) and returns hardcoded Monza lap record and pole-to-win figures for arbitrary circuits; hardcodes a short, stale driver-alias map; ignores pagination when counting starts; no cache TTL or session/circuit safety. |
| `Development Code - Multi-Agent F1 Commentary System.docx` | 330134 | `ae78b884087879ba9087a1f6d18de957154df3029aa12f2066ac0a768b5ae9d5` | The superset draft: Modules 1–3 plus the two-person commentary booth and orchestrator, a simulated booth run and the full agent topology table. | Everything above, plus: legacy `google.generativeai` with `gemini-1.5-pro`; global unbounded dialogue history; fabricated fallback lines served as commentary when the model fails; hardcoded Monza trivia in the demo; no timeout, retry, cost accounting or repetition suppression; the simulation is not a test suite. |
| `Docker & Cloud Emulation - Multi-Agent F1 Commentary System.docx` | 219809 | `8f6c48ca58fd32bab8097c152c28e19cc8f899c9932dddc3bb0b1014b5f5369e` | Shared `requirements.txt`, four per-service Dockerfiles, a `docker-compose.yml` and a local launch workflow. | Pins legacy `google-generativeai`; no lockfile; containers run as root with no health check or readiness; publishes Redis on host port `6379`; relies on `depends_on` for startup ordering; obsolete `version: "3.9"`; injects `GEMINI_API_KEY` into the analyst and historian, contradicting the deterministic-role decision. |
| `Multi-Agent F1 Live Commentary System - Model Specifications & Architecture.docx` | 861376 | `4cc0ded7ed32ceeb4630ff411bafea8cf1aa5a6a8907dd98146adc3241f6d85c` | Short English document mapping each of the five roles to an LLM and justifying the choice. | Assigns an LLM to all five roles, including the deterministic collector, analyst and historian; obsolete Gemini 1.5 Flash/Pro IDs presented without verification; latency and cost rationale asserted with no measurement; no model-availability check before coding. |
| `OpenF1 API - Real-Time Formula 1 Monitoring Guide.docx` | 862199 | `58244de6a921afbe00abf197d0bb47ed275a5fef92c8a8d92f367febaef6d535` | English endpoint catalogue for OpenF1 with cadence, latency, coverage and a suggested monitoring pipeline. | States that the API is free for live *and* historical data — the project's position is that only historical access is free and live access needs a paid subscription; endpoint fields, 2–4 s timing cadence, 200–300 ms telemetry and "within a few seconds of broadcast" latency are presented as guarantees rather than unverified claims; no authentication, quota or rate-limit treatment; example `/sessions?year=2026` is not validated. |
| `Project Notes - Multi-Agent F1 Commentary System.docx` | 6485 | `387ae8ca7f54879ba33470b71dace6e30261c2c17ae0d1ca29fe6fb1655cfcc0` | Empty Word document; it has no body text. | Contains no content and nothing to salvage. It is archived for completeness and to keep the original set intact. |

## What to use instead

- Current target architecture: [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md)
- Review of this corpus against the target: [`../docs/SOURCE-REVIEW.md`](../docs/SOURCE-REVIEW.md)
- Project overview and status: [`../README.md`](../README.md)
