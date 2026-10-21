# F17 — R3F studio with legacy coexistence

Objective: rebuild `ThreeCommentatorStudio` on **@react-three/fiber** with professional
lighting and post-processing, while **keeping the current imperative studio available behind a
toggle** — both versions coexist, consume the same props, and the user flips between them.

## Specs

- **S1** (the user's own words verbatim): *"si vamos con R3F y tendremos opción de manteer
  ambas, no ?"* — the R3F migration is authorized **only** as a coexistence: the legacy studio
  is not deleted, not replaced silently, and a visible toggle switches between them.
- **S2** (measured surface): React **19** → `@react-three/fiber` **v9** + `drei` v10 +
  `@react-three/postprocessing`. `ThreeCommentatorStudio` is mounted in **two** places —
  `src/App.tsx:688` and `src/components/ObsStudioView.tsx:254` — with the props interface
  `{ activeSpeaker: BoothSpeaker | null; isSpeaking: boolean; currentTurnQuote?: string;
  onTriggerCheer?: () => void }`. Both mount points must offer the toggle.
- **S3** (coexistence contract): a new `ThreeCommentatorStudioR3F.tsx` with the **same props
  interface**; a `Studio3DSwitcher` renders the chosen one plus a visible Legacy/R3F toggle;
  the legacy component's file and behaviour are **untouched**; the switcher replaces only the
  two mount sites. No other component changes.
- **S4** (the R3F visual baseline — the stage-1 improvements, now declarative): studio
  environment lighting (drei `Environment`), contact shadows under the desk, 3-point rig with a
  rim light in the existing red/cyan neon motif, `ACESFilmicToneMapping`, bloom
  post-processing, avatars with better proportions and a speaking animation driven by
  `isSpeaking`, and the active speaker highlighted. Screens show the same kind of content the
  legacy studio shows (its demo data), via canvas textures.
- **S5** (verification): `tsc --noEmit` clean; both toggle modes render in the browser with
  zero console errors (playwright); screenshots of both; the legacy mode pixel-comparable to
  today's (untouched code).
- **S6** (limits): no avatar replacement with external models (Ready Player Me is a later
  unit); no changes to services, App logic beyond the two mount sites, or the legacy file; no
  CI changes (the red inherited workflow is a separate decision).

## Tasks

- **T1**: deps (`bun add`), `ThreeCommentatorStudioR3F.tsx`, `Studio3DSwitcher.tsx`, the two
  mount-site swaps, tests-by-browser. Route: parent (frontend prototype on `main`, following
  the PR #87 pattern). Commit on `feat/f17-r3f-studio`.
- **T2**: browser verification both modes (playwright, screenshots), `tsc`, then PR.

## Log

- **L1** (2026-10-21, verbatim): *"si vamos con R3F y tendremos opción de manteer ambas, no ?"*
  — after the user saw the PR #87 improvement and asked for tools to reach a professional style;
  the R3F path was proposed by the parent and the coexistence condition added by the user.
- **L2** (2026-10-21): React 19 and the two mount sites measured (`package.json`,
  `src/App.tsx:688`, `src/components/ObsStudioView.tsx:254`); the props interface quoted from
  the legacy component. R3F v9/drei v10 chosen because of the React 19 constraint — v8 would
  downgrade React.
