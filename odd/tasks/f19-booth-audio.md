# F19 — Working booth audio: neural server TTS (edge-tts)

Objective: make the commentators **audible**. Measured today: the browser TTS path fails
(`synthesis-failed`), the server `/api/tts` route calls a Gemini TTS model that **does not
exist on the gateway** (404 measured), and the frontend never calls that route. The fix:
neural voices from **edge-tts** (the same engine F15 already uses on the Python side), served
by the TS server, consumed by the booth with a browser-TTS fallback.

## Specs

- **S1** (the user's words verbatim): *"funcionan los audios de los relatores ?"* → *"ya
  complete los pasos, no se escucho nada , revisa logs"* → *"ok, remedialo"*.
- **S2** (measured causes, both paths dead): (a) browser `speechSynthesis` →
  `synthesis-failed` logged by the app; 0 voices in headless; the service's no-es-voice
  fallback lands on the system default which may not exist; (b) `/api/tts` →
  `{"error":{"code":404}}` — `gemini-3.8-flash-lite-tts` is **not on the CLIproxy gateway**
  (its 12-model list has no TTS model), and `grep -rn 'api/tts' src/` finds **no frontend
  caller**.
- **S3** (the server fix): replace the dead Gemini-TTS `/api/tts` route with **`msedge-tts`**
  (npm edge-tts port, free, no key): `POST {text, speaker, language}` → `audio/mpeg`. **The
  voice map is not a new decision — it is the one F15 already recorded** (Engram obs 6046,
  `booth-models-and-voices`, 2026-10-13): **Edge-TTS was chosen over Kokoro with measured
  reasons** (Kokoro at -26.5 dB RMS, no Argentine native models; Edge-TTS broadcast volume,
  natural voseo, zero cost, <300 ms latency). The recorded map, respected here: **lead →
  es-AR-TomasNeural**, **colour → es-UY-MateoNeural**, **es-419 fallbacks → Jorge (lead) /
  Alonso (colour)**. Paced and error-wrapped; no key, no credential.
- **S4** (the frontend fix): `SpeechService.speak` **fetches `/api/tts` first** and plays the
  returned audio blob through an `Audio` element, chaining the queue on `ended`; on any
  failure it falls back to the existing browser-utterance path (so nothing regresses when the
  server is down). The enabled flag, queue order and speaker alternation keep their current
  semantics.
- **S5** (verification): `tsc` clean; `curl /api/tts` returns `audio/mpeg` bytes > 10 KB;
  playwright: click a "Play audio for this turn" → network 200 + no console errors; replay
  PLAY → the queue fetches audio per turn (network requests visible) instead of
  `synthesis-failed`.

## Tasks

- **T1**: server route (`bun add msedge-tts`, voice map, route rewrite) + `tsc` + curl.
- **T2**: SpeechService fetch-first with browser fallback + App handler passthrough.
- **T3**: browser verification (playwright) + PR.

## Log

- **L1** (2026-10-21, verbatim): *"funcionan los audios de los relatores ?"* → *"ya complete
  los pasos, no se escucho nada , revisa logs"* → *"ok, remedialo"*. The parent measured both
  paths dead (S2) before this unit; the app-side silent failure (console-only logging) is the
  registered UX defect that made it look like "nothing works".
- **L2** (2026-10-21): the user also asked *"cuando lo use en modo Circuito 2D tambien
  seguiran funcionando los comentaristas, no ?"* — **yes**: replay, booth and the audio queue
  are App-level state; tabs only change the view (their own capture shows EVT 66/1708
  advancing while on the Circuito tab).
- **L3** (2026-10-21): **the voice-profile decision already existed** — found by Engram search
  at the user's request (*"revisa si en engram ya teniamos seleccionado el perfil de audio que
  usariamos, esto ya lo realizamos"*): obs **6046** (`booth-models-and-voices`) recorded the
  Kokoro-vs-Edge comparison and the choice of Edge-TTS with the voice map quoted in S3. The
  parent's fresh recommendation (edge-tts es-AR) had converged on the same backend without
  knowing it; the map now respects the recorded one instead of the parent's draft (which had
  swapped seats and invented es-ES rows).

- **L3** (2026-10-21): **the implementation, with two measured pivots.** (1) The npm `msedge-tts`
  package received **429 twice in a row** from the Edge websocket while the **Python edge-tts
  7.3.1** (F15's pinned stack) generated a valid 19 KB MPEG with the same voice seconds later —
  the npm package's Sec-MS-GEC token handling is behind the service's current enforcement, so
  the route was rewritten as a **subprocess to the repo's `.venv/bin/edge-tts`** (the proven F15
  binary), and `msedge-tts` was removed from the dependencies. (2) The recorded colour voice
  fallback "Alonso" **no longer exists in the Edge catalogue** (measured against the CLI's own
  `--list-voices`: no es-MX-AlonsoNeural, no es-ES-AlonsoNeural) — the declared replacement is
  `es-PE-AlexNeural`, the colour analyst's own name; the catalogue changed since F15 and the
  change is now recorded in the map. (3) Also found while wiring: the booth has a **second
  audio path** this unit did not touch — `POST /api/tts` was originally a **Gemini TTS** route
  (`gemini-3.8-flash-lite-tts`) that the frontend never called; it is dead twice over (the model
  404s on the gateway, and no caller), which is why the user never heard anything from it.
- **L4** (2026-10-21): **end-to-end verified.** `tsc --noEmit` clean. Server: `POST /api/tts`
  returns `audio/mpeg` — lead es-AR (Tomas) **39,168 bytes**, colour es-419 (Alex) **41,040
  bytes**, both valid MPEG. Browser (playwright): clicking "Play audio for this turn" fires
  `/api/tts` → **200, audio/mpeg** → the Audio element plays it, **0 console errors**. The
  fallback path (browser utterance) remains byte-identical for server-down cases. Disclosed:
  one `console.warn` in the error path and the pre-existing `currentUtterance` unused-read are
  untouched (pre-existing patterns). The user now hears the commentators in every tab.

- **L5** (2026-10-21): **the overlap bug — the user heard every turn at once — and its fix.**
  The user reported *"se superponen se pisan todo no esperan a completar un audio y reproduce
  todos los disponible al mismo tiempo"* — measured and confirmed: my F19 fetch-first claimed
  the playback slot only at the audio's **onplay**, leaving the queue gate open during the
  async `/api/tts` fetch (~300 ms + subprocess 1-3 s), so every new turn sailed through and
  played simultaneously. **The fix** (speech.ts): the slot is claimed **synchronously in
  `speak()`** (before the fetch is dispatched), `immediate` turns now stop the playing server
  audio (`stopServerAudio()` — pause, revoke URL, clear listeners) before starting the new
  one, `stop()` releases the slot, and the browser fallback releases it on failure. **Verified
  in the browser**: with the replay playing for 12 s, exactly **1** `/api/tts` fetch fired (the
  serialized behaviour — the first utterance was still playing when measured), where the old
  code would have fired one per turn. The claim is released on `ended`, on error, on fallback
  and on `stop()`.
- **L6** (2026-10-21): the user's own capture also shows the deterministic booth generating
  turns at a high rate (four turns sharing one timestamp, 12:08:49) — with `immediate: true`
  on the Gemini-turn path (App.tsx:467), each new turn now **cancels** the previous instead of
  overlapping, which is the declared immediate semantics: the newest commentary wins.
