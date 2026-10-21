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

- **L3** (2026-10-21): **the credential mystery resolved by the user.** pi's `auth.json`
  (`/home/s/.pi/agent/auth.json`, inspected masked — structure and lengths only, values never
  printed) holds `cli-proxy.key` — a **51-character key with prefix `sk-uc4`** and
  `base_url http://127.0.0.1:8317/v1` — whereas `clients.env.sh`'s `CLIPROXY_API_KEY` and
  `OPENAI_API_KEY` are both 24 characters. The native-dialect rejections of T2 are therefore
  explained: the working CLIproxy credential is the 51-char key in pi's auth store, not the
  24-char vars. The user confirmed the proxy is already working and closed the thread
  ("ya quedó funcionando, no es necesario") — no further testing. Wiring `server.ts` to that
  credential for option B remains available if wanted later.

- **L4** (2026-10-21): **L3 corrected by the user's clarification + the full census.** auth.json
  was pointed at for **comparison, not authority** — and the user asserted the credential is the
  same one held in `clients.env.sh`. The full variable census (the first one was **truncated at
  12 names**, which hid the decisive row) measured: `clients.env.sh` **does** hold the working
  credential — `GEMINI_API_KEY` = 51 chars, prefix `sk-uc4` (the same key as pi's auth.json) —
  under the **existing names** `GEMINI_API_KEY` + `GOOGLE_GEMINI_BASE_URL`
  (`http://127.0.0.1:8317/v1`). My T2 failure had measured the wrong variable
  (`CLIPROXY_API_KEY`, 24 chars, `sk-tes` — the OpenAI/Anthropic dialects' key). **Fix
  applied:** the `direct` provider now honors `GOOGLE_GEMINI_BASE_URL` as an optional base URL,
  and the live verification closed the loop: server startup resolves
  *`direct (GEMINI_API_KEY via http://127.0.0.1:8317/v1)`*, `/api/gemini/status` returns
  `available: true`, and the earlier `bun -e` native generation with that exact key+base
  returned `"ok"` — **F08's untested native-dialect wiring is now verified end-to-end**, with
  zero renames of the user's existing env names.
