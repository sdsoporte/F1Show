# F16 — Live capture with latency measurement: the 2026 Austin weekend

Objective: consume the free OpenF1 API **during** a live session — recording verbatim and
measuring **when each family's data starts loading and with how much delay** — answering the
user's question (real-time or delayed) with measurements instead of assumptions, and gaining a
fresh **2026** corpus to replace the 2024 scaffolding the project was built on. Branch: none —
the capture happens in `/tmp` and only its analyzed artifacts reach the repository, through a
separate authorization with the pre-agreed size gate.

## Specs

- **S1** (the user's own words verbatim): *"los datos que tomamos antes fueron de ejemplo para
  ordenar nuestro flow, deberíamos realizar una nueva prueba"*, and *"podemos hacer una prueba
  en vivo usando data real registrada. como si fuese live. este finde tenemos carrera, deberíamos
  monitorear en que momento se empieza la carga de datos. si es en tiempo real o con cuanta
  demora"*. Scope chosen: **"Captura en vivo + latencia (recomendado)"** — verbatim capture plus
  latency, not latency alone.
- **S2** (the identified sessions, measured from the live 2026 calendar on 2026-10-20, 1 GET):
  meeting **1297** (Austin, United States) — Practice 1 `11389` Fri 2026-10-23 17:30 UTC,
  Practice 2 `11390` Fri 21:00, Practice 3 `11391` Sat 17:30, **Qualifying `11392` Sat 21:00 UTC
  (18:00 ART)**, **Race `11396` Sun 2026-10-25 20:00 UTC (17:00 ART)**. No Sprint at this
  meeting. The capture targets **Qualifying (rehearsal-grade) and Race (primary)**; practices
  are optional and only if the user asks.
- **S3** (the capture): a throwaway probe kept in `/tmp` — never in the repository — polling the
  seven family endpoints for the target `session_key` on a fixed cadence (**3 s between
  requests, ≈20 req/min, inside the documented 3 req/s and 30 req/min free tier**), `GET` only,
  host `api.openf1.org` only, **no authentication of any kind**, `trust_env=False`,
  `follow_redirects=False`, bounded timeout. Every response body is written **verbatim** to
  `/tmp/f1show_live_<session_key>/` — but a body identical to that family's previous snapshot is
  recorded as a timeline row only (deduplicated), so the disk holds every *state transition*
  plus the final state. **Nothing is written into the repository during the capture.**
- **S4** (the metrics, defined before the capture so the numbers cannot be fitted after): per
  family — (a) **first appearance**: the first poll whose response is a JSON array with ≥1
  record, expressed as seconds after the session's `date_start`; (b) **staleness**: per poll,
  the newest source timestamp in the response minus the poll instant (the delay answer); (c)
  **cadence**: inter-update intervals over the session; (d) the timeline itself, one row per
  poll. The metrics definition is frozen here; the capture only produces data for it.
- **S5** (analysis and corpus decision, deferred): after the sessions, the analysis produces the
  latency table and the recommendation. What enters `fixtures/openf1/` as a new recorded
  session — the final verbatim snapshot of each family, or nothing — is **a separate user
  decision** taken with the measured sizes in hand, subject to the pre-agreed size gate
  (~2 MB/family, ~12 MB total) and a PROVENANCE section in the established format.
- **S6** (hard limits): no model call, no credential, no purchase, no paid tier — this does not
  touch F13's subscription gate (that gate governs live *model* commentary; the data path is
  free). If the free tier answers 429 or the source is down, the probe records the fact and
  keeps pacing; nothing is retried aggressively. The rehearsal (below) may not exceed 7 GETs
  against completed sessions.

## Tasks

- **T1**: the probe script in `/tmp` + a rehearsal against a completed 2026 session
  (≤7 GETs) proving the machinery: pacing, verbatim deduplicated writes, timeline rows,
  staleness extraction. Route: parent. Commit: nothing — `/tmp` only.
- **T2**: run the probe during **Qualifying `11392`** (Saturday) — rehearsal-grade capture with
  real latency data. Route: the probe runs unattended; analysis after.
- **T3**: run the probe during the **Race `11396`** (Sunday) — the primary measurement.
- **T4**: the latency analysis (S4 metrics), the size-gated corpus recommendation, and the
  user's decision on what enters the repository.

## Log

- **L1** (2026-10-20, verbatim): *"podemos hacer una prueba en vivo usando data real registrada.
  como si fuese live. este finde tenemos carrera, deberíamos monitorear en que momento se empieza
  la carga de datos. si es en tiempo real o con cuanta demora"* — with the scope selection quoted
  in S1. Context: the user's point that the recorded 2024 corpus was scaffolding ("datos de
  ejemplo para ordenar nuestro flow"), so the new test doubles as the first fresh-data exercise.
- **L2** (2026-10-20): the 2026 calendar was measured with 1 GET (`sessions?year=2026`, 131
  sessions): this weekend is **Austin, meeting 1297** — the same circuit as recorded sessions
  9617/9608, two years later, which makes the fresh-data comparison direct. Cleanup of 26 local
  + 23 remote merged branches and the stale worktrees was executed the same day (the user's
  "sí deberíamos limpiar"), leaving `main` at `80bffab` alone.

- **L3** (2026-10-21): **driver/team identity across seasons — reviewed at the user's request, one bug measured.** The user flagged: in 2024 Colapinto was at Williams; in 2026 he runs for Alpine. **Measured:** (a) the **2024 replay is historically correct by design** — the drivers payload is per-session (`fixtures/openf1/{9617,9655}/drivers.json` both show `Franco COLAPINTO | Williams | #43`, accurate for those 2024 rounds) and the booth joins from the loaded per-session payload (F09f design held); (b) the **prototype's SIM mode is stale** — `server/f1SignalR.ts:352` hardcodes the **2024 grid** (Colapinto → Williams, Ocon → Alpine) as the fallback for its "2026 Live Simulation" stream; (c) the **F16 live capture arrives with its own 2026 `drivers.json`**, which the pipeline binds per-session — so Colapinto/Alpine binds automatically for 2026 sessions. **Follow-up (this unit's T4):** after the capture, rebuild the SIM mode's default driver list **from the captured 2026 drivers.json** (measured data, never invented) — and update the stale "2024 grid" hardcoded list in `f1SignalR.ts`.
