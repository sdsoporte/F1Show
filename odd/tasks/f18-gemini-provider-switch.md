# F18 — Gemini provider switch: direct key or CLI proxy

Objective: `server.ts` can use **either** provider for its Gemini commentary — A: the direct
Gemini key, B: the CLI proxy (CPAMC) — selected by env, auto-detected by default, and visible
at startup.

## Specs

- **S1** (the user's words verbatim): *"y podemos crear algo que sea funcional a las dos
  opciones ? Switch Usar A o B"*.
- **S2** (measured surface): `server.ts:15` reads only `GEMINI_API_KEY` and builds
  `new GoogleGenAI({ apiKey, httpOptions: { headers: { 'User-Agent': 'aistudio-build' } } })`.
  The proxy credentials exist in `.env.private/clients.env.sh` as `CLIPROXY_BASE_URL` +
  `CLIPROXY_API_KEY` (names only measured; values never printed). The proxy answers
  **401** unauthenticated on `:8317/v1/models` — alive, rejecting as expected.
- **S3** (the switch): a small module `server/geminiProvider.ts` with a **pure resolver** —
  `GEMINI_PROVIDER` env accepts `direct | proxy | auto` (default `auto`); an invalid value is
  refused naming the valid ones. `auto`: `GEMINI_API_KEY` → direct; else
  `CLIPROXY_BASE_URL`+`CLIPROXY_API_KEY` → proxy; else `null` client with a startup log
  explaining how to configure. The proxy client passes `httpOptions.baseUrl` to the SDK. The
  **User-Agent header is preserved in both modes** (the only header the legacy code declared).
  The startup log names the active provider and, for proxy, the base URL — never a key.
- **S4** (the honest caveat, inherited from F08): the proxy's verified path was
  **OpenAI-compatible**; the **native Gemini dialect through the proxy was left untested**.
  T2 closes that gap with one minimal generation. If the native path answers 404/405, the
  finding is recorded and option B stays documented-but-unverified for the native client.
- **S5** (limits): `.env` values are provided by the user (Bun auto-loads `.env`;
  `clients.env.sh` requires explicit sourcing — documented, not sourced by code). No UI change,
  no CI change, no key values ever logged.

## Tasks

- **T1**: `server/geminiProvider.ts` + the `server.ts` init swap + `.env.example` docs +
  `tsc`. Route: parent. Commit: `feat/f18-provider-switch`.
- **T2**: live test of the proxy native-dialect generation (closes F08's gap) — creds sourced
  from `clients.env.sh`, never printed. Route: parent.

## Log

- **L1** (2026-10-21, verbatim): *"y podemos crear algo que sea funcional a las dos opciones ?
  Switch Usar A o B"* — after the parent answered that `server.ts` reads only `GEMINI_API_KEY`
  and the proxy requires an edit.
- **L2** (2026-10-21): **T2 measured — the proxy's native-dialect endpoint routes but rejects
  both stored credentials.** The experiment matrix (values never printed): native dialect via
  `CLIPROXY_BASE_URL` (no `/v1`) with `CLIPROXY_API_KEY` → `{"error":"Invalid API key"}`; same
  base with `OPENAI_API_KEY` → identical; base **with** `/v1` (either key) → **404 Not Found**
  (the `/v1/v1beta` join does not exist); raw `curl /v1beta/models` with the key as
  `x-goog-api-key` → `Invalid API key` again. **Findings:** the proxy **does route** the native
  Gemini path (a Gemini-shaped auth error, not a 404 — F08's untested wiring is now measured to
  this depth), and both stored credentials (both len-24, likely the same value) are **rejected
  for the native endpoint** — they authenticate the OpenAI-compatible endpoint instead. **Option
  B via the native dialect is therefore blocked on credentials, not on code**: it needs the
  proxy's native-dialect key (CLI-proxy-api typically issues one, or uses its own OAuth to
  upstream). The alternative — consuming the proxy's OpenAI-compatible endpoint from the TS
  server — is a different client shape and stays a user decision. Option A (direct key)
  remains zero-change.
